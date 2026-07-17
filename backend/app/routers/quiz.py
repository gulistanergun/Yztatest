from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.services.quiz_service import QuizService
from app.db.neo4j_client import get_neo4j_driver
from app.db.qdrant_client import get_qdrant_client
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/quiz", tags=["Quiz"])


async def get_quiz_service() -> QuizService:
    neo4j = await get_neo4j_driver()
    qdrant = await get_qdrant_client()
    return QuizService(neo4j_driver=neo4j, qdrant_client=qdrant)


class QuizGenerateRequest(BaseModel):
    concept_name: Optional[str] = Field(
        default=None,
        description="Quiz üretilecek kavram. Boş bırakılırsa fsrs_p'si en düşük (unutulmak üzere olan) kavram otomatik seçilir.",
    )
    num_questions: int = Field(default=4, ge=3, le=5, description="Soru sayısı (3-5)")
    force_new: bool = Field(
        default=False,
        description="True ise soru bankası atlanır ve LLM ile taze soru üretilir.",
    )


@router.post(
    "/generate",
    summary="Quiz Sorusu Üret",
    description=(
        "Kavramın kendi kaynaklarından (Neo4j) + anlamsal komşu içeriklerden (Qdrant RAG) "
        "LLM ile çoktan seçmeli quiz üretir. Çeldiriciler embedding uzayındaki yakın kavramlardan seçilir. "
        "concept_name verilmezse FSRS'e göre en riskli kavram hedeflenir. "
        "Skor, mevcut POST /api/v1/quiz/submit ile gönderilir."
    ),
)
async def generate_quiz(
    payload: QuizGenerateRequest,
    service: QuizService = Depends(get_quiz_service),
):
    result = await service.generate_quiz(
        concept_name=payload.concept_name,
        num_questions=payload.num_questions,
        force_new=payload.force_new,
    )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Concept '{payload.concept_name}' bulunamadı."
            if payload.concept_name
            else "Quiz üretilecek kavram yok (harita boş).",
        )
    if result.get("error") == "no_sources":
        raise HTTPException(
            status_code=422,
            detail=f"'{result['concept']}' için kaynak içerik yok; quiz üretilemedi.",
        )
    if result.get("error") == "generation_failed":
        raise HTTPException(
            status_code=502,
            detail=f"'{result['concept']}' için soru üretimi başarısız oldu, tekrar deneyin.",
        )
    return result


@router.get(
    "/recommendations",
    summary="Quiz Önerileri (Riskli Kavramlar)",
    description="FSRS fsrs_p değeri en düşük (unutulmak üzere olan) kavramları döner. Frontend 'günün quizi' önerisi için.",
)
async def quiz_recommendations(
    limit: int = 5,
    service: QuizService = Depends(get_quiz_service),
):
    concepts = await service.get_weak_concepts(limit=max(1, min(20, limit)))
    return {"concepts": concepts, "total": len(concepts)}
