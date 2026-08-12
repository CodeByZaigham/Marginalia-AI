import os
import shutil
import uuid

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from . import db
from .config import BASE_DIR, CHROMA_ROOT, SUPPORTED_EXTENSIONS, UPLOAD_DIR
from .documentloader import load_and_chunk
from .embeddings import add_documents, delete_source_embeddings, sample_documents
from .llm import ask, condense_question, generate_overview, generate_suggested_questions
from .retrievers import retrieve
from .schemas import ChatRequest, NoteCreate, NotebookCreate, NotebookRename

app = FastAPI(title="Notebook RAG Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db.init_db()

@app.get("/api/health")
def api_health():
    return {"status": "ok"}