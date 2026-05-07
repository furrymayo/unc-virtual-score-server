"""Cloud relay tests — no real network.

The relay accepts dependency-injected ``ws_factory`` and ``sleep``, so we
exercise the connect/snapshot/tick logic against a fake websocket and a
deterministic sleep.
"""
from __future__ import annotations

import json
import threading
from dataclasses import replace

import pytest

from website import cloud_relay, ingestion, statcrew, trackman, virtius
from website.config import CONFIG


# --- Fake websocket -------------------------------------------------------


class FakeWS:
    def __init__(self):
        self.sent: list[dict] = []
        self.closed = False
        self._send_raises_after: int | None = None

    def send(self, frame: str) -> None:
        if self._send_raises_after is not None and len(self.sent) >= self._send_raises_after:
            raise ConnectionError("simulated disconnect")
        self.sent.append(json.loads(frame))

    def close(self) -> None:
        self.closed = True


def _make_factory(*sockets: FakeWS):
    """Return a factory that yields the given fake sockets in order, recording
    auth headers."""
    sockets_iter = iter(sockets)
    calls: list[tuple[str, str, str]] = []

    def factory(url: str, token: str, publisher_name: str = "") -> FakeWS:
        calls.append((url, token, publisher_name))
        try:
            return next(sockets_iter)
        except StopIteration:
            raise RuntimeError("factory exhausted")

    factory.calls = calls  # type: ignore[attr-defined]
    return factory


def _enabled_config(**overrides):
    return replace(
        CONFIG,
        cloud_relay_enabled=True,
        cloud_relay_url="ws://test/ws/publisher",
        cloud_relay_token="secret",
        cloud_relay_publisher_name="onprem-test",
        cloud_relay_poll_interval=0.01,
        cloud_relay_reconnect_min=0.0,
        cloud_relay_reconnect_max=0.0,
        **overrides,
    )


# --- State helpers --------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_state():
    """Snapshot and restore the in-memory state these tests touch."""
    saved_parsed = {k: dict(v) for k, v in ingestion.parsed_data.items()}
    saved_by_source = {k: dict(v) for k, v in ingestion.parsed_data_by_source.items()}
    saved_seen = dict(ingestion.last_seen_by_source)
    saved_clocks = {k: dict(v) for k, v in ingestion._clock_snapshots.items()}
    saved_tm = {k: dict(v) for k, v in trackman.trackman_data.items()}
    saved_sc = {k: dict(v) for k, v in getattr(statcrew, "statcrew_data", {}).items()}
    saved_vt = {k: dict(v) for k, v in getattr(virtius, "virtius_data", {}).items()}
    yield
    ingestion.parsed_data.clear()
    ingestion.parsed_data.update(saved_parsed)
    ingestion.parsed_data_by_source.clear()
    ingestion.parsed_data_by_source.update(saved_by_source)
    ingestion.last_seen_by_source.clear()
    ingestion.last_seen_by_source.update(saved_seen)
    ingestion._clock_snapshots.clear()
    ingestion._clock_snapshots.update(saved_clocks)
    trackman.trackman_data.clear()
    trackman.trackman_data.update(saved_tm)
    if hasattr(statcrew, "statcrew_data"):
        statcrew.statcrew_data.clear()
        statcrew.statcrew_data.update(saved_sc)
    if hasattr(virtius, "virtius_data"):
        virtius.virtius_data.clear()
        virtius.virtius_data.update(saved_vt)


# --- Tests ----------------------------------------------------------------


def test_disabled_relay_does_not_start():
    cfg = replace(CONFIG, cloud_relay_enabled=False)
    relay = cloud_relay.CloudRelay(config=cfg, ws_factory=_make_factory())
    relay.start()
    assert relay._thread is None


def test_missing_url_or_token_does_not_start(caplog):
    cfg = replace(CONFIG, cloud_relay_enabled=True, cloud_relay_url="", cloud_relay_token="x")
    relay = cloud_relay.CloudRelay(config=cfg, ws_factory=_make_factory())
    relay.start()
    assert relay._thread is None

    cfg = replace(CONFIG, cloud_relay_enabled=True, cloud_relay_url="ws://x", cloud_relay_token="")
    relay = cloud_relay.CloudRelay(config=cfg, ws_factory=_make_factory())
    relay.start()
    assert relay._thread is None


