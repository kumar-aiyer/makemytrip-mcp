---
name: india-travel-pricing
description: Use when pricing or comparing Indian travel - hotels, flights, trains or outstation cabs - with the makemytrip MCP tools. Triggers on "price the hotels", "what would the cab cost", "compare against the operator quote", "how much for the train", "cost this itinerary".
---

# Pricing Indian travel with the makemytrip tools

Call `mmt_capabilities` first when starting a costing exercise. It reports which tools are
verified, which are experimental, and the booking windows, which differ by travel mode.

## Quoting prices

Always quote **base and tax separately, then the all-in figure**. MakeMyTrip displays them
apart and the all-in is roughly 18% above the headline; a single blended number is how
budgets end up understated.

Hotel prices are **per night**, not stay totals for the range. Multiply by nights for a
trip budget - the tools return `stay_estimate_all_in_inr` (`nightly x nights`) for this, and
it is an **estimate**: MakeMyTrip quotes one representative nightly rate per range, not a
per-date breakdown. The fields are `nightly_base_inr`, `nightly_tax_inr`, `nightly_all_in_inr`; the
`nightly_` prefix is load-bearing. Anything that says "stay totals" or
`all_in_per_night_inr` predates 2026-09-05 and is wrong.

For an intercity leg use `mmt_intercity_options` rather than calling the flight, train and
cab tools separately and comparing by hand. Flights and trains are quoted per person and a
cab per vehicle; mixing those units is the single most common way a trip total goes wrong,
and the tool does that arithmetic once, keeping `unit` visible on every row. It marks an
option `dominated` when another is both cheaper and faster - beyond that it does not
recommend, because the trade-off depends on the whole itinerary. It also surfaces the train
leg whether or not you would have thought to ask, which matters: outside the 60-day
reservation window the honest answer is `not_in_window`, not silence.

For a multi-stop trip use `mmt_price_itinerary` rather than looping `mmt_hotel_search`. It
multiplies each leg by its own nights and sums the legs it just fetched, returning
`total_all_in_estimate_inr` in the same object, so the total cannot drift from the rows above
it. Never add nightly rates across legs yourself - a two-night stay would count the same as a
fortnight.

## Reading empty results

An empty result on this site is usually a **constraint, not an absence**. Read the `kind`
and `warning` fields rather than reporting "nothing found":

- `not_in_window` - trains only. Indian Railways opens reservations 60 days ahead; the
  result carries `booking_opens`. Say when to look again.
- `unregistered_place` - cabs. The place needs registering with `mmt_cab_find_place`, or
  `mmt_cab_add_place` with a URL the user pastes.
- `bad_input` - a city, station or airport name the server does not know. The error lists
  what it does know.
- `null_prices` - rows came back with no prices. A configuration problem in the server, not
  an availability problem. Say so.
- A property returning nothing may simply **not be sold on MakeMyTrip**, which is different
  from being sold out. Do not conflate them.

## Booking

These tools cannot book, and that is deliberate. Treat every figure as a **benchmark**.
When the user is ready to book, direct rates with the hotel on a flexible, free-cancellation
rate are usually at or below the OTA figure and leave the reservation in the hotel's own
system.

These are retail rates. A tour operator buys below them, so when comparing against a
package quote, use these as a private scorecard rather than an opening number.

## Speed

A first call in a session starts a browser and takes up to about 20 seconds; later calls are
a few seconds. Results are cached for 20 minutes - pass `fresh: true` when the user
explicitly wants a re-check. If several calls are slow, `mmt_selftest` reports which tier the
router has fallen back to and why.
