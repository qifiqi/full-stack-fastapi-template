"""P2 worker/service unit tests (per-test SQLite, no HTTP stack)."""

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.core.workers import TaskManager
from app.models import GoogleSheet, ReturnSeriesPoint, ScheduledTask, Task, TaskResult
from app.services.config_manager import init_config_manager
from app.services.model_summary.extractor import extract_hot_columns_for_result


@pytest.fixture
def session_factory() -> Generator[Any]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=None,
    )
    SQLModel.metadata.create_all(engine)
    factory = Session

    def _factory() -> Session:
        return Session(engine, expire_on_commit=False)

    _factory.__name__ = "session_factory"  # for repr clarity
    init_config_manager(_factory)
    with _factory() as session:
        session.add(
            GoogleSheet(spreadsheet_id="SS-GOLDEN", name="golden", registry_scope="c_series")
        )
        session.commit()
    yield _factory
    engine.dispose()


def _make_task(factory: Any, **overrides: Any) -> Task:
    task = Task(
        name=overrides.get("name", "golden-task"),
        task_type=overrides.get("task_type", "google_sheet"),
        config=overrides.get("config", {"stock_code": "600000", "spreadsheet_id": "SS"}),
        status=overrides.get("status", "pending"),
        spreadsheet_id="SS",
        stock_code="600000",
        market_type="cn",
    )
    with factory() as session:
        session.add(task)
        session.commit()
        session.refresh(task)
        task_id = int(task.id or 0)
    task.id = task_id
    return task


# ---------------------------------------------------------------------------
# 领取互斥: two claimers, only one wins
# ---------------------------------------------------------------------------


def test_claim_mutex(session_factory: Any) -> None:
    task = _make_task(session_factory)
    manager_a = TaskManager(session_factory, instance_id="worker-a")
    manager_b = TaskManager(session_factory, instance_id="worker-b")

    with session_factory() as session:
        assert manager_a._claim_task(session, int(task.id)) is True
        # second claim on the same row must fail (status no longer pending)
        assert manager_b._claim_task(session, int(task.id)) is False

    with session_factory() as session:
        row = session.get(Task, int(task.id))
        assert row is not None
        assert row.status == "running"
        assert row.running_instance == "worker-a"
        assert row.heartbeat_at is not None
        assert row.started_at is not None


# ---------------------------------------------------------------------------
# stop_requested 桥接: poller bridges the DB flag into the stop Event
# ---------------------------------------------------------------------------


def test_stop_requested_bridge(session_factory: Any) -> None:
    task = _make_task(session_factory, status="running")
    manager = TaskManager(session_factory, instance_id="local")
    manager.bind(init_config_manager(session_factory))
    event = manager.task_stop_events.setdefault(int(task.id), __import__("threading").Event())

    with session_factory() as session:
        row = session.get(Task, int(task.id))
        assert row is not None
        row.running_instance = "local"
        row.stop_requested = True
        session.add(row)
        session.commit()

    assert not event.is_set()
    manager.poller_tick()
    assert event.is_set()


# ---------------------------------------------------------------------------
# 心跳超时 watchdog: attempt=N/3 protocol
# ---------------------------------------------------------------------------


def test_watchdog_resets_stale_heartbeat(session_factory: Any) -> None:
    task = _make_task(session_factory, status="running")
    manager = TaskManager(session_factory, instance_id="local")
    now = datetime.now(UTC)
    with session_factory() as session:
        row = session.get(Task, int(task.id))
        assert row is not None
        row.running_instance = "local"
        row.heartbeat_at = now - timedelta(minutes=30)
        session.add(row)
        session.commit()

    manager.watchdog_tick()

    with session_factory() as session:
        row = session.get(Task, int(task.id))
        assert row is not None
        assert row.status == "pending"
        assert row.running_instance is None
        assert "attempt=1/3" in (row.error_message or "")


def test_watchdog_abandons_after_max_attempts(session_factory: Any) -> None:
    task = _make_task(
        session_factory,
        status="running",
        config={"attempt_note": "watchdog 已放弃自动重启 (尝试 3 次) attempt=3/3 marker"},
    )
    manager = TaskManager(session_factory, instance_id="local")
    with session_factory() as session:
        row = session.get(Task, int(task.id))
        assert row is not None
        row.running_instance = "local"
        row.heartbeat_at = datetime.now(UTC) - timedelta(minutes=30)
        row.error_message = "watchdog marker attempt=3/3"
        session.add(row)
        session.commit()

    manager.watchdog_tick()

    with session_factory() as session:
        row = session.get(Task, int(task.id))
        assert row is not None
        assert row.status == "error"
        assert "watchdog 已放弃自动重启" in (row.error_message or "")


# ---------------------------------------------------------------------------
# 热列 golden: C3 sample result JSON -> hot columns + is_best flips
# ---------------------------------------------------------------------------

C3_SAMPLE_RESULT = {
    "I15": "12.50%",
    "I16": "28.10%",
    "I17": "-8.25%",
    "I18": "5.00%",
    "I19": "9.30%",
    "I20": "-12.00%",
    "I21": "1.20%",
    "I22": "0.35%",
    "I23": "230%",
}


