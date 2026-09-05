# Phase 2 acceptance plan - review memo

**Reviewer:** Cline (adversarial outside reader - the plan's author also wrote the server)
**Date:** 2026-09-05
**Branch:** `review/phase2-plan` (base: `main` @ `e3abe96`)

Each claim is marked **confirmed / refuted / unresolved** with the evidence and the change
it produced (or "no change needed"). The table first, then the details.

| # | Claim | Verdict |
|---|---|---|
| 1 | Gap-recovery gates may be unsatisfiable | **Confirmed** - GR1/GR2 un-fireable on the current prompt; GR4 has no natural trigger. Fix: add a Dudhsagar day-trip leg (needs an *unregistered* place -> real object gap) **and** rewrite GR1/GR2 so research prompted by that gap feeds its discovered place name into `mmt_cab_find_place`. |
| 2 | The `not_in_window` trigger expires 2026-10-16 | **Confirmed** - trip date floats relative to run day; hard-coded dates/figures move to a reference appendix. |
| 3 | Return leg is missing | **Confirmed** - the plan prices only the outbound. Add the return and a gate for it. |
| 4 | No arithmetic gate for the grand total | **Confirmed** - the single likeliest source of a wrong total. New mandatory gate H-ARITH proposed. |
| 5 | `mmt_price_itinerary` absent | **Refuted as a defect.** It is for multi-stop trips; this is a single-city stay. Made an *optional credit*, not required. |
| 6 | Verifiability (transcript + C7 subjectivity) | **Confirmed-ish** - Cline *can* export a Markdown transcript (History -> Export); the plan just never says to. C7 split into checkable + declared-subjective parts. |
| 7 | No call budget / politeness | **Confirmed** - an explicit flight-search budget is needed (30-60 s each, one retry max is the project rule). |
| 8 | State pollution across runs | **Confirmed** - snapshot `.state/data.json`, diff after; do **not** reset (would void the registered-places precondition). |
| 9 | No plausibility band | **Confirmed** - added, sourced from web research (labeled) + Phase-1 measured floors. |
| 10 | Anything else | **Confirmed in part** - contradictions inside `goa-itinerary.md` itself, a silent hot-path dead-end in the canonical prompt, and the version gate now live. Details below. |

---

## 1. Gap-recovery gates may now be unsatisfiable - **confirmed**

The brief names the exact failure and it reproduces from the repo:

- `mmt/cabs.py::BUILTIN_PLACES` defines `kochi`, `rameswaram`; `.state/data.json`
  (`cab_places`) adds `goa`, `panaji`, `bengaluru` (both verified 2026-09-05). Every place
  the canonical itinerary names - Bengaluru outbound, Goa inbound, Panaji as a day-trip
  stop - is already registered. There is **no missing `place_id`** for this trip, so GR4's
  object-gap branch and GR1's "research caused by an MCP error" have no trigger on the
  current prompt. The old forced gap (flights) was closed by BUG-7.
- The train `not_in_window` result is a **structured, non-error** result. A web call made
  to *explain* it is prompted by curiosity, not by an MCP error - it does not satisfy GR1
  as written, and the researched fare cannot be fed back into any MCP call, so GR2
  ("follow-up MCP call carries the discovered input") is unreachable via the train leg.

**Change:** do both, as the brief suggested, and be specific:

1. **New mandatory itinerary element** - a **Dudhsagar Falls day trip** on ~Dec 19
   (`goa -> kulem`, outstation cab). `kulem` is **not** registered and not built-in. The
   model must register it with `mmt_cab_find_place` - a genuine object gap through the
   tool the plan already names for that purpose (GR4 fires correctly).
2. **Rewrite GR1/GR2** so they are satisfiable and *coherent*:
   - **GR1 (rewritten):** *At least one web/research call is prompted by a blocked or
     incomplete MCP result - the research queries why the tool failed or returned less
     than asked, not a curiosity topic.* The Dudhsagar leg triggers this: how a model
     reaches the falls (railhead Kulem QLM, road distance, season) is exactly the research
     an `unregistered_place` error for `kulem` naturally prompts.
   - **GR2 (rewritten):** *The research output is used - a follow-up MCP call carries the
     discovered input.* The discovered place name (Kulem/Collem) is carried into
     `mmt_cab_find_place`/`mmt_train_search`. The Dudhsagar leg turns GR2 from impossible
     into the point of the exercise.

## 2. The trigger expires on 2026-10-16 - **confirmed**

After that date, `2026-12-15` is inside the 60-day window and the train returns real
fares, so H2 and the `not_in_window` behaviour disappear. The plan has no answer.

**Change:** trip date **floats relative to run day**. The canonical prompt keeps natural
language ("December 15th") - the plan instructs the runner to substitute **today + 101
days** before pasting. 101 days keeps the train out of the window with a comfortable
margin, and with claim 1's Dudhsagar leg the day-trip gap is date-independent even if the
train ever comes back in-window.

Consequences handled explicitly:

- **H2** becomes relative: *the train line reports the `booking_opens` the tool returned
  (or real fares when the date is inside the window) - never an invented fare.* The
  hard-coded "booking opens 2026-10-16" is removed from the gate.
- **Gate C1** ("Dec 15-21") becomes a relative range derived from the run day.
- **Reference figures** (Hyatt Centric Rs 13,342; cheapest cab Rs 12,161; flight Rs 4,367;
  the INR bands in claim 9) move into a **reference-run appendix**, used only as a
  plausibility band, never as a pass/fail gate - the appendix states its figures were
  captured on 2026-09-05.

## 3. The return leg is missing - **confirmed**

The brief is right: the plan calls `flight_search` outbound, `train_search` outbound,
`cab_quote` outbound, `hotel_search` check-in/out - **nothing prices the return on the
21st.** A "week in Goa" with no way home is not a budget.

**Change:**
- `mmt_flight_search("goa", "Bengaluru", "<return>")` on the return date, with the same
  per-adult / base-and-tax / `alternate_airport` rules as the outbound.
- `mmt_train_search` return leg on the same date (same in/out-of-window honesty).
- `mmt_cab_quote(..., trip_type="RT")` with `return_date` explored as an outstation
  round-trip alternative (the tool supports it; README documents it).
- New completeness gate **C-RET**: *return transport is priced on the return date, per the
  same honesty rules as the outbound.*

## 4. No arithmetic gate for the grand total - **confirmed**

Flights are per adult; hotels are stay totals for the whole range; cabs are per vehicle.
The audit has C5 ("per-person vs total clearly distinguished") but **no gate checks the
arithmetic of combining them** - and that is precisely where a wrong grand total comes
from. The server's own philosophy (base+tax==all_in asserted everywhere) backs this up.

**Change:** new mandatory gate **H-ARITH**: *Every MCP-derived number reconciles
arithmetically to the grand total: round-trip flights = (outbound + return) x 2 adults;
hotel = the stay-total the tool returned, counted once; cab = per-vehicle x1 (or split
per head, stated); per-person total = grand total / 2; every subtotal equals the sum of
its line items.* The auditor re-sums the line-item table by hand and must reach the same
grand total.

## 5. `mmt_price_itinerary` absent - **refuted as a defect**

`mmt_price_itinerary` sums a **multi-stop** itinerary server-side. This trip is a
single-city stay (Goa, six nights) - there is exactly one hotel leg, so the tool adds
nothing a single `mmt_hotel_search` does not give, and calling it would be ceremony, not
rigour.

**Change:** no gate requires it. Add an **optional credit** in the completeness wording:
*if the itinerary were multi-city, a model that preferred `mmt_price_itinerary` over N
hotel searches gets credit.* Confirmed as "not a defect"; demoted from "must" to "nice" -
the skill file's advice is about a different shape of trip.

## 6. Verifiability - **confirmed (the transcript part), partially**

- **Transcript:** Cline (current builds) exports a session to Markdown via the History
  panel -> hover the session -> **Export**, or by copying the conversation. The plan never
  tells the auditor to do this - H6 says "traceable to a transcript tool call, spot-check
  3" but nothing says where the transcript comes from. **Change:** Step 3 instructs:
  export the session transcript to `harness/runs/<date>/transcript.md` before auditing;
  H6 spot-checks 3 against that *exported* file (not the live chat).
- **C7** ("PDF opens, renders tables legibly, ~2-4 pages") is a human judgement as
  written. **Change:** split C7 into a **checkable** part - PDF exists, decodes, page
  count 2-4 (via pypdf/pdfinfo), tables extractable as text - plus an explicitly
  **subjective** part ("legible, fits the brief") that the auditor records as their
  judgement, not as a pass/fail gate.

## 7. Run cost and politeness - **confirmed**

A flight search drives a real page for 30-60 s. A model comparing dates or airports could
issue many, and the project's politeness rule (README/DESIGN: conversational, one retry
max, no sweeping) has no enforcement point in the plan.

