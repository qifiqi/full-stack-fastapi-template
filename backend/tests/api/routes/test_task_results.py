"""Integration tests: task results, return series, logs."""

from typing import Any

from datetime import date

from fastapi.testclient import TestClient

from app.core.config import settings

BASE = settings.API_V1_STR


def _mk_task_with_result(client: TestClient, db: Any) -> tuple[int, int]:
    from app.models import Task, TaskResult, ReturnSeriesPoint

    with db:
        task = Task(name="result-task", task_type="google_sheet", config={})
        db.add(task)
        db.commit()
        db.refresh(task)
        result = TaskResult(
            task_id=int(task.id or 0),
            step_index=0,
            success=True,
            params={"stock_code": "600000.SS"},
            result={"I15": "12.5%", "I16": "30%", "I18": "5%"},
            stock_code="600000.SS",
            best_metric_name="ReturnBeats",
            best_metric_value=0.075,
            is_best=True,
        )
        db.add(result)
        db.commit()
        db.refresh(result)
        db.add(
            ReturnSeriesPoint(
                task_result_id=int(result.id or 0),
                date=date(2026, 1, 4),
                index_return=0.01,
                start_return=0.02,
            )
        )
        db.commit()
        return int(task.id or 0), int(result.id or 0)


def test_result_list_is_lightweight(client: TestClient, db: Any) -> None:
    task_id, result_id = _mk_task_with_result(client, db)
    response = client.get(f"{BASE}/task-results/tasks/{task_id}/results")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    item = body["data"][0]
    assert "params" not in item and "result" not in item
    assert item["is_best"] is True

    detail = client.get(f"{BASE}/task-results/{result_id}")
    assert detail.status_code == 200
    assert detail.json()["result"]["I15"] == "12.5%"

    client.delete(f"{BASE}/tasks/{task_id}")


def test_return_series_range_query(client: TestClient, db: Any) -> None:
    task_id, result_id = _mk_task_with_result(client, db)
    response = client.get(
        f"{BASE}/task-results/{result_id}/return-series",
        params={"start": "2026-01-01", "end": "2026-12-31"},
    )
    assert response.status_code == 200
    points = response.json()
    assert len(points) == 1
    assert points[0]["date"] == "2026-01-04"

    empty = client.get(
        f"{BASE}/task-results/{result_id}/return-series",
        params={"start": "2030-01-01", "end": "2030-12-31"},
    )
    assert empty.json() == []
    client.delete(f"{BASE}/tasks/{task_id}")


def test_model_summary_best_only_query(client: TestClient, db: Any) -> None:
    task_id, _result_id = _mk_task_with_result(client, db)
    response = client.get(f"{BASE}/model-summary/", params={"stock_code": "600000.SS"})
    assert response.status_code == 200
    body = response.json()
    assert body["count"] >= 1
    row = next(r for r in body["data"] if r["task_id"] == task_id)
    assert row["best_metric_name"] == "ReturnBeats"
    client.delete(f"{BASE}/tasks/{task_id}")


def test_model_summary_rebuild_and_status(client: TestClient, db: Any) -> None:
    task_id, _result_id = _mk_task_with_result(client, db)
    rebuild = client.post(f"{BASE}/model-summary/rebuild", json={"task_ids": [task_id]})
    assert rebuild.status_code == 200
    status = client.get(f"{BASE}/model-summary/rebuild/status")
    assert status.status_code == 200
    assert status.json()["state"] in {"completed", "idle", "running"}
    columns = client.get(f"{BASE}/model-summary/columns")
    assert columns.status_code == 200
    client.delete(f"{BASE}/tasks/{task_id}")


def test_task_logs_endpoint(client: TestClient, db: Any) -> None:
    from app.models import Task, TaskLog

    with db:
        task = Task(name="log-task", task_type="google_sheet", config={})
        db.add(task)
        db.commit()
        db.refresh(task)
        db.add(TaskLog(task_id=int(task.id or 0), level="INFO", message="hello"))
        db.commit()
        task_id = int(task.id or 0)

    response = client.get(f"{BASE}/tasks/{task_id}/logs")
    assert response.status_code == 200
    assert response.json()["count"] == 1

    logs = client.get(f"{BASE}/logs/", params={"task_id": task_id})
    assert logs.status_code == 200
    assert logs.json()["count"] == 1

    latest = client.get(f"{BASE}/logs/latest")
    assert latest.status_code == 200

    client.delete(f"{BASE}/tasks/{task_id}")
