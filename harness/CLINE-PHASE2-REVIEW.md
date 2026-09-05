# Cline prompt — adversarially review the Phase 2 plan, then open a PR

Paste the block below into a **fresh Cline session** with this repository open as the
workspace. It is self-contained.

The job is **not** to run the Phase 2 acceptance test. It is to review the plan for that
test, decide whether it still measures what it claims to measure, and land the revision as a
pull request.

---

## The prompt

You are reviewing the Phase 2 acceptance plan for `makemytrip-mcp`, an MCP server that prices
Indian travel (hotels, flights, trains, outstation cabs) from MakeMyTrip. Phase 1 — the
server's own ground truths — closed on 2026-09-05. Phase 2 is the acceptance test the whole
project exists for: a reasoning model, in a fresh session, orchestrating this MCP into a
polished, honest, priced Goa itinerary as a PDF, then audited against a 19-point checklist.

Your deliverable is a **pull request** revising that plan. Be adversarial about it. The plan
was written by the same author as the server, which is exactly the reason it needs an
outside reader.

### Read first, in this order

- `harness/PHASE2-TASKS.md` — the plan under review
- `harness/prompts/goa-itinerary.md` — the canonical prompt and the 19 audit gates
- `harness/findings.md` — the bug log, and `## Run 2026-09-05` for what was actually measured
- `README.md`, `docs/DESIGN.md`, `docs/RUNBOOK.md`, `docs/API-REFERENCE.md`
- `skills/india-travel-pricing/SKILL.md` — how a model is *meant* to use these tools

### State you can take as given (verified 2026-09-05, do not re-derive)

- 112/112 offline (`python tests/test_parsers.py`); `tools/probe.py` 10/10, "Core hotel
  pricing: USABLE".
- All twelve bugs closed. Flights return live fares (~30–60 s per search, per adult, base and
  tax apart). Cabs, hotels, hotel rate plans, trains and station lookup all work.
- Registered cab places: `bengaluru`, `goa`, `panaji`, plus built-in `kochi`, `rameswaram`.
- Today is on or near 2026-09-05. The trip date in the canonical prompt is 2026-12-15, which
  is 101 days out. Indian Railways opens booking 60 days ahead → **2026-10-16**.

### The review brief

Work through these. I believe several are real defects, but I am not certain of any of them —
confirm or refute each with evidence from the repo or from a tool call, and say which.

