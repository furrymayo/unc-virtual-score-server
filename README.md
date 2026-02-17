# Flask Virtual Scoreboard

A Flask web application that displays real-time sports scoreboards by reading data from OES serial controllers over TCP, UDP, or serial COM ports. Supports 10 sports with dedicated display templates.

## Supported Sports

Basketball, Hockey, Lacrosse, Football, Volleyball, Wrestling, Soccer, Softball, Baseball, Gymnastics

Also includes TrackMan UDP integration for Baseball and Softball pitch/hit tracking.

## Gymnastics Special Case (Lacrosse Sport Code)

Gymnastics is a one-off exception. The OES controller has no Gymnastics sport code, so the venue transmits Gymnastics using the Lacrosse packet type. Only the running clock is used for Gymnastics, and we must avoid confusing this data with real Lacrosse from other venues.

To handle this safely, we support **per-source sport overrides** on configured TCP data sources. Assign the Gymnastics venue's TCP data source a `sport_overrides` mapping that remaps Lacrosse packets to Gymnastics. Other venues that actually play Lacrosse remain unaffected.

Example `data_sources.json` entry:

```json
{
  "id": "tcp:10.0.0.9:9999",
  "name": "Gym Venue",
  "host": "10.0.0.9",
  "port": 9999,
  "enabled": true,
  "sport_overrides": {
    "Lacrosse": "Gymnastics"
  }
}
```

Or via API:

```json
POST /data_sources
{
  "host": "10.0.0.9",
  "port": 9999,
  "name": "Gym Venue",
  "sport_overrides": {"Lacrosse": "Gymnastics"}
}
```

## Project Structure

```
main.py                  # Entry point (~12 lines)
website/
  __init__.py            # Flask app factory, registers blueprints
  views.py               # Home page route
  sports.py              # Sport page routes (renders templates)
  api.py                 # 12 API routes (Blueprint)
  protocol.py            # Serial protocol parser and sport decoders
  ingestion.py           # Data store, serial/TCP/UDP readers, source management
  trackman.py            # TrackMan state, parser, UDP listener
  statcrew.py            # StatCrew XML parser, file watcher thread
  Templates/             # Jinja2 HTML templates
tests/                   # pytest test suite
deploy/                  # Deployment files (systemd unit)
docs/                    # Architecture, infrastructure, decisions, issues
examples/                # Sample StatCrew XML file
```

## Local Development

```bash
# Clone and set up
git clone <repo-url>
cd flaskVirtualScoreboard
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your values

# Run
python main.py
```

The app will be available at `http://localhost:5000`.

### Running Tests

```bash
source venv/bin/activate
pytest tests/ -v
```

## Deploying to Ubuntu Server (Testing)

This section covers deploying for testing purposes using git + venv + systemd. This gives you fast iteration: push changes, pull on the server, restart the service.

### 1. Server Prerequisites

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git
```

### 2. Create a Service User and Project Directory

```bash
sudo useradd -r -s /usr/sbin/nologin scoreboard
# Add to dialout group for serial port access
sudo usermod -aG dialout scoreboard
# Create the project directory with correct ownership
sudo mkdir -p /opt/scoreboard
sudo chown scoreboard:scoreboard /opt/scoreboard
```

### 3. Clone the Repository

```bash
sudo -u scoreboard git clone <repo-url> /opt/scoreboard
cd /opt/scoreboard
```

### 4. Set Up the Virtual Environment

```bash
sudo -u scoreboard python3 -m venv /opt/scoreboard/venv
sudo -u scoreboard /opt/scoreboard/venv/bin/pip install -r requirements.txt
```

### 5. Configure Environment

```bash
sudo -u scoreboard cp .env.example .env
```

Generate a secret key, then edit the `.env` file:

```bash
# Generate a random secret key (copy the output)
python3 -c "import secrets; print(secrets.token_hex(32))"

# Edit the config (use TERM=xterm if you get a terminal error)
TERM=xterm sudo -u scoreboard nano /opt/scoreboard/.env
```

Here's what each variable does and when to change it:

| Variable | Default | What to set |
|----------|---------|-------------|
| `FLASK_SECRET_KEY` | *(empty)* | **Required.** Paste the random string you generated above. This signs session cookies — without it the app uses an insecure fallback. |
| `FLASK_HOST` | `0.0.0.0` | Leave as-is. `0.0.0.0` means the app accepts connections from any machine on the network. Change to `127.0.0.1` to only allow access from the server itself. |
| `FLASK_PORT` | `5000` | The port the web UI runs on. Change if 5000 is already in use or if you want a different port. |
| `FLASK_DEBUG` | `1` | Set to `1` for testing (auto-reloads on code changes, detailed error pages). Set to `0` for anything beyond your local network. |
| `SCOREBOARD_TCP_PORT` | `5001` | Port for the inbound TCP listener. OES controllers or relay software can push scoreboard packets to this port. Only change if 5001 conflicts with another service. |
| `SCOREBOARD_UDP_PORT` | `5002` | Port for the inbound UDP listener. Same as above but for UDP. Only change if 5002 conflicts. |

A typical testing `.env` looks like:

```
FLASK_SECRET_KEY=a1b2c3d4e5f6...your_generated_key_here
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
FLASK_DEBUG=1
SCOREBOARD_TCP_PORT=5001
SCOREBOARD_UDP_PORT=5002
```

### 6. Install the systemd Service

```bash
sudo cp deploy/scoreboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable scoreboard
sudo systemctl start scoreboard
```

### 7. Verify It's Running

```bash
sudo systemctl status scoreboard
# View live logs
sudo journalctl -u scoreboard -f
```

The app will be available at `http://<server-ip>:5000`.

