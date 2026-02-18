import colorsys
import json
import os
import re
import threading
import time
import xml.etree.ElementTree as ET

# --- Shared state ---

_ALL_SPORTS = {
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
}

_CONFIG_FILE = "statcrew_sources.json"
_DEFAULT_POLL_INTERVAL = 2.0

statcrew_config = {}
statcrew_data = {}
statcrew_lock = threading.Lock()
statcrew_threads = {}
statcrew_stop_events = {}
statcrew_mtimes = {}


def _init_config():
    """Initialize config for all sports."""
    global statcrew_config, statcrew_data
    for sport in _ALL_SPORTS:
        if sport not in statcrew_config:
            statcrew_config[sport] = {
                "enabled": False,
                "file_path": "",
                "poll_interval": _DEFAULT_POLL_INTERVAL,
            }
        if sport not in statcrew_data:
            statcrew_data[sport] = {}


_init_config()


# --- NCAA Team Color Lookup ---

_AWAY_COLOR_FALLBACK = "#d46a6a"
_ncaa_teams = []


def _load_ncaa_colors():
    """Load NCAA team colors JSON once at module init."""
    global _ncaa_teams
    json_path = os.path.join(os.path.dirname(__file__), "ncaa_team_colors.json")
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            _ncaa_teams = json.load(f)
    except Exception as exc:
        print(f"Failed to load NCAA team colors: {exc}")
        _ncaa_teams = []


def _hex_to_hsl(hex_color):
    """Convert hex color to (h: 0-360, s: 0-1, l: 0-1)."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        return (0, 0, 0)
    r = int(hex_color[0:2], 16) / 255.0
    g = int(hex_color[2:4], 16) / 255.0
    b = int(hex_color[4:6], 16) / 255.0
    # colorsys uses HLS (not HSL) — returns (h, l, s)
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return (h * 360, s, l)


def _is_valid_away_color(hex_color):
    """Reject white (L>0.85), black (L<0.15), blue (H 170-260 with S>0.2)."""
    h, s, l = _hex_to_hsl(hex_color)
    if l > 0.85:
        return False  # too white
    if l < 0.15:
        return False  # too black
    if 170 <= h <= 260 and s > 0.2:
        return False  # too blue (conflicts with Carolina blue)
    return True


def _normalize_name(name):
    """Lowercase, strip periods, collapse whitespace."""
    name = name.lower().replace(".", "").strip()
    return re.sub(r"\s+", " ", name)


def _find_ncaa_team(away_name, away_code):
    """3-pass matching against NCAA team colors list."""
    if not away_name and not away_code:
        return None

    norm_name = _normalize_name(away_name) if away_name else ""
    norm_code = (away_code or "").lower().strip()

    # Pass 1: exact normalized name match
    for team in _ncaa_teams:
        if norm_name and _normalize_name(team["name"]) == norm_name:
            return team

    # Pass 2: StatCrew name is prefix of JSON name (word boundary)
    if norm_name:
        for team in _ncaa_teams:
            json_name = _normalize_name(team["name"])
            if json_name.startswith(norm_name + " ") or json_name == norm_name:
                return team

    # Pass 3: code matches slug prefix
    if norm_code:
        for team in _ncaa_teams:
            slug = team.get("slug", "")
            if slug.startswith(norm_code + "_") or slug == norm_code:
                return team

    return None


def lookup_away_team_color(away_name, away_code):
    """Find team, pick first valid color, fallback to #d46a6a."""
    team = _find_ncaa_team(away_name, away_code)
    if not team:
        return _AWAY_COLOR_FALLBACK
    for color in team.get("colors", []):
        if _is_valid_away_color(color):
            return color
    return _AWAY_COLOR_FALLBACK


_load_ncaa_colors()


# --- Config persistence ---


