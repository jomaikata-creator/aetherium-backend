"""Test project creation, validation, team visibility, and role scoping."""
def test_create_project(client, admin_headers):
    client.post("/api/clients", json={"name": "C", "email": "c@c.com"}, headers=admin_headers)
    r = client.post("/api/projects", json={
        "client_id": 1, "project_name": "Test Site", "full_price": 3000, "deposit_amount": 1500,
    }, headers=admin_headers)
    assert r.status_code == 201
    data = r.json()
    assert data["remaining_amount"] == 1500
    assert data["monthly_fee"] == 300.0
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
    # Lead
    client.post("/api/employees", json={
        "email": "lead3@test.com", "password": "x", "full_name": "L3", "role": "lead"
    }, headers=admin_headers)
    # Admin creates unassigned client
    client.post("/api/clients", json={"name": "Admin Client", "email": "ac@test.com"}, headers=admin_headers)
    # Login as lead
    r = client.post("/api/auth/login", json={"email": "lead3@test.com", "password": "x"})
    lead_headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    r = client.post("/api/projects", json={
        "client_id": 1, "project_name": "Hack", "full_price": 1000, "deposit_amount": 500,
    }, headers=lead_headers)
    assert r.status_code == 403


def test_lead_sees_team_projects(client, admin_headers):
    """Lead can view projects of their creatives."""
    # Lead
    client.post("/api/employees", json={
        "email": "leadV@test.com", "password": "x", "full_name": "LV", "role": "lead"
    }, headers=admin_headers)
    lead_id = 2

    # Creative under lead
    client.post("/api/employees", json={
        "email": "crV@test.com", "password": "x", "full_name": "CV",
        "role": "creative", "manager_id": lead_id
    }, headers=admin_headers)

    # Client for creative
    client.post("/api/clients", json={
        "assigned_to": 3, "name": "Team Client", "email": "tc@test.com"
    }, headers=admin_headers)
    # Project for that client
    client.post("/api/projects", json={
        "client_id": 1, "project_name": "Team Project", "full_price": 2000, "deposit_amount": 1000,
    }, headers=admin_headers)

    r = client.post("/api/auth/login", json={"email": "leadV@test.com", "password": "x"})
    lead_headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    r = client.get("/api/projects", headers=lead_headers)
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["project_name"] == "Team Project"