### Updating After Changes

From your dev machine, push your changes to the repo. Then on the server:

```bash
cd /opt/scoreboard
sudo -u scoreboard git pull
sudo systemctl restart scoreboard
```

That's the full re-deploy cycle: three commands.

### Quick Edits on the Server

For rapid iteration, you can edit files directly on the server:

```bash
sudo -u scoreboard nano /opt/scoreboard/website/api.py
sudo systemctl restart scoreboard
```

### Useful Commands

| Command | What it does |
|---------|-------------|
| `sudo systemctl start scoreboard` | Start the service |
| `sudo systemctl stop scoreboard` | Stop the service |
| `sudo systemctl restart scoreboard` | Restart after changes |
| `sudo systemctl status scoreboard` | Check if running |
| `sudo journalctl -u scoreboard -f` | Tail logs |
| `sudo journalctl -u scoreboard --since "5 min ago"` | Recent logs |

### Mounting the StatCrew Network Share

StatCrew XML files live on a Windows network share. Mount it so the app's file browser can access them.

```bash
# Install CIFS utilities
sudo apt install cifs-utils -y

# Create mount point
sudo mkdir -p /mnt/stats

# Create credentials file (edit with your username/password/domain)
sudo nano /etc/credentials-statcrew
# username=YOUR_USERNAME
# password=YOUR_PASSWORD
# domain=AD.UNC.EDU
sudo chmod 600 /etc/credentials-statcrew

# Test the mount
sudo mount -t cifs //152.2.228.104/www /mnt/stats -o credentials=/etc/credentials-statcrew,vers=3.0,uid=$(id -u),gid=$(id -g)

# Verify
ls /mnt/stats
```

Make it persistent by adding this line to `/etc/fstab`:

```
//152.2.228.104/www  /mnt/stats  cifs  credentials=/etc/credentials-statcrew,vers=3.0,uid=1000,gid=1000,iocharset=utf8,_netdev,nofail  0  0
```

Then test with `sudo mount -a`. Once mounted, use the app's StatCrew config page to browse and select XML files under `/mnt/stats`.

### Firewall

If the server has a firewall enabled, open port 5000:

```bash
sudo ufw allow 5000/tcp
```

If using TrackMan UDP or OES UDP listeners, also open those ports:

```bash
sudo ufw allow 5002/udp    # Scoreboard UDP
sudo ufw allow 20998/udp   # TrackMan (default)
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/get_raw_data/<sport>` | Latest parsed data for a sport |
| GET | `/get_sources` | List active data sources |
| GET | `/get_available_com_ports` | List serial ports on the machine |
| POST | `/update_server_config` | Switch between serial/UDP/auto mode |
| GET/POST | `/data_sources` | List or add TCP data sources |
| DELETE/PATCH | `/data_sources/<id>` | Remove or update a data source |
| GET/POST | `/trackman_config/<sport>` | Get or update TrackMan config |
| GET | `/get_trackman_data/<sport>` | Latest TrackMan data |
| GET | `/get_trackman_debug/<sport>` | TrackMan debug info (raw + parsed) |
| GET/POST | `/statcrew_config/<sport>` | Get or update StatCrew config |
| GET | `/get_statcrew_data/<sport>` | Latest parsed StatCrew data |
| GET | `/browse_files?path=...` | Browse server filesystem for XML files |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FLASK_SECRET_KEY` | `dev-fallback-key` | Session signing key |
| `FLASK_HOST` | `0.0.0.0` | Bind address |
| `FLASK_PORT` | `5000` | Web server port |
| `FLASK_DEBUG` | `1` | Enable Flask debug mode (`1` or `0`) |
| `SCOREBOARD_TCP_PORT` | `5001` | Inbound TCP listener port |
| `SCOREBOARD_UDP_PORT` | `5002` | Inbound UDP listener port |
| `SCOREBOARD_SOURCES_FILE` | `data_sources.json` | Path to saved data sources |
