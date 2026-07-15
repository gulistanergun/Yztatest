from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.neo4j_client import get_neo4j_driver, create_constraints, close_neo4j_driver
from app.db.qdrant_client import get_qdrant_client, ensure_collection_exists, close_qdrant_client
from app.routers import ingest, graph, chat
from app.models.schemas import HealthResponse
from app.services.graph_service import GraphService
import asyncio

settings = get_settings()
logger = get_logger(__name__)

async def background_processor():
    """Arka planda her 10 saniyede bir bekleyen verileri isler ve unutma eğrisini günceller."""
    logger.info("[AutoProcessor] Otonom isleyici basladi. Her 10 saniyede bir tarama yapilacak.")
    while True:
        try:
            await asyncio.sleep(10)  # 10 saniye bekle
            neo4j_driver = await get_neo4j_driver()
            qdrant_client = await get_qdrant_client()
            service = GraphService(neo4j_driver=neo4j_driver, qdrant_client=qdrant_client)
            
            # 1. Bekleyen oturumları işle (kavram çıkarımı)
            stats = await service.process_pending_sessions(batch_size=20)
            
            # 2. Unutma Eğrisi (Forgetting Curve) güncellemesini yap
            decay_count = await service.update_all_retrievability()
            
            if stats["processed"] > 0 or stats["skipped"] > 0 or stats["errors"] > 0 or decay_count > 0:
                logger.info(f"[AutoProcessor] Islem tamamlandi: {stats} | {decay_count} kavram guncellendi.")
            else:
                logger.debug("[AutoProcessor] Bekleyen oturum yok.")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"[AutoProcessor] Hata: {e}", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Uygulama yaşam döngüsü yöneticisi.
    Startup'ta DB bağlantılarını kur, shutdown'da kapat.
    """
    # --- STARTUP ---
    logger.info(f"[STARTUP] {settings.APP_NAME} v{settings.APP_VERSION} baslatiliyor...")
    
    neo4j_driver = await get_neo4j_driver()
    await create_constraints(neo4j_driver)
    
    qdrant_client = await get_qdrant_client()
    await ensure_collection_exists(qdrant_client)
    
    logger.info("[STARTUP] Tum veritabani baglantilari hazir. Uygulama istekleri kabul etmeye basladi.")
    
    # Arka plan task'ini baslat
    processor_task = asyncio.create_task(background_processor())
    
    yield  # Uygulama çalışıyor

    # --- SHUTDOWN ---
    logger.info("[SHUTDOWN] Uygulama kapatiliyor, baglantılar temizleniyor...")
    processor_task.cancel()
    await close_neo4j_driver()
    await close_qdrant_client()
    logger.info("[SHUTDOWN] Tum baglantılar kapatildi.")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="LearnSphere AI - Otonom Öğrenme Hafızası Backend API",
    lifespan=lifespan,
)

# CORS: Chrome Extension'dan gelen isteklere izin ver
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Sprint 3'te sadece extension origin'e kısıtlanacak
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Router'ları kaydet
app.include_router(ingest.router)
app.include_router(graph.router)
app.include_router(chat.router)


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check() -> HealthResponse:
    """Sistem sağlık kontrolü: Neo4j ve Qdrant bağlantılarını test eder."""
    neo4j_ok, qdrant_ok = False, False

    try:
        driver = await get_neo4j_driver()
        await driver.verify_connectivity()
        neo4j_ok = True
    except Exception as e:
        logger.warning(f"Health check - Neo4j hatası: {e}")

    try:
        client = await get_qdrant_client()
        await client.get_collections()
        qdrant_ok = True
    except Exception as e:
        logger.warning(f"Health check - Qdrant hatası: {e}")

    return HealthResponse(
        status="healthy" if (neo4j_ok and qdrant_ok) else "degraded",
        version=settings.APP_VERSION,
        neo4j=neo4j_ok,
        qdrant=qdrant_ok,
    )
