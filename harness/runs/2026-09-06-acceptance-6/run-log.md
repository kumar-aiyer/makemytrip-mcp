# Phase 3 — acceptance run 6, pre-flight

Run 5 passed **every mandatory gate** — the first clean sweep — but was ambiguous on the
call budget because four of five flight searches failed (**BUG-20**), and that failure also
denied the run any return-leg data, so **BUG-19's departure exclusion was never exercised by
a subject**. BUG-20 is fixed (`900e9bd`). This run is to get a clean sweep that is also
unambiguous.

- **Operator:** Claude Code, via `harness/mcp_client.py`
- **Subject:** Cline in `mmt-acceptance-workspace` — **not** this repo
- **Repo HEAD:** `900e9bd32f37a6f881b5b3f52a07638b31cbeea8`

## Step 1 — pre-flight

| # | Check | Result |
|---|---|---|
| 1.1 | `mmt_version.loaded_at_commit` == HEAD | **PASS** — `900e9bd…eea8`, server code clean against HEAD |
| 1.2 | `mmt_setup_status.ready` | **PASS** — ready, `headless: false` |
| 1.3 | `mmt_capabilities` | **PASS** — 8 verified tools incl. `intercity_options`, 2 `refuses`, 10 `known_gaps` |
| 1.4 | offline suites | **PASS — 285/285**, 19/19, 33/33 |
| 1.5 | `.state` snapshotted | **PASS** |
| 1.6 | call log truncated | **PASS** — 47 entries cleared after pre-flight |
| 1.7 | workspace cleared | **PASS** — run 5's deliverables archived first |
| 1.8 | environment | one server, `chrome_on_profile=0` |

## Step 1.5 — state

`state-before.json` held ten places from run 5. `state-baseline.json` is back to
`bengaluru, goa, panaji`, `device_id` unchanged. **Step 5 diffs against the baseline.**

## Step 2d — dates: **the run date moved**

The clock rolled over to **2026-09-06**, so today + 101 is now **2026-12-16, a Wednesday** —
not the 15th every previous run used. This is the floating-date design doing its job: the
prompt must be edited, and a subject cannot coast on a date another run established.

| Leg | Date |
|---|---|
| Outbound | **2026-12-16** (Wed) |
| Return | **2026-12-22** |
| Dudhsagar day trip | 2026-12-20 |
| Train ARP opens | 2026-10-17 — still outside the window, as intended |

**The pasted prompt must say "December 16th".** Every earlier run said the 15th.

A useful side effect: the indicative rail quote will now land on a Wednesday rather than the
Tuesday all previous runs saw, so the weekday-matching in `furthest_bookable` gets exercised
on a different day of the week for the first time.

## What this run is testing

**BUG-20's fix, in the hands of a subject.** Run 5 lost 6.6 minutes and its whole return leg
to `empty_valid` after ~99 s. The harvester now re-visits the funnel once inside the call and
says `blocked` in ~30 s if that fails. Live checks after the fix returned the previously
failing GOI→BLR leg in 35 s and 28 s. If flight searches now succeed first time, the budget
question that clouded run 5 disappears.

**BUG-19, finally exercised by a subject.** Every previous return-leg search failed, so no
subject has yet seen a GOI→BLR result with the departure exclusion applied. Live, that route
reports **13 of 25 itineraries departing from a different airport**. If the subject ends up
on a Sindhudurg flight again, the fix is wrong.

**H1, second confirmation.** It passed in run 5 after one sentence was added to the
`intercity_options` note. One pass is not a pattern.

**BUG-17's last gap.** A region-first query ("Goa Dabolim Airport") still falls through to
`fallback` because variants are stripped only from the right. Watch whether the subject
writes its airport query region-first and whether the resulting warning helps or annoys.

## Not done here — needs the human

- No reconnect needed: no tool added or removed since run 5, and the watcher hot-reloads code.
- Subject window on `mmt-acceptance-workspace`, one Cline window, reasoning model.
- **Paste the prompt with the date changed to December 16th.**
- At close-out: `cp .state/diagnostics/calls.jsonl harness/runs/2026-09-06-acceptance-6/`.
