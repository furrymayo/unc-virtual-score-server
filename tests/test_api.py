import json
import os

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
            data=json.dumps(
                {
                    "host": "127.0.0.1",
                    "port": 9999,
                    "name": "Test",
                    "sport_overrides": {"lacrosse": "gymnastics"},
                }
            ),
            content_type="application/json",
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] == "added"
        source_id = body["source"]["id"]
        assert body["source"]["sport_overrides"] == {"Lacrosse": "Gymnastics"}

        resp = client.get("/data_sources")
        sources = resp.get_json()["sources"]
        assert len(sources) == 1
        assert sources[0]["id"] == source_id
        assert sources[0]["sport_overrides"] == {"Lacrosse": "Gymnastics"}

    def test_add_duplicate_gets_unique_id(self, client):
        payload = json.dumps({"host": "127.0.0.1", "port": 9999})
        resp1 = client.post("/data_sources", data=payload, content_type="application/json")
        assert resp1.status_code == 200
        id1 = resp1.get_json()["source"]["id"]
        assert id1 == "tcp:127.0.0.1:9999"

        resp2 = client.post("/data_sources", data=payload, content_type="application/json")
        assert resp2.status_code == 200
        id2 = resp2.get_json()["source"]["id"]
        assert id2 == "tcp:127.0.0.1:9999:2"

        resp3 = client.post("/data_sources", data=payload, content_type="application/json")
        assert resp3.status_code == 200
        id3 = resp3.get_json()["source"]["id"]
        assert id3 == "tcp:127.0.0.1:9999:3"

        resp = client.get("/data_sources")
        sources = resp.get_json()["sources"]
        assert len(sources) == 3

    def test_delete(self, client):
        payload = json.dumps({"host": "127.0.0.1", "port": 9999})
        resp = client.post(
            "/data_sources", data=payload, content_type="application/json"
        )
        source_id = resp.get_json()["source"]["id"]

        resp = client.delete(f"/data_sources/{source_id}")
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "deleted"

        resp = client.get("/data_sources")
        assert len(resp.get_json()["sources"]) == 0

    def test_patch(self, client):
        payload = json.dumps({"host": "127.0.0.1", "port": 9999, "name": "Old"})
        resp = client.post(
            "/data_sources", data=payload, content_type="application/json"
        )
        source_id = resp.get_json()["source"]["id"]

        resp = client.patch(
            f"/data_sources/{source_id}",
            data=json.dumps(
                {
                    "name": "New",
                    "sport_overrides": {"Lacrosse": "Gymnastics"},
                }
            ),
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert resp.get_json()["source"]["name"] == "New"
        assert resp.get_json()["source"]["sport_overrides"] == {
            "Lacrosse": "Gymnastics"
        }

    def test_delete_not_found(self, client):
        resp = client.delete("/data_sources/nonexistent")
        assert resp.status_code == 404

    def test_patch_host_port(self, client):
        payload = json.dumps({"host": "127.0.0.1", "port": 9999, "name": "Original"})
        resp = client.post(
            "/data_sources", data=payload, content_type="application/json"
        )
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


class TestBrowseFiles:
    def test_browse_default_cwd(self, client):
        """Default (no path) returns cwd with entries."""
        resp = client.get("/browse_files")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["current_path"] == os.getcwd()
        assert isinstance(data["entries"], list)
        assert data["parent_path"] is not None or data["current_path"] == "/"

    def test_browse_explicit_path(self, client, tmp_path):
        """Browse a known tmp_path directory with an XML file and a subdir."""
        sub = tmp_path / "subdir"
        sub.mkdir()
        xml_file = tmp_path / "game.xml"
        xml_file.write_text("<game/>")
        txt_file = tmp_path / "notes.txt"
        txt_file.write_text("ignored")

        resp = client.get(f"/browse_files?path={tmp_path}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["current_path"] == str(tmp_path)
        names = [e["name"] for e in data["entries"]]
        assert "subdir" in names
        assert "game.xml" in names
        assert "notes.txt" not in names

    def test_browse_nonexistent_falls_back(self, client, tmp_path):
        """Nonexistent path falls back to parent or cwd."""
        fake = tmp_path / "does_not_exist"
        resp = client.get(f"/browse_files?path={fake}")
        assert resp.status_code == 200
        data = resp.get_json()
        # Should fall back to parent (tmp_path) since it exists
        assert data["current_path"] == str(tmp_path)

    def test_browse_file_redirects_to_parent(self, client, tmp_path):
        """Passing a file path browses its parent directory."""
        xml_file = tmp_path / "stats.xml"
        xml_file.write_text("<stats/>")

        resp = client.get(f"/browse_files?path={xml_file}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["current_path"] == str(tmp_path)

    def test_browse_filters_xml_only(self, client, tmp_path):
        """Only .xml files and directories appear in entries."""
        (tmp_path / "a.xml").write_text("<a/>")
        (tmp_path / "b.json").write_text("{}")
        (tmp_path / "c.txt").write_text("hi")
        (tmp_path / "d").mkdir()

        resp = client.get(f"/browse_files?path={tmp_path}")
        data = resp.get_json()
        names = [e["name"] for e in data["entries"]]
        assert "a.xml" in names
        assert "d" in names
        assert "b.json" not in names
        assert "c.txt" not in names

    def test_browse_drives_not_on_linux(self, client):
        """__drives__ is treated as nonexistent path on Linux (not Windows)."""
        resp = client.get("/browse_files?path=__drives__")
        assert resp.status_code == 200
        data = resp.get_json()
        # On Linux, __drives__ is not a real path, so it falls back to cwd
        assert data["current_path"] == os.getcwd()