def test_hot_column_golden_c3(session_factory: Any) -> None:
    task = _make_task(session_factory)
    from app.services.google_sheet_tasks.c3 import C3Service

    engine = C3Service(
        {"stock_code": "600000", "market_type": "cn", "stock_name": "浦发银行"},
        int(task.id),
        session_factory=session_factory,
        settings=None,
        stop_event=None,
    )
    parameters = {
        "stock_code": "600000",
        "stock_name": "浦发银行",
        "market_type": "cn",
        "year": "2020",
        "A1": "1.0",
        "B1": "0.5",
    }
    saved = engine._save_task_result(0, parameters, dict(C3_SAMPLE_RESULT), True)

    assert saved.stock_code == "600000.SS"
    assert saved.model_key == "default"
    assert saved.model_name == "C3"
    assert saved.best_metric_name == "ReturnBeats"
    # 12.50% - 5.00% = 7.5 percentage points -> 0.075
    assert saved.best_metric_value is not None
    assert abs(saved.best_metric_value - 0.075) < 1e-9
    assert saved.is_best is True
    assert saved.period_key == "full_2020"


def test_is_best_flips_to_better_result(session_factory: Any) -> None:
    task = _make_task(session_factory)
    from app.services.google_sheet_tasks.c3 import C3Service

    engine = C3Service(
        {"stock_code": "600000", "market_type": "cn"},
        int(task.id),
        session_factory=session_factory,
        settings=None,
        stop_event=None,
    )
    parameters = {"stock_code": "600000", "market_type": "cn"}
    first = engine._save_task_result(0, parameters, dict(C3_SAMPLE_RESULT), True)
    assert first.is_best is True

    worse = dict(C3_SAMPLE_RESULT)
    worse["I15"] = "3.00%"
    second = engine._save_task_result(1, parameters, worse, True)
    assert second.is_best is False

    better = dict(C3_SAMPLE_RESULT)
    better["I15"] = "20.00%"
    third = engine._save_task_result(2, parameters, better, True)
    assert third.is_best is True

    with session_factory() as session:
        best_rows = session.exec(
            select(TaskResult).where(TaskResult.is_best == True)  # noqa: E712
        ).all()
        assert len(best_rows) == 1
        assert int(best_rows[0].id or 0) == int(third.id or 0)


def test_return_series_rows_written(session_factory: Any) -> None:
    task = _make_task(session_factory)
    from app.services.google_sheet_tasks.c3 import C3Service

    engine = C3Service(
        {"stock_code": "600000", "market_type": "cn"},
        int(task.id),
        session_factory=session_factory,
        settings=None,
        stop_event=None,
    )
    result = dict(C3_SAMPLE_RESULT)
    result["_return_date"] = [
        {"stock_date": "2026-01-04", "index_return": 0.01, "start_return": 0.02},
        {"stock_date": "2026-01-05", "index_return": 0.015, "start_return": 0.03},
    ]
    saved = engine._save_task_result(0, {"stock_code": "600000"}, result, True)

    with session_factory() as session:
        points = session.exec(
            select(ReturnSeriesPoint).where(
                ReturnSeriesPoint.task_result_id == int(saved.id or 0)
            )
        ).all()
        assert len(points) == 2
        assert points[0].date.isoformat() == "2026-01-04"
        assert points[1].start_return == 0.03


# ---------------------------------------------------------------------------
# extractor 纯函数 golden
# ---------------------------------------------------------------------------


def test_extractor_hot_columns_golden() -> None:
    hot = extract_hot_columns_for_result(
        task_type="google_sheet",
        task_name="浦发-2020-1",
        task_config={"stock_code": "600000", "market_type": "cn", "year_n": "1y"},
        parameters={"stock_code": "600000", "year": "2020", "A1": "2"},
        result=dict(C3_SAMPLE_RESULT),
    )
    assert hot["stock_code"] == "600000.SS"
    assert hot["best_metric_name"] == "ReturnBeats"
    assert abs((hot["best_metric_value"] or 0) - 0.075) < 1e-9
    assert hot["model_name"] == "C3"


# ---------------------------------------------------------------------------
# cron DB 锁: acquire / release / stale takeover
# ---------------------------------------------------------------------------


def test_cron_run_lock_lifecycle_and_stale_takeover(session_factory: Any) -> None:
    from app.core import scheduler as scheduler_module

    task = ScheduledTask(
        name="cleanup", task_type="cleanup_old_logs", cron_expression="0 0 * * *"
    )
    with session_factory() as session:
        session.add(task)
        session.commit()
        session.refresh(task)
        task_id = int(task.id or 0)

    with session_factory() as session:
        assert scheduler_module.acquire_run_lock(session, task_id, "inst-1") is True
    with session_factory() as session:
        # second instance cannot claim a fresh lock
        assert scheduler_module.acquire_run_lock(session, task_id, "inst-2") is False

    with session_factory() as session:
        assert scheduler_module.release_run_lock(session, task_id, "inst-1") is True

    with session_factory() as session:
        row = session.get(ScheduledTask, task_id)
        assert row is not None
        row.is_running = True
        row.running_instance_id = "dead-instance"
        row.last_run_at = datetime.now(UTC) - timedelta(hours=12)
        session.add(row)
        session.commit()

    stale_before = datetime.now(UTC) - timedelta(hours=6)
    with session_factory() as session:
        assert (
            scheduler_module.acquire_run_lock(
                session, task_id, "inst-3", stale_before=stale_before
            )
            is True
        )
        row = session.get(ScheduledTask, task_id)
        assert row is not None
        assert row.running_instance_id == "inst-3"
