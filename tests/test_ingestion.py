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
    ingestion.reset_baseball_state()


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


# --- Baseball inning state machine tests ---

def _base_baseball(outs="0", away_innings=None, home_innings=None):
    """Helper: minimal baseball parsed dict."""
    return {
        "away_innings": away_innings or [" "] * 10,
        "home_innings": home_innings or [" "] * 10,
        "balls": "0", "strikes": "0", "outs": outs,
        "batter_num": " 1", "pitch_speed": "000",
        "away_runs": " 0", "away_hits": " 0", "away_errors": " 0",
        "home_runs": " 0", "home_hits": " 0", "home_errors": " 0",
    }


class TestBaseballInningStateMachine:
    def setup_method(self):
        _reset_ingestion_state()

    def test_cold_start_top_1st(self):
        """First packet with 0 outs → TOP 1st."""
        ingestion.record_packet("Baseball", _base_baseball(outs="0"), "t")
        result = ingestion.get_sport_data("Baseball")
        assert result["half"] == "TOP"
        assert result["inning"] == 1
        assert result["inning_display"] == "TOP 1st"

    def test_top_to_mid_on_3_outs(self):
        """Outs going to 3 in TOP → MID (same inning)."""
        ingestion.record_packet("Baseball", _base_baseball(outs="0"), "t")
        ingestion.record_packet("Baseball", _base_baseball(outs="1"), "t")
        ingestion.record_packet("Baseball", _base_baseball(outs="3"), "t")
        result = ingestion.get_sport_data("Baseball")
        assert result["half"] == "MID"
        assert result["inning"] == 1
        assert result["inning_display"] == "MID 1st"

    def test_mid_to_bot_on_outs_reset(self):
        """Outs dropping below 3 after MID → BOT (same inning)."""
        ingestion.record_packet("Baseball", _base_baseball(outs="0"), "t")
        ingestion.record_packet("Baseball", _base_baseball(outs="3"), "t")  # MID 1
        ingestion.record_packet("Baseball", _base_baseball(outs="0"), "t")  # BOT 1
        result = ingestion.get_sport_data("Baseball")
        assert result["half"] == "BOT"
        assert result["inning"] == 1
        assert result["inning_display"] == "BOT 1st"

    def test_bot_to_end_on_3_outs(self):
        """Outs going to 3 in BOT → END (same inning)."""
        ingestion.record_packet("Baseball", _base_baseball(outs="0"), "t")
        ingestion.record_packet("Baseball", _base_baseball(outs="3"), "t")  # MID 1
        ingestion.record_packet("Baseball", _base_baseball(outs="0"), "t")  # BOT 1
        ingestion.record_packet("Baseball", _base_baseball(outs="3"), "t")  # END 1
        result = ingestion.get_sport_data("Baseball")
        assert result["half"] == "END"
        assert result["inning"] == 1
        assert result["inning_display"] == "END 1st"

    def test_end_to_top_advances_inning(self):
        """Outs dropping below 3 after END → TOP of next inning."""
        ingestion.record_packet("Baseball", _base_baseball(outs="0"), "t")
        ingestion.record_packet("Baseball", _base_baseball(outs="3"), "t")  # MID 1
        ingestion.record_packet("Baseball", _base_baseball(outs="0"), "t")  # BOT 1
        ingestion.record_packet("Baseball", _base_baseball(outs="3"), "t")  # END 1
        ingestion.record_packet("Baseball", _base_baseball(outs="0"), "t")  # TOP 2
        result = ingestion.get_sport_data("Baseball")
        assert result["half"] == "TOP"
        assert result["inning"] == 2
        assert result["inning_display"] == "TOP 2nd"

    def test_full_game_cycle_three_innings(self):
        """Simulate 3 complete innings, verify inning advances correctly."""
        for inn in range(1, 4):
            # TOP
            ingestion.record_packet("Baseball", _base_baseball(outs="0"), "t")
            r = ingestion.get_sport_data("Baseball")
            assert r["half"] == "TOP" and r["inning"] == inn

            # MID
            ingestion.record_packet("Baseball", _base_baseball(outs="3"), "t")
            r = ingestion.get_sport_data("Baseball")
            assert r["half"] == "MID" and r["inning"] == inn

            # BOT
            ingestion.record_packet("Baseball", _base_baseball(outs="0"), "t")
            r = ingestion.get_sport_data("Baseball")
            assert r["half"] == "BOT" and r["inning"] == inn

            # END
            ingestion.record_packet("Baseball", _base_baseball(outs="3"), "t")
            r = ingestion.get_sport_data("Baseball")
            assert r["half"] == "END" and r["inning"] == inn

        # TOP of 4th
        ingestion.record_packet("Baseball", _base_baseball(outs="0"), "t")
        r = ingestion.get_sport_data("Baseball")
        assert r["half"] == "TOP" and r["inning"] == 4

    def test_zero_run_inning_stays_mid(self):
        """The core bug: away scores 0 runs → blank linescore.
        Outs=3 should still show MID, not TOP."""
        # All innings blank (no runs scored anywhere)
        ingestion.record_packet("Baseball", _base_baseball(outs="1"), "t")
        ingestion.record_packet("Baseball", _base_baseball(outs="2"), "t")
        ingestion.record_packet("Baseball", _base_baseball(outs="3"), "t")
        result = ingestion.get_sport_data("Baseball")
        assert result["half"] == "MID"
        assert result["inning"] == 1

    def test_mid_persists_while_outs_stays_3(self):
        """MID should persist across multiple packets with outs=3."""
        ingestion.record_packet("Baseball", _base_baseball(outs="0"), "t")
        ingestion.record_packet("Baseball", _base_baseball(outs="3"), "t")  # MID
        ingestion.record_packet("Baseball", _base_baseball(outs="3"), "t")  # still MID
        ingestion.record_packet("Baseball", _base_baseball(outs="3"), "t")  # still MID
        result = ingestion.get_sport_data("Baseball")
        assert result["half"] == "MID"
        assert result["inning"] == 1

    def test_bootstrap_with_linescore_data(self):
        """Cold start mid-game: away has more filled innings → BOT."""
        away = ["2", "0", " ", " ", " ", " ", " ", " ", " ", " "]
        home = ["1", " ", " ", " ", " ", " ", " ", " ", " ", " "]
        ingestion.record_packet("Baseball", _base_baseball(outs="1", away_innings=away, home_innings=home), "t")
        result = ingestion.get_sport_data("Baseball")
        assert result["half"] == "BOT"
        assert result["inning"] == 2

    def test_bootstrap_mid_game_outs_3(self):
        """Cold start mid-game with outs=3 and away ahead → MID."""
        away = ["3", " ", " ", " ", " ", " ", " ", " ", " ", " "]
        home = [" ", " ", " ", " ", " ", " ", " ", " ", " ", " "]
        ingestion.record_packet("Baseball", _base_baseball(outs="3", away_innings=away, home_innings=home), "t")
        result = ingestion.get_sport_data("Baseball")
        assert result["half"] == "MID"
        assert result["inning"] == 1

    def test_reset_clears_state(self):
        """reset_baseball_state() returns to TOP 1."""
        ingestion.record_packet("Baseball", _base_baseball(outs="3"), "t")
        ingestion.reset_baseball_state()
        ingestion.record_packet("Baseball", _base_baseball(outs="0"), "t")
        result = ingestion.get_sport_data("Baseball")
        assert result["half"] == "TOP"
        assert result["inning"] == 1


class TestOrdinal:
    def test_ordinals(self):
        assert ingestion._ordinal(1) == "1st"
        assert ingestion._ordinal(2) == "2nd"
        assert ingestion._ordinal(3) == "3rd"
        assert ingestion._ordinal(4) == "4th"
        assert ingestion._ordinal(9) == "9th"
        assert ingestion._ordinal(11) == "11th"
        assert ingestion._ordinal(12) == "12th"
        assert ingestion._ordinal(13) == "13th"
        assert ingestion._ordinal(21) == "21st"
