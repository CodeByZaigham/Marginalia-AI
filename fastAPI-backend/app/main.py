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

app = FastAPI(title="Marginalia Notebook")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db.init_db()

@app.get("/api/notebooks")
def api_list_notebooks():
    return db.list_notebooks()


@app.post("/api/notebooks")
def api_create_notebook(payload: NotebookCreate):
    notebook_id = uuid.uuid4().hex
    db.create_notebook(notebook_id, payload.name.strip() or "Untitled notebook")
    return db.get_notebook(notebook_id)


@app.get("/api/notebooks/{notebook_id}")
def api_get_notebook(notebook_id: str):
    nb = db.get_notebook(notebook_id)
    if not nb:
        raise HTTPException(404, "Notebook not found")
    nb["sources"] = db.list_sources(notebook_id)
    return nb


@app.patch("/api/notebooks/{notebook_id}")
def api_rename_notebook(notebook_id: str, payload: NotebookRename):
    if not db.get_notebook(notebook_id):
        raise HTTPException(404, "Notebook not found")
    db.rename_notebook(notebook_id, payload.name.strip() or "Untitled notebook")
    return db.get_notebook(notebook_id)


@app.delete("/api/notebooks/{notebook_id}")
def api_delete_notebook(notebook_id: str):
    if not db.get_notebook(notebook_id):
        raise HTTPException(404, "Notebook not found")
    db.delete_notebook(notebook_id)
    shutil.rmtree(os.path.join(CHROMA_ROOT, notebook_id), ignore_errors=True)
    shutil.rmtree(os.path.join(UPLOAD_DIR, notebook_id), ignore_errors=True)
    return {"status": "deleted"}

@app.post("/api/notebooks/{notebook_id}/sources")
def api_upload_sources(notebook_id: str, files: list[UploadFile] = File(...)):
    if not db.get_notebook(notebook_id):
        raise HTTPException(404, "Notebook not found")

    notebook_upload_dir = os.path.join(UPLOAD_DIR, notebook_id)
    os.makedirs(notebook_upload_dir, exist_ok=True)

    results = []
    for f in files:
        ext = os.path.splitext(f.filename or "")[1].lower()
        source_id = uuid.uuid4().hex

        if ext not in SUPPORTED_EXTENSIONS:
            db.create_source(source_id, notebook_id, f.filename or "unnamed", ext, "failed",
                              error=f"Unsupported file type '{ext}'")
            results.append({"id": source_id, "filename": f.filename, "status": "failed",
                             "error": f"Unsupported file type '{ext}'"})
            continue

        dest_path = os.path.join(notebook_upload_dir, f"{source_id}{ext}")
        with open(dest_path, "wb") as out:
            shutil.copyfileobj(f.file, out)

        try:
            chunks = load_and_chunk(dest_path, f.filename or source_id, source_id)
            add_documents(notebook_id, chunks)
        except Exception as e:
            db.create_source(source_id, notebook_id, f.filename or "unnamed", ext, "failed",
                              error=str(e))
            results.append({"id": source_id, "filename": f.filename, "status": "failed", "error": str(e)})
            continue

        db.create_source(source_id, notebook_id, f.filename or "unnamed", ext, "ready",
                          num_chunks=len(chunks))
        results.append({"id": source_id, "filename": f.filename, "status": "ready",
                         "num_chunks": len(chunks)})

    try:
        sample = sample_documents(notebook_id, k=8)
        if sample:
            db.set_overview(notebook_id, generate_overview(sample))
            db.set_suggested_questions(notebook_id, generate_suggested_questions(sample))
    except Exception:
        pass

    return {"sources": results}


@app.get("/api/notebooks/{notebook_id}/sources")
def api_list_sources(notebook_id: str):
    if not db.get_notebook(notebook_id):
        raise HTTPException(404, "Notebook not found")
    return db.list_sources(notebook_id)


@app.delete("/api/notebooks/{notebook_id}/sources/{source_id}")
def api_delete_source(notebook_id: str, source_id: str):
    if not db.get_source(source_id):
        raise HTTPException(404, "Source not found")
    delete_source_embeddings(notebook_id, source_id)
    db.delete_source(source_id)
    return {"status": "deleted"}

@app.get("/api/notebooks/{notebook_id}/chat")
def api_get_history(notebook_id: str):
    if not db.get_notebook(notebook_id):
        raise HTTPException(404, "Notebook not found")
    return db.list_messages(notebook_id)


@app.delete("/api/notebooks/{notebook_id}/chat")
def api_clear_history(notebook_id: str):
    if not db.get_notebook(notebook_id):
        raise HTTPException(404, "Notebook not found")
    db.clear_messages(notebook_id)
    return {"status": "cleared"}


@app.post("/api/notebooks/{notebook_id}/chat")
def api_chat(notebook_id: str, payload: ChatRequest):
    if not db.get_notebook(notebook_id):
        raise HTTPException(404, "Notebook not found")

    query = payload.message.strip()
    if not query:
        raise HTTPException(400, "Message cannot be empty.")

    sources = db.list_sources(notebook_id)
    if not any(s["status"] == "ready" for s in sources):
        raise HTTPException(400, "Add at least one source before chatting.")

    history = db.list_messages(notebook_id)

    standalone_query = condense_question(query, history)
    docs = retrieve(notebook_id, standalone_query)
    answer, citations = ask(query, docs, history)

    db.add_message(notebook_id, "user", query)
    db.add_message(notebook_id, "assistant", answer, citations)

    return {"answer": answer, "citations": citations}

@app.get("/api/notebooks/{notebook_id}/notes")
def api_list_notes(notebook_id: str):
    if not db.get_notebook(notebook_id):
        raise HTTPException(404, "Notebook not found")
    return db.list_notes(notebook_id)


@app.post("/api/notebooks/{notebook_id}/notes")
def api_create_note(notebook_id: str, payload: NoteCreate):
    if not db.get_notebook(notebook_id):
        raise HTTPException(404, "Notebook not found")
    note_id = db.create_note(notebook_id, payload.title.strip() or "Untitled note", payload.content)
    return db.get_note(note_id)


@app.delete("/api/notebooks/{notebook_id}/notes/{note_id}")
def api_delete_note(notebook_id: str, note_id: str):
    if not db.get_note(note_id):
        raise HTTPException(404, "Note not found")
    db.delete_note(note_id)
    return {"status": "deleted"}

@app.get("/api/health")
def api_health():
    return {"status": "ok"}