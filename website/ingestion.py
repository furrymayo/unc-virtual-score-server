import json
import os
import socket
import threading
import time

import serial
import serial.tools.list_ports

from .config import CONFIG
from .protocol import PacketStreamParser, identify_and_parse

# --- Environment config ---

DEFAULT_TCP_PORT = CONFIG.scoreboard_tcp_port
DEFAULT_UDP_PORT = CONFIG.scoreboard_udp_port
DATA_SOURCES_FILE = CONFIG.scoreboard_sources_file

# --- Shared state ---

parsed_data = {
    "Basketball": {},
    "Hockey": {},
    "Lacrosse": {},
    "Football": {},
    "Volleyball": {},
    "Wrestling": {},
    "Track": {},
    "Soccer": {},
    "Softball": {},
    "Baseball": {},
    "Gymnastics": {},
}

parsed_data_by_source = {}
last_seen_by_source = {}
parsed_data_lock = threading.Lock()

SUPPORTED_SPORTS = set(parsed_data.keys())

# --- Accessor functions ---

_STALE_TTL = 3600  # 1 hour


# --- Baseball inning state machine ---
#
# The OES controller reports blank (not "0") for half-innings where no runs
# have been scored.  This makes line-score counting unreliable for determining
# TOP/BOT.  Instead we track outs transitions:
#   TOP  ──outs==3──▸ MID  ──outs<3──▸ BOT  ──outs==3──▸ END  ──outs<3──▸ TOP(+1)

_baseball_states = {}


def _get_baseball_state(source_id):
    """Return (creating if needed) the baseball state for a given source."""
    key = source_id or "__default__"
    if key not in _baseball_states:
        _baseball_states[key] = {
            "half": "TOP",
            "inning": 1,
            "prev_outs": None,
            "initialized": False,
        }
    return _baseball_states[key]


def _ordinal(n):
    """Return ordinal string: 1 → '1st', 2 → '2nd', 11 → '11th', etc."""
    if 11 <= (n % 100) <= 13:
        return f"{n}th"
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _bootstrap_baseball_state(parsed):
    """Cold-start: best-guess inning state from line scores and outs."""
    away = parsed.get("away_innings", [])
    home = parsed.get("home_innings", [])
    filled = lambda v: v is not None and str(v).strip() != ""
    away_count = sum(1 for v in away if filled(v))
    home_count = sum(1 for v in home if filled(v))

    outs_raw = str(parsed.get("outs", "")).strip()
    outs = int(outs_raw) if outs_raw.isdigit() else 0

    if away_count > home_count:
        half = "MID" if outs == 3 else "BOT"
        inning = away_count
    else:
        inning = max(away_count + 1, 1)
        half = "MID" if outs == 3 else "TOP"

    return {"half": half, "inning": inning, "prev_outs": outs, "initialized": True}


def _update_baseball_inning(parsed, source_id):
    """Advance the baseball inning state machine.

    Must be called under parsed_data_lock.
    Returns (half, inning) where half is TOP/MID/BOT/END.
    """
    state = _get_baseball_state(source_id)

    outs_raw = str(parsed.get("outs", "")).strip()
    outs = int(outs_raw) if outs_raw.isdigit() else None

    if not state["initialized"]:
        bootstrapped = _bootstrap_baseball_state(parsed)
        state.update(bootstrapped)
    elif outs is not None:
        half = state["half"]
        inning = state["inning"]

        if outs == 3:
            # Half-inning just ended
            if half == "TOP":
                half = "MID"
            elif half == "BOT":
                half = "END"
        elif half in ("MID", "END"):
            # Outs < 3 while in a transition state → new half started
            if half == "MID":
                half = "BOT"
            else:  # END
                half = "TOP"
                inning += 1

        state["half"] = half
        state["inning"] = inning
        state["prev_outs"] = outs

    return state["half"], state["inning"]


def reset_baseball_state(source_id=None):
    """Reset the inning state machine (e.g. new game).

    If source_id given, reset that one source; if None, clear all.
    """
    with parsed_data_lock:
        if source_id is not None:
            _baseball_states.pop(source_id or "__default__", None)
        else:
            _baseball_states.clear()


