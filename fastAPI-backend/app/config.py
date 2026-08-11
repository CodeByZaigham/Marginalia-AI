import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # backend/

DATA_DIR = os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "data"))
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
CHROMA_ROOT = os.path.join(DATA_DIR, "chroma-db")
DB_PATH = os.path.join(DATA_DIR, "app.db")

EMBEDDING_MODEL_NAME = os.environ.get(
    "EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2"
)
CHAT_MODEL_NAME = os.environ.get("CHAT_MODEL_NAME", "mistral-medium-latest")

MAX_HISTORY_TURNS = 6 
RETRIEVAL_K = 8

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".csv", ".ppt", ".pptx", ".docx"}

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(CHROMA_ROOT, exist_ok=True)