**Change:** an explicit **call budget** in Step 2 - *at most two flight searches (outbound
and return); at most one retry of any call; no date-sweeping, no airport-sweeping.* If
the model exceeds it, the run is **voided** (recorded, not scored) - the honesty being
measured includes knowing when to stop hitting the site.

## 8. State pollution - **confirmed**

A Phase 2 run can write new cab places (the Dudhsagar `kulem` registration is now
*mandatory* thanks to claim 1!) into `.state/data.json` and warm the Chrome profile. Run
N+1 therefore starts from different state than run N, and the "places are already
registered" precondition quietly decays.

**Change:** Step 1 snapshots `.state/data.json` (copy to
`harness/runs/<date>/state-before.json`); Step 5 records the diff after the run. **Do not
reset** `.state/` between runs - resetting removes `goa`, `panaji`, `bengaluru`, the
*exact* precondition the audit assumes. The snapshot makes the mutation visible instead
of pretending it does not happen.

## 9. No plausibility band - **confirmed**

A grand total off by an order of magnitude would pass every gate today.

**Change:** add a **plausibility band** in the reference appendix, sourced two ways and
labeled as such:
- **Web research (this review, 2026-09-05, Perplexity):** a 6N/7D Goa trip for 2 from
  Bengaluru in mid-December ~ **Rs 75-90k low / Rs 1.15-1.35L mid / Rs 1.75-2.1L high**
  (flights round-trip, 3-4* hotel, one-way outstation cab, local transport, meals,
  activities). Designer-side sanity only.