def record_packet(sport, parsed, source_id):
    """Thread-safe: store a parsed packet in the global data stores."""
    received_at = time.time()
    if source_id is None:
        source_id = "unknown"

    with parsed_data_lock:
        if sport not in parsed_data:
            parsed_data[sport] = {}
        # Baseball inning enrichment
        if sport == "Baseball":
            half, inning = _update_baseball_inning(parsed, source_id)
            parsed = {
                **parsed,
                "inning": inning,
                "half": half,
                "inning_display": f"{half} {_ordinal(inning)}",
            }

        parsed_with_meta = {
            **parsed,
            "_meta": {
                "source": source_id,
                "received_at": received_at,
            },
        }

        parsed_data[sport] = parsed_with_meta
        parsed_data_by_source.setdefault(source_id, {})[sport] = parsed_with_meta
        last_seen_by_source[source_id] = received_at


def get_sport_data(sport, source_id=None):
    """Thread-safe: retrieve latest data for a sport."""
    with parsed_data_lock:
        if source_id:
            return dict(parsed_data_by_source.get(source_id, {}).get(sport, {}))
        return dict(parsed_data.get(sport, {}))


def get_sources_snapshot():
    """Thread-safe: return list of source info dicts.

    Includes a friendly ``name`` for each source by cross-referencing the
    configured ``data_sources`` list.  Lock ordering: ``data_sources_lock``
    first, then ``parsed_data_lock`` (no existing code acquires them in
    reverse order).
    """
    now = time.time()
    with data_sources_lock:
        name_by_id = {s["id"]: s.get("name", s["id"]) for s in data_sources}
    with parsed_data_lock:
        return [
            {
                "source": source_id,
                "name": name_by_id.get(source_id, source_id),
                "last_seen": last_seen,
                "age_seconds": round(now - last_seen, 3),
                "sports": list(parsed_data_by_source.get(source_id, {}).keys()),
            }
            for source_id, last_seen in last_seen_by_source.items()
        ]


def purge_stale_sources():
    """Remove sources not seen within _STALE_TTL seconds."""
    cutoff = time.time() - _STALE_TTL
    with parsed_data_lock:
        stale = [sid for sid, ts in last_seen_by_source.items() if ts < cutoff]
        for sid in stale:
            last_seen_by_source.pop(sid, None)
            parsed_data_by_source.pop(sid, None)


# --- handle_serial_packet ---


def handle_serial_packet(packet, source_id=None):
    sport, parsed = identify_and_parse(packet)
    if sport and parsed is not None:
        sport, parsed = _apply_sport_overrides(sport, parsed, source_id)
        record_packet(sport, parsed, source_id)


# --- Serial reader ---

_serial_stop_event = threading.Event()
_serial_thread = None


def serial_port_reader(port, stop_event):
    try:
        ser = serial.Serial(port, 9600, timeout=1)
    except Exception as exc:
        print(f"Failed to open serial port {port}: {exc}")
        return

    parser = PacketStreamParser()

    try:
        while not stop_event.is_set():
            try:
                raw = ser.read(256)
            except Exception as exc:
                print(f"Serial read error: {exc}")
                break

            if not raw:
                continue

            for packet in parser.feed_bytes(raw):
                handle_serial_packet(packet, source_id=f"serial:{port}")
    finally:
        try:
            ser.close()
        except Exception:
            pass


def start_serial_reader(port):
    global _serial_thread
    stop_serial_reader()
    _serial_stop_event.clear()
    _serial_thread = threading.Thread(
        target=serial_port_reader, args=(port, _serial_stop_event), daemon=True
    )
    _serial_thread.start()


def stop_serial_reader():
    global _serial_thread
    if _serial_thread is not None:
        _serial_stop_event.set()
        _serial_thread.join(timeout=2)
        _serial_thread = None


# --- TCP client (outbound connections to OES controllers) ---

tcp_client_threads = {}
tcp_client_events = {}
tcp_clients_lock = threading.Lock()