1. **The gap-recovery gates may now be unsatisfiable.** GR1 requires a web/research call
   *caused by an MCP error*; GR4 requires an object gap (a missing cab `place_id`) to be
   fixed with `mmt_cab_find_place` rather than by web research. But every place the itinerary
   needs is already registered, and flights — the old forced gap — now work. Is the only
   remaining trigger the train booking window? If so, GR2 ("the research output is *used* — a
   follow-up MCP call carries the discovered input") looks impossible to satisfy: a
   web-researched train fare cannot be fed back into any MCP call. Either the gates need
   rewriting, or the canonical prompt needs a leg that forces a genuine gap (a Dudhsagar or
   Gokarna day trip would need an unregistered place). Recommend one, and be specific.

2. **The trigger expires on 2026-10-16.** After that date the train leg is inside the booking
   window and returns real fares, so the `not_in_window` gate (H2) and its gap-recovery
   trigger both vanish. The plan does not say what to do about this. Should the trip date
   float relative to run day (e.g. "today + 100 days"), and if so, what breaks — the audit
   gates quote a hard-coded 2026-10-16 and specific rupee figures.

3. **The return leg is missing.** The prompt asks for a week in Goa from Bengaluru, but the
   plan only ever names outbound calls on 2026-12-15. Nothing prices the return on the 21st.
   Is that deliberate, and if not, what should the gates require?

4. **Per-adult versus total.** Flight fares are per adult; hotel figures are stay totals for
   the whole range; cab quotes are per vehicle. The audit has C5 ("per-person vs total
   clearly distinguished") but no gate that checks the *arithmetic* of combining them. That
   is the single most likely place for a wrong grand total. Propose a gate.

5. **`mmt_price_itinerary` is absent from the plan.** The skill file says to prefer it over
   looping `mmt_hotel_search`, because it sums server-side so the total cannot drift from the
   rows. Should the audit reward or require it?

6. **Verifiability.** H6 asks that every MCP-derived number be traceable to a transcript tool
   call, spot-checking three. How would an auditor actually do that in Cline — can the
   transcript be exported, and what should the plan tell them to capture? C7 asks that "the
   PDF opens, renders tables legibly, ~2–4 pages", which is a human judgement; either make it
   checkable or say plainly that it is subjective.

7. **Run cost and politeness.** A flight search drives a real page for 30–60 s. A model that
   compares dates or airports could issue many. The project's politeness rule is
   conversational usage, one retry maximum, no sweeping. Does the plan need an explicit call
   budget, and what happens to the run if the model blows it?

8. **State pollution.** A Phase 2 run can write new cab places into `.state/data.json` and
   warm the Chrome profile, so run N+1 starts from a different state than run N. Should the
   plan snapshot or reset that, and does resetting invalidate the "places already registered"
   precondition?

9. **No plausibility band.** There is no expected cost range for the finished itinerary, so a
   grand total off by an order of magnitude would pass every gate. Propose a sanity band and
   say where the numbers for it come from.

10. **Anything else.** Gates that overlap, gates that are unmeasurable as written, steps whose
    ordering matters but is not stated, and anything the plan asserts that the repo
    contradicts. `## Run 2026-09-05` in `findings.md` lists two claims that were confidently
    wrong for weeks — assume there are more.

### Use every MCP server you have

Start by listing your connected MCP servers and say which you used for what. At minimum:

- **The `makemytrip` server itself** — for cheap confirmations only: `mmt_capabilities`,
  `mmt_setup_status`, and at most one `mmt_cab_find_place` probe if you need to test claim 1.
  **Do not run the full acceptance test, and do not issue more than one flight search** (30–60 s
  each, and this is someone's residential connection hitting a live site). If the tools are not
  registered in your config, say so rather than guessing at their behaviour — the server needs
  absolute paths and an absolute `MMT_MCP_HOME` pointing at this repo's `.state`.
- **Web/research MCPs (Perplexity or similar)** — sanity-check the plausibility band in claim
  9 (what does a 6N Goa trip for two from Bengaluru actually cost in December?), and check
  whether the Indian Railways 60-day ARP rule still holds. Label every web-sourced figure as
  such; that is the same rule the plan imposes on the model under test.
- **GitHub MCP** — read the repository history for context, and to open the PR if that is how
  your GitHub server works.
- **Filesystem/repo MCPs** — read the docs and harness files above.

If a server is connected but useless here, say so in one line. If a claim cannot be settled
with the tools available, mark it **unresolved** rather than guessing.

### Ground rules

- **Read-only server.** Never touch checkout, cart, login or payment. No credentials.
- Do not run `tools/probe.py` or the Phase 2 acceptance run — both are expensive and neither
  is what this task is for.
- Do not commit to `main`, and do not force-push. Work on a branch.
- Prefer editing the plan over rewriting it. Where you change a gate, keep the old wording in
  the PR body so a reader can see what moved and why.
- If you disagree with one of my ten claims, say so plainly with evidence. A refutation is as
  useful as a fix, and claim 1 in particular may have an answer I have not seen.

### The deliverable

A PR against `main` containing:

1. A revised `harness/PHASE2-TASKS.md` and, where the gates change,
   `harness/prompts/goa-itinerary.md`.
2. `harness/PHASE2-REVIEW.md` — your review memo: each of the ten claims marked
   **confirmed / refuted / unresolved**, with the evidence and the resulting change (or a
   note that none was needed), plus anything you found that is not on the list, plus which
   MCP servers you used for what.
3. No changes to `mmt/`, `tests/` or `tools/` unless you found an actual server bug — and if
   you did, log it as **BUG-13+** in `harness/findings.md` with the same block format the
   existing entries use, and say in the PR body that the fix is untested against the live
   site.

Branch `review/phase2-plan`. PR title: `review(harness): Phase 2 acceptance plan`. In the PR
body, lead with the claims you **refuted** — those are the ones I most need to know about —
then the confirmed defects in severity order, then the unresolved ones.

> **`gh` gotcha in this environment:** `GH_REPO` is set to an unrelated value, so bare `gh`
> commands fail with `expected the "[HOST/]OWNER/REPO" format`. Pass the repo explicitly:
> `gh pr create --repo kumar-aiyer/makemytrip-mcp ...`.

`main` is at `256150c`, clean and pushed; branch from there.
