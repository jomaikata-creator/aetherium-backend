"""Test project creation, validation, and role scoping."""
def test_create_project(client, admin_headers):
    # Need a client first
    client.post("/api/clients", json={"name": "C", "email": "c@c.com"}, headers=admin_headers)
    r = client.post("/api/projects", json={
        "client_id": 1,
        "project_name": "Test Site",
        "full_price": 3000,
        "deposit_amount": 1500,
    }, headers=admin_headers)
    assert r.status_code == 201
    data = r.json()
    assert data["remaining_amount"] == 1500
    assert data["monthly_fee"] == 300.0  # hardcoded
    assert data["status"] == "quoted"


def test_deposit_exceeds_full(client, admin_headers):
    client.post("/api/clients", json={"name": "C", "email": "c@c.com"}, headers=admin_headers)
    r = client.post("/api/projects", json={
        "client_id": 1, "project_name": "Bad", "full_price": 1000, "deposit_amount": 2000,
    }, headers=admin_headers)
    assert r.status_code == 400


def test_list_projects(client, admin_headers):
    client.post("/api/clients", json={"name": "C", "email": "c@c.com"}, headers=admin_headers)
    client.post("/api/projects", json={
        "client_id": 1, "project_name": "P1", "full_price": 1000, "deposit_amount": 500,
    }, headers=admin_headers)
    r = client.get("/api/projects", headers=admin_headers)
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_lead_cannot_create_for_other_clients(client, admin_headers):
    # Create lead
    client.post("/api/employees", json={
        "email": "lead3@test.com", "password": "x", "full_name": "L3", "role": "lead"
    }, headers=admin_headers)
    # Admin creates client assigned to admin (assigned_to=None = unassigned)
    client.post("/api/clients", json={"name": "Admin Client", "email": "ac@test.com"}, headers=admin_headers)
    # Login as lead
    r = client.post("/api/auth/login", json={"email": "lead3@test.com", "password": "x"})
    lead_headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    # Lead tries to create project for admin's client → 403
    r = client.post("/api/projects", json={
        "client_id": 1, "project_name": "Hack", "full_price": 1000, "deposit_amount": 500,
    }, headers=lead_headers)
    assert r.status_code == 403
