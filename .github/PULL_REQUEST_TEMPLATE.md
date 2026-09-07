## What and why

<!-- What changes, and what problem it solves. The "why" matters more than the "what". -->

## How it was verified

<!-- Offline suites are the minimum. If this touches live behaviour, say what you actually
     watched happen - "tests pass" is not the same as "I watched it price a real route". -->

- [ ] `python tests/test_parsers.py`
- [ ] `python tests/test_version.py`
- [ ] `python tests/test_watch_server.py`
- [ ] `python tools/doctor.py`
- [ ] Live check (say which route/date, or N/A):

## Checklist

- [ ] A regression test exists for any bug fixed, named after the failure
- [ ] No new blended prices - base, tax and all-in stay separate
- [ ] Any new figure carries its unit in the field name (`nightly_`, `party_total_`, ...)
- [ ] Nothing is estimated silently; gaps are labelled
- [ ] Politeness preserved: no new polling, no extra retries, device id untouched
- [ ] If tool inputs or outputs changed, it is called out above (hosts need a reconnect)

## Scope

- [ ] This adds no booking, cart, payment, login or account path

<!-- That boundary is permanent - see CONTRIBUTING.md. PRs crossing it are closed. -->
