from pydantic import BaseModel


class ClickUpTask(BaseModel):
    id: str
    name: str
    description: str | None = None
    status: str | None = None
    assignees: list[dict] = []
    tags: list[dict] = []
    url: str | None = None


class ClickUpComment(BaseModel):
    id: str
    comment_text: str
    user: dict | None = None
    date: str | None = None
