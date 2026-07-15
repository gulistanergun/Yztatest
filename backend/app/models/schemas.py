from pydantic import BaseModel, Field
from typing import Literal
from datetime import datetime


class MessagePair(BaseModel):
    """Kullanıcının sorduğu soru ve LLM'in verdiği cevap çifti."""
    question: str = Field(..., min_length=1, description="Kullanıcının sorusu")
    answer: str = Field(..., min_length=1, description="LLM'in cevabı")


class IngestRequest(BaseModel):
    """Chrome Extension'dan gelen ham veri modeli."""
    platform: Literal["ChatGPT", "Gemini", "YouTube", "Web"] = Field(..., description="Verinin geldiği platform (Web = sağ tık menüsüyle kaydedilen seçim)")
    url: str = Field(..., description="Konuşmanın yapıldığı URL")
    timestamp: datetime = Field(..., description="ISO 8601 formatında zaman damgası")
    session_id: str = Field(..., description="Tarayıcı oturum ID'si")
    data: MessagePair


class IngestResponse(BaseModel):
    """Başarılı ingest işleminin döndürdüğü yanıt."""
    status: Literal["success", "skipped"] = "success"
    message: str
    session_id: str


class HealthResponse(BaseModel):
    """Sağlık kontrolü endpoint'inin döndürdüğü yanıt."""
    status: str
    version: str
    neo4j: bool
    qdrant: bool
