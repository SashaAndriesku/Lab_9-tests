from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from testcontainers.postgres import PostgresContainer

from rental.api import app, connection

pytestmark = pytest.mark.api


@pytest.fixture(scope="module")
def client():
    with PostgresContainer("postgres:17.6-alpine") as postgres:
        options = dict(
            host=postgres.get_container_host_ip(),
            port=postgres.get_exposed_port(5432),
            user=postgres.username,
            password=postgres.password,
            dbname=postgres.dbname,
            autocommit=True,
        )
        with psycopg.connect(**options) as init_db:
            migration = Path(__file__).resolve().parents[1] / "migrations/V1__create_tables.sql"
            init_db.execute(migration.read_text(encoding="utf-8"))

        def override_connection():
            with psycopg.connect(**options) as db:
                yield db

        app.dependency_overrides[connection] = override_connection
        with TestClient(app) as test_client:
            yield test_client
        app.dependency_overrides.clear()


def test_api_create_and_get_equipment(client):
    code = f"API-EQ-{uuid4().hex[:10]}"
    create_resp = client.post("/equipment", json={"code": code, "daily_rate": 1200, "stock": 4})
    assert create_resp.status_code == 201
    created = create_resp.json()
    assert created["code"] == code
    assert created["stock"] == 4

    get_resp = client.get(f"/equipment/{created['id']}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == created["id"]


def test_api_get_missing_equipment_returns_404(client):
    resp = client.get("/equipment/999999")
    assert resp.status_code == 404
    assert resp.json()["code"] == "NOT_FOUND"


def test_api_rental_lifecycle_and_stock_conflict(client):
    code = f"API-EQ-{uuid4().hex[:10]}"
    eq = client.post("/equipment", json={"code": code, "daily_rate": 1000, "stock": 2}).json()

    rent_resp = client.post(
        "/rentals",
        json={
            "reference": f"REF-{uuid4().hex[:10]}",
            "equipment_id": eq["id"],
            "quantity": 2,
            "days": 3,
            "premium": False,
        },
    )
    assert rent_resp.status_code == 201
    rental = rent_resp.json()
    assert rental["total"] == 6000
    assert rental["status"] == "Active"

    conflict_resp = client.post(
        "/rentals",
        json={
            "reference": f"REF-{uuid4().hex[:10]}",
            "equipment_id": eq["id"],
            "quantity": 1,
            "days": 2,
            "premium": False,
        },
    )
    assert conflict_resp.status_code == 409
    assert conflict_resp.json()["code"] == "RENTAL_CONFLICT"

    return_resp = client.post(f"/rentals/{rental['id']}/return", json={"overdue_days": 0})
    assert return_resp.status_code == 200
    assert return_resp.json()["status"] == "Returned"