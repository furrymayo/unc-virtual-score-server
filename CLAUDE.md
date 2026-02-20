# Flask Virtual Scoreboard

**Last Updated**: 2026-02-21
**Status**: Active
**Primary OS**: Both (Windows + Linux)
**Repo**: https://github.com/furrymayo/unc-virtual-score-server

## Overview
Flask web application that displays real-time sports scoreboards by reading data from OES serial controllers over TCP, UDP, or serial COM ports. Supports 10 sports with dedicated display templates. Optional TrackMan UDP integration for Baseball/Softball pitch/hit tracking. StatCrew XML integration for enhanced stats display.

## Current State
- Modular architecture: monolith refactored into 7 focused modules
- All 10 sport parsers fully implemented
- TCP data source management with persistence (data_sources.json)
- Duplicate host:port data sources supported (auto-suffixed IDs: `:2`, `:3`, etc.)
- Per-source `sport_overrides` for Gymnastics (Lacrosse → Gymnastics remap)
- Home page sport override dropdown for assigning overrides to data sources
- TrackMan UDP integration for Baseball/Softball (strike zone visualization)
- Virtius live scoring API integration for Gymnastics (polls `api.virti.us`)
- Virtius watchers auto-start on server boot from `virtius_sources.json`
- Virtius includes exhibition gymnasts in lineups, running all-around leaders from 2+ events
- StatCrew XML integration with `<status>` element for real-time game state (current pitcher, batter, batting team, pitch count)
- StatCrew `<pitching appear>` attribute for accurate pitcher detection after substitutions
- Live pitch count: `<pitching pitches>` (cumulative) + `<status np>` (current at-bat) — self-correcting
- StatCrew `batord` elements reflect live lineup changes (substitutions, pinch hitters)
- StatCrew base runners from `<status first="" second="" third="">` (primary), `<play>` elements (fallback)
- StatCrew inning display: MID/END transitions from `<status>` outs/endinn/vh, OES fallback guarded
- StatCrew at-bat card: "Today:" game stats (H-AB, RBI, HR) + "Season:" stats (AVG, HR)
- StatCrew pitcher card: "Today:" prefix on game stat line
- Dynamic away team colors: NCAA 347-team color JSON lookup, HSL validation (rejects white/black/blue), CSS `var(--away-color)` theming
- Team tricode labels on Pitching/At Bat cards with team font color
- Linescore row styling: away team color, home Carolina blue, subtle background differentiation
- TrackMan values rounded to whole numbers (no decimal)
- StatCrew network share mounted at `/mnt/stats` on Ubuntu server (CIFS, persistent)
- StatCrew poll interval: 2s (file mtime check 0.3ms, full parse 10ms)
- 173 pytest tests covering protocol, ingestion, trackman, statcrew (incl. color lookup, lacrosse), virtius/gymnastics, and API
- systemd deployment config for Ubuntu server
- Stale source cleanup thread (1hr TTL, 5min interval)
- All 12 templates TV-optimized with consistent design language (see TV Layout Reference below)
- Shared TV layout pattern: clock-dominant Row 1 (period|game clock|sport-specific), flush-joined score+stat cards Row 2, sport-specific Row 3, StatCrew stats Row 4 (hidden until data)
- Responsive `clamp()` CSS sizing throughout all templates for TV/desktop readability
- Conditional formatting: clock red warnings, basketball fouls green ≥6, wrestling advantage green ≥1:00
- StatCrew XML parsers: baseball/softball/basketball/lacrosse/football/soccer/field hockey/volleyball fully implemented and tested; wrestling pending (no StatCrew XML available)
- Debug console: side-by-side OES/TrackMan log panels with timestamps, color-coded JSON, clear buttons, auto-scroll (500 entry cap)
- Home page: modernized hub with responsive sport cards, styled data source management panel
- OES baseball batter_num 0x3A blank handling fixed in protocol.py

## Quick Reference
| Item | Value |
|------|-------|
| Entry point | `main.py` |
| Default port | 5000 (Flask) |
| Serial baud | 9600 |
| Supported sports | Basketball, Field Hockey, Lacrosse, Football, Volleyball, Wrestling, Soccer, Softball, Baseball, Gymnastics |
| Test command | `pytest tests/ -v` |
| Deploy guide | `README.md` |

