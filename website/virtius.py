import json
import os
import threading
import time
import urllib.parse
import urllib.request


_SUPPORTED_SPORTS = {"Gymnastics"}
_CONFIG_FILE = "virtius_sources.json"
_DEFAULT_POLL_INTERVAL = 2.0
_LEADER_LIMIT = 6

virtius_config = {}
virtius_data = {}
virtius_lock = threading.Lock()
virtius_threads = {}
virtius_stop_events = {}


def _init_config():
    for sport in _SUPPORTED_SPORTS:
        if sport not in virtius_config:
            virtius_config[sport] = {
                "enabled": False,
                "session_url": "",
                "session_key": "",
                "poll_interval": _DEFAULT_POLL_INTERVAL,
            }
        if sport not in virtius_data:
            virtius_data[sport] = {}


_init_config()


def _extract_session_key(value):
    if not value:
        return ""
    raw = str(value).strip()
    if not raw:
        return ""

    parsed = urllib.parse.urlparse(raw)
    if parsed.scheme and parsed.netloc:
        params = urllib.parse.parse_qs(parsed.query)
        key = params.get("s", [""])[0]
        if key:
            return key
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) >= 2 and parts[0].lower() == "session":
            return parts[1]
    return raw


def _normalize_session_url(value):
    if not value:
        return "", ""
    raw = str(value).strip()
    if not raw:
        return "", ""

    key = _extract_session_key(raw)
    if not key:
        return "", ""

    parsed = urllib.parse.urlparse(raw)
    if not parsed.scheme:
        return f"https://virti.us/session?s={key}", key
    return raw, key


def normalize_sport(sport):
    if not sport:
        return None
    normalized = str(sport).strip().title()
    if normalized in _SUPPORTED_SPORTS:
        return normalized
    return None


def _load_config():
    if not os.path.exists(_CONFIG_FILE):
        return
    try:
        with open(_CONFIG_FILE, "r", encoding="utf-8") as handle:
            loaded = json.load(handle)
        if not isinstance(loaded, dict):
            return
    except Exception as exc:
        print(f"Failed to load Virtius config: {exc}")
        return

    with virtius_lock:
        for sport, cfg in loaded.items():
            if sport not in _SUPPORTED_SPORTS or not isinstance(cfg, dict):
                continue
            session_url, session_key = _normalize_session_url(
                cfg.get("session_url", "")
            )
            poll_interval = cfg.get("poll_interval", _DEFAULT_POLL_INTERVAL)
            try:
                poll_interval = float(poll_interval)
            except (TypeError, ValueError):
                poll_interval = _DEFAULT_POLL_INTERVAL

            virtius_config[sport] = {
                "enabled": bool(cfg.get("enabled", False)) and bool(session_key),
                "session_url": session_url,
                "session_key": session_key,
                "poll_interval": poll_interval,
            }


