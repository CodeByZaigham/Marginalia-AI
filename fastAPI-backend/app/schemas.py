from pydantic import BaseModel, Field


class NotebookCreate(BaseModel):
    name: str = Field(default="Untitled notebook", max_length=200)


class NotebookRename(BaseModel):
    name: str = Field(max_length=200)


class ChatRequest(BaseModel):
    message: str


class NoteCreate(BaseModel):
    title: str = Field(default="Untitled note", max_length=200)
    content: str