## Module Map
| Module | Responsibility |
|--------|---------------|
| `main.py` | Slim entry point, starts app + background threads (ingestion, statcrew, virtius) |
| `website/__init__.py` | App factory, registers 3 blueprints (views, sports, api) |
| `website/views.py` | Home page route |
| `website/sports.py` | Sport page routes (renders templates) |
| `website/api.py` | 14 API routes (Blueprint), calls ingestion/trackman/statcrew/virtius accessors |
| `website/protocol.py` | Protocol constants, PacketStreamParser, decoders, 9 sport parsers, `identify_and_parse()` |
| `website/ingestion.py` | Data store, serial/TCP/UDP readers, source management, cleanup thread |
| `website/trackman.py` | TrackMan state, JSON parser, UDP listener, config management |
| `website/statcrew.py` | StatCrew XML parser (baseball/softball/basketball/lacrosse), file watcher thread, config persistence, NCAA color lookup |
| `website/ncaa_team_colors.json` | Static NCAA team colors data (347 teams) for away team color lookup |
| `website/virtius.py` | Virtius live scoring API poller, session parser, config persistence |

## Dependency Graph (no cycles)
```
protocol.py      → (nothing)
trackman.py      → (nothing in website/)
statcrew.py      → (nothing in website/)
virtius.py       → (nothing in website/)
ingestion.py     → protocol
api.py           → ingestion, trackman, statcrew, virtius
__init__.py      → views, sports, api
main.py          → website (create_app), ingestion, statcrew, virtius
```

## File Map
| Need to know... | See |
|-----------------|-----|
| System design & data flow | `docs/architecture.md` |
| Serial protocol details | `docs/infrastructure.md` |
| Why we made X decision | `docs/decisions.md` |
| Current blockers/issues | `docs/known-issues.md` |
| Deployment instructions | `README.md` |
| Sport-specific parsing | `docs/reference/` |

## StatCrew XML Key Elements
| Element | Purpose |
|---------|---------|
| `<status>` | Real-time game state: `batter`, `pitcher`, `vh` (batting team), `np` (pitches in current at-bat), `b`/`s` (count), `outs`, `inning`, `first`/`second`/`third` (runners), `endinn` |
| `<pitching appear="N">` | Order of pitcher appearance — highest value = most recently entered pitcher per team |
| `<pitching pitches="X">` | Cumulative pitch count — only updates after completed at-bats |
| `<batord>` | Live batting order — updates with substitutions (pinch hitters get `in`/`seq` attrs) |
| `<pitches text="BKSFP">` | Per-at-bat pitch sequence within `<play>` elements |
| `<innsummary>` | Present when a half-inning is complete |

## StatCrew Basketball XML Elements
| Element | Purpose |
|---------|---------|
| `<bbgame>` / `<wbbgame>` | Root tag — men's vs women's basketball |
| `<player oncourt="Y/N">` | Active player on court flag |
| `<stats tp="" treb="" ast="" stl="" blk="" pf="">` | Player game stats (total points, total rebounds, assists, steals, blocks, personal fouls) |

