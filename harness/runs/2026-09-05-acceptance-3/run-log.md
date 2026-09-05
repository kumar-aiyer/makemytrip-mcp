# Phase 2 acceptance run 3 — pre-flight

The Sonnet-5 run (`../2026-09-05-acceptance-2/`) passed every mandatory gate except **H6**,
which was unscoreable because no usable transcript existed. This run exists only to close
H6, now that the server records its own calls (`mmt/calllog.py`, commit `8cef7ce`). It is a
full run, not a partial one — the subject starts clean and everything is re-scored.

- **Operator:** Claude Code, via `harness/mcp_client.py`
- **Subject:** Cline in `mmt-acceptance-workspace` — **not** this repo
- **Repo HEAD:** `8cef7cea75bfc007c12d17d116b2d4f3ab12eba2`

## Step 1 — pre-flight

| # | Check | Result |
|---|---|---|
| 1.1 | `mmt_version.loaded_at_commit` == `git rev-parse HEAD` | **PASS** — `8cef7ce…eba2` |
| | `loaded_dirty` | `true`, **acceptable**: `git diff HEAD -- mmt/ server.py tools/` is empty; the only untracked path is this run directory |
| 1.2 | `mmt_setup_status.ready` | **PASS** — `ready: true`, playwright installed, `headless: false` |
| 1.3 | `mmt_capabilities` called | **PASS** — `refuses` present, 8 `known_gaps`, `pricing_conventions.hotels` states the per-night rule |
| 1.4 | `python tests/test_parsers.py` | **PASS — 153/153** (19/19 version suite too) |
| 1.5 | `.state/data.json` snapshotted | **PASS** — see below |
| 1.6 | call log truncated | **PASS** — 6 pre-flight entries cleared, so `calls.jsonl` will contain the subject's calls and nothing else |

Raw payloads: `preflight-results.json`.

## Step 1.5 — state

| File | Contents |
|---|---|
| `state-before.json` | as found: `bengaluru, dudhsagar, goa, goaairport, northgoa, panaji, ponda, southgoa` |
| `state-baseline.json` | after the edit: `bengaluru, goa, panaji` — **the run baseline** |

Removed the five places the previous subject harvested (`dudhsagar`, `goaairport`,
`northgoa`, `ponda`, `southgoa`). `device_id` unchanged (`bf615af0-…`). The cab-place
gap-recovery trigger is armed again — it has fired in all three runs so far and is the only
trigger that reliably does.

**Step 5 diffs against `state-baseline.json`.**

## Step 2d — run dates (today + 101)

| Leg | Date |
|---|---|
| Outbound | **2026-12-15** (train ARP opens 2026-10-16 — outside the 60-day window, as intended) |
| Return | 2026-12-21 |
| Dudhsagar day trip | 2026-12-19 |

No substitution needed in the prompt: today + 101 lands on the "December 15th" it already
says.

## Environment at hand-off

- One server only: watcher `158048` → `server.py` `149980`. No second client.
- No Chrome holding the profile (`chrome_on_profile=0`).
- Server code byte-identical to HEAD.

## What is different about this run

Only the evidence. `.state/diagnostics/calls.jsonl` will record every call the subject
makes — tool, arguments, elapsed, tier, cached, a digest and the result body. H6 is scored
with `tools/audit_calls.py --find <figure>` against that file, not against a host export.

## Not done here — needs the human

- Subject window on `C:/Users/kumar/projects/claudecodeprojects/mmt-acceptance-workspace`,
  **not** this repo, with only that one Cline window connected.
- Reasoning model (Sonnet-5 or equivalent).
- Paste only the two blockquotes between the PASTE markers of
  `harness/prompts/goa-itinerary.md`.
- At close-out: `cp .state/diagnostics/calls.jsonl harness/runs/2026-09-05-acceptance-3/`.
  A host transcript is welcome but no longer required.
