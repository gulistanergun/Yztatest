from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings
from qdrant_client import AsyncQdrantClient
from app.db.qdrant_client import get_qdrant_client
from app.core.config import get_settings
from app.core.embeddings import get_local_embeddings
from app.core.logging import get_logger
import time

settings = get_settings()
logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/chat", tags=["Chat"])

class ChatRequest(BaseModel):
    query: str

class ChatResponse(BaseModel):
    answer: str
    sources: list[dict]

async def get_llm():
    return ChatGoogleGenerativeAI(
        model="gemini-3.5-flash",
        temperature=0.3,
        api_key=settings.GOOGLE_API_KEY,
    )

async def get_embeddings():
    # Sorgu embedding'i de ingest ile AYNI yerel modeli kullanmali;
    # aksi halde vektor boyutu (384) Qdrant koleksiyonuyla uyusmaz.
    return get_local_embeddings()

@router.post("/", response_model=ChatResponse)
async def chat_with_brain(
    request: ChatRequest,
    qdrant: AsyncQdrantClient = Depends(get_qdrant_client),
    llm: ChatGoogleGenerativeAI = Depends(get_llm),
    embeddings: HuggingFaceEmbeddings = Depends(get_embeddings)
):
    """Kullanıcının Zihin Haritasındaki bilgilerine dayanarak cevap verir (RAG)."""
    start_time = time.time()
    try:
        # 1. Kullanici sorgusunu vektore cevir
        logger.info(f"[Chat] Soru alindi: {request.query}")
        embed_start = time.time()
        query_vector = await embeddings.aembed_query(request.query)
        logger.info(f"[Chat] Embedding tamamlandi. Süre: {time.time() - embed_start:.2f}s")

        # 2. Qdrant'ta benzer belgeleri ara (Top 3)
        search_start = time.time()
        search_result = await qdrant.search(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            query_vector=query_vector,
            limit=3
        )
        logger.info(f"[Chat] Qdrant aramasi tamamlandi. Süre: {time.time() - search_start:.2f}s. Bulunan kaynak: {len(search_result)}")

        if not search_result:
            return ChatResponse(
                answer="Hafızamda bu konuyla ilgili bir bilgi bulamadım. Belki bu konu hakkında yeni kaynaklar eklemelisin!",
                sources=[]
            )

        # 3. Bulunan baglamlari (context) birlestir
        contexts = []
        sources = []
        for scored_point in search_result:
            payload = scored_point.payload
            contexts.append(f"Kaynak: {payload.get('platform')}\nİçerik: {payload.get('text')}")
            sources.append({
                "platform": payload.get("platform"),
                "concepts": payload.get("concepts", []),
                "score": scored_point.score
            })
            
        context_text = "\n\n---\n\n".join(contexts)

        # 4. LLM'e Prompt gonder
        prompt = f"""Sen kullanıcının kişisel öğrenme asistanı ve 'İkinci Beyni'sin.
Kullanıcı sana kendi zihin haritasındaki bilgileri soruyor.
SADECE aşağıdaki bağlamdaki bilgileri kullanarak kullanıcının sorusuna kısa ve net bir dille cevap ver.
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
