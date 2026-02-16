import json
import socket
import threading
import time

# --- Shared state ---

_SUPPORTED_SPORTS = {"Baseball", "Softball"}

trackman_data = {
    "Baseball": {},
    "Softball": {},
}

trackman_debug = {
    "Baseball": {"raw": "", "error": ""},
    "Softball": {"raw": "", "error": ""},
}

trackman_config = {
    "Baseball": {"enabled": False, "port": 20998, "feed_type": "broadcast"},
    "Softball": {"enabled": False, "port": 20998, "feed_type": "broadcast"},
}

trackman_lock = threading.Lock()
trackman_threads = {}
trackman_stop_events = {}
trackman_sockets = {}
trackman_ports = {}

# --- Accessor functions ---


def get_data(sport):
    with trackman_lock:
        return dict(trackman_data.get(sport, {}))


def get_debug(sport):
    with trackman_lock:
        return {
            "raw": trackman_debug.get(sport, {}).get("raw"),
            "error": trackman_debug.get(sport, {}).get("error"),
            "parsed": dict(trackman_data.get(sport, {})),
        }


def get_config(sport):
    with trackman_lock:
        config = dict(trackman_config.get(sport, {}))
    config["running"] = sport in trackman_threads
    return config


def update_config(sport, payload):
    """Apply a config update. Returns (response_dict, status_code)."""
    with trackman_lock:
        current = dict(trackman_config.get(sport, {}))

    port = payload.get("port", current.get("port", 20998))
    feed_type = str(
        payload.get("feed_type", current.get("feed_type", "broadcast"))
    ).lower()
    enabled = payload.get("enabled", current.get("enabled", False))

    try:
        port = int(port)
    except (TypeError, ValueError):
        return {"error": "invalid port"}, 400

    if port < 1 or port > 65535:
        return {"error": "invalid port"}, 400

    if feed_type not in {"broadcast", "scoreboard"}:
        return {"error": "invalid feed type"}, 400

    enabled = bool(enabled)

    if enabled:
        for other_sport, other_port in trackman_ports.items():
            if other_sport != sport and other_port == port:
                return {"error": "port already in use"}, 409
        start_trackman_listener(sport, port)
    else:
        stop_trackman_listener(sport)

    with trackman_lock:
        trackman_config[sport] = {
            "enabled": enabled,
            "port": port,
            "feed_type": feed_type,
        }
        updated = dict(trackman_config[sport])
    updated["running"] = sport in trackman_threads

    return updated, 200


# --- Normalization ---


def normalize_sport(sport):
    if not sport:
        return None
    normalized = str(sport).strip().title()
    if normalized in _SUPPORTED_SPORTS:
        return normalized
    return None


# --- Parsers ---


def _parse_trackman_payload(payload):
    if not isinstance(payload, dict):
        return {}

    parsed = {}
    pitch = payload.get("Pitch")
    hit = payload.get("Hit")

    if isinstance(pitch, dict) or isinstance(hit, dict):
        parsed["feed_type"] = "broadcast"

        if isinstance(pitch, dict):
            parsed["pitch_speed"] = pitch.get("Speed")
            parsed["spin_rate"] = pitch.get("SpinRate")
            location = pitch.get("Location")
            if isinstance(location, dict):
                parsed["plate_x"] = location.get("X")
                parsed["plate_y"] = location.get("Y")
                parsed["plate_z"] = location.get("Z")

            parsed["time"] = parsed.get("time") or pitch.get("TrackStartTime")

        if isinstance(hit, dict):
            parsed["hit_exit_velocity"] = hit.get("Speed")
            parsed["hit_launch_angle"] = hit.get("Angle")
            parsed["hit_distance"] = hit.get("Distance")
            parsed["time"] = parsed.get("time") or hit.get("TrackStartTime")

        parsed["track_id"] = (
            payload.get("PlayId") or payload.get("TrackId") or payload.get("Id")
        )
        parsed["time"] = parsed.get("time") or payload.get("Time")
        return {key: value for key, value in parsed.items() if value is not None}

    pitch_speed = payload.get("PitchExitSpeed")
    if pitch_speed is None:
        pitch_speed = payload.get("PitchReleaseSpeed")
    if pitch_speed is None:
        pitch_speed = payload.get("PitchSpeed")

    hit_speed = payload.get("HitSpeed")
    if hit_speed is None:
        hit_speed = payload.get("HitExitVelocity")

    if pitch_speed is not None:
        parsed["pitch_speed"] = pitch_speed
    if hit_speed is not None:
        parsed["hit_exit_velocity"] = hit_speed

    parsed["track_id"] = payload.get("Id") or payload.get("TrackId")
    parsed["time"] = payload.get("Time")
    parsed["feed_type"] = "scoreboard"

    return {key: value for key, value in parsed.items() if value is not None}


