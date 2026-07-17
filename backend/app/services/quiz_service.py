from typing import Optional

from neo4j import AsyncDriver
from qdrant_client import AsyncQdrantClient
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.embeddings import get_local_embeddings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


# ---- Pydantic Model: LLM'in dönecegi yapı ----
class QuizQuestion(BaseModel):
    question: str = Field(description="Soru metni (Türkçe)")
    options: list[str] = Field(description="4 sık: 1 dogru + 3 celdirici")
    correct_index: int = Field(description="Dogru sıkkın indeksi (0-3)")
    explanation: str = Field(description="Dogru cevabın kısa açıklaması (1-2 cümle)")


class GeneratedQuiz(BaseModel):
    questions: list[QuizQuestion] = Field(description="Üretilen quiz soruları")


QUIZ_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """Sen bir öğrenme asistanının quiz üreticisisin. Görevin, kullanıcının KENDİ öğrenme
kaynaklarından yola çıkarak "{concept}" kavramı hakkında {num_questions} adet çoktan seçmeli soru üretmek.

KURALLAR:
1. Soruları SADECE aşağıdaki bağlam (kullanıcının kendi öğrenme geçmişi) üzerine kur.
   Bağlamda olmayan bilgiden soru üretme — cevabı bağlamdan doğrulanamayan soruyu ekleme.
2. Her soruda tam 4 şık olsun: 1 doğru cevap + 3 çeldirici.
3. Çeldiricileri mümkün olduğunca şu "ilişkili kavramlar" listesinden veya onların özelliklerinden seç:
   {distractor_pool}
   Bu kavramlar anlamsal olarak yakın olduğu için iyi çeldiricidir; ama doğru cevapla karıştırılamayacak
   kadar da net yanlış olmalılar.
4. Soru zorluğunu kavramın hatırlama durumuna göre ayarla: hatırlama olasılığı {fsrs_p}
   (düşükse temel hatırlama soruları, yüksekse uygulama/karşılaştırma soruları sor).
5. Sorular Türkçe olsun; teknik terimler orijinal (İngilizce) kalabilir.
6. correct_index her soruda farklı konumda olsun (hep 0 olmasın).

Yanıtını SADECE aşağıdaki JSON formatında ver, başka hiçbir şey yazma:
{{
  "questions": [
    {{
      "question": "soru metni",
      "options": ["şık A", "şık B", "şık C", "şık D"],
      "correct_index": 2,
      "explanation": "kısa açıklama"
    }}
  ]
}}""",
    ),
    (
        "human",
        "Kavram: {concept} (Konu: {topic})\n\nBağlam (kullanıcının öğrenme kaynakları):\n{context}",
    ),
])


