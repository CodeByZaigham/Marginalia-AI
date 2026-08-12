from dotenv import load_dotenv
from langchain_classic.retrievers.multi_query import MultiQueryRetriever
from langchain_mistralai import ChatMistralAI

from .config import CHAT_MODEL_NAME, RETRIEVAL_K
from .embeddings import get_store

load_dotenv()

_llm = None


def get_llm():
    global _llm
    if _llm is None:
        _llm = ChatMistralAI(model=CHAT_MODEL_NAME)
    return _llm


def retrieve(notebook_id: str, query: str, k: int = RETRIEVAL_K):
    store = get_store(notebook_id)

    retriever = store.as_retriever(
        search_type="mmr",
        search_kwargs={"k": k},
    )

    query_variations = MultiQueryRetriever.from_llm(
        llm=get_llm(),
        retriever=retriever,
    )

    return query_variations.invoke(query)
