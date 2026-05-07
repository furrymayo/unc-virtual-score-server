"""Outbound WSS publisher → AWS edge service.

Off by default. Enabled by `CLOUD_RELAY_ENABLED=1`. Reads existing
in-memory state through the regular accessor functions; never modifies
any on-prem behavior, locks, or threads.

Wire protocol: see docs/plan.md and the edge repo's `edge/wire.py`.
Frames are state-replace, not events. The relay re-samples fresh state
every poll cycle and only emits a frame when the value differs from the
last one sent — so a slow socket can never replay a stale value once a
newer one is available.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any, Callable

from . import ingestion, statcrew, trackman, virtius
from .config import CONFIG

log = logging.getLogger(__name__)

PROTOCOL_VERSION = 1

RELAY_SPORTS: tuple[str, ...] = (
    "Basketball",
    "Hockey",
    "Lacrosse",
    "Football",
    "Volleyball",
    "Wrestling",
    "Soccer",
    "Softball",
    "Baseball",
    "Gymnastics",
)

# Per-kind sport coverage for optional payloads. The on-prem app only
# tracks these combinations; sampling the others would be wasted work.
PAYLOAD_KINDS: dict[str, tuple[str, ...]] = {
    "trackman": ("Baseball", "Softball"),
    "statcrew": RELAY_SPORTS,
    "virtius": ("Gymnastics",),
}

PAYLOAD_GETTERS: dict[str, Callable[[str], dict]] = {
    "trackman": trackman.get_data,
    "statcrew": statcrew.get_data,
    "virtius": virtius.get_data,
}


class CloudRelay:
    """Background WSS publisher.

    One thread owns the connection, the sampling loop, and the socket
    writes — so no write lock is needed. ``start()`` is idempotent;
    ``stop()`` joins the thread and closes the socket.
    """

    def __init__(self, config=CONFIG, ws_factory=None, sleep=None):
        self._config = config
        self._ws_factory = ws_factory or _default_ws_factory
        self._sleep = sleep or (lambda secs: self._stop.wait(secs))
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._ws_lock = threading.Lock()
        self._ws = None
        self._last_sent: dict[tuple[str, str | None], Any] = {}

    def start(self) -> None:
        if not self._config.cloud_relay_enabled:
            log.info("cloud relay disabled (CLOUD_RELAY_ENABLED=0)")
            return
        if not self._config.cloud_relay_url:
            log.warning("cloud relay enabled but CLOUD_RELAY_URL is empty; not starting")
            return
        if not self._config.cloud_relay_token:
            log.warning("cloud relay enabled but CLOUD_RELAY_TOKEN is empty; not starting")
            return
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="cloud-relay", daemon=True)
        self._thread.start()
        log.info("cloud relay started → %s", self._config.cloud_relay_url)

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        with self._ws_lock:
            ws = self._ws
        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None

    def _run(self) -> None:
        backoff = self._config.cloud_relay_reconnect_min
        while not self._stop.is_set():
            try:
                self._connect_and_pump()
                backoff = self._config.cloud_relay_reconnect_min
            except Exception as exc:  # noqa: BLE001 — log and retry
                log.warning("cloud relay session ended: %s", exc)
            if self._stop.is_set():
                break
            if self._sleep(backoff):
                break
            backoff = min(backoff * 2.0, self._config.cloud_relay_reconnect_max)

    def _connect_and_pump(self) -> None:
        ws = self._ws_factory(
            self._config.cloud_relay_url,
            self._config.cloud_relay_token,
            self._config.cloud_relay_publisher_name,
        )
        with self._ws_lock:
            self._ws = ws
        try:
            self._last_sent.clear()
            self._send_hello(ws)
            self._send_initial_state(ws)
            poll = max(0.05, float(self._config.cloud_relay_poll_interval))
            while not self._stop.is_set():
                if self._sleep(poll):
                    return
                self._tick(ws)
        finally:
            with self._ws_lock:
                self._ws = None
            try:
                ws.close()
            except Exception:
                pass

    def _send_hello(self, ws) -> None:
        self._send(ws, {
            "type": "hello",
            "publisher": self._config.cloud_relay_publisher_name,
            "version": PROTOCOL_VERSION,
        })

    def _send_initial_state(self, ws) -> None:
        sports_state = {}
        for sport in RELAY_SPORTS:
            data = ingestion.get_sport_data(sport)
            if data:
                sports_state[sport] = data
                self._last_sent[("sport", sport)] = data
        self._send(ws, {"type": "snapshot", "state": sports_state})

        for sport in RELAY_SPORTS:
            clock = ingestion.get_clock_snapshot(sport)
            if clock:
                self._send(ws, {"type": "clock", "sport": sport, "clock": clock})
                self._last_sent[("clock", sport)] = clock

        for kind, sports in PAYLOAD_KINDS.items():
            getter = PAYLOAD_GETTERS[kind]
            for sport in sports:
                payload = getter(sport)
                if payload:
                    self._send(ws, {"type": kind, "sport": sport, "payload": payload})
                    self._last_sent[(kind, sport)] = payload

        sources = ingestion.get_sources_snapshot()
        self._send(ws, {"type": "sources", "sources": sources})
        self._last_sent[("sources", None)] = sources

    def _tick(self, ws) -> None:
        for sport in RELAY_SPORTS:
            data = ingestion.get_sport_data(sport)
            if data and data != self._last_sent.get(("sport", sport)):
                self._send(ws, {"type": "sport", "sport": sport, "state": data})
                self._last_sent[("sport", sport)] = data

            clock = ingestion.get_clock_snapshot(sport)
            if clock and clock != self._last_sent.get(("clock", sport)):
                self._send(ws, {"type": "clock", "sport": sport, "clock": clock})
                self._last_sent[("clock", sport)] = clock

        for kind, sports in PAYLOAD_KINDS.items():
            getter = PAYLOAD_GETTERS[kind]
            for sport in sports:
                payload = getter(sport)
                if payload and payload != self._last_sent.get((kind, sport)):
                    self._send(ws, {"type": kind, "sport": sport, "payload": payload})
                    self._last_sent[(kind, sport)] = payload

        sources = ingestion.get_sources_snapshot()
        if sources != self._last_sent.get(("sources", None)):
            self._send(ws, {"type": "sources", "sources": sources})
            self._last_sent[("sources", None)] = sources

    @staticmethod
    def _send(ws, frame: dict[str, Any]) -> None:
        ws.send(json.dumps(frame, default=_json_default))


def _json_default(value):
    if isinstance(value, (set, frozenset)):
        return list(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    raise TypeError(f"unserializable: {type(value).__name__}")


def _default_ws_factory(url: str, token: str, publisher_name: str = ""):
    from websocket import create_connection

    headers = [f"X-Publisher-Auth: {token}"]
    if publisher_name:
        # The edge logs the publisher identity from this header, not the
        # hello frame. Without it auth.log entries arrive blank.
        headers.append(f"X-Publisher-Name: {publisher_name}")

    return create_connection(
        url,
        header=headers,
        timeout=10,
    )


_relay: CloudRelay | None = None
_relay_lock = threading.Lock()


def start_cloud_relay() -> CloudRelay | None:
    """Start the global relay if enabled. Safe no-op when disabled."""
    global _relay
    with _relay_lock:
        if not CONFIG.cloud_relay_enabled:
            return None
        if _relay is None:
            _relay = CloudRelay()
        _relay.start()
        return _relay


def stop_cloud_relay() -> None:
    global _relay
    with _relay_lock:
        if _relay is not None:
            _relay.stop()
            _relay = None
