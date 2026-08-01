from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings
from qdrant_client import AsyncQdrantClient
from neo4j import AsyncDriver
from app.db.qdrant_client import get_qdrant_client
from app.db.neo4j_client import get_neo4j_driver
from app.core.config import get_settings
from app.core.embeddings import get_local_embeddings
from app.core.logging import get_logger
import time

settings = get_settings()
logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/chat", tags=["Chat"])

VECTOR_SEARCH_LIMIT = 8
VECTOR_SCORE_THRESHOLD = 0.35
MAX_CONTEXT_SOURCES = 8

class ChatRequest(BaseModel):
    query: str

class ChatResponse(BaseModel):
    answer: str
    sources: list[dict]

async def get_llm():
    return ChatGoogleGenerativeAI(
        model="gemini-3.1-flash-lite",
        temperature=0.3,
        api_key=settings.GOOGLE_API_KEY,
    )

async def get_embeddings():
    # Sorgu embedding'i de ingest ile AYNI yerel modeli kullanmali;
    # aksi halde vektor boyutu (384) Qdrant koleksiyonuyla uyusmaz.
    return get_local_embeddings()

async def _expand_via_graph(neo4j: AsyncDriver, concept_names: set[str]) -> list[dict]:
    """Verilen kavramlarin RELATED_TO komsularini ve komsularin kaynaklarini getirir."""
    if not concept_names:
        return []
    try:
        async with neo4j.session() as session:
            result = await session.run(
                """
                MATCH (c:Concept)
                WHERE c.name IN $names
                MATCH (c)-[:RELATED_TO]-(n:Concept)
                WHERE NOT n.name IN $names
                OPTIONAL MATCH (rs:RawSession)-[:EXTRACTED_CONCEPT]->(n)
                RETURN DISTINCT n.name AS concept, rs.question AS question,
                       rs.answer AS answer, rs.platform AS platform
                """,
                names=list(concept_names),
            )
            records = await result.data()
            return [r for r in records if r.get("answer")]
    except Exception as e:
        logger.error(f"[Chat] Graf genisletme hatasi, vektor sonuclariyla devam ediliyor: {e}")
        return []

@router.post("/", response_model=ChatResponse)
async def chat_with_brain(
    request: ChatRequest,
    qdrant: AsyncQdrantClient = Depends(get_qdrant_client),
    llm: ChatGoogleGenerativeAI = Depends(get_llm),
    embeddings: HuggingFaceEmbeddings = Depends(get_embeddings),
    neo4j: AsyncDriver = Depends(get_neo4j_driver),
):
    """Kullanıcının Zihin Haritasındaki bilgilerine dayanarak cevap verir (hibrit RAG: vektör + graf)."""
    start_time = time.time()
    try:
        # 1. Kullanici sorgusunu vektore cevir
        logger.info(f"[Chat] Soru alindi: {request.query}")
        embed_start = time.time()
        query_vector = await embeddings.aembed_query(request.query)
        logger.info(f"[Chat] Embedding tamamlandi. Süre: {time.time() - embed_start:.2f}s")

        # 2. Asama: Qdrant'ta benzer belgeleri ara (genisletilmis limit + skor esigi)
        search_start = time.time()
        search_result = await qdrant.search(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            query_vector=query_vector,
            limit=VECTOR_SEARCH_LIMIT,
            score_threshold=VECTOR_SCORE_THRESHOLD,
        )
        logger.info(f"[Chat] Qdrant aramasi tamamlandi. Süre: {time.time() - search_start:.2f}s. Bulunan kaynak: {len(search_result)}")

        contexts: list[str] = []
        sources: list[dict] = []
        seen_concepts: set[str] = set()

        for scored_point in search_result:
            payload = scored_point.payload or {}
            text = payload.get("text")
            if not text:
                continue
            concepts = payload.get("concepts", []) or []
            contexts.append(f"Kaynak: {payload.get('platform')}\nİçerik: {text}")
            sources.append({
                "platform": payload.get("platform"),
                "concept": concepts[0] if concepts else None,
                "concepts": concepts,
                "score": scored_point.score,
                "via": "vector",
            })
            seen_concepts.update(concepts)

        # 3. Asama: bulunan kavramlarin RELATED_TO komsularini graf ile genislet
        if seen_concepts:
            graph_start = time.time()
            graph_hits = await _expand_via_graph(neo4j, seen_concepts)
            logger.info(f"[Chat] Graf genisletme tamamlandi. Süre: {time.time() - graph_start:.2f}s. Bulunan komsu kaynak: {len(graph_hits)}")
            for hit in graph_hits:
                if len(contexts) >= MAX_CONTEXT_SOURCES:
                    break
                contexts.append(
                    f"Kaynak: {hit.get('platform')} (ilişkili kavram: {hit.get('concept')})\n"
                    f"İçerik: {hit.get('answer')}"
                )
                sources.append({
                    "platform": hit.get("platform"),
                    "concept": hit.get("concept"),
                    "concepts": [hit.get("concept")] if hit.get("concept") else [],
                    "score": None,
                    "via": "graph",
                })

        # 4. Hicbir kaynak bulunamadiysa LLM'i cagirmadan durustce yanit ver
        if not contexts:
            logger.info(f"[Chat] Eslesme bulunamadi, LLM cagrilmiyor. TOPLAM SURE: {time.time() - start_time:.2f}s")
            return ChatResponse(
                answer="Hafızamda bu konuyla ilgili bir bilgi bulamadım. Belki bu konu hakkında yeni kaynaklar eklemelisin!",
                sources=[]
            )

        context_text = "\n\n---\n\n".join(contexts)

        # 5. LLM'e Prompt gonder
        prompt = f"""Sen kullanıcının kişisel öğrenme asistanı ve 'İkinci Beyni'sin.
Kullanıcı sana kendi zihin haritasındaki bilgileri soruyor.
SADECE aşağıdaki bağlamdaki bilgileri kullanarak kullanıcının sorusuna net bir dille cevap ver.
Bağlamda birden fazla kaynak veya kavram varsa aralarındaki bağlantıyı kurarak sentezle;
tek bir parçayı olduğu gibi tekrarlama.
Cevap bağlamda yoksa 'Bunu henüz öğrenmedik' de.

Bağlam:
{context_text}

Soru: {request.query}
Cevabın:"""

        llm_start = time.time()
        logger.info("[Chat] Gemini API cagriliyor...")
        response = await llm.ainvoke(prompt)
        logger.info(f"[Chat] Gemini API cevap verdi. Süre: {time.time() - llm_start:.2f}s")
        logger.info(f"[Chat] TOPLAM ISLEM SURESI: {time.time() - start_time:.2f}s")

        answer_text = response.content
        if isinstance(answer_text, list):
            # Extract text from list of blocks
            answer_text = " ".join([
                block.get("text", "") for block in answer_text 
                if isinstance(block, dict) and "text" in block
            ])
            if not answer_text.strip():
                answer_text = str(response.content)

        return ChatResponse(
            answer=answer_text,
            sources=sources
        )

    except Exception as e:
        logger.error(f"[Chat] RAG Hatasi (Gecen sure: {time.time() - start_time:.2f}s): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Sohbet isleminde bir hata olustu.")