class QuizService:
    """
    Sprint 3 - Quiz Döngüsü (üretim ayağı):
    1. Hedef kavramı seç (istekte verilmediyse fsrs_p'si en düşük = unutulmak üzere olan kavram)
    2. Hibrit retrieval: Neo4j'den kavramın kendi kaynakları (graph) + Qdrant'tan anlamsal komşu
       içerikler (vector) birleştirilir
    3. Çeldirici madenciliği: embedding uzayında hedefe yakın kavramlar + RELATED_TO komşuları
       çeldirici havuzu olarak LLM'e verilir
    4. LLM (structured output) 3-5 çoktan seçmeli soru üretir
    Skorlama Gülistan'ın POST /quiz/submit endpoint'inde (FSRS güncellemesi) kapanır.
    """

    def __init__(self, neo4j_driver: AsyncDriver, qdrant_client: AsyncQdrantClient = None):
        self.neo4j = neo4j_driver
        self.qdrant = qdrant_client
        self.embeddings = get_local_embeddings()
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-3.5-flash",
            temperature=0.4,
            api_key=settings.GOOGLE_API_KEY,
        )
        self.parser = JsonOutputParser(pydantic_object=GeneratedQuiz)
        self.chain = QUIZ_PROMPT | self.llm | self.parser

    async def get_weak_concepts(self, limit: int = 5) -> list[dict]:
        """
        FSRS'e göre en riskli (fsrs_p düşük) ve en az 1 kaynağı olan kavramları döner.
        Frontend "günün quizi" önerisi için kullanır.
        """
        async with self.neo4j.session() as session:
            result = await session.run(
                """
                MATCH (rs:RawSession)-[:EXTRACTED_CONCEPT]->(c:Concept)
                WITH c, count(rs) AS source_count
                RETURN c.name  AS name,
                       c.topic AS topic,
                       coalesce(c.fsrs_p, 1.0) AS fsrs_p,
                       c.fsrs_s AS stability,
                       source_count
                ORDER BY fsrs_p ASC
                LIMIT $limit
                """,
                limit=limit,
            )
            return [dict(r) for r in await result.data()]

    async def generate_quiz(
        self, concept_name: Optional[str] = None, num_questions: int = 4
    ) -> Optional[dict]:
        """
        Bir kavram için quiz üretir. concept_name verilmezse en zayıf kavram otomatik seçilir.
        Kavram bulunamazsa None, kaynak yoksa {"error": "no_sources", ...} döner.
        """
        # 1. Hedef kavramı belirle (verilmediyse FSRS'e göre en riskli olan)
        if not concept_name:
            weak = await self.get_weak_concepts(limit=1)
            if not weak:
                return None
            concept_name = weak[0]["name"]
            logger.info(f"[Quiz] Otomatik hedef seçildi (en düşük fsrs_p): {concept_name}")

        # 2. Neo4j: kavram + RELATED_TO komşuları + kaynak oturumları (graph retrieval)
        concept = await self._fetch_concept_with_sources(concept_name)
        if concept is None:
            return None

        # 3. Qdrant: anlamsal olarak yakın içerikler + çeldirici kavramlar (vector retrieval)
        extra_chunks, distractor_pool = await self._semantic_retrieval(
            concept_name, exclude={concept_name}
        )
        # Graf komşuları da çeldirici havuzuna girer
        distractor_pool = list(dict.fromkeys(concept["neighbors"] + distractor_pool))[:10]

        # 4. Bağlamı birleştir: önce kavramın kendi kaynakları, sonra anlamsal komşular
        context_parts = []
        for src in concept["sources"][:5]:
            context_parts.append(
                f"[Kendi kaynağı | {src.get('platform', '?')}] "
                f"{(src.get('question') or '')[:300]}\n{(src.get('answer') or '')[:800]}"
            )
        context_parts.extend(extra_chunks[:3])

        if not context_parts:
            logger.warning(f"[Quiz] '{concept_name}' için kaynak içerik yok, quiz üretilemez.")
            return {"error": "no_sources", "concept": concept_name}

        context_text = "\n\n---\n\n".join(context_parts)

        # 5. LLM ile structured output soru üretimi
        try:
            raw: dict = await self.chain.ainvoke({
                "concept": concept_name,
                "topic": concept.get("topic") or "genel",
                "num_questions": max(3, min(5, num_questions)),
                "fsrs_p": concept.get("fsrs_p") if concept.get("fsrs_p") is not None else 1.0,
                "distractor_pool": ", ".join(distractor_pool) if distractor_pool else "(havuz boş — makul çeldiriciler üret)",
                "context": context_text,
            })
            quiz = GeneratedQuiz(**raw)
        except Exception as e:
            logger.error(f"[Quiz] LLM soru üretim hatası ({concept_name}): {e}", exc_info=True)
            return {"error": "generation_failed", "concept": concept_name}

        # 6. Doğrulama: bozuk soruları ele (4 şıktan az / correct_index taşmış)
        valid_questions = [
            q for q in quiz.questions
            if len(q.options) == 4 and 0 <= q.correct_index < 4
        ]
        if not valid_questions:
            return {"error": "generation_failed", "concept": concept_name}

        logger.info(
            f"[Quiz] '{concept_name}' için {len(valid_questions)} soru üretildi "
            f"(çeldirici havuzu: {len(distractor_pool)}, kaynak: {len(context_parts)})"
        )
        return {
            "concept": concept_name,
            "topic": concept.get("topic"),
            "fsrs_p": concept.get("fsrs_p"),
            "questions": [q.model_dump() for q in valid_questions],
            "sources_used": len(context_parts),
        }

    async def _fetch_concept_with_sources(self, name: str) -> Optional[dict]:
        """Kavramı, RELATED_TO komşularını ve bağlı RawSession içeriklerini çeker."""
        async with self.neo4j.session() as session:
            result = await session.run(
                """
                MATCH (c:Concept {name: $name})
                OPTIONAL MATCH (c)-[:RELATED_TO]-(n:Concept)
                OPTIONAL MATCH (rs:RawSession)-[:EXTRACTED_CONCEPT]->(c)
                RETURN c.name  AS name,
                       c.topic AS topic,
                       c.fsrs_p AS fsrs_p,
                       [x IN collect(DISTINCT n.name) WHERE x IS NOT NULL] AS neighbors,
                       [s IN collect(DISTINCT {
                            question: rs.question,
                            answer: rs.answer,
                            platform: rs.platform
                       }) WHERE s.answer IS NOT NULL] AS sources
                """,
                name=name,
            )
            record = await result.single()
            return dict(record) if record else None

    async def _semantic_retrieval(
        self, concept_name: str, exclude: set[str]
    ) -> tuple[list[str], list[str]]:
        """
        Qdrant'ta kavram adına anlamsal olarak yakın içerikleri arar.
        Döner: (ek bağlam parçaları, çeldirici kavram adayları).
        Çeldiriciler embedding uzayında hedefe yakın ama farklı kavramlardır —
        anlamsal yakınlık onları "inandırıcı yanlış şık" yapar.
        """
        if not self.qdrant:
            return [], []
        try:
            query_vector = await self.embeddings.aembed_query(concept_name)
            hits = await self.qdrant.search(
                collection_name=settings.QDRANT_COLLECTION_NAME,
                query_vector=query_vector,
                limit=8,
            )
        except Exception as e:
            logger.error(f"[Quiz] Qdrant arama hatası: {e}", exc_info=True)
            return [], []

        chunks: list[str] = []
        distractors: list[str] = []
        for hit in hits:
            payload = hit.payload or {}
            text = payload.get("text", "")
            concepts = payload.get("concepts", [])
            # Hedef kavramın geçtiği içerikler bağlama girer
            if concept_name in concepts and text:
                chunks.append(f"[Anlamsal komşu | skor {hit.score:.2f}] {text[:800]}")
            # Yakın ama farklı kavramlar çeldirici adayıdır
            for cname in concepts:
                if cname not in exclude and cname not in distractors:
                    distractors.append(cname)
        return chunks, distractors