## StatCrew Lacrosse XML Elements
| Element | Purpose |
|---------|---------|
| `<lcgame>` | Root tag — both men's and women's lacrosse |
| `<show faceoffs="1" dcs="0">` | Gender detection: `faceoffs="1"` = men's, `dcs="1"` = women's |
| `<totals><shots g="" a="" sh="" sog="" freepos="">` | Team shot totals (goals, assists, shots, shots on goal, free position goals) |
| `<totals><misc facewon="" facelost="" gb="" dc="" turnover="" ct="">` | Team misc stats (face-offs W/L, ground balls, draw controls, turnovers, caused turnovers) |
| `<totals><goalie saves="" sf="">` | Goalie stats — saves and shots faced (for save % calculation) |
| `<totals><clear clearm="" cleara="">` | Clears made / attempted |
| `<totals><penalty foul="">` | Foul count (primarily women's card-based system) |

## TV Layout Reference
All sport templates follow a consistent clock-dominant design. Row 1 is always the largest element.

| Sport | Row 1 (Clock Row) | Row 2 (Score Row) | Row 3 (Sport-Specific) | Row 4 (StatCrew Stats) | Conditional Formatting |
|-------|-------------------|-------------------|------------------------|------------------------|----------------------|
| Basketball | Period \| GameClock \| ShotClock | Score+Fouls/TOL/Bonus | Roster tables (oncourt) | — (stats in roster) | Clock red <10s, fouls green ≥6 (men's), bonus green |
| Lacrosse | Period \| GameClock \| ShotClock | Score+TOL/Shots/SOG | Penalty cards (2 slots) | FO/DC, GB, TO, CT, Clears, Save% | Shot clock red <10s |
| Field Hockey | Period \| GameClock \| PenaltyCorners | Score+Shots/Saves | Penalty cards (2 slots) | SOG, PC, Fouls, DSv, Save% | — |
| Soccer | Half \| GameClock \| CornerKicks | Score+Shots/Saves/PKs | — (no penalties) | SOG, Fouls, Offside, Save%, YC/RC | — |
| Football | Quarter \| GameClock \| PlayClock | Score+TOL (possession dots) | Down/ToGo/BallOn | 1stDn, TotYds, Rush, Pass, TO, Pen | Play clock red <10s, game clock red <2min |
| Volleyball | Set \| GameClock \| SetsWon | Score+TOL (serve dots) | Set scores table (S1-S5) | K, A, D, Blk, Hit%, Err | — |
| Wrestling | Period \| MatchClock \| WeightClass | Bout score+AdvTime | InjTime \| DualScore \| InjTime | — (no team stats) | Clock red <30s, adv green ≥1:00 |
| Baseball | Pitching \| Inning \| AtBat | Away/B-S-O/Home scores | Linescore (9-inning) | — (stats in cards) | — |
| Softball | Pitching \| Inning \| AtBat | Away/B-S-O/Home scores | Linescore (7-inning) | — (stats in cards) | — |
| Gymnastics (dual) | Rotation bar | Home\|Clock\|Away scores | Lineup cards (2-col) | All-around leaders | — |
| Gymnastics (3/4) | Rotation bar + clock | N team score cards | Lineup cards (N-col) | All-around leaders (per-team colors) | Teams sorted by rank |
| Debug | — | — | OES log \| TrackMan log | — | Errors red, data green |
| Home | — | Sports grid (10+debug) | Data source manager | — | — |

## Recent Activity
- 2026-02-21: Gymnastics multi-team meets — 3/4 team support (tri-meets, quad-meets). API returns `team_colors` dict for per-team NCAA color lookup. Frontend dual/multi branching: dual meets pixel-identical to previous, multi meets get N-column team cards sorted by rank (leader left), clock moves to rotation bar, per-team inline colors on score cards/lineup cards/AA leaders. Flicker prevention via `lastTeamCount` tracking. New CSS grid classes (`gym-grid-3/4`, `gym-lineup-3/4`). 5 new API tests. 173 total tests.
- 2026-02-20: Lacrosse Shots/SOG fix — StatCrew shots and SOG override OES when available (OES controller sends 0 for shots). Added SOG display to Row 2 stat cards alongside TOL and Shots.
- 2026-02-19: Home page modernized — responsive sport cards with tag/name structure, styled data source management (primary/secondary buttons, action buttons), removed Bootstrap utilities, consistent dark UNC theme
- 2026-02-19: Debug console modernized — side-by-side OES/TrackMan log panels with timestamps, color-coded JSON output, clear buttons, auto-scroll, 500 entry cap, custom scrollbar, removed innerHTML XSS usage
- 2026-02-19: Wrestling TV-optimized layout — clock-dominant design (Period|MatchClock|WeightClass row, flush-joined bout score+advantage time cards, InjuryTime|DualMeetScore|InjuryTime situation row). Weight class in accent color. Dual meet score in H/A team colors. Match clock red <30s, advantage time green ≥1:00 (riding time point).
- 2026-02-19: Volleyball TV-optimized layout — clock-dominant design (Set|GameClock|SetsWon row, flush-joined score+TOL cards with serve dots, set scores table with team-colored rows). Sets Won in clock row with H/A team colors. Set scores table with S1-S5 columns, home Carolina blue / away dynamic color. StatCrew template hooks wired (K, A, D, Blk, Hit%, Err), pending example XML for parser.
- 2026-02-19: Football TV-optimized layout — clock-dominant design (Quarter|GameClock|PlayClock row, flush-joined score+TOL cards with possession dots, Down/ToGo/BallOn situation row). Play clock red <10s, game clock red <2min. StatCrew template hooks wired (1st Dn, Tot Yds, Rush, Pass, TO, Pen), pending example XML for parser.
- 2026-02-19: Soccer TV-optimized layout — clock-dominant design (Half|GameClock|CornerKicks row, flush-joined score+stat cards with Shots/Saves/PKs, StatCrew team stats bar with SOG/Fouls/Offside/Save%/YC-RC). No penalty row (soccer uses cards not timed suspensions). Corner kicks in clock row slot. Works for both men's and women's. StatCrew template hooks wired, pending example XML for parser.
- 2026-02-19: Field Hockey TV-optimized layout — clock-dominant design (Period|GameClock|PenaltyCorners row, flush-joined score+stat cards with Shots/Saves, penalty cards with green/yellow card timers, team stats bar for StatCrew). Penalty corners replace shot clock in clock row (field hockey has no shot clock). StatCrew template hooks wired (SOG, PC, Fouls, DSv, Save%), pending example XML for parser.
- 2026-02-19: Lacrosse TV-optimized layout — clock-dominant design (Period|GameClock|ShotClock row, flush-joined score+stat cards, penalty cards with 2 slots per team, team stats bar from StatCrew). StatCrew `<lcgame>` parser with men's/women's gender detection via `<show>` element, team stats extraction (FO W-L, DC, GB, TO, CT, Clears, Save%, Fouls). Gender-aware stat labels (FO for men's, DC for women's). Shot clock red <10s. 10 new tests.
- 2026-02-18: Basketball TV-optimized layout — clock-dominant 3-row design (Period|GameClock|ShotClock row, flush-joined score+stat cards with roster tables), StatCrew basketball player parsing (oncourt detection, full game stats, men's/women's gender), conditional formatting (clock red <10s, fouls green ≥6 men's, bonus green), fixed `bbgame` misclassification bug in statcrew parser
- 2026-02-18: Live game enhancements — dynamic away team colors (NCAA JSON lookup, HSL validation, CSS variable theming), team tricode labels on Pitching/At Bat cards, linescore row styling (away color, home Carolina blue), base runners from `<status>` element, inning MID/END transitions with OES/StatCrew priority fix, at-bat "Today:"/"Season:" stat labels with HR, pitcher "Today:" prefix, TrackMan whole-number rounding
- 2026-02-18: Softball rewrite — mirrors Baseball layout (Pitching/Inning/AtBat top row, Away/B-S-O/Home score row, 7-inning linescore), removed TrackMan elements, OES fallback for pitcher/batter. Cleaned up dead files (auth.py, models.py). Added `virtius_sources.json` for boot persistence.
- 2026-02-18: Gymnastics overhaul — TV-optimized template (rotation bar, team scores, clock, lineup cards, all-around leaders), Virtius API integration with exhibition gymnasts and running AA totals, duplicate host:port data sources with auto-suffixed IDs, home page sport override dropdown, Virtius auto-start on boot
- 2026-02-18: Baseball real-time: `<status>` element for live batter/pitcher/batting team, `appear` attr for pitcher detection after subs, live pitch count (`pitches` + `np`), reduced poll/fetch to 2s, TV layout restructure (compact cards, center linescore)
- 2026-02-17: TV readability overhaul — collapsed navbar to thin bar, raised all clamp() ceilings (~2x primary, ~1.5x secondary), fixed baseball TrackMan card overflow, strike zone 3:4 portrait ratio, linescore static Away/Home labels, reduced team score cards, added `away_code`/`home_code` to statcrew parser
- 2026-02-17: Added Gymnastics sport_overrides, CIFS network share mount for StatCrew (`/mnt/stats`), StatCrew XML integration, redesigned Baseball page, fixed strike zone coordinate mapping (needs live verification)
- 2026-02-16: Major refactor — split main.py monolith into 5 modules, added tests, systemd deploy, XSS fixes, pushed to new repo (unc-virtual-score-server)
- 2026-02-14: Rebuilt sport UIs with dark UNC theme, added TrackMan dashboard
- 2026-02-13: Added TCP/UDP ingestion, full sport parsers, source tracking
- 2025-12-30: Project structure standardization, credentials secured to .env
