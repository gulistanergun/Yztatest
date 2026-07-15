from functools import lru_cache
from langchain_huggingface import HuggingFaceEmbeddings


@lru_cache()
def get_local_embeddings() -> HuggingFaceEmbeddings:
    """
    Yerel (Offline) embedding modeli — Privacy First.
    all-MiniLM-L6-v2: 384 boyut, Qdrant koleksiyonuyla ayni.
    lru_cache sayesinde model surece bir kez yuklenir; hem ingest
    hem chat ayni instance'i paylasir.
    """
    return HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
