import time

from website import ingestion
from website.protocol import STX, CR, TP_VOLLEYBALL, TP_BBALL_BASE_SOFT, BBALL_LEN


def _reset_ingestion_state():
    """Clear shared state between tests."""
    with ingestion.parsed_data_lock:
        for key in ingestion.parsed_data:
            ingestion.parsed_data[key] = {}
        ingestion.parsed_data_by_source.clear()
        ingestion.last_seen_by_source.clear()


class TestRecordAndRetrieve:
    def setup_method(self):
        _reset_ingestion_state()

    def test_record_and_get(self):
        ingestion.record_packet("Basketball", {"home_score": "45"}, "test:1")
        result = ingestion.get_sport_data("Basketball")
        assert result["home_score"] == "45"
        assert result["_meta"]["source"] == "test:1"

    def test_source_filtering(self):
        ingestion.record_packet("Basketball", {"home_score": "10"}, "src:A")
        ingestion.record_packet("Basketball", {"home_score": "20"}, "src:B")
        a = ingestion.get_sport_data("Basketball", source_id="src:A")
        b = ingestion.get_sport_data("Basketball", source_id="src:B")
        assert a["home_score"] == "10"
        assert b["home_score"] == "20"

    def test_get_sources_snapshot(self):
        ingestion.record_packet("Hockey", {"home_score": "3"}, "src:X")
        sources = ingestion.get_sources_snapshot()
        assert len(sources) == 1
        assert sources[0]["source"] == "src:X"
        assert "Hockey" in sources[0]["sports"]


class TestPurgeStale:
    def setup_method(self):
        _reset_ingestion_state()

    def test_purge_removes_old(self):
        ingestion.record_packet("Soccer", {"period": "1"}, "old:src")
        with ingestion.parsed_data_lock:
            ingestion.last_seen_by_source["old:src"] = time.time() - 7200
        ingestion.purge_stale_sources()
        sources = ingestion.get_sources_snapshot()
        assert len(sources) == 0

    def test_purge_keeps_fresh(self):
        ingestion.record_packet("Soccer", {"period": "1"}, "fresh:src")
        ingestion.purge_stale_sources()
        sources = ingestion.get_sources_snapshot()
        assert len(sources) == 1


class TestHandleSerialPacket:
    def setup_method(self):
        _reset_ingestion_state()

    def test_integration_basketball(self):
        pkt = [0x30] * BBALL_LEN
        pkt[0] = STX
        pkt[1] = TP_BBALL_BASE_SOFT
        pkt[-1] = CR
        ingestion.handle_serial_packet(pkt, source_id="test:serial")
        result = ingestion.get_sport_data("Basketball")
        assert result  # should have some parsed data
        assert result["_meta"]["source"] == "test:serial"

    def test_short_packet_no_crash(self):
        ingestion.handle_serial_packet([STX], source_id="test:short")
        result = ingestion.get_sport_data("Basketball")
        assert result == {}
