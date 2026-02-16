# Decision Log

**Last Updated**: 2026-02-13

## Format

| Date | Decision | Rationale | Alternatives Considered |
|------|----------|-----------|------------------------|
| YYYY-MM-DD | What was decided | Why | What else was considered |

## Decisions

| Date | Decision | Rationale | Alternatives Considered |
|------|----------|-----------|------------------------|
| 2023-08-31 | Remove UDP/TCP, use serial COM only | Simplify until local COM ports working | Keep all three protocols |
| 2023-08-30 | Add data source type selector in nav-bar | User needs to switch between sources | Separate config page |
| 2025-12-30 | Move SECRET_KEY to .env | Security - was hardcoded in git history | Keep hardcoded (rejected) |
| 2026-02-13 | Reintroduce TCP/UDP ingestion with auto mode | Support multi-venue network feeds | Serial-only mode |
| 2026-02-13 | Track packet length for shared sport codes | Avoid misclassification across sports | Regex/heuristic parsing |
