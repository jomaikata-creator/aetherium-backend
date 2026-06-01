"""Test client CRUD + role scoping."""
def test_create_client(client, admin_headers):
    r = client.post("/api/clients", json={
        "name": "Test Client", "email": "client@test.com"
    }, headers=admin_headers)
    assert r.status_code == 201
    assert r.json()["name"] == "Test Client"


def test_list_clients_admin(client, admin_headers):
    client.post("/api/clients", json={"name": "A", "email": "a@b.com"}, headers=admin_headers)
    client.post("/api/clients", json={"name": "B", "email": "b@c.com"}, headers=admin_headers)
    r = client.get("/api/clients", headers=admin_headers)
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_lead_scope(client, admin_headers):
    # Create lead
    client.post("/api/employees", json={
        "email": "lead2@test.com", "password": "x", "full_name": "L", "role": "lead"
    }, headers=admin_headers)
    # Create client assigned to lead
    client.post("/api/clients", json={
        "assigned_to": 2, "name": "Lead Client", "email": "lc@test.com"
    }, headers=admin_headers)
    # Login as lead
    r = client.post("/api/auth/login", json={"email": "lead2@test.com", "password": "x"})
    lead_headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    # Lead sees only their client
    r = client.get("/api/clients", headers=lead_headers)
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["name"] == "Lead Client"
