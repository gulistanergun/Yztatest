# pyrefly: ignore [missing-import]
from neo4j import AsyncDriver
# pyrefly: ignore [missing-import]
from qdrant_client import AsyncQdrantClient
from app.models.schemas import IngestRequest
from app.core.logging import get_logger

logger = get_logger(__name__)


class IngestService:
    """
    Chrome Extension'dan gelen ham veriyi işleyen servis katmanı.
    
    Sprint 1 kapsamı:
    - Gelen veriyi Neo4j'e 'raw' düğüm olarak kaydet (Sprint 2'de LangChain Agent çözecek)
    - Veriyi loglayarak ilerleyişi takip et
    
    Sprint 2'de bu class'a LangChain Agent çağrıları eklenerek kavram çıkarımı yapılacak.
    """

    def __init__(self, neo4j_driver: AsyncDriver, qdrant_client: AsyncQdrantClient):
        self.neo4j = neo4j_driver
        self.qdrant = qdrant_client

    async def process(self, request: IngestRequest) -> dict:
        logger.info(
            f"[Ingest] Yeni veri alındı | "
            f"Platform: {request.platform} | "
            f"Session: {request.session_id}"
        )

        # Sprint 1: Ham veriyi Neo4j'e 'RawSession' düğümü olarak kaydet.
        # Sprint 2: Bu düğüm, LangChain Agent tarafından okunup Concept düğümlerine dönüştürülecek.
        await self._store_raw_session(request)

        return {
            "status": "success",
            "message": "Veri başarıyla kaydedildi. Kavram çıkarımı kuyruğa alındı.",
            "session_id": request.session_id,
        }

    async def _store_raw_session(self, request: IngestRequest):
        """
        Ham soru-cevap çiftini Neo4j'e RawSession düğümü olarak kaydeder.
        Sprint 2'de bu düğümler işlenerek Concept ağına dönüştürülecek.
        """
        async with self.neo4j.session() as session:
            await session.run(
                """
                MERGE (rs:RawSession {session_id: $session_id})
                ON CREATE SET
                    rs.platform     = $platform,
                    rs.url          = $url,
                    rs.timestamp    = $timestamp,
                    rs.question     = $question,
                    rs.answer       = $answer,
                    rs.processed    = false,
                    rs.created_at   = datetime()
                ON MATCH SET
                    rs.updated_at   = datetime()
                """,
                session_id=request.session_id,
                platform=request.platform,
                url=request.url,
                timestamp=request.timestamp.isoformat(),
                question=request.data.question,
                answer=request.data.answer,
            )
        logger.debug(f"[Ingest] RawSession Neo4j'e yazıldı: {request.session_id}")
