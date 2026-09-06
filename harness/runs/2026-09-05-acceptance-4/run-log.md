# Phase 3 — acceptance run 4, pre-flight

Run 3 (`../2026-09-05-acceptance-3/`) passed everything except **H1**, and scored **H6 for
the first time** off the server's own call log. Since then four things landed that no
subject has ever seen: `mmt_intercity_options`, the past-date guard (BUG-18), the
`cab_find_place` match confidence (BUG-17), and indicative rail fares with A/C + fast
filtering. This run closes H1 and puts all four in front of a subject.

- **Operator:** Claude Code, via `harness/mcp_client.py`
- **Subject:** Cline in `mmt-acceptance-workspace` — **not** this repo
- **Repo HEAD:** `a65f066baf4a4e9f9a41293f12fe5355d4593ff0`

## Step 1 — pre-flight

| # | Check | Result |
|---|---|---|
| 1.1 | `mmt_version.loaded_at_commit` == HEAD | **PASS** — `a65f066…3ff0` |
| | `loaded_dirty` | `true`, acceptable: `git diff HEAD -- mmt/ server.py tools/` is empty; only this run directory is untracked |
| 1.2 | `mmt_setup_status.ready` | **PASS** — ready, `headless: false` |
| 1.3 | `mmt_capabilities` | **PASS** — 8 verified tools including `intercity_options`; `refuses` = past dates, same-day RT; 10 `known_gaps`; the rail filter and per-night rules both stated |
| 1.4 | offline suites | **PASS — 258/258** parsers, 19/19 version, 33/33 watch_server |
| 1.5 | `.state` snapshotted | **PASS** |
| 1.6 | call log truncated | **PASS** — 41 entries cleared after pre-flight, so `calls.jsonl` is the subject and nothing else |
| 1.7 | workspace cleared | **PASS** — see below |

## Workspace hygiene, fixed

Run 3 ran with runs 2 and 3's artifacts still sitting in the subject's workspace — an
operator failure, mine. It was checked and found not to have been used, but it should never
have been possible. `mmt-acceptance-workspace` is **empty** at hand-off this time; the
previous deliverables are archived under their own run directories.

## Step 1.5 — state

| File | Contents |
|---|---|
| `state-before.json` | as found: `bengaluru, calangute, goa, goaairport, mollem, palolem, panaji` |
| `state-baseline.json` | after the edit: `bengaluru, goa, panaji` — **the run baseline** |

Removed the four places run 3 harvested. `device_id` unchanged. The cab-place gap is armed
again; it has fired in every run so far and is the only gap-recovery trigger that reliably
does.

**Step 5 diffs against `state-baseline.json`.**

## Step 2d — dates (today + 101)

Outbound **2026-12-15** (a Tuesday), return 2026-12-21, Dudhsagar 2026-12-19. Train ARP
opens 2026-10-16, so the rail leg is outside the window — which is now interesting rather
than a dead end, because the server quotes the furthest bookable date instead of stopping.

## What is new since a subject last looked

| Change | What it should do to the run |
|---|---|
| `mmt_intercity_options` | one call prices flight + train + cab on a party-total footing. If the subject uses it, **H2 becomes hard to fail**: rail arrives whether or not it thought to ask |
| Indicative rail fares | a date past the booking window now returns real fares for the furthest bookable date, flagged and dated. Watch whether the subject presents them honestly or as the requested date's fare |
| A/C + fast rail filter | comparison rows are A/C classes within 1.25x the quickest; Vande Bharat gets a slot where one runs |
| BUG-18 past-date guard | a wrong-year date is refused in milliseconds. Run 3 burned ~200 s and two flight searches on exactly that |
| BUG-17 match confidence | `mmt_cab_find_place` now returns `match` with a `warning` when a locality query lands on a venue. Watch whether the subject reads it |

## The gate this run exists to settle

**H1** — run 3 collapsed base/tax into all-in although every call returned the split and
`capabilities.pricing_conventions.split` says they are always reported separately. Run 2
printed `3,222 + 1,145 = 4,367`. Nothing was changed in the tool, because nothing in the
tool was wrong; this run establishes whether run 3 was the outlier.

## Not done here — needs the human

- **Reconnect the Cline MCP connection.** `mmt_intercity_options` is a new tool and
  `tools/list` is snapshotted at connect; without a reconnect the subject cannot see it and
  the main point of this run is lost.
- Subject window on `mmt-acceptance-workspace`, one Cline window only, reasoning model.
- Paste only the two blockquotes between the PASTE markers of `prompts/goa-itinerary.md`.
- At close-out: `cp .state/diagnostics/calls.jsonl harness/runs/2026-09-05-acceptance-4/`.
