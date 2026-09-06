# Phase 3 — acceptance run 5, pre-flight

Run 4 passed nine gates and failed two, both of them ours. This run re-tests exactly those
two after the fixes in `5984678`; everything else it re-tests for free.

- **Operator:** Claude Code, via `harness/mcp_client.py`
- **Subject:** Cline in `mmt-acceptance-workspace` — **not** this repo
- **Repo HEAD:** `59846782e5174ee6f271720752930edd4690c54d`

## Step 1 — pre-flight

| # | Check | Result |
|---|---|---|
| 1.1 | `mmt_version.loaded_at_commit` == HEAD | **PASS** — `5984678…0c54d` |
| | server code vs HEAD | clean — `git diff HEAD -- mmt/ server.py tools/` is empty |
| 1.2 | `mmt_setup_status.ready` | **PASS** — ready, `headless: false` |
| 1.3 | `mmt_capabilities` | **PASS** — 8 verified tools incl. `intercity_options`, 2 `refuses`, 10 `known_gaps` |
| 1.4 | offline suites | **PASS — 271/271**, 19/19, 33/33 |
| 1.5 | `.state` snapshotted | **PASS** |
| 1.6 | call log truncated | **PASS** — 40 entries cleared after pre-flight |
| 1.7 | workspace cleared | **PASS** — run 4's deliverables archived first, workspace empty |
| 1.8 | environment | one server, `chrome_on_profile=0` |

## Step 1.5 — state

`state-before.json` held eleven places, including run 4's three airport attempts
(`goi_airport`, `goi_airport2`, `goi_airport3`). `state-baseline.json` is back to
`bengaluru, goa, panaji`; `device_id` unchanged. **Step 5 diffs against the baseline.**

## Dates

Outbound **2026-12-15**, return 2026-12-21, Dudhsagar 2026-12-19. Unchanged, so the prompt
needs no substitution.

## What this run is testing

**H5 — the gate run 4 failed because of us.** `alternate_airport` now covers departures as
well as arrivals. On the GOI→BLR leg that misled run 4, **13 of 25 itineraries depart from
another airport** and are now excluded and counted. If a subject still ends up on a
Sindhudurg flight, the fix is wrong; if it lands on IndiGo 6E 6163 at ~Rs 11,988 for two,
the fix holds.

**H1 — failed twice running.** `mmt_intercity_options` now says in its `note` that flight and
cab rows carry `base_inr` and `tax_inr` and that they should be reported separately. This is
the cheapest possible nudge. **If this subject also collapses the split, stop blaming the
subject** — three of four would mean H1 asks for something the tool surface does not
encourage, and the gate or the schema needs the rethink, not the model.

**BUG-17's refinement.** `"Palolem Goa"` → `Palolem` should now come back `high` with no
warning, while a genuine mis-resolve still warns. Run 4's subject visibly acted on these
warnings, so the risk of a false one is that it teaches the next subject to ignore them.

## Not done here — needs the human

- **No reconnect needed this time.** No tool was added or removed since run 4; only
  behaviour inside existing tools changed, and the watcher hot-reloads code. Reconnecting
  anyway does no harm.
- Subject window on `mmt-acceptance-workspace`, one Cline window, reasoning model.
- Paste only the two blockquotes between the PASTE markers of `prompts/goa-itinerary.md`.
- At close-out: `cp .state/diagnostics/calls.jsonl harness/runs/2026-09-05-acceptance-5/`.