def _load_statcrew_config():
    """Load config from JSON file."""
    global statcrew_config
    if not os.path.exists(_CONFIG_FILE):
        return
    try:
        with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        if isinstance(loaded, dict):
            with statcrew_lock:
                for sport, cfg in loaded.items():
                    if sport in _ALL_SPORTS and isinstance(cfg, dict):
                        statcrew_config[sport] = {
                            "enabled": bool(cfg.get("enabled", False)),
                            "file_path": str(cfg.get("file_path", "")),
                            "poll_interval": float(
                                cfg.get("poll_interval", _DEFAULT_POLL_INTERVAL)
                            ),
                        }
    except Exception as exc:
        print(f"Failed to load statcrew config: {exc}")


def _save_statcrew_config():
    """Save config to JSON file."""
    with statcrew_lock:
        to_save = {sport: dict(cfg) for sport, cfg in statcrew_config.items()}
    try:
        with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(to_save, f, indent=2)
    except Exception as exc:
        print(f"Failed to save statcrew config: {exc}")


# --- Accessor functions ---


def get_data(sport):
    """Get parsed StatCrew data for a sport."""
    with statcrew_lock:
        return dict(statcrew_data.get(sport, {}))


def get_config(sport):
    """Get StatCrew config for a sport."""
    with statcrew_lock:
        config = dict(statcrew_config.get(sport, {}))
    config["running"] = sport in statcrew_threads
    return config


def update_config(sport, payload):
    """Apply a config update. Returns (response_dict, status_code)."""
    if sport not in _ALL_SPORTS:
        return {"error": "unsupported sport"}, 404

    with statcrew_lock:
        current = dict(statcrew_config.get(sport, {}))

    file_path = payload.get("file_path", current.get("file_path", ""))
    poll_interval = payload.get(
        "poll_interval", current.get("poll_interval", _DEFAULT_POLL_INTERVAL)
    )
    enabled = payload.get("enabled", current.get("enabled", False))

    # Validate poll_interval
    try:
        poll_interval = float(poll_interval)
    except (TypeError, ValueError):
        poll_interval = _DEFAULT_POLL_INTERVAL

    if poll_interval < 1.0:
        poll_interval = 1.0
    if poll_interval > 60.0:
        poll_interval = 60.0

    enabled = bool(enabled)
    file_path = str(file_path).strip()

    # Start or stop watcher based on enabled flag
    if enabled and file_path:
        start_statcrew_watcher(sport, file_path, poll_interval)
    else:
        stop_statcrew_watcher(sport)
        enabled = False  # Can't be enabled without a file path

    with statcrew_lock:
        statcrew_config[sport] = {
            "enabled": enabled,
            "file_path": file_path,
            "poll_interval": poll_interval,
        }
        updated = dict(statcrew_config[sport])

    _save_statcrew_config()
    updated["running"] = sport in statcrew_threads
    return updated, 200


def normalize_sport(sport):
    """Normalize sport name to canonical form."""
    if not sport:
        return None
    normalized = str(sport).strip().title()
    if normalized in _ALL_SPORTS:
        return normalized
    return None


# --- Helpers ---


def _ordinal(n):
    """Convert number to ordinal string: 1 → '1st', 2 → '2nd', etc."""
    try:
        n = int(n)
    except (TypeError, ValueError):
        return str(n)
    if 11 <= (n % 100) <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


# --- XML Parser ---


