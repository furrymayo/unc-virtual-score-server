# Decision Log

**Last Updated**: 2026-02-17

## Decisions

| Date | Decision | Rationale | Alternatives Considered |
|------|----------|-----------|------------------------|
| 2023-08-31 | Remove UDP/TCP, use serial COM only | Simplify until local COM ports working | Keep all three protocols |
| 2023-08-30 | Add data source type selector in nav-bar | User needs to switch between sources | Separate config page |
| 2025-12-30 | Move SECRET_KEY to .env | Security — was hardcoded in git history | Keep hardcoded (rejected) |
| 2026-02-13 | Reintroduce TCP/UDP ingestion with auto mode | Support multi-venue network feeds | Serial-only mode |
| 2026-02-13 | Track packet length for shared sport codes | Avoid misclassification across sports | Regex/heuristic parsing |
| 2026-02-16 | Refactor main.py monolith into 5 modules | 1527-line file was unmaintainable; no tests possible | Keep monolith, partial extract |
| 2026-02-16 | Use threading.Event instead of bare bools | Bare bools are technically a race condition under threading | Keep bools (CPython GIL protects in practice) |
| 2026-02-16 | Rename auth.py → sports.py | File had nothing to do with auth; blueprint name was misleading | Keep name (rejected) |
| 2026-02-16 | Deploy with git + venv + systemd (not Docker) | Testing phase — serial port passthrough in Docker is painful, faster iteration with git pull | Docker, gunicorn/nginx |
| 2026-02-16 | New repo (unc-virtual-score-server) | Clean start without IDE files and stale backups in history | Push to existing flaskVirtualScoreboard repo |
| 2026-02-17 | Per-source sport_overrides for Gymnastics | OES has no Gymnastics sport code; gym venue sends Lacrosse packets. Remap at the source level to avoid affecting real Lacrosse venues | Global sport code remap (would break Lacrosse), separate listener |
| 2026-02-17 | CIFS mount at /mnt/stats for StatCrew XML | Persistent network share avoids manual file transfers; app file browser can directly access StatCrew XMLs | SCP/rsync cron job, NFS (Windows share = CIFS) |
