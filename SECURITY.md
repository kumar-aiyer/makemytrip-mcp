# Security

## Reporting a vulnerability

Please **do not open a public issue** for a security problem.

Use GitHub's private vulnerability reporting on this repository:
**Security → Report a vulnerability**. That reaches the maintainer privately and keeps the
report out of the public tracker until it is fixed.

Expect an acknowledgement within a few days. This is a personal project maintained in spare
time, so please be patient with the timeline.

## What is in scope

- Anything that could execute code on a user's machine through the server, its tool
  arguments, or a crafted response from the site it reads.
- Anything that writes outside the state directory (`~/.makemytrip-mcp` by default).
- Anything that leaks the contents of that directory — it holds a device id, a browser
  profile with makemytrip.com cookies, and a log of every tool call with its results.

## What is not

- **Missing booking, payment or login features.** Their absence is deliberate and permanent;
  see [CONTRIBUTING.md](CONTRIBUTING.md).
- **MakeMyTrip blocking you.** The server reads undocumented internal endpoints and the site
  can change or refuse at any time. That is expected behaviour, not a vulnerability.
- **Use from a datacenter IP.** MakeMyTrip's CDN answers those with HTTP 403 by design.

## What the server does with your data

Everything stays on your machine. The server sends requests to makemytrip.com and nowhere
else. It has no telemetry, no analytics and no network destination other than the site it
reads. Locally it keeps:

| Path (under the state directory) | What it holds |
|---|---|
| `data.json` | a stable device id and the cab pickup/drop places you have registered |
| `chrome-profile/` | a browser profile, including makemytrip.com cookies |
| `diagnostics/calls.jsonl` | every tool call with arguments and results, rotated at 16 MB |
| `diagnostics/failures.jsonl` | failed fetches, for debugging |

Delete the state directory to reset all of it. Set `MMT_CALL_LOG=0` to turn off the call
log.
