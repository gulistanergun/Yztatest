from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.services.graph_service import GraphService
from app.db.neo4j_client import get_neo4j_driver
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1", tags=["Graph"])


from app.db.qdrant_client import get_qdrant_client

async def get_graph_service() -> GraphService:
    neo4j = await get_neo4j_driver()
    qdrant = await get_qdrant_client()
    return GraphService(neo4j_driver=neo4j, qdrant_client=qdrant)


@router.get(
    "/graph",
    summary="Zihin Haritasini getir",
    description="Neo4j'deki tum Concept node ve iliskilerini React frontend icin JSON olarak doner.",
)
async def get_graph(
    service: GraphService = Depends(get_graph_service),
):
    """React force-graph'in kullanacagi node/edge formati."""
    return await service.get_graph_data()


@router.get(
    "/sources",
    summary="NotebookLM Sidebar Kaynakları",
    description="Öğrenme kaynaklarını (YouTube, ChatGPT oturumları) listeler.",
)
async def get_sources(
    service: GraphService = Depends(get_graph_service),
):
    """Sol panelde listelenecek kaynaklar."""
    return await service.get_sources()


@router.post(
    "/graph/process",
    summary="Bekleyen oturumlari isle",
    description="processed=false olan RawSession'lari LangChain Agent ile Concept node'larina cevir.",
)
async def process_sessions(
    batch_size: int = 10,
    service: GraphService = Depends(get_graph_service),
):
    """Manuel tetikleme endpoint'i. Sprint 3'te APScheduler ile otomatik hale gelecek."""
    stats = await service.process_pending_sessions(batch_size=batch_size)
    return {"status": "done", "stats": stats}

@router.delete(
    "/sources/{session_id}",
    summary="Öğrenme Kaynağını Sil",
    description="Bir oturumu ve ona bağlı (öksüz kalan) kavramları tamamen siler."
)
async def delete_source(
    session_id: str,
    service: GraphService = Depends(get_graph_service),
):
    await service.delete_session(session_id)
    return {"status": "deleted", "session_id": session_id}


class QuizSubmitPayload(BaseModel):
    concept_name: str
    score: float


@router.post(
    "/quiz/submit",
    summary="Quiz Sonucunu Gonder",
    description="Kullanicinin cozdugu quizin sonucuna gore FSRS parametrelerini (Stabilite/Zorluk) gunceller."
)
async def submit_quiz_result(
    payload: QuizSubmitPayload,
    service: GraphService = Depends(get_graph_service),
):
    return await service.update_concept_after_quiz(
        concept_name=payload.concept_name,
        score=payload.score
    )
