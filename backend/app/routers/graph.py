from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any

from app.services.graph_service import GraphService
from app.services.learning_goal_service import LearningGoalService
from app.db.neo4j_client import get_neo4j_driver
from app.db.qdrant_client import get_qdrant_client
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1", tags=["Graph"])

async def get_graph_service() -> GraphService:
    neo4j = await get_neo4j_driver()
    qdrant = await get_qdrant_client()
    return GraphService(neo4j_driver=neo4j, qdrant_client=qdrant)

async def get_learning_goal_service() -> LearningGoalService:
    neo4j = await get_neo4j_driver()
    return LearningGoalService(neo4j_driver=neo4j)

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

@router.get(
    "/quiz/history",
    summary="Quiz Gecmisi",
    description="Kullanicinin gecmiste cozdugu quizlerin listesini (en yeniden eskiye) dondurur.",
)
async def get_quiz_history(
    limit: int = 50,
    concept: str | None = None,
    service: GraphService = Depends(get_graph_service),
):
    history = await service.get_quiz_history(limit=limit, concept=concept)
    return {"history": history, "total": len(history)}

class ImportPayload(BaseModel):
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]

@router.post(
    "/graph/import",
    summary="Grafiği İçe Aktar",
    description="JSON yedeğinden gelen düğüm ve ilişkileri Neo4j'ye yazar."
)
async def import_graph_endpoint(
    payload: ImportPayload,
    service: GraphService = Depends(get_graph_service),
):
    await service.import_graph_data(payload.model_dump())
    return {"status": "success", "imported_nodes": len(payload.nodes)}

@router.get(
    "/clusters",
    summary="Konu Kümeleri",
    description=(
        "Kavramları topic bazında gruplar. Her kümenin ortalama hatırlama oranı "
        "ve sağlık durumu (strong/warning/critical) döndürülür. "
        "Harita büyüdüğünde okunabilirlik için frontend kümeleme yapabilir."
    ),
)
async def get_clusters(
    service: GraphService = Depends(get_graph_service),
):
    """Topic bazlı kavram kümeleri ve her kümenin FSRS sağlık durumu."""
    return await service.get_topic_clusters()

@router.get(
    "/learning-path",
    summary="Hedef kavrama giden öğrenme yolu",
    description=(
        "Mevcut sağlam (fsrs_p yüksek) kavramlardan hedef kavrama en kısa "
        "RELATED_TO rotasını (Neo4j shortestPath) bulur; rotadaki zayıf "
        "duraklari isaretler."
    ),
)
async def get_learning_path(
    target: str,
    max_hops: int = 6,
    service: GraphService = Depends(get_graph_service),
):
    """target bir sorgu parametresi (?target=...) — kavram isimlerinde '/' olabildiği için path param kullanılmaz."""
    result = await service.get_learning_path(target, max_hops=max_hops)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Concept '{target}' bulunamadi.")
    return result

class LearningGoalRequest(BaseModel):
    goal: str

@router.post(
    "/learning-goal",
    summary="Serbest metin öğrenme hedefi çözümle",
    description=(
        "Kullanıcının haritada henüz olmayan bir hedefi (örn. 'Büyük Dil Modelleri (LLM)') "
        "serbest metinle girmesini sağlar. Hedef zaten haritada varsa mevcut shortestPath "
        "akışına (LLM'siz) devreder; yoksa LLM ile genel önkoşulları bulur ve kullanıcının "
        "kendi haritasındaki karşılıklarının sağlık durumunu kontrol eder."
    ),
)
async def resolve_learning_goal(
    payload: LearningGoalRequest,
    graph_service: GraphService = Depends(get_graph_service),
    goal_service: LearningGoalService = Depends(get_learning_goal_service),
):
    goal = payload.goal.strip()
    if not goal:
        raise HTTPException(status_code=422, detail="goal bos olamaz.")

    resolved = await goal_service.resolve_goal(goal)
    if resolved["in_graph"]:
        path = await graph_service.get_learning_path(resolved["target"])
        return {"in_graph": True, **(path or {"found": False, "target": resolved["target"]})}
    return resolved

@router.delete("/graph/clear", summary="Tüm Veritabanını Sıfırla")
async def clear_database(
    neo4j_driver = Depends(get_neo4j_driver),
    qdrant_client = Depends(get_qdrant_client)
):
    """Tüm zihin haritasını, kaynakları ve geçmişi veritabanından ve vektör uzayından tamamen siler."""
    # 1. Neo4j (Kavramlar ve İlişkiler) Temizliği
    async with neo4j_driver.session() as session:
        await session.run("MATCH (n) DETACH DELETE n")
    
    # 2. Qdrant (Vektörler) Temizliği (Hayalet quiz çeldiricilerini engeller)
    if qdrant_client:
        settings = get_settings()
        from qdrant_client.models import Filter
        try:
            await qdrant_client.delete(
                collection_name=settings.QDRANT_COLLECTION_NAME,
                points_selector=Filter() 
            )
        except Exception as e:
            logger.warning(f"Qdrant temizlenemedi: {e}")
            
    return {"status": "success", "message": "Sistem başarıyla fabrika ayarlarına döndürüldü."}