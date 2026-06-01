"""Test employee CRUD (admin only)."""
def test_create_employee(client, admin_headers):
    r = client.post("/api/employees", json={
        "email": "lead@test.com",
        "password": "lead123",
        "full_name": "Test Lead",
        "role": "lead",
    }, headers=admin_headers)
    assert r.status_code == 201
    assert r.json()["role"] == "lead"


def test_list_employees(client, admin_headers):
    r = client.get("/api/employees", headers=admin_headers)
    assert r.status_code == 200
    assert len(r.json()) >= 1


def test_create_employee_duplicate_email(client, admin_headers):
    r = client.post("/api/employees", json={
        "email": "admin@test.com", "password": "x", "full_name": "X", "role": "creative"
    }, headers=admin_headers)
    assert r.status_code == 400


def test_non_admin_cannot_create(client, admin_headers):
    # Create a creative employee first, then try as them
    client.post("/api/employees", json={
        "email": "c@test.com", "password": "c123456", "full_name": "C", "role": "creative"
    }, headers=admin_headers)
    r = client.post("/api/auth/login", json={"email": "c@test.com", "password": "c123456"})
    token = r.json()["access_token"]
    r = client.post("/api/employees", json={
        "email": "x@test.com", "password": "x", "full_name": "X", "role": "creative"
    }, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403
