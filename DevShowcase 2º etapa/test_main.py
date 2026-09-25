import importlib
import os

from fastapi.testclient import TestClient


def test_second_stage_flow(tmp_path):
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path / 'test.db'}"
    import main
    importlib.reload(main)
    with TestClient(main.app) as client:
        profile = client.post("/api/profiles", json={"name": "Daniele", "github_url": "https://github.com/example"})
        assert profile.status_code == 201
        pid = profile.json()["id"]
        tech = client.post("/api/technologies", json={"name": "Python"})
        assert tech.status_code == 201
        tid = tech.json()["id"]
        assert client.post("/api/technologies", json={"name": "Python"}).status_code == 409
        created = client.post("/api/projects", json={"title": "API", "description": "Teste", "repository_url": "https://github.com/example/api", "profile_id": pid, "technology_ids": []})
        assert created.status_code == 201
        project_id = created.json()["id"]
        route = f"/api/projects/{project_id}"
        assert client.put(route + "/technologies", json={"technology_ids": [tid]}).json()["technology_ids"] == [tid]
        assert client.put(route + "/technologies", json={"technology_ids": [tid]}).json()["technology_ids"] == [tid]
        assert client.post(route + "/feedbacks", json={"author": "A", "comment": "Ótimo", "rating": 5}).status_code == 201
        assert client.post(route + "/feedbacks", json={"author": "B", "comment": "Bom", "rating": 3}).status_code == 201
        listing = client.get(f"/api/projects?technology_id={tid}&page=1&page_size=1").json()
        assert listing["total"] == listing["pages"] == 1
        assert listing["items"][0]["average_rating"] == 4.0
        assert client.get("/api/projects?technology_id=9999").json()["total"] == 0
        bad = client.post(route + "/feedbacks", json={"author": "A", "comment": "Ruim", "rating": 6})
        assert bad.status_code == 400 and bad.json()["error"]["code"] == 400
        missing = client.post("/api/projects/99999/feedbacks", json={"author": "A", "comment": "Teste", "rating": 4})
        assert missing.status_code == 404 and missing.json()["error"]["code"] == 404
        assert client.post(route + "/feedbacks", content="invalid", headers={"content-type": "application/json"}).status_code == 400
