import os
from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from .config import CHROMA_ROOT, EMBEDDING_MODEL_NAME

load_dotenv()

_embedding_model = None

def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)
    return _embedding_model


def _persist_dir(notebook_id: str) -> str:
    path = os.path.join(CHROMA_ROOT, notebook_id)
    os.makedirs(path, exist_ok=True)
    return path


def get_store(notebook_id: str) -> Chroma:
    return Chroma(
        persist_directory=_persist_dir(notebook_id),
        embedding_function=get_embedding_model(),
    )


def add_documents(notebook_id: str, chunks):
    store = get_store(notebook_id)
    if chunks:
        store.add_documents(chunks)
    return store


def sample_documents(notebook_id: str, k: int = 8):
    from langchain_core.documents import Document

    store = get_store(notebook_id)
    try:
        raw = store._collection.get(limit=k, include=["documents", "metadatas"])
        docs = raw.get("documents") or []
        metas = raw.get("metadatas") or [{}] * len(docs)
        if docs:
            return [Document(page_content=d, metadata=m or {}) for d, m in zip(docs, metas)]
    except Exception:
        pass

    try:
        return store.similarity_search("summary overview main topics", k=k)
    except Exception:
        return []


def delete_source_embeddings(notebook_id: str, source_id: str):
    store = get_store(notebook_id)
    try:
        store.delete(where={"source_id": source_id})
    except Exception:
        pass