def test_initial_state_sends_hello_snapshot_and_frames():
    ingestion.parsed_data["Basketball"] = {"home_score": "10", "away_score": "5"}
    ingestion._clock_snapshots["Basketball"] = {
        "game_clock": "8:23",
        "shot_clock": "14",
        "period": "2",
        "_seq": 1,
    }
    trackman.trackman_data["Baseball"] = {"speed": 92, "spin": 2300}
    ingestion.last_seen_by_source["src1"] = 1234.5
    ingestion.parsed_data_by_source["src1"] = {
        "Basketball": {"home_score": "10", "away_score": "5"},
    }

    ws = FakeWS()
    relay = cloud_relay.CloudRelay(
        config=_enabled_config(),
        ws_factory=_make_factory(ws),
    )

    relay._connect_and_pump_init = relay._send_initial_state  # readability
    # Drive the handshake without entering the poll loop.
    relay._send_hello(ws)
    relay._send_initial_state(ws)

    types = [f["type"] for f in ws.sent]
    assert types[0] == "hello"
    assert ws.sent[0]["publisher"] == "onprem-test"
    assert ws.sent[0]["version"] == cloud_relay.PROTOCOL_VERSION

    snapshot = next(f for f in ws.sent if f["type"] == "snapshot")
    assert snapshot["state"]["Basketball"] == {"home_score": "10", "away_score": "5"}
    # Sports with empty data are omitted from snapshot.
    assert "Football" not in snapshot["state"]

    clock_frames = [f for f in ws.sent if f["type"] == "clock"]
    assert len(clock_frames) == 1
    assert clock_frames[0]["sport"] == "Basketball"
    assert clock_frames[0]["clock"]["game_clock"] == "8:23"

    tm_frames = [f for f in ws.sent if f["type"] == "trackman"]
    assert len(tm_frames) == 1
    assert tm_frames[0]["sport"] == "Baseball"
    assert tm_frames[0]["payload"] == {"speed": 92, "spin": 2300}

    sources_frames = [f for f in ws.sent if f["type"] == "sources"]
    assert len(sources_frames) == 1
    assert sources_frames[0]["sources"][0]["source"] == "src1"


def test_tick_only_sends_changed_frames():
    ingestion.parsed_data["Basketball"] = {"home_score": "10"}
    ws = FakeWS()
    relay = cloud_relay.CloudRelay(config=_enabled_config(), ws_factory=_make_factory(ws))
    relay._send_initial_state(ws)
    initial = len(ws.sent)

    # No state change → tick emits nothing.
    relay._tick(ws)
    assert len(ws.sent) == initial

    # Change one sport → exactly one new frame.
    ingestion.parsed_data["Basketball"] = {"home_score": "11"}
    relay._tick(ws)
    assert len(ws.sent) == initial + 1
    assert ws.sent[-1] == {
        "type": "sport",
        "sport": "Basketball",
        "state": {"home_score": "11"},
    }

    # Tick again with no changes → still nothing.
    relay._tick(ws)
    assert len(ws.sent) == initial + 1


def test_full_run_loop_with_injected_sleep():
    """Drive the relay through one connect → one tick → stop."""
    ingestion.parsed_data["Basketball"] = {"home_score": "1"}
    ws = FakeWS()
    relay = cloud_relay.CloudRelay(
        config=_enabled_config(),
        ws_factory=_make_factory(ws),
    )

    sleep_calls = {"n": 0}

    def fake_sleep(_secs):
        sleep_calls["n"] += 1
        if sleep_calls["n"] == 1:
            # First sleep: let the tick run, then mutate state for it.
            ingestion.parsed_data["Basketball"] = {"home_score": "2"}
            return False  # don't stop
        relay._stop.set()
        return True  # stop

    relay._sleep = fake_sleep
    relay._run()

    types = [f["type"] for f in ws.sent]
    assert types.count("hello") == 1
    assert types.count("snapshot") == 1
    # The post-snapshot tick should have caught the score bump.
    sport_frames = [f for f in ws.sent if f["type"] == "sport"]
    assert any(f["state"] == {"home_score": "2"} for f in sport_frames)
    assert ws.closed is True


def test_reconnect_after_disconnect():
    ingestion.parsed_data["Basketball"] = {"home_score": "1"}
    ws1 = FakeWS()
    ws1._send_raises_after = 1  # disconnect right after `hello`
    ws2 = FakeWS()
    factory = _make_factory(ws1, ws2)

    relay = cloud_relay.CloudRelay(
        config=_enabled_config(),
        ws_factory=factory,
    )

    sleep_calls = {"n": 0}

    def fake_sleep(_secs):
        sleep_calls["n"] += 1
        # After the second connect's handshake completes, stop.
        if ws2.sent and any(f["type"] == "snapshot" for f in ws2.sent):
            relay._stop.set()
            return True
        return False

    relay._sleep = fake_sleep
    relay._run()

    assert len(factory.calls) == 2
    # Second socket must have received a fresh hello + snapshot.
    types = [f["type"] for f in ws2.sent]
    assert "hello" in types
    assert "snapshot" in types
    # Auth header carried the configured token.
    assert all(token == "secret" for _url, token in factory.calls)


def test_send_serializes_frame():
    ws = FakeWS()
    cloud_relay.CloudRelay._send(ws, {"type": "ping", "ts": 1.5})
    assert ws.sent == [{"type": "ping", "ts": 1.5}]
