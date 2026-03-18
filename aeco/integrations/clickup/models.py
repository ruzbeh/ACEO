from typing import List, Optional

from pydantic import BaseModel, field_validator


class ClickUpTask(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    status: Optional[str] = None

    @field_validator("status", mode="before")
    @classmethod
    def normalize_status(cls, v: object) -> Optional[str]:
        if v is None:
            return None
        if isinstance(v, str):
            return v.strip() or None
        if isinstance(v, dict):
            return (v.get("status") or "").strip() or None
        return str(v) if v else None
    assignees: List[dict] = []
    tags: List[dict] = []
    url: Optional[str] = None


class ClickUpComment(BaseModel):
    id: str
    comment_text: str
    user: Optional[dict] = None
    date: Optional[str] = None
