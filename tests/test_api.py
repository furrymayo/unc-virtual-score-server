import json

import pytest

from website import ingestion


@pytest.fixture(autouse=True)
def _reset_state():
    """Clear shared state between tests."""
    with ingestion.parsed_data_lock:
        for key in ingestion.parsed_data:
            ingestion.parsed_data[key] = {}
        ingestion.parsed_data_by_source.clear()
        ingestion.last_seen_by_source.clear()
    with ingestion.data_sources_lock:
        ingestion.data_sources.clear()
    yield


class TestGetEndpoints:
    def test_get_raw_data_empty(self, client):
        resp = client.get("/get_raw_data/Basketball")
        assert resp.status_code == 200
        assert resp.get_json() == {}

    def test_get_raw_data_with_data(self, client):
        ingestion.record_packet("Basketball", {"home_score": "50"}, "test:1")
        resp = client.get("/get_raw_data/Basketball")
        data = resp.get_json()
        assert data["home_score"] == "50"

    def test_get_sources_empty(self, client):
        resp = client.get("/get_sources")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["sources"] == []

    def test_get_trackman_data_unknown_sport(self, client):
        resp = client.get("/get_trackman_data/Tennis")
        assert resp.status_code == 404

    def test_get_trackman_debug_unknown_sport(self, client):
        resp = client.get("/get_trackman_debug/Tennis")
        assert resp.status_code == 404


class TestDataSourcesCRUD:
    def test_add_and_list(self, client):
        resp = client.post(
            "/data_sources",
            data=json.dumps({"host": "127.0.0.1", "port": 9999, "name": "Test"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] == "added"
        source_id = body["source"]["id"]

        resp = client.get("/data_sources")
        sources = resp.get_json()["sources"]
        assert len(sources) == 1
        assert sources[0]["id"] == source_id

    def test_add_duplicate(self, client):
        payload = json.dumps({"host": "127.0.0.1", "port": 9999})
        client.post("/data_sources", data=payload, content_type="application/json")
        resp = client.post("/data_sources", data=payload, content_type="application/json")
        assert resp.status_code == 409

    def test_delete(self, client):
        payload = json.dumps({"host": "127.0.0.1", "port": 9999})
        resp = client.post("/data_sources", data=payload, content_type="application/json")
        source_id = resp.get_json()["source"]["id"]

        resp = client.delete(f"/data_sources/{source_id}")
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "deleted"

        resp = client.get("/data_sources")
        assert len(resp.get_json()["sources"]) == 0

    def test_patch(self, client):
        payload = json.dumps({"host": "127.0.0.1", "port": 9999, "name": "Old"})
        resp = client.post("/data_sources", data=payload, content_type="application/json")
        source_id = resp.get_json()["source"]["id"]

        resp = client.patch(
            f"/data_sources/{source_id}",
            data=json.dumps({"name": "New"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert resp.get_json()["source"]["name"] == "New"

    def test_delete_not_found(self, client):
        resp = client.delete("/data_sources/nonexistent")
        assert resp.status_code == 404

    def test_patch_host_port(self, client):
        payload = json.dumps({"host": "127.0.0.1", "port": 9999, "name": "Original"})
        resp = client.post("/data_sources", data=payload, content_type="application/json")
        old_id = resp.get_json()["source"]["id"]

        resp = client.patch(
            f"/data_sources/{old_id}",
            data=json.dumps({"host": "10.0.0.5", "port": 8888}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        updated = resp.get_json()["source"]
        assert updated["host"] == "10.0.0.5"
        assert updated["port"] == 8888
        assert updated["id"] == "tcp:10.0.0.5:8888"
        assert updated["name"] == "Original"

        # Old id should no longer exist
        resp = client.get("/data_sources")
        sources = resp.get_json()["sources"]
        ids = [s["id"] for s in sources]
        assert old_id not in ids
        assert "tcp:10.0.0.5:8888" in ids

    def test_patch_host_port_conflict(self, client):
        p1 = json.dumps({"host": "127.0.0.1", "port": 9999})
        p2 = json.dumps({"host": "10.0.0.5", "port": 8888})
        client.post("/data_sources", data=p1, content_type="application/json")
        resp2 = client.post("/data_sources", data=p2, content_type="application/json")
        source2_id = resp2.get_json()["source"]["id"]

        # Try to change source2 to the same host:port as source1
        resp = client.patch(
            f"/data_sources/{source2_id}",
            data=json.dumps({"host": "127.0.0.1", "port": 9999}),
            content_type="application/json",
        )
        assert resp.status_code == 409

    def test_add_missing_fields(self, client):
        resp = client.post(
            "/data_sources",
            data=json.dumps({"host": "127.0.0.1"}),
            content_type="application/json",
        )
        assert resp.status_code == 400
