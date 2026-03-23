"""Tests for scheduler engine, cron parsing, and metric triggers."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from aeco.scheduler.engine import SchedulerEngine, next_cron_time, _parse_cron_field
from aeco.scheduler.triggers import MetricTrigger, TriggerEngine


class TestCronParsing:
    """Test cron expression parsing."""

    def test_parse_star(self) -> None:
        result = _parse_cron_field("*", 0, 59)
        assert result == set(range(0, 60))

    def test_parse_single(self) -> None:
        result = _parse_cron_field("5", 0, 59)
        assert result == {5}

    def test_parse_range(self) -> None:
        result = _parse_cron_field("1-5", 0, 59)
        assert result == {1, 2, 3, 4, 5}

    def test_parse_step(self) -> None:
        result = _parse_cron_field("*/15", 0, 59)
        assert result == {0, 15, 30, 45}

    def test_parse_comma_list(self) -> None:
        result = _parse_cron_field("1,3,5", 0, 59)
        assert result == {1, 3, 5}

    def test_next_cron_time_hourly(self) -> None:
        after = datetime(2026, 3, 21, 10, 30, 0, tzinfo=timezone.utc)
        next_time = next_cron_time("0 * * * *", after)
        assert next_time.hour == 11
        assert next_time.minute == 0

    def test_next_cron_time_daily_9am(self) -> None:
        after = datetime(2026, 3, 21, 10, 0, 0, tzinfo=timezone.utc)
        next_time = next_cron_time("0 9 * * *", after)
        assert next_time.day == 22
        assert next_time.hour == 9
        assert next_time.minute == 0

    def test_next_cron_time_every_5_min(self) -> None:
        after = datetime(2026, 3, 21, 10, 2, 0, tzinfo=timezone.utc)
        next_time = next_cron_time("*/5 * * * *", after)
        assert next_time.minute == 5

    def test_invalid_cron_raises(self) -> None:
        with pytest.raises(ValueError):
            next_cron_time("0 0 *", None)


class TestSchedulerEngine:
    """Test the scheduler engine job management."""

    def test_add_and_list_jobs(self) -> None:
        scheduler = SchedulerEngine()

        async def dummy():
            pass

        job = scheduler.add_job("test", "0 * * * *", dummy)
        assert job.name == "test"
        jobs = scheduler.list_jobs()
        assert len(jobs) == 1
        assert jobs[0]["name"] == "test"
        assert jobs[0]["next_run_at"] is not None

    def test_remove_job(self) -> None:
        scheduler = SchedulerEngine()

        async def dummy():
            pass

        job = scheduler.add_job("test", "0 * * * *", dummy)
        assert scheduler.remove_job(job.job_id)
        assert len(scheduler.list_jobs()) == 0

    def test_remove_nonexistent_returns_false(self) -> None:
        scheduler = SchedulerEngine()
        assert not scheduler.remove_job("nonexistent")

    def test_pause_and_resume(self) -> None:
        scheduler = SchedulerEngine()

        async def dummy():
            pass

        job = scheduler.add_job("test", "0 * * * *", dummy)
        scheduler.pause_job(job.job_id)
        assert not scheduler.get_job(job.job_id).is_active

        scheduler.resume_job(job.job_id)
        assert scheduler.get_job(job.job_id).is_active


class TestMetricTrigger:
    """Test metric trigger evaluation."""

    def test_trigger_fires_when_above_threshold(self) -> None:
        trigger = MetricTrigger(
            trigger_id="t1",
            name="High churn",
            metric_source="stripe",
            metric_name="churn_rate",
            comparison="gt",
            threshold=5.0,
        )
        assert trigger.evaluate(6.0)
        assert not trigger.evaluate(4.0)

    def test_trigger_fires_when_below_threshold(self) -> None:
        trigger = MetricTrigger(
            trigger_id="t2",
            name="Low MRR",
            metric_source="stripe",
            metric_name="mrr",
            comparison="lt",
            threshold=1000.0,
        )
        assert trigger.evaluate(500.0)
        assert not trigger.evaluate(1500.0)

    def test_cooldown_prevents_rapid_fire(self) -> None:
        trigger = MetricTrigger(
            trigger_id="t3",
            name="Test",
            metric_source="test",
            metric_name="val",
            comparison="gt",
            threshold=5.0,
            cooldown_minutes=60,
        )
        assert trigger.evaluate(10.0)
        trigger.fire()
        # Should not fire again due to cooldown
        assert not trigger.evaluate(10.0)

    def test_fire_returns_action(self) -> None:
        trigger = MetricTrigger(
            trigger_id="t4",
            name="Test",
            metric_source="test",
            metric_name="val",
            comparison="gt",
            threshold=5.0,
            action_args={"goals": ["Fix it"]},
        )
        trigger.evaluate(10.0)
        action = trigger.fire()
        assert action["trigger_name"] == "Test"
        assert action["action_args"]["goals"] == ["Fix it"]

    def test_inactive_trigger_does_not_fire(self) -> None:
        trigger = MetricTrigger(
            trigger_id="t5",
            name="Test",
            metric_source="test",
            metric_name="val",
            comparison="gt",
            threshold=5.0,
        )
        trigger.is_active = False
        assert not trigger.evaluate(10.0)


class TestTriggerEngine:
    """Test the trigger engine."""

    def test_add_and_list(self) -> None:
        engine = TriggerEngine()
        trigger = MetricTrigger(
            trigger_id="t1",
            name="Test",
            metric_source="test",
            metric_name="val",
            comparison="gt",
            threshold=5.0,
        )
        engine.add_trigger(trigger)
        assert len(engine.list_triggers()) == 1

    def test_remove(self) -> None:
        engine = TriggerEngine()
        trigger = MetricTrigger(
            trigger_id="t1",
            name="Test",
            metric_source="test",
            metric_name="val",
            comparison="gt",
            threshold=5.0,
        )
        engine.add_trigger(trigger)
        assert engine.remove_trigger("t1")
        assert len(engine.list_triggers()) == 0

    @pytest.mark.asyncio
    async def test_check_all_with_fetcher(self) -> None:
        engine = TriggerEngine()

        async def mock_fetcher(metric_name: str):
            return 10.0

        engine.register_fetcher("test", mock_fetcher)
        trigger = MetricTrigger(
            trigger_id="t1",
            name="Test",
            metric_source="test",
            metric_name="val",
            comparison="gt",
            threshold=5.0,
        )
        engine.add_trigger(trigger)

        fired = await engine.check_all()
        assert len(fired) == 1
        assert fired[0]["trigger_name"] == "Test"

    @pytest.mark.asyncio
    async def test_check_all_no_fire(self) -> None:
        engine = TriggerEngine()

        async def mock_fetcher(metric_name: str):
            return 3.0

        engine.register_fetcher("test", mock_fetcher)
        trigger = MetricTrigger(
            trigger_id="t1",
            name="Test",
            metric_source="test",
            metric_name="val",
            comparison="gt",
            threshold=5.0,
        )
        engine.add_trigger(trigger)

        fired = await engine.check_all()
        assert len(fired) == 0

    @pytest.mark.asyncio
    async def test_setup_default_triggers(self) -> None:
        engine = TriggerEngine()
        defaults = await engine.setup_default_triggers()
        assert len(defaults) == 4
        assert len(engine.list_triggers()) == 4
