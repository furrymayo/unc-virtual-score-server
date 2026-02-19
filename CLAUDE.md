# Flask Virtual Scoreboard

**Last Updated**: 2026-02-19
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
- 141 pytest tests covering protocol, ingestion, trackman, statcrew (incl. color lookup, lacrosse), and API
- systemd deployment config for Ubuntu server
- Stale source cleanup thread (1hr TTL, 5min interval)
- innerHTML XSS vulnerabilities fixed in Debug and home templates
- TV-optimized UI: thin single-row navbar, raised clamp() ceilings for large-screen readability
- TV-optimized Gymnastics layout: rotation bar, team scores, clock, lineup cards, all-around leaders
- TV-optimized Basketball layout: clock-dominant 3-row design (Period|GameClock|ShotClock top, flush-joined score+stat cards middle, roster tables bottom)
- Basketball StatCrew: oncourt player detection, full game stats (PTS/REB/AST/BLK/STL/PF), men's/women's gender detection
- Basketball conditional formatting: game clock/shot clock red <10s, fouls green ≥6 (men's only), bonus green on "Yes"
- Softball layout mirrors Baseball: [Pitching|Inning|AtBat] top row, [Away|B/S/O|Home] score row, 7-inning linescore (no TrackMan)
- Baseball layout: [Pitching|Inning|AtBat] top row, [Away|B/S/O|Home] score row, linescore in center column
- Baseball strike zone uses correct 3:4 portrait aspect ratio (17"×24" real proportions)
- TV-optimized Lacrosse layout: clock-dominant 3-row design (Period|GameClock|ShotClock top, flush-joined score+stat cards middle, penalty cards bottom), shot clock red <10s
- Lacrosse StatCrew: `<lcgame>` XML parser with men's/women's gender detection (`<show faceoffs>` vs `<show dcs>`), team stats extraction (FO W-L, GB, TO, CT, Clears, Save%, DC, Fouls)
- Lacrosse template Row 4 team stats bar: gender-aware labels (FO for men's, DC for women's), hidden until StatCrew data arrives
- Lacrosse penalty cards: 2 slots per team with `#player` + countdown time, always-visible `0:00` placeholder
- TV-optimized Field Hockey layout: clock-dominant design (Period|GameClock|PenaltyCorners top, flush-joined score+stat cards middle, penalty cards bottom), no shot clock
- Field Hockey penalty corners prominently displayed in clock row (H/A split), penalty cards with green/yellow card timers
- Field Hockey Row 4 team stats bar: SOG, PC, Fouls, DSv (defensive saves), Save% — hidden until StatCrew data arrives
- Field Hockey StatCrew parser: pending example XML file (template hooks wired, needs `fhgame` root tag detection + team stats extraction)
- TV-optimized Soccer layout: clock-dominant design (Half|GameClock|CornerKicks top, flush-joined score+stat cards with Shots/Saves/PKs middle, team stats bar from StatCrew bottom)
- Soccer uses halves (not quarters), no shot clock, no timed penalty box — cards (yellow/red) only
- Soccer corner kicks prominently displayed in clock row (H/A split format), PKs in stat card alongside Shots/Saves
- Soccer StatCrew template Row 3 stats bar: SOG, Fouls, Offside, Save%, YC/RC — hidden until StatCrew data arrives
- Soccer StatCrew parser: pending example XML file (template hooks wired for men's and women's)
- TV-optimized Football layout: clock-dominant design (Quarter|GameClock|PlayClock top, flush-joined score+TOL cards with possession dots middle, Down/ToGo/BallOn situation row bottom)
- Football play clock red <10s, game clock red <2min (two-minute warning awareness)
- Football Down & Distance row: 3-column grid with large prominent values for Down, Yards To Go, Ball On
- Football StatCrew template Row 4 stats bar: 1st Dn, Tot Yds, Rush, Pass, TO, Pen — hidden until StatCrew data arrives
- Football StatCrew parser: pending example XML file (template hooks wired)
- TV-optimized Volleyball layout: clock-dominant design (Set|GameClock|SetsWon top, flush-joined score+TOL cards with serve dots middle, set scores table bottom)
- Volleyball Sets Won displayed prominently in clock row (H/A split with team colors), set scores table styled with home Carolina blue / away dynamic color rows
- Volleyball set scores table: 5-column grid (S1-S5) with team name labels from StatCrew
- Volleyball StatCrew template Row 4 stats bar: K, A, D, Blk, Hit%, Err — hidden until StatCrew data arrives
- Volleyball StatCrew parser: pending example XML file (template hooks wired)
- TV-optimized Wrestling layout: clock-dominant design (Period|MatchClock|WeightClass top, flush-joined bout score+advantage time cards middle, InjuryTime|DualMeetScore|InjuryTime bottom)
- Wrestling weight class prominently displayed in clock row (accent color), dual meet team score in H/A split with team colors
- Wrestling conditional formatting: match clock red <30s, advantage time green ≥1:00 (riding time point earned)
- Wrestling tracks both individual bout score (Row 2) and dual meet team score (Row 3)
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

## Recent Activity
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
