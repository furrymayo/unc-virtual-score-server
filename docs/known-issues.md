# Known Issues

**Last Updated**: 2026-02-16

## Active Issues

| ID | Issue | Impact | Workaround | Blocked By |
|----|-------|--------|------------|------------|
| 1 | No auth on API endpoints | Config can be changed by any network client | Restrict by network ACL until auth added | Security decision |
| 3 | `data_sources.json` path is relative | File location depends on working directory | Always start from project root, or set `SCOREBOARD_SOURCES_FILE` env var | — |

## Resolved Issues

| ID | Issue | Resolution | Date |
|----|-------|------------|------|
| 1 | Most sport parsers were stubs | Implemented full parsers from legacy app | 2026-02-13 |
| 2 | Source lists can grow unbounded | Added stale source cleanup thread (1hr TTL, 5min interval) | 2026-02-16 |
| 4 | innerHTML XSS in Debug.html and home.html | Replaced with createElement + textContent + appendChild | 2026-02-16 |
| 5 | Thread stop using bare bool (race condition) | Converted to threading.Event | 2026-02-16 |