def tcp_client_worker(source):
    source_id = source["id"]
    host = source["host"]
    port = source["port"]

    stop_event = tcp_client_events[source_id]
    parser = PacketStreamParser()
    backoff = 1.0

    while not stop_event.is_set():
        conn = None
        try:
            conn = socket.create_connection((host, port), timeout=5)
            conn.settimeout(1.0)
            print(f"Connected to TCP source {source_id}")
            backoff = 1.0

            while not stop_event.is_set():
                try:
                    data = conn.recv(4096)
                except socket.timeout:
                    continue
                except Exception as exc:
                    print(f"TCP read error from {source_id}: {exc}")
                    break

                if not data:
                    break

                for packet in parser.feed_bytes(data):
                    handle_serial_packet(packet, source_id=source_id)
        except Exception as exc:
            print(f"TCP connect error for {source_id}: {exc}")
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

        if stop_event.is_set():
            break

        if stop_event.wait(backoff):
            break
        backoff = min(backoff * 2, 10.0)


def start_tcp_client(source):
    source_id = source["id"]
    with tcp_clients_lock:
        if source_id in tcp_client_threads:
            return
        stop_event = threading.Event()
        tcp_client_events[source_id] = stop_event
        thread = threading.Thread(target=tcp_client_worker, args=(source,), daemon=True)
        tcp_client_threads[source_id] = thread
        thread.start()


def stop_tcp_client(source_id):
    with tcp_clients_lock:
        event = tcp_client_events.pop(source_id, None)
        thread = tcp_client_threads.pop(source_id, None)
    if event:
        event.set()
    if thread:
        thread.join(timeout=2)


# --- Network listeners (inbound TCP server + UDP) ---

_network_stop_event = threading.Event()
_tcp_thread = None
_udp_thread = None
_tcp_server_socket = None
_udp_socket = None


def udp_listener(port, stop_event):
    global _udp_socket
    parser = PacketStreamParser()

    try:
        _udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        _udp_socket.bind(("0.0.0.0", port))
        _udp_socket.settimeout(1.0)
        print(f"UDP listener bound to 0.0.0.0:{port}")
    except Exception as exc:
        print(f"Failed to start UDP listener on {port}: {exc}")
        return

    try:
        while not stop_event.is_set():
            try:
                data, _addr = _udp_socket.recvfrom(4096)
            except socket.timeout:
                continue
            except Exception as exc:
                print(f"UDP receive error: {exc}")
                break

            for packet in parser.feed_bytes(data):
                handle_serial_packet(packet, source_id=f"udp:{_addr[0]}:{_addr[1]}")
    finally:
        try:
            _udp_socket.close()
        except Exception:
            pass


def tcp_connection_reader(conn, addr, stop_event):
    parser = PacketStreamParser()
    conn.settimeout(1.0)
    try:
        while not stop_event.is_set():
            try:
                data = conn.recv(4096)
            except socket.timeout:
                continue
            except Exception as exc:
                print(f"TCP read error from {addr}: {exc}")
                break

            if not data:
                break

            for packet in parser.feed_bytes(data):
                handle_serial_packet(packet, source_id=f"tcp:{addr[0]}:{addr[1]}")
    finally:
        try:
            conn.close()
        except Exception:
            pass


def tcp_listener(port, stop_event):
    global _tcp_server_socket

    try:
        _tcp_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        _tcp_server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        _tcp_server_socket.bind(("0.0.0.0", port))
        _tcp_server_socket.listen(5)
        _tcp_server_socket.settimeout(1.0)
        print(f"TCP listener bound to 0.0.0.0:{port}")
    except Exception as exc:
        print(f"Failed to start TCP listener on {port}: {exc}")
        return

    try:
        while not stop_event.is_set():
            try:
                conn, addr = _tcp_server_socket.accept()
            except socket.timeout:
                continue
            except Exception as exc:
                print(f"TCP accept error: {exc}")
                break

            thread = threading.Thread(
                target=tcp_connection_reader, args=(conn, addr, stop_event), daemon=True
            )
            thread.start()
    finally:
        try:
            _tcp_server_socket.close()
        except Exception:
            pass


def start_network_listeners(tcp_port, udp_port, mode):
    global _tcp_thread, _udp_thread
    _network_stop_event.clear()

    if mode in {"tcp", "auto"}:
        _tcp_thread = threading.Thread(
            target=tcp_listener, args=(tcp_port, _network_stop_event), daemon=True
        )
        _tcp_thread.start()

    if mode in {"udp", "auto"}:
        _udp_thread = threading.Thread(
            target=udp_listener, args=(udp_port, _network_stop_event), daemon=True
        )
        _udp_thread.start()


