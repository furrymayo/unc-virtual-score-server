import time

from website import ingestion
from website.protocol import (
    STX,
    CR,
    TP_VOLLEYBALL,
    TP_BBALL_BASE_SOFT,
    TP_LACROSSE_FH,
    BBALL_LEN,
    LAX_LEN,
)


def _reset_ingestion_state():
    """Clear shared state between tests."""
    with ingestion.parsed_data_lock:
        for key in ingestion.parsed_data:
            ingestion.parsed_data[key] = {}
        ingestion.parsed_data_by_source.clear()
        ingestion.last_seen_by_source.clear()
        ingestion._auto_sticky_source.clear()
        ingestion._clock_snapshots.clear()
        ingestion._clock_seq = 0
    ingestion.reset_baseball_state()
    with ingestion.data_sources_lock:
        ingestion.data_sources.clear()
    with ingestion._sse_connection_lock:
        ingestion._sse_connection_count = 0


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

    def test_get_sources_snapshot_name_fallback(self):
        """Sources without a configured name fall back to source_id."""
        ingestion.record_packet("Hockey", {"home_score": "3"}, "udp:10.0.0.1:5000")
        sources = ingestion.get_sources_snapshot()
        assert len(sources) == 1
        assert sources[0]["name"] == "udp:10.0.0.1:5000"

    def test_get_sources_snapshot_name_from_config(self):
        """Sources with a configured name show the friendly name."""
        with ingestion.data_sources_lock:
            ingestion.data_sources.append(
                {"id": "tcp:10.0.0.1:4000", "name": "Kenan Stadium", "host": "10.0.0.1", "port": 4000, "enabled": True, "sport_overrides": {}}
            )
        ingestion.record_packet("Football", {"home_score": "7"}, "tcp:10.0.0.1:4000")
        sources = ingestion.get_sources_snapshot()
        assert len(sources) == 1
        assert sources[0]["name"] == "Kenan Stadium"


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

    def test_lacrosse_override_to_gymnastics(self):
        with ingestion.data_sources_lock:
            ingestion.data_sources.append(
                {
                    "id": "tcp:10.0.0.9:9999",
                    "name": "Gym Venue",
                    "host": "10.0.0.9",
                    "port": 9999,
                    "enabled": True,
                    "sport_overrides": {"Lacrosse": "Gymnastics"},
                }
            )

        pkt = [0x30] * LAX_LEN
        pkt[0] = STX
        pkt[1] = TP_LACROSSE_FH
        pkt[-1] = CR

        ingestion.handle_serial_packet(pkt, source_id="tcp:10.0.0.9:9999")
        gym = ingestion.get_sport_data("Gymnastics")
        assert gym.get("game_clock") is not None
        assert ingestion.get_sport_data("Lacrosse") == {}


# --- Baseball inning state machine tests ---


