import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from aeco.models.audit import AuditLogEntry


class AuditLogger:
    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    async def log(
        self,
        agent_id: str,
        action: str,
        input_summary: str = "",
        output_summary: str = "",
        workflow_run_id: uuid.UUID | None = None,
        task_id: uuid.UUID | None = None,
        llm_provider: str | None = None,
        llm_model: str | None = None,
        tokens_used: int | None = None,
        duration_ms: int | None = None,
        success: bool = True,
        error_message: str | None = None,
    ) -> AuditLogEntry:
        entry = AuditLogEntry(
            agent_id=agent_id,
            action=action,
            workflow_run_id=workflow_run_id,
            task_id=task_id,
            input_summary=input_summary[:2000],
            output_summary=output_summary[:2000],
            llm_provider=llm_provider,
            llm_model=llm_model,
            tokens_used=tokens_used,
            duration_ms=duration_ms,
            success=success,
            error_message=error_message,
        )
        async with self._session_factory() as session:
            session: AsyncSession
            session.add(entry)
            await session.commit()
            await session.refresh(entry)
        return entry
