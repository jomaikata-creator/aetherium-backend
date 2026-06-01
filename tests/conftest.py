"""Test fixtures — override DB engine with single-connection in-memory SQLite."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from database import Base
from models import Employee, EmployeeRole
from auth import hash_password


@pytest.fixture(scope="function")
def client():
    """TestClient with single-connection in-memory DB, fresh per test."""
    import database as db_module

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    db_module.engine = engine
    db_module.SessionLocal.configure(bind=engine)

    import main as main_module
    main_module.engine = engine

    Base.metadata.create_all(bind=engine)

    session = db_module.SessionLocal()
    admin = Employee(
        email="admin@test.com",
        password_hash=hash_password("admin123"),
        full_name="Test Admin",
        role=EmployeeRole.admin,
        is_active=True,
    )
    session.add(admin)
    session.commit()
    session.close()

    from main import app
    from fastapi.testclient import TestClient
    with TestClient(app) as tc:
        yield tc


@pytest.fixture
def admin_token(client):
    r = client.post("/api/auth/login", json={"email": "admin@test.com", "password": "admin123"})
    return r.json()["access_token"]


@pytest.fixture
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}