def _parse_statcrew_xml(xml_text):
    """Parse StatCrew XML format into a dict.

    StatCrew XML typically includes:
    - venue info (date, location, attendance)
    - team info (names, records)
    - totals (team stats)
    - player stats

    Returns a dict with parsed data, or empty dict on parse failure.
    """
    if not xml_text:
        return {}

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return {}

    parsed = {}

    # Detect sport type from root element
    root_tag = root.tag.lower()
    is_baseball = root_tag in ("bsgame",)
    is_basketball = root_tag in ("bbgame", "wbbgame")
    if is_basketball:
        parsed["basketball_gender"] = "W" if root_tag == "wbbgame" else "M"

    # Try to extract venue info
    venue = root.find(".//venue")
    if venue is not None:
        parsed["venue"] = {
            "date": venue.get("date", ""),
            "location": venue.get("location", ""),
            "stadium": venue.get("stadium", ""),
            "attendance": venue.get("attend", ""),
            "gameid": venue.get("gameid", ""),
            "weather": venue.get("weather", ""),
            "temp": venue.get("temp", ""),
            "start": venue.get("start", ""),
            "end": venue.get("end", ""),
            "duration": venue.get("duration", ""),
        }

    # Try to extract team info
    teams = root.findall(".//team")
    visitor_team = None
    home_team = None

    if teams:
        parsed["teams"] = []
        for team in teams:
            vh = team.get("vh", "").upper()
            team_data = {
                "id": team.get("id", ""),
                "name": team.get("name", ""),
                "code": team.get("code", ""),
                "record": team.get("record", ""),
                "rank": team.get("rank", ""),
                "vh": vh,
            }
            # Look for linescore or totals
            linescore = team.find("linescore")
            if linescore is not None:
                team_data["linescore"] = {
                    "runs": linescore.get("runs", ""),
                    "hits": linescore.get("hits", ""),
                    "errs": linescore.get("errs", ""),
                    "lob": linescore.get("lob", ""),
                }
                # Get inning-by-inning
                innings = []
                for line in linescore.findall("lineinn"):
                    innings.append(line.get("score", ""))
                if innings:
                    team_data["innings"] = innings

            totals = team.find("totals")
            if totals is not None:
                # Baseball/softball has separate hitting/pitching/fielding
                hitting = totals.find("hitting")
                if hitting is not None:
                    team_data["hitting"] = dict(hitting.attrib)
                pitching = totals.find("pitching")
                if pitching is not None:
                    team_data["pitching"] = dict(pitching.attrib)
                fielding = totals.find("fielding")
                if fielding is not None:
                    team_data["fielding"] = dict(fielding.attrib)
                # Generic stats fallback
                stats = totals.find("stats")
                if stats is not None:
                    team_data["totals"] = dict(stats.attrib)

            # Track visitor/home
            if vh == "V":
                visitor_team = team_data
            elif vh == "H":
                home_team = team_data

            parsed["teams"].append(team_data)

    # Extract player stats with baseball-specific info
    for team in teams:
        team_id = team.get("id", "")
        vh = team.get("vh", "").upper()
        players = []
        pitchers = []
        batters = []

        for player in team.findall(".//player"):
            player_data = {
                "name": player.get("name", ""),
                "shortname": player.get("shortname", ""),
                "uni": player.get("uni", ""),
                "pos": player.get("pos", ""),
                "spot": player.get("spot", ""),
                "gs": player.get("gs", ""),
            }

            # Hitting stats (for batters)
            hitting = player.find("hitting")
            if hitting is not None:
                player_data["hitting"] = dict(hitting.attrib)
                batters.append(player_data)

            # Pitching stats (for pitchers)
            pitching = player.find("pitching")
            if pitching is not None:
                player_data["pitching"] = dict(pitching.attrib)
                pitchers.append(player_data)

            # Season stats
            hitseason = player.find("hitseason")
            if hitseason is not None:
                player_data["hitseason"] = dict(hitseason.attrib)

            # Generic stats fallback
            stats = player.find("stats")
            if stats is not None:
                player_data["stats"] = dict(stats.attrib)

            if player_data.get("name") or player_data.get("uni"):
                players.append(player_data)

        if players:
            if "players" not in parsed:
                parsed["players"] = {}
            parsed["players"][team_id] = players

        # Store pitchers separately for easy access
        if pitchers:
            if "pitchers" not in parsed:
                parsed["pitchers"] = {}
            parsed["pitchers"][vh] = pitchers

        if batters:
            if "batters" not in parsed:
                parsed["batters"] = {}
            parsed["batters"][vh] = batters

    # For baseball, create convenient top-level accessors
    if is_baseball or visitor_team or home_team:
        if visitor_team:
            parsed["away_name"] = visitor_team.get("name", "Away")
            parsed["away_code"] = visitor_team.get("code", "") or visitor_team.get("id", "")
            parsed["away_id"] = visitor_team.get("id", "")
            parsed["away_record"] = visitor_team.get("record", "")
            parsed["away_lob"] = visitor_team.get("linescore", {}).get("lob", "")
            parsed["away_team_color"] = lookup_away_team_color(
                parsed["away_name"], parsed["away_code"]
            )
        if home_team:
            parsed["home_name"] = home_team.get("name", "Home")
            parsed["home_code"] = home_team.get("code", "") or home_team.get("id", "")
            parsed["home_id"] = home_team.get("id", "")
            parsed["home_record"] = home_team.get("record", "")
            parsed["home_lob"] = home_team.get("linescore", {}).get("lob", "")

        # Find current pitcher per team using the 'appear' attribute
        # from <pitching>. The highest appear value = most recent entry.
        for vh in ["V", "H"]:
            prefix = "away" if vh == "V" else "home"
            pitchers = parsed.get("pitchers", {}).get(vh, [])
            if not pitchers:
                continue
            current_p = max(
                pitchers,
                key=lambda p: int(p.get("pitching", {}).get("appear", "0") or "0"),
            )
            p_stats = current_p.get("pitching", {})
            parsed[f"{prefix}_pitcher_name"] = current_p.get("name", "")
            parsed[f"{prefix}_pitcher_uni"] = current_p.get("uni", "")
            parsed[f"{prefix}_pitcher_ip"] = p_stats.get("ip", "")
            parsed[f"{prefix}_pitcher_h"] = p_stats.get("h", "")
            parsed[f"{prefix}_pitcher_r"] = p_stats.get("r", "")
            parsed[f"{prefix}_pitcher_er"] = p_stats.get("er", "")
            parsed[f"{prefix}_pitcher_bb"] = p_stats.get("bb", "")
            parsed[f"{prefix}_pitcher_so"] = p_stats.get("so", "")
            parsed[f"{prefix}_pitcher_pitches"] = p_stats.get("pitches", "")
            parsed[f"{prefix}_pitcher_strikes"] = p_stats.get("strikes", "")

        # Use <status> element for real-time game state (current batter,
        # pitcher, inning, batting team, count). This is the authoritative
        # source — updated live by the StatCrew operator.
        status = root.find(".//status")
        if status is not None:
            parsed["current_batter_name"] = status.get("batter", "")
            parsed["current_pitcher_name"] = status.get("pitcher", "")
            batting_vh = status.get("vh", "").upper()
            if batting_vh in ("V", "H"):
                parsed["batting_team"] = (
                    "away" if batting_vh == "V" else "home"
                )

            # Inning display with MID/END transitions on 3 outs
            s_inning = status.get("inning", "")
            s_outs = int(status.get("outs", "0") or "0")
            s_endinn = status.get("endinn", "").upper() == "Y"
            if s_inning:
                inning_over = s_outs >= 3 or s_endinn
                if inning_over:
                    half = "MID" if batting_vh == "V" else "END"
                else:
                    half = "TOP" if batting_vh == "V" else "BOT"
                parsed["inning_display"] = f"{half} {_ordinal(s_inning)}"

            # Live pitch count: cumulative pitches + current at-bat pitches.
            # <pitching pitches="X"> only updates after completed at-bats.
            # <status np="Y"> tracks pitches in the current at-bat.
            # Add np to the active pitcher's cumulative count.
            status_np = int(status.get("np", "0") or "0")
            status_pitcher = status.get("pitcher", "")
            if status_np and status_pitcher:
                fielding_vh = "V" if batting_vh == "H" else "H"
                prefix = "away" if fielding_vh == "V" else "home"
                cum_pitches = parsed.get(f"{prefix}_pitcher_pitches", "")
                if cum_pitches:
                    live_pitches = int(cum_pitches) + status_np
                    parsed[f"{prefix}_pitcher_pitches"] = str(live_pitches)

        # --- Base runners ---
        # Default to empty (no runners on base)
        parsed["runner_first"] = ""
        parsed["runner_second"] = ""
        parsed["runner_third"] = ""

        game_complete = (
            status is not None and status.get("complete", "").upper() == "Y"
        )
        if not game_complete:
            # Primary: <status first="" second="" third=""> (live, authoritative)
            if status is not None and (
                status.get("first") is not None
                or status.get("second") is not None
                or status.get("third") is not None
            ):
                parsed["runner_first"] = status.get("first", "")
                parsed["runner_second"] = status.get("second", "")
                parsed["runner_third"] = status.get("third", "")
            else:
                # Fallback: last <play> element in current half-inning
                plays_el = root.find(".//plays")
                if plays_el is not None:
                    target_batting = None
                    if status is not None:
                        s_vh = status.get("vh", "").upper()
                        s_inn = status.get("inning", "")
                        if s_vh and s_inn:
                            for batting in plays_el.findall("batting"):
                                if (
                                    batting.get("vh", "").upper() == s_vh
                                    and batting.get("inning", "") == s_inn
                                ):
                                    target_batting = batting
                                    break

                    if target_batting is None:
                        for batting in reversed(plays_el.findall("batting")):
                            if batting.find("innsummary") is None:
                                target_batting = batting
                                break

                    if target_batting is not None:
                        if target_batting.find("innsummary") is None:
                            play_els = target_batting.findall("play")
                            if play_els:
                                last_play = play_els[-1]
                                parsed["runner_first"] = last_play.get(
                                    "first", ""
                                )
                                parsed["runner_second"] = last_play.get(
                                    "second", ""
                                )
                                parsed["runner_third"] = last_play.get(
                                    "third", ""
                                )

        # Build batter lists from batord (full lineup) + overlay hitting stats
        for team in teams:
            vh = team.get("vh", "").upper()
            if vh not in ("V", "H"):
                continue
            prefix = "away" if vh == "V" else "home"

            # Start with batting order — available from first pitch
            batord_by_uni = {}
            for bo in team.findall(".//batord"):
                uni = bo.get("uni", "")
                if uni:
                    batord_by_uni[uni] = {
                        "name": bo.get("name", ""),
                        "uni": uni,
                        "spot": bo.get("spot", ""),
                    }

            # Build lookup of hitting/season stats by uni from player elements
            stats_by_uni = {}
            for b in parsed.get("batters", {}).get(vh, []):
                uni = b.get("uni", "")
                if uni:
                    stats_by_uni[uni] = b

            # Merge: batord roster + player stats overlay
            batter_list = []
            seen = set()
            for uni, bo in batord_by_uni.items():
                p = stats_by_uni.get(uni, {})
                h_stats = p.get("hitting", {})
                season = p.get("hitseason", {})
                # Prefer player name (has proper formatting) over batord name
                name = p.get("name", "") or bo["name"]
                batter_list.append({
                    "name": name,
                    "uni": uni,
                    "spot": bo["spot"],
                    "ab": h_stats.get("ab", ""),
                    "h": h_stats.get("h", ""),
                    "rbi": h_stats.get("rbi", ""),
                    "hr": h_stats.get("hr", ""),
                    "avg": season.get("avg", ""),
                    "season_hr": season.get("hr", ""),
                })
                seen.add(uni)

            # Add any players with hitting stats not in batord (pinch hitters)
            for uni, p in stats_by_uni.items():
                if uni not in seen:
                    h_stats = p.get("hitting", {})
                    season = p.get("hitseason", {})
                    batter_list.append({
                        "name": p.get("name", ""),
                        "uni": uni,
                        "spot": p.get("spot", ""),
                        "ab": h_stats.get("ab", ""),
                        "h": h_stats.get("h", ""),
                        "rbi": h_stats.get("rbi", ""),
                        "hr": h_stats.get("hr", ""),
                        "avg": season.get("avg", ""),
                        "season_hr": season.get("hr", ""),
                    })

            parsed[f"{prefix}_batters"] = batter_list

    # --- Basketball: extract oncourt players with stats ---
    if is_basketball:
        for team in teams:
            vh = team.get("vh", "").upper()
            if vh not in ("V", "H"):
                continue
            prefix = "away" if vh == "V" else "home"
            oncourt = []
            for player in team.findall(".//player"):
                if player.get("gp", "0") == "0":
                    continue
                stats_el = player.find("stats")
                s = dict(stats_el.attrib) if stats_el is not None else {}
                oncourt.append({
                    "name": player.get("name", ""),
                    "uni": player.get("uni", ""),
                    "pos": player.get("pos", ""),
                    "oncourt": player.get("oncourt", "N").upper() == "Y",
                    "pts": s.get("tp", "0"),
                    "reb": s.get("treb", "0"),
                    "ast": s.get("ast", "0"),
                    "stl": s.get("stl", "0"),
                    "blk": s.get("blk", "0"),
                    "pf": s.get("pf", "0"),
                    "to": s.get("to", "0"),
                    "min": s.get("min", "0"),
                    "fgm": s.get("fgm", "0"),
                    "fga": s.get("fga", "0"),
                    "fgm3": s.get("fgm3", "0"),
                    "fga3": s.get("fga3", "0"),
                    "ftm": s.get("ftm", "0"),
                    "fta": s.get("fta", "0"),
                })
            # Sort: oncourt first, then by points descending
            oncourt.sort(
                key=lambda p: (not p["oncourt"], -int(p.get("pts", "0") or "0"))
            )
            parsed[f"{prefix}_players"] = oncourt

    # Generic fallback: try to extract all elements with text content
    if not parsed:
        for elem in root.iter():
            if elem.text and elem.text.strip():
                key = elem.tag
                if key not in parsed:
                    parsed[key] = elem.text.strip()
            for attr_key, attr_val in elem.attrib.items():
                compound_key = f"{elem.tag}_{attr_key}"
                if compound_key not in parsed:
                    parsed[compound_key] = attr_val

    return parsed