def stop_network_listeners():
    global _tcp_thread, _udp_thread, _tcp_server_socket, _udp_socket
    _network_stop_event.set()

    if _tcp_server_socket is not None:
        try:
            _tcp_server_socket.close()
        except Exception:
            pass
        _tcp_server_socket = None

    if _udp_socket is not None:
        try:
            _udp_socket.close()
        except Exception:
            pass
        _udp_socket = None

    if _tcp_thread is not None:
        _tcp_thread.join(timeout=2)
        _tcp_thread = None

    if _udp_thread is not None:
        _udp_thread.join(timeout=2)
        _udp_thread = None


# --- Data source management ---

data_sources_lock = threading.Lock()
data_sources = []


def _normalize_sport_name(value):
    if value is None:
        return None
    name = str(value).strip()
    if not name:
        return None
    normalized = name.title()
    if normalized in SUPPORTED_SPORTS:
        return normalized
    return None


def normalize_sport_overrides(overrides):
    if not overrides:
        return {}
    if not isinstance(overrides, dict):
        return {}

    normalized = {}
    for raw_from, raw_to in overrides.items():
        from_sport = _normalize_sport_name(raw_from)
        to_sport = _normalize_sport_name(raw_to)
        if from_sport and to_sport:
            normalized[from_sport] = to_sport
    return normalized


def _get_source_override(source_id, sport):
    if not source_id or not sport:
        return None
    with data_sources_lock:
        for source in data_sources:
            if source.get("id") == source_id:
                overrides = source.get("sport_overrides", {})
                return overrides.get(sport)
    return None


def _apply_sport_overrides(sport, parsed, source_id):
    override = _get_source_override(source_id, sport)
    if not override:
        return sport, parsed

    if override == "Gymnastics" and sport == "Lacrosse":
        parsed = {"game_clock": parsed.get("game_clock")}

    return override, parsed


def _normalize_source_entry(entry):
    if not isinstance(entry, dict):
        return None
    source_id = entry.get("id")
    host = entry.get("host")
    port = entry.get("port")
    sport_overrides = normalize_sport_overrides(entry.get("sport_overrides"))

    if not source_id or not host or not port:
        return None

    try:
        port = int(port)
    except (TypeError, ValueError):
        return None

    name = entry.get("name") or source_id
    enabled = bool(entry.get("enabled", True))

    return {
        "id": str(source_id),
        "name": str(name),
        "host": str(host),
        "port": port,
        "enabled": enabled,
        "sport_overrides": sport_overrides,
    }


def _load_data_sources():
    if not os.path.exists(DATA_SOURCES_FILE):
        return []
    try:
        with open(DATA_SOURCES_FILE, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except Exception as exc:
        print(f"Failed to read {DATA_SOURCES_FILE}: {exc}")
        return []

    if not isinstance(raw, list):
        return []

    normalized = []
    for entry in raw:
        normalized_entry = _normalize_source_entry(entry)
        if normalized_entry:
            normalized.append(normalized_entry)
    return normalized


def _save_data_sources():
    with data_sources_lock:
        payload = list(data_sources)
    try:
        with open(DATA_SOURCES_FILE, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
    except Exception as exc:
        print(f"Failed to write {DATA_SOURCES_FILE}: {exc}")


def _make_source_id(host, port):
    return f"tcp:{host}:{port}"


def _make_unique_source_id(host, port):
    """Generate a unique source ID, appending :2, :3, etc. if the base ID is taken."""
    base_id = _make_source_id(host, port)
    existing_ids = {source["id"] for source in data_sources}
    if base_id not in existing_ids:
        return base_id
    suffix = 2
    while f"{base_id}:{suffix}" in existing_ids:
        suffix += 1
    return f"{base_id}:{suffix}"


def start_configured_sources():
    global data_sources
    loaded = _load_data_sources()
    with data_sources_lock:
        data_sources = loaded

    for source in loaded:
        if source.get("enabled", True):
            start_tcp_client(source)


def get_available_com_ports():
    return [port.device for port in serial.tools.list_ports.comports()]


# --- Stale source cleanup ---


def start_cleanup_thread(interval=300):
    """Daemon thread that purges stale sources every *interval* seconds."""

    def _loop():
        while True:
            time.sleep(interval)
            purge_stale_sources()

    thread = threading.Thread(target=_loop, daemon=True)
    thread.start()
    return thread
