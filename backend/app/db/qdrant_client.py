from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams
from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)

_client: AsyncQdrantClient | None = None

# all-MiniLM-L6-v2 vektör boyutu
EMBEDDING_DIMENSION = 384


async def get_qdrant_client() -> AsyncQdrantClient:
    """
    Qdrant async client'ını başlatır ve döner (Singleton).
    """
    global _client
    if _client is None:
        logger.info(f"[QDRANT] Baglanti kuruluyor: {settings.QDRANT_HOST}:{settings.QDRANT_PORT}")
        _client = AsyncQdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
        )
        logger.info("[QDRANT] Baglanti basariyla kuruldu.")
    return _client


async def ensure_collection_exists(client: AsyncQdrantClient):
    """
    Qdrant'ta 'learnsphere_concepts' koleksiyonu yoksa oluşturur.
    Bu koleksiyon, kullanıcı kavramlarının embedding'lerini tutar.
    """
    collections = await client.get_collections()
    existing = [c.name for c in collections.collections]

    if settings.QDRANT_COLLECTION_NAME not in existing:
        await client.create_collection(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            vectors_config=VectorParams(
                size=EMBEDDING_DIMENSION,
                distance=Distance.COSINE,
            ),
        )
        logger.info(f"[QDRANT] Koleksiyon olusturuldu: '{settings.QDRANT_COLLECTION_NAME}'")
    else:
        # Mevcut koleksiyonun boyutunu kontrol et
        col_info = await client.get_collection(settings.QDRANT_COLLECTION_NAME)
        if col_info.config.params.vectors.size != EMBEDDING_DIMENSION:
            logger.warning("[QDRANT] Koleksiyon boyutu uyumsuz! Silinip yeniden olusturuluyor...")
            await client.delete_collection(settings.QDRANT_COLLECTION_NAME)
            await client.create_collection(
                collection_name=settings.QDRANT_COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=EMBEDDING_DIMENSION,
                    distance=Distance.COSINE,
                ),
            )
            logger.info(f"[QDRANT] Koleksiyon yeniden olusturuldu: '{settings.QDRANT_COLLECTION_NAME}'")
        else:
            logger.info(f"[QDRANT] Koleksiyon zaten mevcut: '{settings.QDRANT_COLLECTION_NAME}'")


async def close_qdrant_client():
    """Uygulama kapanırken client'ı kapat."""
    global _client
    if _client:
        await _client.close()
        _client = None
        logger.info("[QDRANT] Baglanti kapatildi.")
