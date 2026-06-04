"""Test client CRUD + role scoping + team visibility."""
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


def test_lead_team_visibility(client, admin_headers):
    """Lead sees their own clients + their creatives' clients."""
    # Create lead
    client.post("/api/employees", json={
        "email": "lead2@test.com", "password": "xxxxxx", "full_name": "L", "role": "lead"
    }, headers=admin_headers)
    lead_id = 2

    # Create creative reporting to lead
    client.post("/api/employees", json={
        "email": "creative@test.com", "password": "xxxxxx", "full_name": "C",
        "role": "creative", "manager_id": lead_id
    }, headers=admin_headers)
    creative_id = 3

    # Client assigned to lead (own)
    client.post("/api/clients", json={
        "assigned_to": lead_id, "name": "Lead Client", "email": "lc@test.com"
    }, headers=admin_headers)
    # Client assigned to creative (team)
    client.post("/api/clients", json={
        "assigned_to": creative_id, "name": "Creative Client", "email": "cc@test.com"
    }, headers=admin_headers)

    # Login as lead
    r = client.post("/api/auth/login", json={"email": "lead2@test.com", "password": "xxxxxx"})
    lead_headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    # Lead sees both
    r = client.get("/api/clients", headers=lead_headers)
    assert r.status_code == 200
    names = [c["name"] for c in r.json()]
    assert "Lead Client" in names
    assert "Creative Client" in names


def test_creative_self_only(client, admin_headers):
    """Creative sees only their own clients."""
    client.post("/api/employees", json={
        "email": "cr2@test.com", "password": "xxxxxx", "full_name": "CR", "role": "creative"
    }, headers=admin_headers)
    creative_id = 2

    # Another creative
    client.post("/api/employees", json={
        "email": "cr3@test.com", "password": "xxxxxx", "full_name": "CR3", "role": "creative"
    }, headers=admin_headers)

    client.post("/api/clients", json={
        "assigned_to": creative_id, "name": "My Client", "email": "my@test.com"
    }, headers=admin_headers)
    client.post("/api/clients", json={
        "assigned_to": 3, "name": "Other Client", "email": "other@test.com"
    }, headers=admin_headers)

    r = client.post("/api/auth/login", json={"email": "cr2@test.com", "password": "xxxxxx"})
    cr_headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    r = client.get("/api/clients", headers=cr_headers)
    assert r.status_code == 200
    names = [c["name"] for c in r.json()]
    assert "My Client" in names
    assert "Other Client" not in names


def test_lead_cannot_edit_any(client, admin_headers):
    """Lead is read-only — cannot edit own or team clients."""
    # Lead
    client.post("/api/employees", json={
        "email": "leadE@test.com", "password": "xxxxxx", "full_name": "LE", "role": "lead"
    }, headers=admin_headers)
    lead_id = 2

    # Creative under lead
    client.post("/api/employees", json={
        "email": "cre@test.com", "password": "xxxxxx", "full_name": "CRE",
        "role": "creative", "manager_id": lead_id
    }, headers=admin_headers)

    # Lead's own client
    client.post("/api/clients", json={
        "assigned_to": lead_id, "name": "My Own", "email": "own@test.com"
    }, headers=admin_headers)
    # Creative's client
    client.post("/api/clients", json={
        "assigned_to": 3, "name": "Team Client", "email": "team@test.com"
    }, headers=admin_headers)

    r = client.post("/api/auth/login", json={"email": "leadE@test.com", "password": "xxxxxx"})
    lead_headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    # Lead cannot edit own client (read-only)
    r = client.patch("/api/clients/1", json={"name": "Renamed"}, headers=lead_headers)
    assert r.status_code == 403

    # Lead cannot edit team's client
    r = client.patch("/api/clients/2", json={"name": "Hacked"}, headers=lead_headers)
    assert r.status_code == 403
