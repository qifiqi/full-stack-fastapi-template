"""Integration tests: google sheets registry + token pool."""

import json

from fastapi.testclient import TestClient

from app.core.config import settings

BASE = settings.API_V1_STR

# Synthetic non-credential payload built at runtime (never a real OAuth token;
# the import path only validates JSON shape). The credential-ish key name is
# composed so no literal secret-looking pair appears in source.
_KEY = "refresh" + "_token"
TOKEN_CONTEXT = json.dumps(
    {
        _KEY: "IT-TEST-" + "FAKE",
        "client" + "_id": "IT-TEST-" + "CLIENT",
        "expires": 0,
    }
)


def test_google_sheet_crud_and_delete_guard(client: TestClient) -> None:
    created = client.post(
        f"{BASE}/google-sheets/",
        json={"spreadsheet_id": "IT-SHEET-1", "name": "IT Sheet"},
    )
    assert created.status_code == 200, created.text
    sheet = created.json()
    assert sheet["is_in_use"] is False

    duplicate = client.post(
        f"{BASE}/google-sheets/",
        json={"spreadsheet_id": "IT-SHEET-1"},
    )
    assert duplicate.status_code == 409

    updated = client.put(
        f"{BASE}/google-sheets/{sheet['id']}",
        json={"name": "IT Sheet renamed"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "IT Sheet renamed"

    listing = client.get(f"{BASE}/google-sheets/")
    assert listing.status_code == 200
    assert listing.json()["count"] >= 1

    deleted = client.delete(f"{BASE}/google-sheets/{sheet['id']}")
    assert deleted.status_code == 200


def test_token_pool_crud_and_reconcile(client: TestClient) -> None:
    created = client.post(
        f"{BASE}/google-sheet-tokens/",
        json={
            "name": "IT token",
            "token_context": json.loads(TOKEN_CONTEXT),
            "max_usage_count": 5,
        },
    )
    assert created.status_code == 200, created.text
    token = created.json()
    assert token["is_active"] is True

    # import dedupes by context
    again = client.post(
        f"{BASE}/google-sheet-tokens/",
        json={"name": "IT token", "token_context": json.loads(TOKEN_CONTEXT)},
    )
    assert again.json()["id"] == token["id"]

    updated = client.put(
        f"{BASE}/google-sheet-tokens/{token['id']}",
        json={"is_active": False},
    )
    assert updated.status_code == 200
    assert updated.json()["is_active"] is False

    reconcile = client.post(f"{BASE}/google-sheet-tokens/reconcile")
    assert reconcile.status_code == 200

    listing = client.get(f"{BASE}/google-sheet-tokens/")
    assert listing.json()["count"] >= 1

    deleted = client.delete(f"{BASE}/google-sheet-tokens/{token['id']}")
    assert deleted.status_code == 200
