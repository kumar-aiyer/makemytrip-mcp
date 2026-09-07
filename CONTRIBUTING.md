# Contributing

Thanks for looking. This is a small, deliberately narrow project and it stays that way.

**Every change needs the maintainer's approval before it merges.** Open a pull request;
`@kumar-aiyer` is a required reviewer on everything via [CODEOWNERS](.github/CODEOWNERS).
Please do not push to `main`.

## What this project is, and is not

It reads **live Indian travel prices** — flights, trains, cabs, hotels — from MakeMyTrip
and hands them to an MCP host on **one person's desktop**, to help plan a trip.

It is **read-only by construction**. There is no booking, cart, payment, login or account
path anywhere in it, and none will be accepted. That is not a missing feature, it is the
boundary the project is built on. A pull request that adds one will be closed.

Also out of scope: scheduled polling, price-history harvesting, bulk or multi-user
operation, anything that rotates the device id, and anything that turns this into a hosted
service.

## The rules a change has to keep

These come from real bugs, each of which is written up in
[`harness/findings.md`](harness/findings.md). They are the review criteria.

1. **Never present an unvalidated value as a good one.** Almost every bug this project has
   had is that one bug in different clothes: an Akamai stub counted as a successful fetch, a
   nightly rate labelled a stay total, a flight from a different state offered as a Goa
   departure, a car-rental office registered as an airport, a blocked page reported as an
   empty route. Prefer a clear error to a plausible number.
2. **Put the unit in the name.** `nightly_all_in_inr`, not `all_in_inr`. Mixing a per-adult
   fare with a per-vehicle one is how trip totals go wrong.
3. **Base and tax stay separate.** Every price surfaces as base, tax and all-in. Never emit
   a single blended figure.
4. **Guidance goes where the caller is looking.** A correct value in a place nobody reads is
   not a correct answer — a rule stated in one tool does not reach a caller using another.
5. **Politeness is a feature.** One stable device id, concurrency capped at 4, one retry
   maximum, no scheduled polling, request volume near what a person browsing would generate.
6. **Don't estimate silently.** If the server cannot know something — door-to-door travel
   time, a fare for a date outside the booking window — say what it does know and label the
   gap.

## Running the checks

```bash
python -m pip install playwright     # runtime dependency, optional for the offline suites
python tools/doctor.py               # will this even start on this machine
python tests/test_parsers.py         # offline: parsers, arithmetic, tool surface
python tests/test_version.py
python tests/test_watch_server.py
```

The offline suites need **no network, no browser and no playwright** — they assert on
structure and arithmetic, never on particular rupee figures, because live prices drift daily
and a test that pins one fails for the wrong reason. CI runs exactly these on every pull
request.

`python tools/probe.py` is the live gate. It drives real searches, so it needs Chrome and a
residential connection, and it is not run in CI.

## Pull requests

- One concern per PR, with the reasoning in the description — *why*, not just *what*.
- Add a regression test for any bug you fix. Name it after the failure, not the function.
- Match the surrounding style: comments explain why something is the way it is, especially
  where the obvious approach was tried and did not work.
- If you changed tool inputs or outputs, say so plainly — hosts snapshot the tool list at
  connect and a schema change needs a reconnect.
- If a change affects live behaviour, say how you verified it. "Tests pass" is not the same
  as "I watched it price a real route".

## Reporting bugs

Use the issue templates. A live-pricing bug is much easier to act on with the relevant lines
from `~/.makemytrip-mcp/diagnostics/calls.jsonl`, which records every tool call with its
arguments and result. **Read it before pasting** — it contains your searches.

## Licence

By contributing you agree that your contributions are licensed under the
[MIT License](LICENSE) that covers this project.
