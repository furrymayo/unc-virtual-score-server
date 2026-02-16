# Infrastructure

**Last Updated**: 2026-02-13

## Hosts & Connections

TODO: Document hosts and connections

## Serial Communication

| Parameter | Value |
|-----------|-------|
| Baud Rate | 9600 |
| Data Format | ASCII Coded Decimal |
| Port | Configurable via API (default: COM1) |

## Sport Codes

| Code (byte) | Sport |
|-------------|-------|
| `0x74` (`t`) | Basketball, Baseball, Softball (distinguished by length) |
| `0x6C` (`l`) | Lacrosse, Field Hockey (distinguished by length) |
| `0x66` (`f`) | Football |
| `0x76` (`v`) | Volleyball |
| `0x77` (`w`) | Wrestling |
| `0x73` (`s`) | Soccer |

## Network

| Service | Port | Protocol |
|---------|------|----------|
| Flask Dev Server | 5000 | HTTP |
| Scoreboard TCP Listener | 5001 (default) | TCP |
| Scoreboard UDP Listener | 5002 (default) | UDP |
| TrackMan Broadcast Feed | 20998 (default) | UDP |
| TrackMan Scoreboard Feed | 20999 (default) | UDP |

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `FLASK_SECRET_KEY` | Flask session signing key | Yes |
| `SCOREBOARD_TCP_PORT` | TCP listener port | No |
| `SCOREBOARD_UDP_PORT` | UDP listener port | No |

## Server Configuration API

`POST /update_server_config`

Example payloads:

```json
{"source":"auto","tcp_port":5001,"udp_port":5002,"port":"COM1"}
```

```json
{"source":"tcp","tcp_port":5000}
```

```json
{"source":"udp","udp_port":5000}
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
