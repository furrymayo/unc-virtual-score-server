# Infrastructure

**Last Updated**: 2026-02-16

## Deployment

| Parameter | Value |
|-----------|-------|
| Target OS | Ubuntu Server (testing) |
| Install path | `/opt/scoreboard` |
| Service user | `scoreboard` (dialout group for serial) |
| Process manager | systemd (`scoreboard.service`) |
| Service file | `deploy/scoreboard.service` |
| Config file | `/opt/scoreboard/.env` |
| Re-deploy | `git pull && sudo systemctl restart scoreboard` |
| Logs | `sudo journalctl -u scoreboard -f` |

## Serial Communication

| Parameter | Value |
|-----------|-------|
| Baud Rate | 9600 |
| Data Format | ASCII Coded Decimal |
| Port | Configurable via API (default: COM1) |

## Sport Codes

| Code (byte) | Sport |
|-------------|-------|
| `0x74` (`t`) | Basketball (23 bytes), Baseball (52 bytes), Softball (75 bytes) |
| `0x6C` (`l`) | Lacrosse (47 bytes), Field Hockey (51 bytes) |
| `0x66` (`f`) | Football |
| `0x76` (`v`) | Volleyball |
| `0x77` (`w`) | Wrestling |
| `0x73` (`s`) | Soccer |

## Network Ports

| Service | Port | Protocol |
|---------|------|----------|
| Flask Web Server | 5000 (default) | HTTP |
| Scoreboard TCP Listener | 5001 (default) | TCP |
| Scoreboard UDP Listener | 5002 (default) | UDP |
| TrackMan Broadcast Feed | 20998 (default) | UDP |

## Environment Variables

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `FLASK_SECRET_KEY` | `dev-fallback-key` | Yes | Flask session signing key |
| `FLASK_HOST` | `0.0.0.0` | No | Bind address |
| `FLASK_PORT` | `5000` | No | Web server port |
| `FLASK_DEBUG` | `1` | No | Debug mode (`1` or `0`) |
| `SCOREBOARD_TCP_PORT` | `5001` | No | TCP listener port |
| `SCOREBOARD_UDP_PORT` | `5002` | No | UDP listener port |
| `SCOREBOARD_SOURCES_FILE` | `data_sources.json` | No | Path to saved data sources |

## Server Configuration API

`POST /update_server_config`

Example payloads:

```json
{"source":"auto","tcp_port":5001,"udp_port":5002,"port":"COM1"}
```

```json
{"source":"serial","port":"COM3"}
```

## TrackMan API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/trackman_config/<sport>` | GET | Get TrackMan config for Baseball/Softball |
| `/trackman_config/<sport>` | POST | Update TrackMan config (port, feed type, enabled) |
| `/get_trackman_data/<sport>` | GET | Latest parsed TrackMan payload |
| `/get_trackman_debug/<sport>` | GET | Raw TrackMan payload + parse status |
