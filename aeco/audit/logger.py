import uuid
from typing import Any, Optional

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
        workflow_run_id: Optional[uuid.UUID] = None,
        task_id: Optional[uuid.UUID] = None,
        llm_provider: Optional[str] = None,
        llm_model: Optional[str] = None,
        tokens_used: Optional[int] = None,
        duration_ms: Optional[int] = None,
        success: bool = True,
        error_message: Optional[str] = None,
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