# --- File Watcher ---


def statcrew_watcher(sport, file_path, poll_interval, stop_event):
    """Poll file mtime, parse on change."""
    print(f"StatCrew watcher started for {sport}: {file_path}")

    while not stop_event.is_set():
        try:
            if os.path.exists(file_path):
                mtime = os.path.getmtime(file_path)
                last_mtime = statcrew_mtimes.get(sport)

                if last_mtime is None or mtime > last_mtime:
                    # File changed, read and parse
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            xml_text = f.read()
                        parsed = _parse_statcrew_xml(xml_text)
                        if parsed:
                            parsed["_meta"] = {
                                "source": file_path,
                                "mtime": mtime,
                                "parsed_at": time.time(),
                            }
                            with statcrew_lock:
                                statcrew_data[sport] = parsed
                            statcrew_mtimes[sport] = mtime
                            print(f"StatCrew data updated for {sport}")
                    except Exception as exc:
                        print(f"StatCrew parse error for {sport}: {exc}")
        except Exception as exc:
            print(f"StatCrew watcher error for {sport}: {exc}")

        # Wait for poll interval or stop event
        stop_event.wait(poll_interval)

    print(f"StatCrew watcher stopped for {sport}")


def stop_statcrew_watcher(sport):
    """Stop the StatCrew watcher for a sport."""
    event = statcrew_stop_events.get(sport)
    if event:
        event.set()
    thread = statcrew_threads.get(sport)
    if thread:
        thread.join(timeout=2)
    statcrew_stop_events.pop(sport, None)
    statcrew_threads.pop(sport, None)
    statcrew_mtimes.pop(sport, None)


def start_statcrew_watcher(sport, file_path, poll_interval=None):
    """Start the StatCrew watcher for a sport."""
    if poll_interval is None:
        poll_interval = _DEFAULT_POLL_INTERVAL

    stop_statcrew_watcher(sport)

    stop_event = threading.Event()
    statcrew_stop_events[sport] = stop_event
    thread = threading.Thread(
        target=statcrew_watcher,
        args=(sport, file_path, poll_interval, stop_event),
        daemon=True,
    )
    statcrew_threads[sport] = thread
    thread.start()


def start_configured_watchers():
    """Start watchers for all enabled sports from saved config."""
    _load_statcrew_config()
    with statcrew_lock:
        configs = {sport: dict(cfg) for sport, cfg in statcrew_config.items()}

    for sport, cfg in configs.items():
        if cfg.get("enabled") and cfg.get("file_path"):
            start_statcrew_watcher(
                sport,
                cfg["file_path"],
                cfg.get("poll_interval", _DEFAULT_POLL_INTERVAL),
            )
