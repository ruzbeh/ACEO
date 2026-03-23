"""Lightweight async scheduler for recurring portfolio cycles and metric checks.

Uses asyncio tasks + cron parsing instead of APScheduler to avoid extra deps.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)


def _parse_cron_field(field: str, min_val: int, max_val: int) -> set[int]:
    """Parse a single cron field into a set of matching values."""
    values: set[int] = set()
    for part in field.split(","):
        if "/" in part:
            base, step_str = part.split("/", 1)
            step = int(step_str)
            if base == "*":
                start = min_val
            else:
                start = int(base)
            values.update(range(start, max_val + 1, step))
        elif "-" in part:
            lo, hi = part.split("-", 1)
            values.update(range(int(lo), int(hi) + 1))
        elif part == "*":
            values.update(range(min_val, max_val + 1))
        else:
            values.add(int(part))
    return values


def next_cron_time(cron_expr: str, after: datetime | None = None) -> datetime:
    """Calculate the next datetime matching a 5-field cron expression.

    Fields: minute hour day-of-month month day-of-week (0=Sun or 7=Sun).
    """
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        raise ValueError(f"Expected 5 cron fields, got {len(parts)}: {cron_expr}")

    minutes = _parse_cron_field(parts[0], 0, 59)
    hours = _parse_cron_field(parts[1], 0, 23)
    days = _parse_cron_field(parts[2], 1, 31)
    months = _parse_cron_field(parts[3], 1, 12)
    dows = _parse_cron_field(parts[4], 0, 7)
    # Normalize Sunday: 7 → 0
    if 7 in dows:
        dows.discard(7)
        dows.add(0)

    now = after or datetime.now(timezone.utc)
    candidate = now.replace(second=0, microsecond=0) + timedelta(minutes=1)

    # Search up to 366 days ahead
    for _ in range(366 * 24 * 60):
        if (
            candidate.month in months
            and candidate.day in days
            and candidate.weekday() in _iso_to_cron_dow(dows)
            and candidate.hour in hours
            and candidate.minute in minutes
        ):
            return candidate
        candidate += timedelta(minutes=1)

    raise ValueError(f"No matching time found within 366 days for: {cron_expr}")


def _iso_to_cron_dow(cron_dows: set[int]) -> set[int]:
    """Convert cron day-of-week (0=Sun) to Python weekday (0=Mon)."""
    mapping = {0: 6, 1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5}
    result: set[int] = set()
    for d in cron_dows:
        if d in mapping:
            result.add(mapping[d])
    # If * (all 7 values present), return all
    if len(cron_dows) == 7:
        return set(range(7))
    return result


class ScheduledJob:
    """In-memory representation of a scheduled job."""

    def __init__(
        self,
        job_id: str,
        name: str,
        cron_expression: str,
        callback: Callable[..., Coroutine],
        callback_args: dict[str, Any] | None = None,
        is_active: bool = True,
    ):
        self.job_id = job_id
        self.name = name
        self.cron_expression = cron_expression
        self.callback = callback
        self.callback_args = callback_args or {}
        self.is_active = is_active
        self.next_run_at: datetime | None = None
        self.last_run_at: datetime | None = None
        self.last_result: str | None = None
        self.run_count: int = 0

    def compute_next_run(self, after: datetime | None = None) -> datetime:
        self.next_run_at = next_cron_time(self.cron_expression, after)
        return self.next_run_at

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "name": self.name,
            "cron_expression": self.cron_expression,
            "is_active": self.is_active,
            "next_run_at": self.next_run_at.isoformat() if self.next_run_at else None,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "last_result": self.last_result,
            "run_count": self.run_count,
        }


class SchedulerEngine:
    """Async scheduler that runs jobs on cron schedules."""

    def __init__(self):
        self._jobs: dict[str, ScheduledJob] = {}
        self._task: asyncio.Task | None = None
        self._running = False

    def add_job(
        self,
        name: str,
        cron_expression: str,
        callback: Callable[..., Coroutine],
        callback_args: dict[str, Any] | None = None,
        job_id: str | None = None,
    ) -> ScheduledJob:
        """Add a recurring job."""
        jid = job_id or str(uuid.uuid4())
        job = ScheduledJob(jid, name, cron_expression, callback, callback_args)
        job.compute_next_run()
        self._jobs[jid] = job
        logger.info(f"Scheduled job '{name}' ({jid}), next run: {job.next_run_at}")
        return job

    def remove_job(self, job_id: str) -> bool:
        if job_id in self._jobs:
            del self._jobs[job_id]
            logger.info(f"Removed job {job_id}")
            return True
        return False

    def pause_job(self, job_id: str) -> bool:
        if job_id in self._jobs:
            self._jobs[job_id].is_active = False
            return True
        return False

    def resume_job(self, job_id: str) -> bool:
        if job_id in self._jobs:
            self._jobs[job_id].is_active = True
            self._jobs[job_id].compute_next_run()
            return True
        return False

    def list_jobs(self) -> list[dict]:
        return [j.to_dict() for j in self._jobs.values()]

    def get_job(self, job_id: str) -> ScheduledJob | None:
        return self._jobs.get(job_id)

    async def start(self):
        """Start the scheduler loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Scheduler started")

    async def stop(self):
        """Stop the scheduler loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Scheduler stopped")

    async def _run_loop(self):
        """Main scheduler loop — checks every 30 seconds for due jobs."""
        while self._running:
            try:
                now = datetime.now(timezone.utc)
                for job in list(self._jobs.values()):
                    if not job.is_active or not job.next_run_at:
                        continue
                    if now >= job.next_run_at:
                        asyncio.create_task(self._execute_job(job))
                        job.last_run_at = now
                        job.run_count += 1
                        job.compute_next_run(after=now)
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
            await asyncio.sleep(30)

    async def _execute_job(self, job: ScheduledJob):
        """Execute a single job with error handling."""
        logger.info(f"Executing job '{job.name}' ({job.job_id})")
        try:
            result = await job.callback(**job.callback_args)
            job.last_result = str(result)[:500] if result else "ok"
            logger.info(f"Job '{job.name}' completed: {job.last_result[:100]}")
        except Exception as e:
            job.last_result = f"error: {e}"
            logger.error(f"Job '{job.name}' failed: {e}")
