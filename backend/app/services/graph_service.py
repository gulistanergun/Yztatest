import asyncio
from neo4j import AsyncDriver
from app.services.extraction_service import ConceptExtractor, ExtractionResult
from app.core.logging import get_logger

logger = get_logger(__name__)


from qdrant_client import AsyncQdrantClient
from qdrant_client.models import PointStruct
import uuid
from app.core.config import get_settings
from langchain_google_genai import GoogleGenerativeAIEmbeddings
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
        
        # Embedding modeli
        self.embeddings = GoogleGenerativeAIEmbeddings(
            model="models/gemini-embedding-001",
            google_api_key=settings.GOOGLE_API_KEY
        )

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

        for session in sessions:
            try:
                result = await self.extractor.extract(
                    platform=session["platform"],
                    question=session["question"],
                    answer=session["answer"],
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

