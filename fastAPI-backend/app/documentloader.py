import os

from langchain_community.document_loaders import (
    CSVLoader,
    Docx2txtLoader,
    TextLoader,
    UnstructuredPowerPointLoader,
    PyPDFLoader
)

from .chunking import chunk_csv, chunk_pdf_txt, chunk_ppt


def load_text_file(path: str):
    return TextLoader(path, encoding="utf-8").load()


def load_pdf_file(path: str):
    return PyPDFLoader(path).load()


def load_csv_file(path: str):
    return CSVLoader(file_path=path, encoding="utf-8").load()


def load_ppt_file(path: str):
    return UnstructuredPowerPointLoader(path).load()


def load_docx_file(path: str):
    return Docx2txtLoader(path).load()


def load_and_chunk(path: str, filename: str, source_id: str):
    """
    Load a file from disk, split it into retrieval-sized chunks, and stamp
    every chunk with source_id / filename metadata so answers can be traced
    back to the exact uploaded file (this is what powers citations).
    """
    ext = os.path.splitext(path)[1].lower()

    if ext == ".pdf":
        chunks = chunk_pdf_txt(load_pdf_file(path))
    elif ext == ".csv":
        chunks = chunk_csv(load_csv_file(path))
    elif ext in (".ppt", ".pptx"):
        chunks = chunk_ppt(load_ppt_file(path))
    elif ext == ".txt":
        chunks = chunk_pdf_txt(load_text_file(path))
    elif ext == ".docx":
        chunks = chunk_pdf_txt(load_docx_file(path))
    else:
        raise ValueError(f"Unsupported file type: {ext or '(none)'}")

    for chunk in chunks:
        chunk.metadata["source_id"] = source_id
        chunk.metadata["filename"] = filename

    return chunks
