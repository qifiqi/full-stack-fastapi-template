"""Three-database migration smoke: CRUD + cascade checks on the current engine."""

from datetime import date

from sqlmodel import Session, func, select

from app.core.db import engine
from app.core.security import get_password_hash
from app.models import (
    BacktestProductResultCache,
    BacktestSheetRunLock,
    GoogleSheet,
    GoogleSheetToken,
    Item,
    NavigationMenuItem,
    ReturnSeriesPoint,
    ScheduledTask,
    StockMetadata,
    SystemConfig,
    Task,
    TaskLog,
    TaskResult,
    TaskTemplate,
    User,
)

with Session(engine) as s:
    u = User(
        email="smoke@example.com",
        hashed_password=get_password_hash("x" * 12),
        is_superuser=True,
    )
    s.add(u)
    s.commit()
    s.refresh(u)
    it = Item(title="it", owner_id=u.id)
    s.add(it)
    s.commit()

    t = Task(
        name="smoke",
        task_type="google_sheet",
        config={"stock_code": "600000", "spreadsheet_id": "SS1"},
        spreadsheet_id="SS1",
        stock_code="600000",
        market_type="SH",
    )
    s.add(t)
    s.commit()
    s.refresh(t)
    assert isinstance(t.id, int)

    r = TaskResult(
        task_id=t.id,
        step_index=0,
        params={"a": 1},
        result={"b": 2},
        stock_code="600000",
        best_metric_value=1.25,
        is_best=True,
    )
    s.add(r)
    s.commit()
    s.refresh(r)

    s.add(
        ReturnSeriesPoint(
            task_result_id=r.id, date=date(2026, 1, 5), index_return=0.1, start_return=0.2
        )
    )
    s.add_all(
        [
            GoogleSheet(spreadsheet_id="SS1"),
            GoogleSheetToken(name="t1", token_context={"refresh_token": "x"}),
            ScheduledTask(
                name="cleanup", task_type="cleanup_old_logs", cron_expression="0 0 * * *"
            ),
            SystemConfig(key="task_max_workers", value="8"),
            StockMetadata(stock_code="600000", market_type="SH", name="Pudong"),
            NavigationMenuItem(title="Tasks", path="/tasks"),
            TaskTemplate(name="tpl", config={"k": 1}),
            TaskLog(task_id=t.id, level="INFO", message="hello"),
            BacktestProductResultCache(
                batch_id="b1", cache_key="k1", result={"v": 1}, source_task_id=None
            ),
        ]
    )
    s.commit()

    s.delete(t)
    s.commit()
    assert s.exec(
        select(func.count()).select_from(TaskResult).where(TaskResult.task_id == t.id)
    ).one() == 0
    assert s.exec(select(func.count()).select_from(ReturnSeriesPoint)).one() == 0
    assert s.exec(select(func.count()).select_from(TaskLog)).one() == 0

    lock_task = Task(name="lock-holder", task_type="backtest_training")
    s.add(lock_task)
    s.commit()
    s.refresh(lock_task)
    lock = BacktestSheetRunLock(spreadsheet_id="SS9", task_id=lock_task.id)
    s.add(lock)
    s.commit()

    print(engine.url.database, "SMOKE OK")