def _base_baseball(outs="0", away_innings=None, home_innings=None):
    """Helper: minimal baseball parsed dict."""
    return {
        "away_innings": away_innings or [" "] * 10,
        "home_innings": home_innings or [" "] * 10,
        "balls": "0",
        "strikes": "0",
        "outs": outs,
        "batter_num": " 1",
        "pitch_speed": "000",
        "away_runs": " 0",
        "away_hits": " 0",
        "away_errors": " 0",
        "home_runs": " 0",
        "home_hits": " 0",
        "home_errors": " 0",
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
        ingestion.record_packet(
            "Baseball",
            _base_baseball(outs="1", away_innings=away, home_innings=home),
            "t",
        )
        result = ingestion.get_sport_data("Baseball")
        assert result["half"] == "BOT"
        assert result["inning"] == 2

    def test_bootstrap_mid_game_outs_3(self):
        """Cold start mid-game with outs=3 and away ahead → MID."""
        away = ["3", " ", " ", " ", " ", " ", " ", " ", " ", " "]
        home = [" ", " ", " ", " ", " ", " ", " ", " ", " ", " "]
        ingestion.record_packet(
            "Baseball",
            _base_baseball(outs="3", away_innings=away, home_innings=home),
            "t",
        )
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


class TestAutoSourceStickiness:
    """Auto mode should stick to one source when multiple broadcast the same sport."""

    def setup_method(self):
        _reset_ingestion_state()

    def test_auto_sticks_to_first_source(self):
        """Once Auto locks onto a source, it stays there despite newer packets."""
        ingestion.record_packet("Basketball", {"home_score": "10"}, "src:mens")
        ingestion.record_packet("Basketball", {"home_score": "20"}, "src:womens")

        # Auto should pick womens (most recent) as sticky source
        result = ingestion.get_sport_data("Basketball")
        locked_score = result["home_score"]

        # Now the other source sends newer data
        if locked_score == "20":
            ingestion.record_packet("Basketball", {"home_score": "11"}, "src:mens")
        else:
            ingestion.record_packet("Basketball", {"home_score": "21"}, "src:womens")

        # Auto should still return the sticky source's data
        result2 = ingestion.get_sport_data("Basketball")
        assert result2["home_score"] == locked_score

    def test_auto_switches_when_sticky_stale(self):
        """When the sticky source goes stale, Auto picks the freshest."""
        ingestion.record_packet("Basketball", {"home_score": "10"}, "src:mens")

        # Lock onto mens
        result = ingestion.get_sport_data("Basketball")
        assert result["home_score"] == "10"

        # Make mens source stale by backdating its timestamp
        with ingestion.parsed_data_lock:
            ingestion.last_seen_by_source["src:mens"] = time.time() - 30

        # Now womens sends data
        ingestion.record_packet("Basketball", {"home_score": "20"}, "src:womens")

        # Auto should switch to womens
        result2 = ingestion.get_sport_data("Basketball")
        assert result2["home_score"] == "20"

    def test_explicit_source_bypasses_stickiness(self):
        """Explicit source_id always returns that source's data."""
        ingestion.record_packet("Basketball", {"home_score": "10"}, "src:mens")
        ingestion.record_packet("Basketball", {"home_score": "20"}, "src:womens")

        # Lock auto onto one source
        ingestion.get_sport_data("Basketball")

        # Explicit source always works regardless of stickiness
        mens = ingestion.get_sport_data("Basketball", source_id="src:mens")
        womens = ingestion.get_sport_data("Basketball", source_id="src:womens")
        assert mens["home_score"] == "10"
        assert womens["home_score"] == "20"

    def test_stickiness_is_per_sport(self):
        """Stickiness for one sport doesn't affect another."""
        ingestion.record_packet("Basketball", {"home_score": "10"}, "src:A")
        ingestion.record_packet("Lacrosse", {"home_score": "5"}, "src:B")

        bball = ingestion.get_sport_data("Basketball")
        lax = ingestion.get_sport_data("Lacrosse")
        assert bball["_meta"]["source"] == "src:A"
        assert lax["_meta"]["source"] == "src:B"

    def test_single_source_no_issue(self):
        """With only one source, stickiness is transparent."""
        ingestion.record_packet("Basketball", {"home_score": "10"}, "src:only")
        result = ingestion.get_sport_data("Basketball")
        assert result["home_score"] == "10"

        ingestion.record_packet("Basketball", {"home_score": "15"}, "src:only")
        result2 = ingestion.get_sport_data("Basketball")
        assert result2["home_score"] == "15"


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


class TestClockPubSub:
    def setup_method(self):
        _reset_ingestion_state()

    def test_clock_snapshot_created_for_basketball(self):
        """record_packet creates a clock snapshot for clock sports."""
        ingestion.record_packet(
            "Basketball", {"game_clock": "12:00", "shot_clock": "30", "period": "1", "home_score": "10"}, "t"
        )
        snap = ingestion.get_clock_snapshot("Basketball")
        assert snap is not None
        assert snap["game_clock"] == "12:00"
        assert snap["shot_clock"] == "30"
        assert snap["period"] == "1"
        # Non-clock fields should not be in snapshot
        assert "home_score" not in snap

    def test_no_clock_snapshot_for_baseball(self):
        """record_packet does NOT create clock snapshot for non-clock sports."""
        ingestion.record_packet("Baseball", _base_baseball(outs="0"), "t")
        snap = ingestion.get_clock_snapshot("Baseball")
        assert snap is None

    def test_clock_seq_increments_on_change(self):
        """_clock_seq increments when clock data changes."""
        ingestion.record_packet(
            "Basketball", {"game_clock": "12:00", "shot_clock": "30", "period": "1"}, "t"
        )
        seq1 = ingestion.get_clock_seq()
        assert seq1 > 0

        ingestion.record_packet(
            "Basketball", {"game_clock": "11:59", "shot_clock": "29", "period": "1"}, "t"
        )
        seq2 = ingestion.get_clock_seq()
        assert seq2 > seq1

    def test_clock_seq_no_increment_on_identical(self):
        """_clock_seq does NOT increment when clock data is identical."""
        ingestion.record_packet(
            "Basketball", {"game_clock": "12:00", "shot_clock": "30", "period": "1"}, "t"
        )
        seq1 = ingestion.get_clock_seq()

        ingestion.record_packet(
            "Basketball", {"game_clock": "12:00", "shot_clock": "30", "period": "1"}, "t"
        )
        seq2 = ingestion.get_clock_seq()
        assert seq2 == seq1

    def test_sse_connection_limit(self):
        """SSE connection counter enforces max limit."""
        for _ in range(ingestion.SSE_MAX_CONNECTIONS):
            assert ingestion.sse_connection_acquire() is True
        # Next one should be rejected
        assert ingestion.sse_connection_acquire() is False
        # Release one and try again
        ingestion.sse_connection_release()
        assert ingestion.sse_connection_acquire() is True
