"""Test public consultation endpoint."""
def test_create_consultation(client):
    r = client.post("/api/consultations", json={
        "name": "John", "email": "john@test.com", "message": "Hello"
    })
    assert r.status_code == 201
    assert r.json()["name"] == "John"
    assert not r.json()["read"]


def test_list_consultations(client):
    client.post("/api/consultations", json={"name": "A", "email": "a@b.com"})
    client.post("/api/consultations", json={"name": "B", "email": "b@c.com"})
    r = client.get("/api/consultations")
    assert r.status_code == 200
    assert len(r.json()) == 2
