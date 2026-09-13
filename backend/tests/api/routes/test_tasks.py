"""Integration tests for the tasks API (real PG via compose)."""

from typing import Any

from fastapi.testclient import TestClient
from sqlmodel import select

from app.core.config import settings

BASE = settings.API_V1_STR


def test_create_and_read_task(client: TestClient) -> None:
    response = client.post(
        f"{BASE}/tasks/",
        json={
            "name": "it-task",
            "task_type": "google_sheet",
            "config": {"stock_code": "600000", "spreadsheet_id": "IT-SS", "parameters": [[1]]},
        },
    )
    assert response.status_code == 200, response.text
    task = response.json()
    assert task["status"] == "pending"
    assert task["stock_code"] == "600000.SS"
    assert task["spreadsheet_id"] == "IT-SS"

    read = client.get(f"{BASE}/tasks/{task['id']}")
    assert read.status_code == 200
    assert read.json()["config"]["stock_code"] == "600000.SS"

    listing = client.get(f"{BASE}/tasks/", params={"task_type": "google_sheet"})
    assert listing.status_code == 200
    body = listing.json()
    assert body["count"] >= 1
    assert body["statistics"] is not None

    # status-check
    check = client.get(f"{BASE}/tasks/{task['id']}/status-check")
    assert check.status_code == 200
    assert check.json()["status"] == "pending"

    # config update on pending
    update = client.put(
        f"{BASE}/tasks/{task['id']}/config",
        json={"name": "it-task-renamed"},
    )
    assert update.status_code == 200
    assert update.json()["name"] == "it-task-renamed"

    # delete
    deleted = client.delete(f"{BASE}/tasks/{task['id']}")
    assert deleted.status_code == 200
    assert client.get(f"{BASE}/tasks/{task['id']}").status_code == 404


def test_create_task_invalid_type_422(client: TestClient) -> None:
    response = client.post(
        f"{BASE}/tasks/",
        json={"name": "bad", "task_type": "magic_type", "config": {}},
    )
    assert response.status_code == 422


def test_read_missing_task_404(client: TestClient) -> None:
    assert client.get(f"{BASE}/tasks/999999").status_code == 404


def test_cancel_not_running_409(client: TestClient) -> None:
    response = client.post(f"{BASE}/tasks/999999/cancel")
    assert response.status_code == 404


def test_create_restart_copies_task(client: TestClient, db: Any) -> None:
    from app.models import Task

    with db:
        task = Task(name="origin-task", task_type="google_sheet", config={"stock_code": "1"})
        db.add(task)
        db.commit()
        db.refresh(task)
        task_id = int(task.id or 0)

    restart = client.post(f"{BASE}/tasks/{task_id}/create-restart")
    assert restart.status_code == 200
    body = restart.json()
    assert body["id"] != task_id
    assert "重启" in body["name"]

    client.delete(f"{BASE}/tasks/{task_id}")
    client.delete(f"{BASE}/tasks/{body['id']}")


def test_batch_create_expands_cartesian(client: TestClient) -> None:
    response = client.post(
        f"{BASE}/tasks/batch-create",
        json={
            "config": {
                "base_task_name": "batch",
                "sheets": [
                    {"spreadsheet_id": "B1", "sheet_name": "s", "title": "x-1y-1]"},
                    {"spreadsheet_id": "B2", "sheet_name": "s", "title": "x-1y-2]"},
                ],
                "stock_codes": ["600000"],
                "parameters": [[1, 2]],
            }
        },
    )
    assert response.status_code == 200, response.text
    tasks = response.json()
    assert len(tasks) == 2
    for t in tasks:
        client.delete(f"{BASE}/tasks/{t['id']}")