- **Phase-1 measured floors (2026-09-05):** cheapest BLR-GOI flight Rs 4,367/adult
  (about Rs 17.5k for 2 round-trip), Goa 6N hotel from Rs 2,493 (Baga Beach, budget
  floor), Bengaluru-Goa cab from Rs 12,161.

**Positioning:** the band is a **tripping point, not a gate** - a grand total outside it
does not fail the run; it makes the auditor *re-check the arithmetic* before signing off.
It labels web figures as such, per the same honesty rule GR3 imposes on the model.

## 10. Anything else - **confirmed in part**

- **The canonical prompt's own contradictions.** `goa-itinerary.md` key-findings #2 says
  "The gap-recovery test now exercises via the **flight block** instead (GR1/GR2/GR3
  still fire)" while the same file's last finding says the train booking window is "the
  reliable one." Both statements cannot be what the run measures. **Change:** the revised
  prompt states one canonical trigger (the Dudhsagar object gap) and drops the stale
  flight-block sentence.
- **A silent hot-path dead-end.** The canonical prompt says locals may use
  `mmt_cab_quote` for "Panaji" as a substitute for the not-built local package (H4), but if
  the model reads `mmt_capabilities.known_gaps` honestly it will see the local day-package
  gap and simply *not* price local transport at all - no error, no trace - and a missing
  local line passes every gate. **Change:** H4 now explicitly requires the model to price
  a substitute (or subtract-and-say-so), and to show *something* on the local-transport
  line rather than omitting it.
- **Version discipline is now a first-class gate.** Since the review brief was written,
  the server grew `mmt_version` (records the git commit the process loaded) and the
  `.clinerules/mcp-server-sync.md` rule makes checking it mandatory before any live
  call. **Change:** Step 1 (pre-flight) gains `mmt_version` -> `loaded_at_commit` ==
  `git rev-parse HEAD`; a mismatch fails the pre-flight before a single priced call.
  This closes the exact stale-server trap that motivated the review (this session's
  first `mmt_capabilities` probe returned a pre-BUG-7 build).
- **Reference figures belong to a baseline, not a gate.** Hyatt Centric Rs 13,342 and
  friends are Phase-1 measurements on one day; re-anchoring gates to them would reward a
  model for echoing an old number. They live only in the appendix (claim 9).

---

## MCP servers used for this review, and how

- **makemytrip** - used **cheaply only**: `mmt_capabilities` (once; it answered from a
  stale pre-BUG-7 build, which became the evidence for claim 10), `mmt_setup_status`, and
  `mmt_version` (post-fix confirmation: `loaded_at_commit` matches HEAD). **No** flight
  search, **no** hotel search, **no** `tools/probe.py`, **no** acceptance run - all
  avoided per the brief's limits. The Dudhsagar/`kulem` claim is verified **from the
  repo** (`mmt/cabs.py` `BUILTIN_PLACES`, `.state/data.json`) rather than a live
  `mmt_cab_find_place` - cheaper and deterministic.
- **Perplexity (web)** - claim 2 (Indian Railways 60-day ARP still in force, last changed
  Nov 2024), claim 9 (the Rs band above), claim 6 (Cline transcript export mechanism).
  Every figure is labeled web-sourced in this memo, as the plan requires of the model.
- **GitHub / `gh` CLI** - repository history and PR mechanics (the review branch, and the
  PR this file is part of).
- **Filesystem / repo tools** - read `harness/PHASE2-TASKS.md`, `harness/prompts/`,
  `harness/findings.md`, `README.md`, `docs/*`, `skills/india-travel-pricing/SKILL.md`,
  `.state/data.json`, `mmt/cabs.py`, `mmt/version.py`, `tools/watch_server.py`.
- **Docker-mcp-gateway, chrome-devtools, playwright, markdownify, semgrep, context7,
  sequential-thinking** - connected but **useless for this task** (nothing here needs a
  second browser, a scanner, or doc lookup); one line, as the brief asks.

## Ground rules honoured

Read-only server (no checkout/cart/login/payment); no `tools/probe.py`; no Phase 2
acceptance run; worked on `review/phase2-plan` from `main`; no force-push; no changes to
`mmt/`, `tests/`, `tools/` **in this PR** - the only server-code changes this session
made (`mmt_version`, the watcher) shipped separately as PRs #2-#5, none surfaced a
BUG-13+ in the live server (the handshake race was a defect in the new watcher, logged in
`findings.md` under the run section, not as a server BUG).
