import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

from .config import DB_PATH


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS notebooks (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                overview TEXT,
                suggested_questions TEXT,
                created_at TEXT NOT NULL
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS sources (
                id TEXT PRIMARY KEY,
                notebook_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                filetype TEXT NOT NULL,
                status TEXT NOT NULL,
                num_chunks INTEGER DEFAULT 0,
                error TEXT,
                created_at TEXT NOT NULL
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                notebook_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                citations TEXT,
                created_at TEXT NOT NULL
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS notes (
                id TEXT PRIMARY KEY,
                notebook_id TEXT NOT NULL,
                title TEXT,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            )"""
        )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return uuid.uuid4().hex



def create_notebook(notebook_id: str, name: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO notebooks (id, name, created_at) VALUES (?, ?, ?)",
            (notebook_id, name, _now()),
        )


def _parse_notebook(row) -> dict:
    d = dict(row)
    d["suggested_questions"] = json.loads(d["suggested_questions"]) if d.get("suggested_questions") else []
    return d


def list_notebooks():
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT n.*,
                      (SELECT COUNT(*) FROM sources s WHERE s.notebook_id = n.id) AS source_count
               FROM notebooks n
               ORDER BY n.created_at DESC"""
        ).fetchall()
        return [_parse_notebook(r) for r in rows]


def get_notebook(notebook_id: str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM notebooks WHERE id = ?", (notebook_id,)
        ).fetchone()
        return _parse_notebook(row) if row else None


def rename_notebook(notebook_id: str, name: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE notebooks SET name = ? WHERE id = ?", (name, notebook_id)
        )


def set_overview(notebook_id: str, overview: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE notebooks SET overview = ? WHERE id = ?", (overview, notebook_id)
        )


def set_suggested_questions(notebook_id: str, questions: list):
    with get_conn() as conn:
        conn.execute(
            "UPDATE notebooks SET suggested_questions = ? WHERE id = ?",
            (json.dumps(questions), notebook_id),
        )


def delete_notebook(notebook_id: str):
    with get_conn() as conn:
        conn.execute("DELETE FROM notebooks WHERE id = ?", (notebook_id,))
        conn.execute("DELETE FROM sources WHERE notebook_id = ?", (notebook_id,))
        conn.execute("DELETE FROM messages WHERE notebook_id = ?", (notebook_id,))
        conn.execute("DELETE FROM notes WHERE notebook_id = ?", (notebook_id,))


def create_source(source_id, notebook_id, filename, filetype, status, num_chunks=0, error=None):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO sources
               (id, notebook_id, filename, filetype, status, num_chunks, error, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (source_id, notebook_id, filename, filetype, status, num_chunks, error, _now()),
        )


def list_sources(notebook_id: str):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM sources WHERE notebook_id = ? ORDER BY created_at",
            (notebook_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_source(source_id: str):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone()
        return dict(row) if row else None


def delete_source(source_id: str):
    with get_conn() as conn:
        conn.execute("DELETE FROM sources WHERE id = ?", (source_id,))


def add_message(notebook_id: str, role: str, content: str, citations=None):
    message_id = new_id()
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO messages (id, notebook_id, role, content, citations, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (message_id, notebook_id, role, content, json.dumps(citations or []), _now()),
        )
    return message_id


def list_messages(notebook_id: str):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM messages WHERE notebook_id = ? ORDER BY created_at",
            (notebook_id,),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["citations"] = json.loads(d["citations"]) if d["citations"] else []
            out.append(d)
        return out


def clear_messages(notebook_id: str):
    with get_conn() as conn:
        conn.execute("DELETE FROM messages WHERE notebook_id = ?", (notebook_id,))

def create_note(notebook_id: str, title: str, content: str):
    note_id = new_id()
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO notes (id, notebook_id, title, content, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (note_id, notebook_id, title, content, _now()),
        )
    return note_id


def get_note(note_id: str):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
        return dict(row) if row else None


def list_notes(notebook_id: str):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM notes WHERE notebook_id = ? ORDER BY created_at",
            (notebook_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def delete_note(note_id: str):
    with get_conn() as conn:
        conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
