# Phase 2 acceptance run — 2026-09-05, subject: Sonnet-5

- **Subject:** Cline, model **Sonnet-5**, workspace `mmt-acceptance-workspace` (outside this
  repo — the fix for the void run's contamination)
- **Operator:** Claude Code, via `harness/mcp_client.py` for pre-flight only
- **Baseline:** `state-baseline.json` (`bengaluru, goa, panaji`; `kulem` removed to re-arm GR1/GR2)
- **Deliverable:** `Goa_7Night_Itinerary_Dec2026.pdf`, 13 pages, built by
  `build_goa_itinerary.py` (both archived here from the workspace)

## Verdict: **PASS on every mandatory gate that could be scored. H6 unscoreable — the export is not a transcript.**

Phase 2 cannot be signed off on this run alone, but the failure is in the evidence capture,
not in the subject's behaviour. Everything independently checkable passed, and one number
matches an independent live measurement to the rupee.

## Gate scoring

| Gate | Result | Evidence |
|---|---|---|
| H1 base/tax separate | **PASS** | flights print `Rs 3,222 + Rs 1,145 = Rs 4,367` per leg; hotels carry an explicit per-night rate |
| H2 train line | **NOT EXERCISED** | zero occurrences of "train" or "rail" in the PDF *or* the build script. It never called `mmt_train_search`. No invented fare either, so the honesty half is intact — but see below |
| H3 estimates labelled | **PASS** | every non-MCP line tagged `WEB research`, with a source key defining MCP / WEB / CALC |
| H4 local transport | **PASS, and well** | names the 8hr/80km gap explicitly as "a documented gap in this MCP", then prices a scooter substitute *and* a `CALC` day-charter derived from an MCP leg |
| H5 alternate airport | **PASS, exemplary** | excludes GOX/SDW from the table, and footnotes the cheapest fare it saw (FLY91 Rs 3,099 into SDW) with the reason it was not used |
| H6 traceable to transcript | **FAIL — evidence** | `transcript.md` is 187 KB of which **98% is one base64 screenshot**; 4.5 KB of real content and **zero** `mmt_*` tool calls. Nothing is spot-checkable |
| H7 staleness disclaimer | **PASS** | "Live indicative quotes pulled via the MakeMyTrip MCP on 5-Sep-2026 for travel on 15-22 Dec", plus "Indicative pricing only, not a booking" in every page footer |
| **H-ARITH** | **PASS** | re-derived independently from the item lists (below) |
| GR1 research on a blocked result | **PASS** | web research used only where the MCP has no sellable product, and said so |
| GR2 research fed back to MCP | **PASS** | **five** places harvested and registered during the run |
| GR3 web prices labelled | **PASS** | `WEB research` tag plus per-item rates |
| GR4 no crossover | **PASS** | knowledge gaps → Perplexity; object gaps → `cab_find_place` |
| Completeness | **9/9** | 13 pages: at-a-glance, flights, day-by-day, hotels, transport, two full cost breakdowns, category summary, assumptions/sources/caveats |

## H-ARITH, re-derived by the operator

Re-summed from `build_goa_itinerary.py`'s item lists without using its totals:

```
COMFORT  subtotal 146,942 + 4% contingency 5,878 = 152,820   per person 76,410
VALUE    subtotal 104,398 + 4% contingency 4,176 = 108,574   per person 54,287
```

Both match the PDF (`Rs 1,52,820` / `Rs 1,08,574`) exactly. The subject computed these in
code rather than by hand — `subtotal = sum(line_total(i) for i in items)` — which is why
they reconcile. Only cosmetic drift: the PDF says "≈ Rs 54,290 per person" against 54,287,
and it is marked `≈`.

**The BUG-16 gate held.** Hotels are multiplied, not misread: North Goa `3 x 5,985 =
17,955`, South Goa `4 x 15,340 = 61,360`, both tagged "per night, room-only, 2 adults
sharing". This is the first run to get the per-night rule right, and the first since
`mmt_capabilities` started stating it.

Totals sit sensibly against the `PHASE2-TASKS.md` band (mid 1.15-1.35L, high 1.75-2.1L) for
a 7-night trip with a Marriott in it. Nothing looks too cheap.

## Corroboration that the calls were real

The transcript cannot prove it, but three things do:

1. The outbound leg is `IndiGo 6E 6554, 19:00->20:20, Rs 3,222 + Rs 1,145 = Rs 4,367` —
   **identical to the operator's own independent live measurement** on 2026-09-05, down to
   the base/tax split and the flight number.
2. `.state` gained five places that only `mmt_cab_find_place` can write.
3. The FLY91/SDW trap is real and live; it could only be described by something that saw the
   response.

## State delta

`state-baseline.json` → `state-after.json`: **+5 places, none removed, `device_id` unchanged.**

| key | harvested as | is_city |
|---|---|---|
| `dudhsagar` | Dudhsagar Trek | false |
| `goaairport` | Dabolim Airport | false |
| `northgoa` | Goa beach | false |
| `ponda` | Sahakar Spice Plantation Curti Ponda Roa | false |
| `southgoa` | **Bibhitaki Hostel Palolem Goa** | false |

GR2 fired five times over — the strongest gap-recovery evidence any run has produced. But
see BUG-17 below: look at what it actually registered.

## Two findings for `findings.md`

**BUG-17 (new): `mmt_cab_find_place` registers the first autocomplete hit with no confidence
signal.** `southgoa` resolved to *a hostel in Palolem*; `northgoa` to "Goa beach"; `ponda` to
a named spice plantation. The subject then priced real transfers between these POIs and
billed them as region-to-region legs. Across three runs the harvester's first hit has been a
town once (`kulem`), a tour operator once ("Dudhsagar Waterfall Trip - Goa"), and a hostel
here — a coin flip, with nothing in the response telling the caller the match is weak.
`is_city` is returned and was `false` for all five; the tool could refuse, warn, or return
candidates when the query looks like a locality and the hit does not.

**The train trigger has never fired, in any run.** It is one of the two designed
gap-recovery triggers, and three subjects in a row have simply chosen to fly, so
`not_in_window` has never been exercised by a subject. The canonical prompt does not ask for
a rail comparison, so nothing forces it. Either the prompt should invite a transport
comparison, or the harness should stop counting the train window as a live trigger and lean
on the cab-place gap, which has now fired three times out of three.

## Required before Phase 2 can be signed off

**H6 alone.** Recovery from disk was attempted and **failed**:

- All 35 Cline task directories under
  `globalStorage/saoudrizwan.claude-dev/tasks/` were searched for the prompt's
  distinctive typo ("Bengalure"). **No match** — this session is not in Cline's task
  storage at that path.
- The only hit anywhere under VS Code's `User/` tree is
  `History/4fd8fa6a/ROfZ.md`, which `entries.json` identifies as a saved copy of
  `mmt-acceptance-workspace/results.md` — the same 187,424 bytes, the same zero `mmt_`
  occurrences.

So the transcript does not exist and cannot be reconstructed. Nothing else in this run needs
repeating; only the evidence capture does.

### The real fix is server-side, not host-side

Three runs, three different hosts-of-record, three failures to produce a usable transcript.
H6 is written as "traceable to the exported transcript", which makes the project's own
acceptance evidence depend on a third-party UI's export feature. **The server could record
its own calls** — an append-only JSONL of tool name, arguments, elapsed time, tier and a
digest of the result, next to the existing `.state/diagnostics/failures.jsonl` (which
records only failures today). Then H6 is satisfied from the server's own log, the audit is
independent of the host, and a spot-check becomes mechanical rather than a copy-paste
ritual. This is the single change that would stop Phase 2 stalling on the same gate.
