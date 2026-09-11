import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Tests run against a real Postgres instance so the raw SQL (SERIAL, RETURNING,
# etc.) is exercised the same way it will be in production. Locally, run:
#   docker run --rm -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=appdb -p 5432:5432 postgres:16-alpine
# then: DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/appdb pytest
# In CI, a postgres service container provides this automatically (see ci-cd.yml).
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@localhost:5432/appdb"
)

import pytest
from app import app, engine
from sqlalchemy import text


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client
    # Clean up rows created during each test
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM items"))
        conn.commit()


def test_home(client):
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "message" in data
    assert "version" in data


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "healthy"


def test_info(client):
    resp = client.get("/info")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "hostname" in data
    assert "config" in data
    assert "secrets_status" in data
    assert data["db_status"] == "connected"


def test_404(client):
    resp = client.get("/does-not-exist")
    assert resp.status_code == 404


def test_create_and_list_item(client):
    resp = client.post("/api/items", json={"name": "Test Item", "description": "A test"})
    assert resp.status_code == 201
    created = resp.get_json()
    assert created["name"] == "Test Item"
    assert created["id"] is not None

    resp = client.get("/api/items")
    assert resp.status_code == 200
    items = resp.get_json()
    assert any(i["id"] == created["id"] for i in items)


def test_create_item_requires_name(client):
    resp = client.post("/api/items", json={"description": "no name here"})
    assert resp.status_code == 400


def test_delete_item(client):
    created = client.post("/api/items", json={"name": "To delete"}).get_json()
    item_id = created["id"]

    resp = client.delete(f"/api/items/{item_id}")
    assert resp.status_code == 200

    resp = client.get("/api/items")
    items = resp.get_json()
    assert not any(i["id"] == item_id for i in items)


def test_delete_nonexistent_item(client):
    resp = client.delete("/api/items/999999")
    assert resp.status_code == 404