def _parse_trackman_json(raw_text):
    if not raw_text:
        return []

    raw_text = raw_text.strip()
    if not raw_text:
        return []

    try:
        parsed = json.loads(raw_text)
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)]
        if isinstance(parsed, dict):
            return [parsed]
    except Exception:
        pass

    payloads = []
    for line in raw_text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed_line = json.loads(line)
            if isinstance(parsed_line, dict):
                payloads.append(parsed_line)
        except Exception:
            continue

    if payloads:
        return payloads

    start = raw_text.find("{")
    end = raw_text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            parsed = json.loads(raw_text[start : end + 1])
            if isinstance(parsed, dict):
                return [parsed]
        except Exception:
            pass

    return []


# --- Listener ---


def trackman_listener(sport, port, stop_event):
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("0.0.0.0", port))
        sock.settimeout(1.0)
        trackman_sockets[sport] = sock
        print(f"Trackman listener bound to 0.0.0.0:{port} for {sport}")
    except Exception as exc:
        print(f"Failed to start Trackman listener on {port} for {sport}: {exc}")
        return

    try:
        while not stop_event.is_set():
            try:
                raw, _addr = sock.recvfrom(8192)
            except socket.timeout:
                continue
            except Exception as exc:
                print(f"Trackman receive error ({sport}): {exc}")
                break

            if not raw:
                continue

            try:
                raw_text = raw.decode("utf-8", errors="ignore")
            except Exception:
                raw_text = ""

            with trackman_lock:
                trackman_debug[sport]["raw"] = raw_text or ""
                trackman_debug[sport]["error"] = ""

            payloads = _parse_trackman_json(raw_text or "")
            if not payloads:
                with trackman_lock:
                    trackman_debug[sport]["error"] = "unable to parse json"
                continue

            parsed_packet = None
            for payload in payloads:
                parsed = _parse_trackman_payload(payload)
                if parsed:
                    parsed_packet = parsed

            if not parsed_packet:
                with trackman_lock:
                    trackman_debug[sport]["error"] = "no supported fields"
                continue

            parsed_with_meta = {
                **parsed_packet,
                "_meta": {
                    "source": f"udp:{port}",
                    "received_at": time.time(),
                },
            }

            with trackman_lock:
                trackman_data[sport] = parsed_with_meta
    finally:
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass


def stop_trackman_listener(sport):
    event = trackman_stop_events.get(sport)
    if event:
        event.set()
    thread = trackman_threads.get(sport)
    if thread:
        thread.join(timeout=2)
    trackman_stop_events.pop(sport, None)
    trackman_threads.pop(sport, None)
    sock = trackman_sockets.pop(sport, None)
    if sock:
        try:
            sock.close()
        except Exception:
            pass
    trackman_ports.pop(sport, None)


def start_trackman_listener(sport, port):
    stop_trackman_listener(sport)
    stop_event = threading.Event()
    trackman_stop_events[sport] = stop_event
    thread = threading.Thread(
        target=trackman_listener, args=(sport, port, stop_event), daemon=True
    )
    trackman_threads[sport] = thread
    trackman_ports[sport] = port
    thread.start()
