# Phase 2 Acceptance Run — pre-flight

Directory is `2026-09-05-acceptance` rather than `2026-09-05` because the latter holds the
**guided** data-collection run, which is not the acceptance test and whose evidence must not
be overwritten.

- **Operator:** Claude Code (this session). **Subject:** a fresh Cline session — not yet run.
- **Repo HEAD:** `7e0389b2d0f8d2a53440a3eab68609b5d736807c`, branch `phase2/acceptance-run`
- **Pre-flight run at:** 2026-09-05, via `harness/mcp_client.py` (its own `server.py`,
  spawned and exited; Cline's registered server was idle throughout, no Chrome on the profile)

## Step 1 — pre-flight checklist (runbook `harness/PHASE2-RUNBOOK.md`)

| # | Check | Result |
|---|---|---|
| 1.1 | `mmt_version.loaded_at_commit` == `git rev-parse HEAD` | **PASS** — `7e0389b…807c`, `code_path` is this repo, python 3.14.3 |
| | `loaded_dirty` | `true`, **acceptable**: `git diff HEAD -- mmt/ server.py tools/` is empty; the only untracked path is this run directory |
| 1.2 | `mmt_setup_status.ready` | **PASS** — `ready: true`, `next_steps: []`, `state_dir` absolute and correct |
| | | `warmup: {ok, skipped:true}` — `ensure()` did the homepage navigation itself (16.8 s, real Chrome launch), so the extra nav was redundant, not omitted |
| 1.3 | `mmt_capabilities` **called** (missed last time) | **PASS** — returns `known_gaps`, `cannot`, `refuses`, `pricing_conventions`, `booking_windows` |
| | per-night rule stated | **PASS** — in `pricing_conventions.hotels` (`nightly_*` / `stay_estimate_all_in_inr`) and again in `known_gaps` |
| | alternate-airport gap stated | **PASS** — `known_gaps` names `alternate_airport: true` and GOI vs GOX |
| | same-day cab RT refusal stated | **PASS** — `refuses["cab_quote same-day RT"]` |
| 1.4 | `python tests/test_parsers.py` | **PASS — 140/140** |
| 1.5 | `.state/data.json` snapshotted | **PASS** — see below |

Raw payloads: `preflight-results.json` (plan: `preflight-plan.json`).

## Step 1.5 / state edit

| File | Contents |
|---|---|
| `state-before.json` | state as found, **including** `kulem` (sha256 `1BB0D084…A8A5`) |
| `state-baseline.json` | state after the surgical edit — this is the run baseline |

`kulem` removed from `cab_places`; nothing else touched. Places now `bengaluru, goa, panaji`;
`device_id` unchanged (`bf615af0-…`), verified still unchanged after the pre-flight's Chrome
warmup. The Dudhsagar gap-recovery trigger (GR1/GR2) is therefore armed again.

**Diff Step 5 against `state-baseline.json`, not `state-before.json`** — the runbook's snippet
snapshots before it pops, so `state-before.json` already contains `kulem` and would hide the
`+kulem` that is the evidence GR2 fired.

## Step 2d — run dates (today + 101)

| Leg | Date |
|---|---|
| Outbound | **2026-12-15** (train ARP opens 2026-10-16 — outside the 60-day window, as intended) |
| Return | **2026-12-21** |
| Dudhsagar day trip | **2026-12-19** |

## Not done here — needs the human

- Restart the Cline MCP connection before Step 2 (`mmt_capabilities` gained `refuses`; the
  host snapshots `tools/list` at connect).
- Step 2: paste only the two blockquotes between the PASTE markers of
  `harness/prompts/goa-itinerary.md`, dates substituted. Nothing from the runbook.
- Step 2b: export the transcript to `harness/runs/2026-09-05-acceptance/transcript.md`
  **before** closing the session.