def _save_config():
    with virtius_lock:
        payload = {sport: dict(cfg) for sport, cfg in virtius_config.items()}
    try:
        with open(_CONFIG_FILE, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
    except Exception as exc:
        print(f"Failed to save Virtius config: {exc}")


def get_data(sport):
    with virtius_lock:
        return dict(virtius_data.get(sport, {}))


def get_config(sport):
    with virtius_lock:
        config = dict(virtius_config.get(sport, {}))
    config["running"] = sport in virtius_threads
    return config


def update_config(sport, payload):
    if sport not in _SUPPORTED_SPORTS:
        return {"error": "unsupported sport"}, 404

    with virtius_lock:
        current = dict(virtius_config.get(sport, {}))

    session_url = payload.get("session_url", current.get("session_url", ""))
    poll_interval = payload.get(
        "poll_interval", current.get("poll_interval", _DEFAULT_POLL_INTERVAL)
    )
    enabled = payload.get("enabled", current.get("enabled", False))

    session_url, session_key = _normalize_session_url(session_url)

    try:
        poll_interval = float(poll_interval)
    except (TypeError, ValueError):
        poll_interval = _DEFAULT_POLL_INTERVAL

    if poll_interval < 1.0:
        poll_interval = 1.0
    if poll_interval > 60.0:
        poll_interval = 60.0

    enabled = bool(enabled)

    if enabled and session_key:
        start_virtius_watcher(sport, session_key, poll_interval)
    else:
        stop_virtius_watcher(sport)
        enabled = False

    with virtius_lock:
        virtius_config[sport] = {
            "enabled": enabled,
            "session_url": session_url,
            "session_key": session_key,
            "poll_interval": poll_interval,
        }
        updated = dict(virtius_config[sport])

    _save_config()
    updated["running"] = sport in virtius_threads
    return updated, 200


def _normalize_event_name(name):
    if not name:
        return None
    upper = str(name).strip().upper()
    if "VAULT" in upper:
        return "VAULT"
    if "BAR" in upper:
        return "BARS"
    if "BEAM" in upper:
        return "BEAM"
    if "FLOOR" in upper:
        return "FLOOR"
    if "ALL" in upper and "AROUND" in upper:
        return "ALL_AROUND"
    if upper == "AA":
        return "ALL_AROUND"
    return None


def _parse_score(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _format_score(value):
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return f"{value:.3f}"
    text = str(value).strip()
    if not text:
        return ""
    try:
        return f"{float(text):.3f}"
    except ValueError:
        return text


def _event_in_progress(event):
    gymnasts = event.get("gymnasts", []) if isinstance(event, dict) else []
    for gymnast in gymnasts:
        score = gymnast.get("final_score") if isinstance(gymnast, dict) else None
        if score is None or str(score).strip() == "":
            return True
    return False


def _detect_current_rotation(teams):
    rotations = set()
    for team in teams:
        for event in team.get("events", []) if isinstance(team, dict) else []:
            rotation = event.get("rotation") if isinstance(event, dict) else None
            if rotation is not None:
                rotations.add(rotation)

    if not rotations:
        return None

    sorted_rotations = sorted(rotations)
    for rotation in sorted_rotations:
        for team in teams:
            for event in team.get("events", []) if isinstance(team, dict) else []:
                if event.get("rotation") == rotation and _event_in_progress(event):
                    return rotation
    return sorted_rotations[-1]


def _build_rotation_events(teams):
    rotation_events = {}
    for team in teams:
        team_key = team.get("tricode") or team.get("name") or "Team"
        for event in team.get("events", []) if isinstance(team, dict) else []:
            rotation = event.get("rotation") if isinstance(event, dict) else None
            event_code = _normalize_event_name(event.get("event_name"))
            if rotation is None or not event_code:
                continue
            rotation_events.setdefault(str(rotation), {})[team_key] = event_code
    return rotation_events


def _build_current_lineups(teams, current_rotation):
    lineups = {}
    if not current_rotation:
        return lineups

    for team in teams:
        if not isinstance(team, dict):
            continue
        team_id = team.get("team_id")
        team_key = str(team_id) if team_id is not None else None
        team_code = team.get("tricode") or team.get("name") or "Team"

        current_event = None
        current_event_obj = None
        for event in team.get("events", []) if isinstance(team, dict) else []:
            if event.get("rotation") != current_rotation:
                continue
            event_code = _normalize_event_name(event.get("event_name"))
            if not event_code or event_code == "ALL_AROUND":
                continue
            current_event = event_code
            current_event_obj = event
            break

        if not current_event_obj:
            continue

        gymnasts = []
        for gymnast in current_event_obj.get("gymnasts", []):
            if not isinstance(gymnast, dict):
                continue
            gymnast_type = gymnast.get("type")
            if gymnast_type is not None:
                try:
                    if int(gymnast_type) == 0:
                        continue
                except (TypeError, ValueError):
                    pass
            name = (
                gymnast.get("full_name")
                or " ".join(
                    filter(None, [gymnast.get("first_name"), gymnast.get("last_name")])
                ).strip()
            )
            if not name:
                name = "Gymnast"
            score = _format_score(gymnast.get("final_score"))
            order = gymnast.get("order")
            try:
                order_value = int(order)
            except (TypeError, ValueError):
                order_value = 999
            gymnasts.append(
                {
                    "name": name,
                    "score": score,
                    "order": order_value,
                }
            )

        gymnasts.sort(key=lambda g: g.get("order", 999))
        payload = {
            "event": current_event,
            "gymnasts": gymnasts,
        }

        if team_key:
            lineups[team_key] = payload
        if team_code:
            lineups[team_code] = payload

    return lineups


def _compute_all_around_leaders(teams, limit):
    gymnasts = {}

    for team in teams:
        if not isinstance(team, dict):
            continue
        team_code = (
            team.get("tricode") or team.get("short_name") or team.get("name") or ""
        )
        for event in team.get("events", []) if isinstance(team, dict) else []:
            if not isinstance(event, dict):
                continue
            event_code = _normalize_event_name(event.get("event_name"))
            if event_code not in {"VAULT", "BARS", "BEAM", "FLOOR"}:
                continue
            for gymnast in event.get("gymnasts", []) if isinstance(event, dict) else []:
                if not isinstance(gymnast, dict):
                    continue
                gymnast_type = gymnast.get("type")
                if gymnast_type is not None:
                    try:
                        if int(gymnast_type) == 0:
                            continue
                    except (TypeError, ValueError):
                        pass
                score = _parse_score(gymnast.get("final_score"))
                if score is None:
                    continue
                gymnast_id = gymnast.get("gymnast_id") or ""
                name = (
                    gymnast.get("full_name")
                    or " ".join(
                        filter(
                            None, [gymnast.get("first_name"), gymnast.get("last_name")]
                        )
                    ).strip()
                )
                if not name:
                    continue
                key = gymnast_id or f"{team_code}:{name}"

                entry = gymnasts.setdefault(
                    key,
                    {
                        "name": name,
                        "team": gymnast.get("tricode")
                        or gymnast.get("short_name")
                        or team_code,
                        "scores": {},
                    },
                )
                entry["scores"][event_code] = score

    results = []
    for entry in gymnasts.values():
        if len(entry["scores"]) < 4:
            continue
        total = sum(entry["scores"].values())
        results.append(
            {
                "name": entry["name"],
                "team": entry["team"],
                "score": _format_score(total),
                "place": None,
            }
        )

    results.sort(key=lambda item: _parse_score(item.get("score")) or 0, reverse=True)
    return results[:limit]


def _parse_virtius_json(payload):
    if not isinstance(payload, dict):
        return {}

    meet = payload.get("meet", {}) or {}
    teams_raw = meet.get("teams", []) if isinstance(meet, dict) else []
    event_results = meet.get("event_results", []) if isinstance(meet, dict) else []

    teams = []
    for team in teams_raw:
        if not isinstance(team, dict):
            continue
        event_scores = {}
        event_rotations = {}
        for event in team.get("events", []):
            if not isinstance(event, dict):
                continue
            event_code = _normalize_event_name(event.get("event_name"))
            if not event_code or event_code == "ALL_AROUND":
                continue
            event_scores[event_code] = _format_score(event.get("event_score"))
            event_rotations[event_code] = event.get("rotation")

        final_score = _parse_score(team.get("final_score"))
        if final_score is None:
            score_values = [
                score
                for score in (_parse_score(value) for value in event_scores.values())
                if score is not None
            ]
            total_score = _format_score(sum(score_values)) if score_values else ""
        else:
            total_score = _format_score(final_score)

        teams.append(
            {
                "id": team.get("team_id"),
                "name": team.get("name") or team.get("tricode") or "Team",
                "tricode": team.get("tricode") or "",
                "home": bool(team.get("home_team")),
                "place": team.get("place"),
                "score": total_score,
                "event_scores": event_scores,
                "event_rotations": event_rotations,
            }
        )

    rotation_events = _build_rotation_events(teams_raw)
    current_rotation = _detect_current_rotation(teams_raw)
    current_lineups = _build_current_lineups(teams_raw, current_rotation)

    leaders = {}
    for result in event_results:
        if not isinstance(result, dict):
            continue
        event_code = _normalize_event_name(result.get("event_name"))
        if not event_code:
            continue
        gymnasts = result.get("gymnasts", [])
        if not isinstance(gymnasts, list):
            continue
        sorted_gymnasts = sorted(
            gymnasts,
            key=lambda g: (
                int(g.get("place", 999)) if str(g.get("place", "")).isdigit() else 999
            ),
        )
        top = []
        for gymnast in sorted_gymnasts[:_LEADER_LIMIT]:
            if not isinstance(gymnast, dict):
                continue
            name = (
                gymnast.get("full_name")
                or " ".join(
                    filter(None, [gymnast.get("first_name"), gymnast.get("last_name")])
                ).strip()
            )
            if not name:
                name = "Gymnast"
            top.append(
                {
                    "name": name,
                    "score": _format_score(gymnast.get("final_score")),
                    "team": gymnast.get("tricode") or gymnast.get("short_name") or "",
                    "place": gymnast.get("place"),
                }
            )
        leaders[event_code] = top

    if len(leaders.get("ALL_AROUND", [])) < _LEADER_LIMIT:
        computed = _compute_all_around_leaders(teams_raw, _LEADER_LIMIT)
        if len(computed) > len(leaders.get("ALL_AROUND", [])):
            leaders["ALL_AROUND"] = computed

    for team in teams:
        team_key = str(team.get("id")) if team.get("id") is not None else None
        team_code = team.get("tricode") or team.get("name")
        lineup = None
        if team_key and team_key in current_lineups:
            lineup = current_lineups.get(team_key)
        elif team_code and team_code in current_lineups:
            lineup = current_lineups.get(team_code)
        if lineup:
            team["current_event"] = lineup.get("event")
            team["current_lineup"] = lineup.get("gymnasts")

    return {
        "meet": {
            "name": meet.get("name") if isinstance(meet, dict) else "",
            "location": meet.get("location") if isinstance(meet, dict) else "",
            "date_time": meet.get("date_time") if isinstance(meet, dict) else "",
        },
        "teams": teams,
        "current_rotation": current_rotation,
        "rotation_events": rotation_events,
        "leaders": leaders,
        "updated_at": time.time(),
    }


def _fetch_session_json(session_key):
    url = f"https://api.virti.us/session/{session_key}/json"
    request = urllib.request.Request(
        url,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        payload = response.read().decode("utf-8")
    return json.loads(payload)


def virtius_watcher(sport, session_key, poll_interval, stop_event):
    print(f"Virtius watcher started for {sport}: {session_key}")

    while not stop_event.is_set():
        try:
            raw = _fetch_session_json(session_key)
            parsed = _parse_virtius_json(raw)
            if parsed:
                parsed["_meta"] = {
                    "source": session_key,
                    "fetched_at": time.time(),
                }
                with virtius_lock:
                    virtius_data[sport] = parsed
        except Exception as exc:
            with virtius_lock:
                current = dict(virtius_data.get(sport, {}))
                meta = dict(current.get("_meta", {}))
                meta["error"] = str(exc)
                meta["error_at"] = time.time()
                current["_meta"] = meta
                virtius_data[sport] = current

        stop_event.wait(poll_interval)

    print(f"Virtius watcher stopped for {sport}")


def stop_virtius_watcher(sport):
    event = virtius_stop_events.get(sport)
    if event:
        event.set()
    thread = virtius_threads.get(sport)
    if thread:
        thread.join(timeout=2)
    virtius_stop_events.pop(sport, None)
    virtius_threads.pop(sport, None)


def start_virtius_watcher(sport, session_key, poll_interval=None):
    if poll_interval is None:
        poll_interval = _DEFAULT_POLL_INTERVAL

    stop_virtius_watcher(sport)

    stop_event = threading.Event()
    virtius_stop_events[sport] = stop_event
    thread = threading.Thread(
        target=virtius_watcher,
        args=(sport, session_key, poll_interval, stop_event),
        daemon=True,
    )
    virtius_threads[sport] = thread
    thread.start()


def start_configured_watchers():
    _load_config()
    with virtius_lock:
        configs = {sport: dict(cfg) for sport, cfg in virtius_config.items()}

    for sport, cfg in configs.items():
        if cfg.get("enabled") and cfg.get("session_key"):
            start_virtius_watcher(
                sport,
                cfg["session_key"],
                cfg.get("poll_interval", _DEFAULT_POLL_INTERVAL),
            )
