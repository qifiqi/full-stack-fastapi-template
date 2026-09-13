"""Integration tests: scheduled tasks, templates, configs, navigation, meta, stocks."""

from fastapi.testclient import TestClient

from app.core.config import settings

BASE = settings.API_V1_STR


def test_scheduled_task_lifecycle(client: TestClient) -> None:
    created = client.post(
        f"{BASE}/scheduled-tasks/",
        json={
            "name": "IT cleanup",
            "task_type": "cleanup_old_logs",
            "cron_expression": "30 2 * * *",
            "params": {"days": 3},
        },
    )
    assert created.status_code == 200, created.text
    task = created.json()

    invalid = client.post(
        f"{BASE}/scheduled-tasks/",
        json={"name": "bad", "task_type": "cleanup_old_logs", "cron_expression": "not a cron"},
    )
    assert invalid.status_code == 422

    toggled = client.post(f"{BASE}/scheduled-tasks/{task['id']}/toggle")
    assert toggled.status_code == 200
    assert toggled.json()["enabled"] is False

    run_now = client.post(f"{BASE}/scheduled-tasks/{task['id']}/run")
    assert run_now.status_code == 409  # disabled

    stats = client.get(f"{BASE}/scheduled-tasks/scheduler/stats")
    assert stats.status_code == 200

    deleted = client.delete(f"{BASE}/scheduled-tasks/{task['id']}")
    assert deleted.status_code == 200


def test_task_template_crud(client: TestClient) -> None:
    created = client.post(
        f"{BASE}/task-templates/",
        json={"name": "IT template", "config": {"stock_code": "600000"}},
    )
    assert created.status_code == 200
    template = created.json()
    updated = client.put(
        f"{BASE}/task-templates/{template['id']}",
        json={"name": "IT template v2"},
    )
    assert updated.json()["name"] == "IT template v2"
    assert client.delete(f"{BASE}/task-templates/{template['id']}").status_code == 200


def test_configs_upsert_and_mask(client: TestClient) -> None:
    put = client.put(f"{BASE}/configs/task_max_workers", json={"value": "6"})
    assert put.status_code == 200
    read = client.get(f"{BASE}/configs/task_max_workers")
    assert read.json()["value"] == "6"
    listing = client.get(f"{BASE}/configs/")
    assert listing.status_code == 200
    validate = client.get(f"{BASE}/configs/validate")
    assert validate.status_code == 200


def test_navigation_crud(client: TestClient) -> None:
    created = client.post(
        f"{BASE}/navigation-menu-items/",
        json={"title": "IT nav", "path": "/it-nav", "sort_order": 5},
    )
    assert created.status_code == 200
    item = created.json()
    assert client.delete(f"{BASE}/navigation-menu-items/{item['id']}").status_code == 200


def test_meta_enums_and_versions(client: TestClient) -> None:
    versions = client.get(f"{BASE}/meta/versions")
    assert versions.status_code == 200
    enums = client.get(f"{BASE}/meta/enums")
    assert enums.status_code == 200
    body = enums.json()
    assert any(t["value"] == "google_sheet" for t in body["task_types"])
    assert any(s["value"] == "running" for s in body["task_statuses"])


def test_stocks_search_empty(client: TestClient) -> None:
    response = client.get(f"{BASE}/stocks/search", params={"keyword": "NONEXISTENT999"})
    assert response.status_code == 200
    assert response.json()["count"] == 0
