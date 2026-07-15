from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from typing import Optional
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


# ---- Pydantic Model: LLM'in döneceği yapı ----
class ExtractedConcept(BaseModel):
    name: str = Field(description="Kavramın kısa, net adı. Örn: 'Async/Await', 'LSTM', 'Docker'")
    topic: str = Field(description="Üst konu/alan. Örn: 'Python', 'Derin Öğrenme', 'DevOps'")
    difficulty: str = Field(description="Zorluk seviyesi: 'baslangic', 'orta', 'ileri'")
    related_to: list[str] = Field(description="Bu kavramla ilişkili diğer kavramlar. Maks 3 adet.")


class ExtractionResult(BaseModel):
    concepts: list[ExtractedConcept] = Field(description="Metinden çıkarılan kavramlar listesi")
    main_topic: str = Field(description="Konuşmanın ana konusu/alanı")
    is_educational: bool = Field(
        description="Bu konuşma öğrenme amaçlı mı? Günlük sohbet veya alakasız içerik ise False."
    )


EXTRACTION_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """Sen bir öğrenme ve verimlilik asistanının yapay zeka beynisin.
Sana bir kullanıcı-LLM konuşması veya izlenen video/sayfa içeriği verecekler. Görevin bu içerikten öğrenilen veya bahsedilen "teknik kavramları, araçları ve teknolojileri" çıkarmak.

KURALLAR:
- Sadece gerçekten teknik, eğitimsel veya üretkenlik (Miro, Trello, Notion vb.) ile ilgili araç ve kavramları çıkar.
- "Merhaba", "nasılsın", "teşekkürler" gibi günlük konuşmalar veya tamamen ilgisiz içeriklerde is_educational=false döndür.
- Kavram adları kısa ve kesin olmalı (örn: "Pandas", "Miro", "Docker", "Agile").
- ÇOK ÖNEMLİ (BAĞLANTILAR): Eğer bir alt dal veya kütüphaneden bahsediliyorsa (Örn: Pandas, Numpy), `related_to` listesine KESİNLİKLE onun ana veya üst teknolojisini (Örn: Python) eklemelisin! Hiyerarşik ve mantıksal ağlar (Node-Edge) kuruyorsun.
- Türkçe konuşmalardan da orijinal (genellikle İngilizce) araç/kavram adları çıkar (Örn: "python'da dizi" -> "Array").

Yanıtını SADECE aşağıdaki JSON formatında ver, başka hiçbir şey yazma:
{{
  "concepts": [
    {{
      "name": "kavram_adı",
      "topic": "üst_konu",
      "difficulty": "baslangic|orta|ileri",
      "related_to": ["ana_teknoloji", "ilişkili_kavram"]
    }}
  ],
  "main_topic": "ana_konu",
  "is_educational": true
}}""",
    ),
    (
        "human",
        "Platform: {platform}\n\nKullanıcı Sorusu/Konusu:\n{question}\n\nİçerik (ilk 800 karakter):\n{answer}",
    ),
])


class ConceptExtractor:
    """
    RawSession düğümlerinden teknik kavramları çıkarır.
    Sprint 2'nin kalbi.
    """

    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-3.5-flash",
            temperature=0,
            api_key=settings.GOOGLE_API_KEY,
        )
        self.parser = JsonOutputParser(pydantic_object=ExtractionResult)
        self.chain = EXTRACTION_PROMPT | self.llm | self.parser

    async def extract(
        self,
        platform: str,
        question: str,
        answer: str,
    ) -> Optional[ExtractionResult]:
        """
        Bir soru-cevap çiftinden kavramları çıkarır.
        Eğitimsel değilse None döner.
        """
        try:
            result: dict = await self.chain.ainvoke({
                "platform": platform,
                "question": question[:500],   # Token tasarrufu
                "answer": answer[:800],
            })

            extraction = ExtractionResult(**result)

            if not extraction.is_educational:
                logger.debug(f"[Extractor] Egitimsel degil, atlandi: {question[:60]}")
                return None

            logger.info(
                f"[Extractor] {len(extraction.concepts)} kavram bulundu | "
                f"Ana konu: {extraction.main_topic}"
            )
            return extraction

        except Exception as e:
            logger.error(f"[Extractor] LLM hatasi: {e}", exc_info=True)
            return None
