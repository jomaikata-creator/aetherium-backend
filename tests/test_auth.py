"""Test auth endpoints."""
def test_login_ok(client):
    r = client.post("/api/auth/login", json={"email": "admin@test.com", "password": "admin123"})
    assert r.status_code == 200
    assert "access_token" in r.json()
    assert r.json()["employee"]["role"] == "admin"


def test_login_bad_password(client):
    r = client.post("/api/auth/login", json={"email": "admin@test.com", "password": "wrong"})
    assert r.status_code == 401


def test_login_bad_email(client):
    r = client.post("/api/auth/login", json={"email": "nope@test.com", "password": "admin123"})
    assert r.status_code == 401


def test_me(client, admin_headers):
    r = client.get("/api/auth/me", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["email"] == "admin@test.com"


def test_no_token_rejected(client):
    r = client.get("/api/employees")
    assert r.status_code == 403
