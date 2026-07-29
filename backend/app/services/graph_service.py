import asyncio
from typing import Optional
from datetime import datetime, timezone
from neo4j import AsyncDriver
from app.services.extraction_service import ConceptExtractor, ExtractionResult
from app.core.logging import get_logger

logger = get_logger(__name__)


from qdrant_client import AsyncQdrantClient
from qdrant_client.models import PointStruct
import uuid
from app.core.config import get_settings
from app.core.embeddings import get_local_embeddings
from app.services.fsrs_engine import FSRSEngine


settings = get_settings()

class GraphService:
    """
    Neo4j'deki RawSession'ları işleyip Knowledge Graph'a (Concept node'larına) çevirir.
    Adımlar:
    1. processed=false olan RawSession'ları çek
    2. ConceptExtractor ile kavram çıkar
    3. Concept node'larını ve ilişkilerini Neo4j'e yaz
    4. Soru-Cevap metnini Qdrant'a vektör olarak göm (Embedding)
    5. RawSession'u processed=true olarak işaretle
    """

    def __init__(self, neo4j_driver: AsyncDriver, qdrant_client: AsyncQdrantClient = None):
        self.neo4j = neo4j_driver
        self.qdrant = qdrant_client
        self.extractor = ConceptExtractor()
        self.fsrs = FSRSEngine()
        
        # Yerel (Offline) Embedding modeli - Privacy First
        # (paylasilan singleton: her GraphService olusumunda model yeniden yuklenmez)
        self.embeddings = get_local_embeddings()

    async def process_pending_sessions(self, batch_size: int = 10) -> dict:
        """
        Bekleyen RawSession'ları işler. Batch halinde çalışır.
        Bu metod Sprint 2'de periyodik olarak (APScheduler ile) çağrılacak.
        """
        sessions = await self._fetch_unprocessed(batch_size)
        if not sessions:
            logger.info("[GraphService] Islenmis bekleyen oturum yok.")
            return {"processed": 0, "skipped": 0, "errors": 0}

        stats = {"processed": 0, "skipped": 0, "errors": 0}

        # Mevcut topic ve kavramları (ilk girene göre) Neo4j'den çek
        existing_topics = await self._get_existing_topics()
        existing_concepts = await self._get_existing_concepts()

        for session in sessions:
            try:
                result = await self.extractor.extract(
                    platform=session["platform"],
                    question=session["question"],
                    answer=session["answer"],
                    existing_topics=existing_topics,
                    existing_concepts=existing_concepts,
                )

                if result is None:
                    await self._mark_processed(session["session_id"])
                    stats["skipped"] += 1
                    continue

                await self._write_concepts_to_graph(session, result)
                
                # Qdrant'a Embedding Kaydet (RAG için)
                if self.qdrant:
                    await self._embed_and_save_to_qdrant(session, result)
                    
                await self._mark_processed(session["session_id"])
                stats["processed"] += 1

            except Exception as e:
                logger.error(
                    f"[GraphService] Oturum isleme hatasi: {session['session_id']} | {e}",
                    exc_info=True,
                )
                stats["errors"] += 1
            finally:
                await asyncio.sleep(2)  # Ücretsiz tier API kota sınırına (429) takılmamak için bekle

        logger.info(f"[GraphService] Tamamlandi: {stats}")
        return stats

    async def _fetch_unprocessed(self, limit: int) -> list[dict]:
        """processed=false olan RawSession'ları getirir."""
        async with self.neo4j.session() as session:
            result = await session.run(
                """
                MATCH (rs:RawSession {processed: false})
                RETURN rs.session_id AS session_id,
                       rs.platform   AS platform,
                       rs.question   AS question,
                       rs.answer     AS answer
                LIMIT $limit
                """,
                limit=limit,
            )
            return [dict(r) for r in await result.data()]

    async def _get_existing_topics(self) -> list[str]:
        """Neo4j'deki mevcut benzersiz topic listesini döndürür. LLM'e gönderilir."""
        try:
            async with self.neo4j.session() as session:
                result = await session.run(
                    "MATCH (c:Concept) WHERE c.topic IS NOT NULL RETURN DISTINCT c.topic AS topic"
                )
                records = await result.data()
                return list(set(r["topic"].strip() for r in records if r["topic"]))
        except Exception:
            return []

    async def _get_existing_concepts(self) -> list[str]:
        """Neo4j'deki mevcut kavram isimlerini zamana (ilk girene) göre sıralı döndürür."""
        try:
            async with self.neo4j.session() as session:
                result = await session.run(
                    "MATCH (c:Concept) RETURN c.name AS name ORDER BY c.created_at ASC"
                )
                records = await result.data()
                # Zaten sıralı geldiği için set kullanmıyoruz ki sıra (zaman önceliği) bozulmasın,
                # ama duplicate'leri ayıklamak için dict.fromkeys kullanabiliriz (sırada korur).
                names = [r["name"].strip() for r in records if r["name"]]
                return list(dict.fromkeys(names))
        except Exception:
            return []

    async def delete_session(self, session_id: str):
        """Bir ogrenme kaynagini (RawSession) ve eger bosta kaldiysa konseptlerini siler."""
        # 1. Neo4j'den Sil (Oksuz kalan Concept'leri de temizle)
        async with self.neo4j.session() as session:
            await session.run(
                """
                // RawSession'i ve baglantilarini sil
                MATCH (rs:RawSession {session_id: $session_id})
                DETACH DELETE rs
                """,
                session_id=session_id
            )
            
            # Bosta kalan (hicbir RawSession tarafindan baglanmayan) Conceptleri sil
            await session.run(
                """
                MATCH (c:Concept)
                WHERE NOT ()-[:EXTRACTED_CONCEPT]->(c)
                DETACH DELETE c
                """
            )
            
        # 2. Qdrant'tan Sil (Vektorler)
        if self.qdrant:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            try:
                await self.qdrant.delete(
                    collection_name=settings.QDRANT_COLLECTION_NAME,
                    points_selector=Filter(
                        must=[
                            FieldCondition(
                                key="session_id",
                                match=MatchValue(value=session_id)
                            )
                        ]
                    )
                )
                logger.info(f"[GraphService] {session_id} vektoru Qdrant'tan silindi.")
            except Exception as e:
                logger.error(f"[GraphService] Qdrant silme hatasi: {e}", exc_info=True)
                
        logger.info(f"[GraphService] Session ({session_id}) tamamen silindi.")

    async def _write_concepts_to_graph(
        self, session: dict, extraction: ExtractionResult
    ):
        """
        Çıkarılan kavramları Neo4j'e yazar:
        (User)-[STUDIED {timestamp}]->(Concept)
        (Concept)-[RELATED_TO]->(Concept)
        """
        async with self.neo4j.session() as neo_session:
            for concept in extraction.concepts:
                # FSRS: Başlangıç hafıza metriklerini hesapla
                fsrs_state = self.fsrs.calculate_initial_state(concept.difficulty)

                # Concept node'u oluştur (veya güncelle)
                await neo_session.run(
                    """
                    MERGE (c:Concept {name: $name})
                    ON CREATE SET
                        c.topic      = $topic,
                        c.difficulty = $difficulty,
                        c.created_at = datetime(),
                        c.fsrs_d     = $fsrs_d,
                        c.fsrs_s     = $fsrs_s,
                        c.fsrs_p     = $fsrs_p,
                        c.last_studied = datetime()
                    ON MATCH SET
                        c.topic      = $topic,
                        c.difficulty = $difficulty,
                        c.updated_at = datetime(),
                        c.last_studied = CASE
                            WHEN c.last_studied IS NOT NULL
                                 AND c.last_studied > datetime() - duration({hours: 24})
                            THEN c.last_studied
                            ELSE datetime()
                        END,
                        c.fsrs_s = CASE
                            WHEN c.last_studied IS NOT NULL
                                 AND c.last_studied > datetime() - duration({hours: 24})
                            THEN c.fsrs_s
                            ELSE CASE
                                WHEN coalesce(c.fsrs_s, $fsrs_s) * 1.5 > 365 THEN 365.0
                                ELSE coalesce(c.fsrs_s, $fsrs_s) * 1.5
                            END
                        END
                    """,
                    name=concept.name,
                    topic=concept.topic,
                    difficulty=concept.difficulty,
                    fsrs_d=fsrs_state["difficulty"],
                    fsrs_s=fsrs_state["stability"],
                    fsrs_p=fsrs_state["retrievability"],
                )

                # İlişkilendirme: RELATED_TO
                for related_name in concept.related_to:
                    await neo_session.run(
                        """
                        MERGE (c1:Concept {name: $name})
                        MERGE (c2:Concept {name: $related})
                        MERGE (c1)-[:RELATED_TO]->(c2)
                        """,
                        name=concept.name,
                        related=related_name,
                    )

                # Oturum bilgisini RawSession'a bağla
                await neo_session.run(
                    """
                    MATCH (rs:RawSession {session_id: $session_id})
                    MATCH (c:Concept {name: $concept_name})
                    MERGE (rs)-[:EXTRACTED_CONCEPT]->(c)
                    """,
                    session_id=session["session_id"],
                    concept_name=concept.name,
                )

        logger.debug(
            f"[GraphService] {len(extraction.concepts)} kavram Neo4j'e yazildi | "
            f"Session: {session['session_id']}"
        )

    async def _mark_processed(self, session_id: str):
        """RawSession'u islendi olarak isaretle."""
        async with self.neo4j.session() as session:
            await session.run(
                "MATCH (rs:RawSession {session_id: $id}) SET rs.processed = true",
                id=session_id,
            )

    async def update_concept_after_quiz(self, concept_name: str, score: float) -> dict:
        """
        Kullanıcı quiz sonucunu gönderdiğinde ilgili kavramın FSRS parametrelerini günceller.
        """
        async with self.neo4j.session() as session:
            # 1. Mevcut parametreleri al (Yoksa varsayılan başlangıç değerini ata)
            result = await session.run(
                """
                MATCH (c:Concept {name: $name})
                RETURN c.fsrs_d AS d, c.fsrs_s AS s, c.difficulty AS diff_label
                """,
                name=concept_name
            )
            record = await result.single()
            
            if not record:
                logger.warning(f"[GraphService] Quiz guncellemesi basarisiz: '{concept_name}' bulunamadi.")
                return {"status": "error", "message": f"Concept '{concept_name}' not found."}
                
            current_d = record["d"]
            current_s = record["s"]
            diff_label = record["diff_label"] or "orta"
            
            # Eğer veritabanında FSRS değerleri yoksa (eski kayıtsa) baştan hesapla
            if current_d is None or current_s is None:
                initial_state = self.fsrs.calculate_initial_state(diff_label)
                current_d = initial_state["difficulty"]
                current_s = initial_state["stability"]
                
            # 2. Yeni değerleri FSRS ile hesapla
            updated_state = self.fsrs.calculate_quiz_update(current_d, current_s, score)
            elapsed_days = self.fsrs.calculate_elapsed_days_for_retrievability(
                updated_state["stability"],
                updated_state["retrievability"],
            )
            elapsed_seconds = int(elapsed_days * 24 * 3600)
            
            # 3. Veritabanını güncelle
            await session.run(
                """
                MATCH (c:Concept {name: $name})
                SET c.fsrs_d = $new_d,
                    c.fsrs_s = $new_s,
                    c.fsrs_p = $new_p,
                    c.last_studied = datetime() - duration({seconds: $elapsed_seconds}),
                    c.last_reviewed_at = datetime(),
                    c.updated_at = datetime()
                """,
                name=concept_name,
                new_d=updated_state["difficulty"],
                new_s=updated_state["stability"],
                new_p=updated_state["retrievability"],
                elapsed_seconds=elapsed_seconds,
            )

            # 4. STUDIED gecmisini guncelle (User -> Concept iliskisi)
            # NOT: (c:Concept {name: $name}) ilişki pattern'i icinde inline MERGE edilirse,
            # ayni isimli Concept zaten varken bile MERGE tum path'i eslesmedigi icin
            # yeni bir node yaratmaya calisir ve unique constraint'e carpar. Bu yuzden
            # Concept node'u once ayri bir MATCH ile baglaniyor.
            await session.run(
                """
                MATCH (c:Concept {name: $name})
                MERGE (u:User {id: 'local_user'})
                MERGE (u)-[r:STUDIED]->(c)
                ON CREATE SET r.first_studied = datetime(), r.attempts = 1
                ON MATCH SET r.attempts = coalesce(r.attempts, 0) + 1
                SET r.last_score = $score, r.last_studied = datetime()
                """,
                name=concept_name,
                score=score,
            )

            # 5. Her denemeyi ayri bir QuizAttempt kaydi olarak tut (gecmis paneli icin).
            # STUDIED iliskisi sadece son denemeyi tuttugu icin trend/gecmis gosterilemiyordu.
            await session.run(
                """
                MATCH (c:Concept {name: $name})
                MERGE (u:User {id: 'local_user'})
                CREATE (qa:QuizAttempt {
                    id: $id,
                    score: $score,
                    timestamp: datetime(),
                    new_difficulty: $new_d,
                    new_stability: $new_s,
                    new_retrievability: $new_p
                })
                CREATE (u)-[:ATTEMPTED]->(qa)
                CREATE (qa)-[:OF]->(c)
                """,
                name=concept_name,
                id=str(uuid.uuid4()),
                score=score,
                new_d=updated_state["difficulty"],
                new_s=updated_state["stability"],
                new_p=updated_state["retrievability"],
            )

            logger.info(
                f"[GraphService] '{concept_name}' kavramı quiz sonrasında guncellendi | "
                f"Skor: {score} | "
                f"Yeni S: {updated_state['stability']} | Yeni R: {updated_state['retrievability']}"
            )
            
            return {
                "status": "success",
                "concept": concept_name,
                "score": score,
                "new_stability": updated_state["stability"],
                "new_retrievability": updated_state["retrievability"]
            }

    async def get_quiz_history(self, limit: int = 50, concept: Optional[str] = None) -> list[dict]:
        """
        Kullanıcının geçmiş quiz denemelerini (en yeniden eskiye) döndürür.
        concept verilirse sadece o kavrama ait denemeler (unutma eğrisi grafiği için) döner.
        Frontend'de 'Geçmiş' panelinde ve kavram detayındaki sparkline'da gösterilir.
        """
        async with self.neo4j.session() as session:
            result = await session.run(
                """
                MATCH (u:User {id: 'local_user'})-[:ATTEMPTED]->(qa:QuizAttempt)-[:OF]->(c:Concept)
                WHERE $concept IS NULL OR c.name = $concept
                RETURN qa.id                  AS id,
                       c.name                 AS concept,
                       qa.score               AS score,
                       qa.timestamp           AS timestamp,
                       qa.new_retrievability  AS new_retrievability,
                       qa.new_stability       AS new_stability
                ORDER BY qa.timestamp DESC
                LIMIT $limit
                """,
                limit=max(1, min(200, limit)),
                concept=concept,
            )
            rows = await result.data()

        history = []
        for r in rows:
            ts = r.get("timestamp")
            history.append({
                "id": r["id"],
                "concept": r["concept"],
                "score": r["score"],
                "timestamp": ts.iso_format() if ts else None,
                "new_retrievability": r.get("new_retrievability"),
                "new_stability": r.get("new_stability"),
            })
        return history

    async def get_graph_data(self) -> dict:
        """
        /graph endpoint'i icin Neo4j'den tum Concept node ve edge'lerini ceker.
        React Frontend'in kullanacagi format.
        """
        async with self.neo4j.session() as session:
            result = await session.run(
                """
                MATCH (c:Concept)
                OPTIONAL MATCH (c)-[:RELATED_TO]->(related:Concept)
                OPTIONAL MATCH (rs:RawSession)-[:EXTRACTED_CONCEPT]->(c)
                WITH c, related, rs,
                     trim(replace(replace(replace(rs.question,
                          'Siz şunu dediniz:\\n', ''),
                          'You said:\\n', ''),
                          'Siz şunu dediniz:', '')) AS cleanTitle
                RETURN c.name       AS name,
                       c.topic      AS topic,
                       c.difficulty AS difficulty,
                       c.created_at AS created_at,
                       c.fsrs_s     AS stability,
                       c.last_studied AS last_studied,
                       collect(DISTINCT related.name) AS related_concepts,
                       collect(DISTINCT rs.url) AS source_urls,
                       collect(DISTINCT {title: cleanTitle, answer: rs.answer}) AS source_interactions
                """
            )
            records = await result.data()

        nodes = []
        edges = []
        seen_edges = set()

        import re
        from datetime import datetime, timezone
        for r in records:
            # Clean titles in Python for regex support
            cleaned_interactions = []
            seen_titles = set()
            for inter in r["source_interactions"]:
                t = inter.get("title")
                a = inter.get("answer")
                if t:
                    clean_t = re.sub(r'^(Siz\s+[sş]unu\s+dediniz\s*:?\s*|You\s+said\s*:?\s*)', '', t, flags=re.IGNORECASE).strip()
                    if clean_t and clean_t not in seen_titles:
                        seen_titles.add(clean_t)
                        cleaned_interactions.append({"title": clean_t, "answer": a})

            # Calculate dynamic FSRS retrievability using FSRSEngine
            stability = r.get("stability")
            last_studied = r.get("last_studied")
            fsrs_p = 1.0
            
            if stability is not None and last_studied is not None:
                # Convert neo4j.time.DateTime to python datetime
                studied_dt = last_studied.to_native()
                if studied_dt.tzinfo is None:
                    studied_dt = studied_dt.replace(tzinfo=timezone.utc)
                
                now = datetime.now(timezone.utc)
                elapsed_days = (now - studied_dt).total_seconds() / (24 * 3600)
                fsrs_p = self.fsrs.calculate_current_retrievability(stability, elapsed_days)

            nodes.append({
                "id": r["name"],
                "label": r["name"],
                "topic": r["topic"],
                "cluster_id": (r["topic"] or "Genel").strip(),  # Frontend gruplama/renklendirme için
                "difficulty": r["difficulty"],
                "created_at": r["created_at"].iso_format() if r["created_at"] else None,
                "fsrs_p": fsrs_p,
                "stability": stability,
                "sources": r["source_urls"],
                "source_interactions": cleaned_interactions
            })
            for rel in r["related_concepts"]:
                if rel and (r["name"], rel) not in seen_edges:
                    edges.append({"source": r["name"], "target": rel})
                    seen_edges.add((r["name"], rel))

        return {"nodes": nodes, "edges": edges, "total": len(nodes)}

    async def _embed_and_save_to_qdrant(self, session: dict, extraction: ExtractionResult):
        """Metni vektöre dönüştürüp Qdrant'a kaydeder."""
        try:
            # Kaynak metni (Platform, soru ve cevap)
            text_content = f"Platform: {session['platform']}\nSoru/Konu: {session['question']}\nIcerik: {session['answer']}"
            
            # Kavram isimlerini listele
            concept_names = [c.name for c in extraction.concepts]
            
            # Metni embed et
            vector = await self.embeddings.aembed_query(text_content)
            
            # Qdrant'a kaydet
            point_id = str(uuid.uuid4())
            await self.qdrant.upsert(
                collection_name=settings.QDRANT_COLLECTION_NAME,
                points=[
                    PointStruct(
                        id=point_id,
                        vector=vector,
                        payload={
                            "session_id": session["session_id"],
                            "platform": session["platform"],
                            "text": text_content,
                            "concepts": concept_names,
                            "timestamp": session.get("timestamp", "")
                        }
                    )
                ]
            )
            logger.debug(f"[GraphService] {session['session_id']} Qdrant'a gomuldu.")
        except Exception as e:
            logger.error(f"[GraphService] Qdrant embedding hatasi: {e}", exc_info=True)

    async def get_sources(self) -> list[dict]:
        """NotebookLM Sidebar icin veri kaynaklarini (RawSession) dondurur."""
        async with self.neo4j.session() as session:
            result = await session.run(
                """
                MATCH (rs:RawSession)
                WHERE rs.processed = true
                WITH rs,
                     trim(replace(replace(replace(rs.question,
                         'Siz şunu dediniz:\n', ''),
                         'You said:\n', ''),
                         'Siz şunu dediniz:', '')) AS cleanTitle
                RETURN rs.session_id AS id,
                       rs.platform AS platform,
                       cleanTitle AS title,
                       rs.url AS url,
                       rs.timestamp AS date
                ORDER BY rs.timestamp DESC
                """
            )
            rows = await result.data()
            # Python tarafında da ekstra temizlik
            import re
            cleaned = []
            for r in rows:
                d = dict(r)
                if d.get("title"):
                    d["title"] = re.sub(r'^(Siz\s+[sş]unu\s+dediniz\s*:?\s*|You\s+said\s*:?\s*)', '', d["title"], flags=re.IGNORECASE).strip()
                    # Başlığı 80 karakterle kısalt
                    if len(d["title"]) > 80:
                        d["title"] = d["title"][:77] + "..."
                cleaned.append(d)
            return cleaned

    async def update_all_retrievability(self) -> int:
        """
        Tüm Concept düğümlerinin R (retrievability / fsrs_p) değerini günceller.
        FSRS formülü: R(t) = (1 + factor * t / S)^decay
        """
        async with self.neo4j.session() as session:
            result = await session.run("""
                MATCH (c:Concept)
                WHERE c.fsrs_s IS NOT NULL AND c.last_studied IS NOT NULL
                WITH c,
                     duration.inSeconds(c.last_studied, datetime()).seconds / 86400.0
                     AS elapsed_days
                WHERE elapsed_days > 0
                WITH c, elapsed_days,
                     // FSRS Power Law: R = (1 + factor * t / S)^decay
                     // factor = 0.2346, decay = -0.5
                     (1.0 + 0.2346 * elapsed_days / c.fsrs_s) ^ (-0.5) AS new_p
                WITH c, round(
                    CASE WHEN new_p < 0 THEN 0.0
                         WHEN new_p > 1 THEN 1.0
                         ELSE new_p END, 4) AS rounded_p
                SET c.fsrs_p = rounded_p
                RETURN count(c) AS updated_count
            """)
            record = await result.single()
            return record["updated_count"] if record else 0

    async def _fetch_all_concepts_with_dynamic_p(self) -> list[dict]:
        """
        Tüm Concept'leri (topic filtresi olmadan) dinamik olarak hesaplanmış
        güncel fsrs_p (hatırlama olasılığı) değeriyle birlikte döndürür.
        get_topic_clusters ve get_learning_path arasında paylaşılan çekirdek.
        """
        from datetime import datetime, timezone

        async with self.neo4j.session() as session:
            result = await session.run("""
                MATCH (c:Concept)
                RETURN c.name        AS name,
                       c.topic       AS topic,
                       c.fsrs_p      AS fsrs_p,
                       c.fsrs_s      AS stability,
                       c.fsrs_d      AS fsrs_d,
                       c.difficulty  AS difficulty,
                       c.last_studied AS last_studied
            """)
            records = await result.data()

        now = datetime.now(timezone.utc)
        concepts = []
        for r in records:
            p = r.get("fsrs_p")
            stability = r.get("stability")
            last_studied = r.get("last_studied")

            if stability is not None and last_studied is not None:
                try:
                    studied_dt = last_studied.to_native()
                    if studied_dt.tzinfo is None:
                        studied_dt = studied_dt.replace(tzinfo=timezone.utc)
                    elapsed_days = (now - studied_dt).total_seconds() / (24 * 3600)
                    p = self.fsrs.calculate_current_retrievability(stability, elapsed_days)
                except Exception:
                    pass

            concepts.append({
                "name": r["name"],
                "topic": r["topic"],
                "fsrs_p": round(p, 4) if isinstance(p, (int, float)) else None,
                "difficulty": r["difficulty"],
            })
        return concepts

    @staticmethod
    def _classify_health(p) -> str:
        """FSRS hatırlama olasılığını sağlık durumuna sınıflar: strong/warning/critical/unknown."""
        if not isinstance(p, (int, float)):
            return "unknown"
        if p >= 0.7:
            return "strong"
        if p >= 0.4:
            return "warning"
        return "critical"

    async def get_topic_clusters(self) -> dict:
        """
        Kavramları topic bazında kümeler. Her kümenin:
        - Üye listesi (kavram adı + FSRS metrikleri)
        - Ortalama hatırlama oranı (avg_retrievability)
        - Sağlık durumu (strong/warning/critical)
        döndürülür. Harita büyüdüğünde okunabilirlik için frontend kümeleme yapabilir.
        """
        all_concepts = await self._fetch_all_concepts_with_dynamic_p()
        records = [c for c in all_concepts if c["topic"]]

        if not records:
            return {"clusters": [], "total_clusters": 0}

        cluster_map = {}  # topic -> list[member]

        for r in records:
            topic = (r["topic"] or "Genel").strip()
            member = {
                "name": r["name"],
                "fsrs_p": r["fsrs_p"],
                "difficulty": r["difficulty"],
            }

            if topic not in cluster_map:
                cluster_map[topic] = []
            cluster_map[topic].append(member)

        # Kümeleri oluştur
        clusters = []
        for topic, members in cluster_map.items():
            p_values = [m["fsrs_p"] for m in members if m["fsrs_p"] is not None]
            avg_p = round(sum(p_values) / len(p_values), 4) if p_values else None
            health = self._classify_health(avg_p)

            clusters.append({
                "label": topic,
                "members": members,
                "member_count": len(members),
                "avg_retrievability": avg_p,
                "health": health,
            })

        # Büyük kümeler önce
        clusters.sort(key=lambda c: c["member_count"], reverse=True)

        # Tek elemanlı kümeleri "Genel" altında topla (gerçek küme sayılmazlar)
        general_members = []
        final_clusters = []
        for c in clusters:
            if c["member_count"] <= 1:
                general_members.extend(c["members"])
            else:
                final_clusters.append(c)

        if general_members:
            p_values = [m["fsrs_p"] for m in general_members if m["fsrs_p"] is not None]
            avg_p = round(sum(p_values) / len(p_values), 4) if p_values else None
            health = self._classify_health(avg_p)
            final_clusters.append({
                "label": "Genel",
                "members": general_members,
                "member_count": len(general_members),
                "avg_retrievability": avg_p,
                "health": health,
            })

        return {"clusters": final_clusters, "total_clusters": len(final_clusters)}

    async def get_learning_path(self, target: str, max_hops: int = 6) -> dict | None:
        """
        Hedef kavrama, mevcut sağlam (fsrs_p yüksek) kavramlardan en kısa
        RELATED_TO rotasını (Neo4j shortestPath) bulur ve rota üzerindeki
        zayıf (sağlık durumu 'strong' olmayan) duraklari isaretler.
        Hedef grafikte yoksa None döner (router 404'e çevirir).
        """
        all_concepts = await self._fetch_all_concepts_with_dynamic_p()
        concept_by_name = {c["name"]: c for c in all_concepts}

        if target not in concept_by_name:
            return None

        STRONG_THRESHOLD = 0.7
        MAX_SOURCE_CANDIDATES = 20  # shortestPath her aday icin ayri calisiyor; graf buyuklugunden bagimsiz sabit maliyet icin sinirla

        source_candidates = sorted(
            (c for c in all_concepts if c["name"] != target and c["fsrs_p"] is not None and c["fsrs_p"] >= STRONG_THRESHOLD),
            key=lambda c: c["fsrs_p"],
            reverse=True,
        )[:MAX_SOURCE_CANDIDATES]
        source_candidates = [c["name"] for c in source_candidates]

        if not source_candidates:
            # Soğuk başlangıç: hiçbir kavram 'strong' değilse en yüksek p'ye sahip olanı fallback kaynak yap
            others = [c for c in all_concepts if c["name"] != target]
            if not others:
                return {
                    "found": False,
                    "target": target,
                    "reason": "Henuz baglantili baska kavram yok.",
                }
            best = max(others, key=lambda c: c["fsrs_p"] if c["fsrs_p"] is not None else -1)
            source_candidates = [best["name"]]

        hops = max(1, min(10, int(max_hops)))

        async with self.neo4j.session() as session:
            result = await session.run(
                f"""
                MATCH (target:Concept {{name: $target}})
                MATCH (source:Concept) WHERE source.name IN $source_names
                MATCH p = shortestPath((source)-[:RELATED_TO*1..{hops}]-(target))
                RETURN [n IN nodes(p) | n.name] AS names, length(p) AS len, source.name AS source_name
                ORDER BY len ASC
                LIMIT 1
                """,
                target=target,
                source_names=source_candidates,
            )
            record = await result.single()

        if record is None:
            return {
                "found": False,
                "target": target,
                "reason": "Hedefe mevcut bilgiden ulasan bir yol yok.",
            }

        path = []
        weak_stops = []
        for name in record["names"]:
            concept = concept_by_name.get(name, {"name": name, "topic": None, "fsrs_p": None, "difficulty": None})
            health = self._classify_health(concept.get("fsrs_p"))
            path.append({
                "name": name,
                "topic": concept.get("topic"),
                "difficulty": concept.get("difficulty"),
                "fsrs_p": concept.get("fsrs_p"),
                "health": health,
            })
            if health != "strong":
                weak_stops.append(name)

        return {
            "found": True,
            "target": target,
            "source": record["source_name"],
            "hops": record["len"],
            "path": path,
            "weak_stops": weak_stops,
        }

    async def import_graph_data(self, graph_data: dict):
        """
        Dışarıdan gelen JSON verisini (İçe Aktar / örnek veri seti) Neo4j'ye MERGE ile ekler.
        Beklenen şekil, /api/v1/graph export formatıyla aynı:
        nodes: [{id, topic, difficulty, fsrs_p, stability, created_at}], edges: [{source, target}]

        NOT: Önceki sürüm kenarları 'RELATES_TO' ilişki tipiyle yazıyordu ama harita
        (get_graph_data) 'RELATED_TO' arıyordu — içe aktarılan kenarlar haritada hiç
        görünmüyordu. Ayrıca topic/difficulty/fsrs_p hiç yazılmadığı için içe aktarılan
        kavramlar hep 'Genel' kümesinde ve renksiz (fsrs_p=1.0 sabit) kalıyordu.
        """
        from datetime import datetime, timezone

        nodes = graph_data.get("nodes", [])
        edges = graph_data.get("edges", [])

        async with self.neo4j.session() as session:
            # 1. Düğümleri, FSRS durumlarını koruyarak ekle
            for node in nodes:
                name = node.get("id") or node.get("name")
                if not name:
                    continue

                difficulty = node.get("difficulty") or "orta"
                fsrs_s = node.get("stability")
                fsrs_p = node.get("fsrs_p")
                if fsrs_s is None:
                    fsrs_s = self.fsrs.calculate_initial_state(difficulty)["stability"]
                if fsrs_p is None:
                    fsrs_p = 1.0
                fsrs_d = self.fsrs.calculate_initial_state(difficulty)["difficulty"]

                # last_studied'i geriye tarihli ayarla ki get_graph_data yeniden hesapladığında
                # aynı fsrs_p'ye ulaşsın (bkz. update_concept_after_quiz'deki aynı teknik).
                elapsed_days = self.fsrs.calculate_elapsed_days_for_retrievability(fsrs_s, fsrs_p)
                elapsed_seconds = int(elapsed_days * 24 * 3600)

                await session.run(
                    """
                    MERGE (c:Concept {name: $name})
                    SET c.topic        = $topic,
                        c.difficulty   = $difficulty,
                        c.fsrs_d       = $fsrs_d,
                        c.fsrs_s       = $fsrs_s,
                        c.fsrs_p       = $fsrs_p,
                        c.created_at   = coalesce(c.created_at, datetime($created_at)),
                        c.last_studied = datetime() - duration({seconds: $elapsed_seconds})
                    """,
                    {
                        "name": name,
                        "topic": node.get("topic"),
                        "difficulty": difficulty,
                        "fsrs_d": fsrs_d,
                        "fsrs_s": fsrs_s,
                        "fsrs_p": fsrs_p,
                        "created_at": node.get("created_at") or datetime.now(timezone.utc).isoformat(),
                        "elapsed_seconds": elapsed_seconds,
                    },
                )

            # 2. İlişkileri RELATED_TO olarak kur (haritanın okuduğu ilişki tipiyle aynı)
            for edge in edges:
                source_name = edge.get("source")
                target_name = edge.get("target")
                if not source_name or not target_name:
                    continue
                await session.run(
                    """
                    MATCH (source:Concept {name: $source_name})
                    MATCH (target:Concept {name: $target_name})
                    MERGE (source)-[:RELATED_TO]->(target)
                    """,
                    {"source_name": source_name, "target_name": target_name},
                )
        return True

    async def calculate_brain_health(self):
        async with self.neo4j.session() as session:
            # 1. Total Concepts & FSRS Data
            result = await session.run(
                """
                MATCH (c:Concept)
                WITH coalesce(c.fsrs_p, 1.0) AS p
                WITH count(*) AS total_concepts,
                     avg(p) AS avg_p,
                     sum(CASE WHEN p >= 0.8 THEN 1 ELSE 0 END) AS healthy_count,
                     sum(CASE WHEN p >= 0.5 AND p < 0.8 THEN 1 ELSE 0 END) AS warning_count,
                     sum(CASE WHEN p < 0.5 THEN 1 ELSE 0 END) AS at_risk_count
                RETURN total_concepts, avg_p, healthy_count, warning_count, at_risk_count
                """
            )
            record = await result.single()
            total_concepts = record["total_concepts"] if record else 0

            if total_concepts == 0:
                return {
                    "score": None,
                    "label": None,
                    "breakdown": {
                        "average_retention": {"value": 0.0, "weight": 0.50, "weighted": 0.0},
                        "healthy_ratio": {"value": 0.0, "weight": 0.25, "weighted": 0.0, "count": 0, "total": 0},
                        "recent_quiz_accuracy": {"value": None, "weight": 0.15, "weighted": None, "attempt_count": 0},
                        "study_consistency": {"value": 0.0, "weight": 0.10, "weighted": 0.0, "active_days_last_30": 0}
                    },
                    "concept_summary": {"total": 0, "healthy": 0, "warning": 0, "at_risk": 0},
                    "computed_at": datetime.now(timezone.utc).isoformat()
                }

            avg_p = record["avg_p"] or 0.0
            healthy_count = record["healthy_count"] or 0
            warning_count = record["warning_count"] or 0
            at_risk_count = record["at_risk_count"] or 0

            # 2. Recent Quiz Accuracy
            quiz_result = await session.run(
                """
                MATCH (u:User {id: 'local_user'})-[:ATTEMPTED]->(qa:QuizAttempt)
                RETURN qa.score AS score
                ORDER BY qa.timestamp DESC
                LIMIT 10
                """
            )
            quiz_records = await quiz_result.data()
            recent_quiz_scores = [r["score"] for r in quiz_records if r["score"] is not None]
            recent_quiz_accuracy = (sum(recent_quiz_scores) / len(recent_quiz_scores)) * 100 if recent_quiz_scores else None

            # 3. Study Consistency
            consistency_result = await session.run(
                """
                MATCH (c:Concept)
                WHERE c.created_at IS NOT NULL AND c.created_at >= datetime() - duration({days: 30})
                RETURN date(c.created_at) AS active_day
                UNION
                MATCH (u:User {id: 'local_user'})-[:ATTEMPTED]->(qa:QuizAttempt)
                WHERE qa.timestamp IS NOT NULL AND qa.timestamp >= datetime() - duration({days: 30})
                RETURN date(qa.timestamp) AS active_day
                """
            )
            consistency_records = await consistency_result.data()
            distinct_days = len(set(r["active_day"] for r in consistency_records if r["active_day"] is not None))

            # Weights
            w_retention = 0.50
            w_healthy = 0.25
            w_quiz = 0.15
            w_consistency = 0.10

            if recent_quiz_accuracy is None:
                w_retention = 0.50 / 0.85
                w_healthy = 0.25 / 0.85
                w_consistency = 0.10 / 0.85

            val_retention = avg_p * 100
            val_healthy = (healthy_count / total_concepts) * 100
            val_consistency = min(100.0, (distinct_days / 15) * 100)

            weighted_retention = val_retention * w_retention
            weighted_healthy = val_healthy * w_healthy
            weighted_quiz = recent_quiz_accuracy * w_quiz if recent_quiz_accuracy is not None else None
            weighted_consistency = val_consistency * w_consistency

            total_score = weighted_retention + weighted_healthy + weighted_consistency
            if weighted_quiz is not None:
                total_score += weighted_quiz

            total_score = max(0.0, min(100.0, total_score))
            final_score = int(round(total_score))

            if final_score >= 85:
                label = "Mükemmel"
            elif final_score >= 70:
                label = "İyi"
            elif final_score >= 50:
                label = "Orta"
            elif final_score >= 25:
                label = "Zayıf"
            else:
                label = "Kritik"

            logger.info(f"Computed Brain Health Score: {final_score}")

            return {
                "score": final_score,
                "label": label,
                "breakdown": {
                    "average_retention": {
                        "value": round(val_retention, 1),
                        "weight": round(w_retention, 4),
                        "weighted": round(weighted_retention, 1)
                    },
                    "healthy_ratio": {
                        "value": round(val_healthy, 1),
                        "weight": round(w_healthy, 4),
                        "weighted": round(weighted_healthy, 1),
                        "count": healthy_count,
                        "total": total_concepts
                    },
                    "recent_quiz_accuracy": {
                        "value": round(recent_quiz_accuracy, 1) if recent_quiz_accuracy is not None else None,
                        "weight": round(w_quiz, 4),
                        "weighted": round(weighted_quiz, 1) if weighted_quiz is not None else None,
                        "attempt_count": len(recent_quiz_scores)
                    },
                    "study_consistency": {
                        "value": round(val_consistency, 1),
                        "weight": round(w_consistency, 4),
                        "weighted": round(weighted_consistency, 1),
                        "active_days_last_30": distinct_days
                    }
                },
                "concept_summary": {
                    "total": total_concepts,
                    "healthy": healthy_count,
                    "warning": warning_count,
                    "at_risk": at_risk_count
                },
                "computed_at": datetime.now(timezone.utc).isoformat()
            }
