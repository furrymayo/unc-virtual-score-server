import os
import secrets
from dataclasses import dataclass
from pathlib import Path


def _to_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _resolve_path(value, base_dir):
    raw = str(value or "").strip()
    if not raw:
        return str(base_dir / "data_sources.json")
    path = Path(raw)
    if path.is_absolute():
        return str(path)
    return str(base_dir / path)


def _split_roots(value):
    raw = str(value or "").strip()
    if not raw:
        return []
    return [segment for segment in raw.split(os.pathsep) if segment]


def _to_float(value, default):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class AppConfig:
    flask_host: str
    flask_port: int
    flask_debug: bool
    flask_secret_key: str
    scoreboard_tcp_port: int
    scoreboard_udp_port: int
    scoreboard_sources_file: str
    browse_roots: list[str]
    admin_user: str
    admin_pass: str
    cloud_relay_enabled: bool
    cloud_relay_url: str
    cloud_relay_token: str
    cloud_relay_publisher_name: str
    cloud_relay_poll_interval: float
    cloud_relay_queue_size: int
    cloud_relay_reconnect_min: float
    cloud_relay_reconnect_max: float


def load_config():
    base_dir = Path(__file__).resolve().parent.parent

    host = os.environ.get("FLASK_HOST", "0.0.0.0")
    port = _to_int(os.environ.get("FLASK_PORT", "5000"), 5000)
    debug = _to_bool(os.environ.get("FLASK_DEBUG", "0"), default=False)
    secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)

    tcp_port = _to_int(os.environ.get("SCOREBOARD_TCP_PORT", "5001"), 5001)
    udp_port = _to_int(os.environ.get("SCOREBOARD_UDP_PORT", "5002"), 5002)
    sources_file = _resolve_path(
        os.environ.get("SCOREBOARD_SOURCES_FILE", "data_sources.json"),
        base_dir,
    )

    browse_roots = _split_roots(os.environ.get("BROWSE_ROOTS", "/mnt/stats"))
    if not browse_roots:
        browse_roots = ["/mnt/stats"]

    admin_user = os.environ.get("ADMIN_USER", "admin")
    admin_pass = os.environ.get("ADMIN_PASS", "admin")

    cloud_relay_enabled = _to_bool(os.environ.get("CLOUD_RELAY_ENABLED"), default=False)
    cloud_relay_url = os.environ.get("CLOUD_RELAY_URL", "").strip()
    cloud_relay_token = os.environ.get("CLOUD_RELAY_TOKEN", "")
    cloud_relay_publisher_name = os.environ.get("CLOUD_RELAY_PUBLISHER_NAME", "onprem").strip() or "onprem"
    cloud_relay_poll_interval = _to_float(os.environ.get("CLOUD_RELAY_POLL_INTERVAL", "0.5"), 0.5)
    cloud_relay_queue_size = _to_int(os.environ.get("CLOUD_RELAY_QUEUE_SIZE", "256"), 256)
    cloud_relay_reconnect_min = _to_float(os.environ.get("CLOUD_RELAY_RECONNECT_MIN", "1.0"), 1.0)
    cloud_relay_reconnect_max = _to_float(os.environ.get("CLOUD_RELAY_RECONNECT_MAX", "30.0"), 30.0)

    return AppConfig(
        flask_host=host,
        flask_port=port,
        flask_debug=debug,
        flask_secret_key=secret_key,
        scoreboard_tcp_port=tcp_port,
        scoreboard_udp_port=udp_port,
        scoreboard_sources_file=sources_file,
        browse_roots=browse_roots,
        admin_user=admin_user,
        admin_pass=admin_pass,
        cloud_relay_enabled=cloud_relay_enabled,
        cloud_relay_url=cloud_relay_url,
        cloud_relay_token=cloud_relay_token,
        cloud_relay_publisher_name=cloud_relay_publisher_name,
        cloud_relay_poll_interval=cloud_relay_poll_interval,
        cloud_relay_queue_size=cloud_relay_queue_size,
        cloud_relay_reconnect_min=cloud_relay_reconnect_min,
        cloud_relay_reconnect_max=cloud_relay_reconnect_max,
    )


CONFIG = load_config()
