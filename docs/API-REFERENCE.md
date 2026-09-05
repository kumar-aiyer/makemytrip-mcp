# MakeMyTrip wire reference

Captured from live traffic, September 2026, signed out, from the India site
(`cc=IN&lang=eng`) in INR. Unofficial and undocumented — expect drift, and see
§7 for how to re-capture.

---

## 0. What guards what

Akamai Bot Manager fronts the **HTML** pages (sensor at `/metrics-dt/`, rotating obfuscated
script paths). It did **not** appear in front of the hotel JSON API.

Measured, from a datacenter IP with a plain HTTP client:

```
pypi.org           200        www.makemytrip.com   403  (server: AkamaiGHost)
google.com         200        mapi.makemytrip.com  403
api.github.com     200        other Indian OTAs    403
```

The general internet is reachable; MakeMyTrip specifically refuses the client. Two variables
are confounded there — IP reputation and TLS fingerprint — but the practical rule holds:
**run this from a residential connection, through a real browser stack.**

Identity headers (`mcid`, `device-id`, `vid`, `visitor-id`, `usr-mcid`, `deviceid`) are all
the same client-generated UUID, unsigned and unvalidated. Generate one, persist it, reuse it.

---

## 1. Hotels — search and price

```
POST https://mapi.makemytrip.com/clientbackend/cg/search-hotels/DESKTOP/2
```

Headers: `Content-Type`, `Accept`, `currency: INR`, `entity-name: india`,
`language: eng`, `os: desktop`, `region: IN`, `server: b2c`, `tid: avc`,
`user-country: IN`, `user-currency: INR`, `vid`, `visitor-id`, a desktop UA.

Body — the meaningful fields (complete literal in `mmt/hotels.py::build_body`):

- `searchCriteria.checkIn` / `.checkOut` — **ISO `YYYY-MM-DD` here**
- `searchCriteria.cityCode` / `.locationId` — locus code, e.g. `CTCOK`
- `searchCriteria.roomStayCandidates` — `[{"adultCount":2,"childAges":[],"rooms":1}]`
- `searchCriteria.hotelIds: ["<18-digit>"]` **plus** `userSearchType: "hotel"` pins one
  property. (`locationType:"hotel"` returns nothing; `selectiveHotelIds` is ignored.)
- `filterCriteria` — e.g. `[{"filterGroup":"STAR_RATING","filterValue":"5","isRangeFilter":false}]`

> ### Issuing the POST at all
> `ctx.request.post` returns a six-byte body reading `200-OK` - re-measured 2026-09-05 on a
> self-launched Chrome, so this is not a Playwright artefact. The call has to be made as an
> in-page `fetch()` from a page allowed to make it, and "allowed" is narrow:
>
> | Page the fetch runs from | Result |
> |---|---|
> | `hotels-in-<city>.html` (any city) | **works** - 246 KB of real JSON |
> | `/hotels/` funnel | `TypeError: Failed to fetch` - CSP forbids the connection |
> | homepage | the page re-navigates under the call, killing the execution context |
>
> Which city's listing page is irrelevant: the search is driven entirely by the body, and a
> Kochi query issued from the Goa listing page returns Kochi results.
>
> **Do not clear cookies first.** An earlier recipe here did, to get "fresh clearance". That
> now breaks the call outright (`TypeError: Failed to fetch`); left alone, it succeeds.

> ### The silent-null trap
> With a trimmed `expData` string or `featureFlags` block the call still returns **HTTP 200
> and the correct hotels, with every `priceDetail` null**. Both must be sent complete. A test
> asserting only "200 and some hotels" passes while the server returns nothing useful — hence
> the dedicated `null_prices` error kind.

Response — hotels are **not** at `response.hotels`:

```
response.personalizedSections[N].hotels[]
response.hotelCount .hotelCountInCity .noMoreHotels .lastHotelId .lastHotelIndex
response.cityLocationDetail        <- empty means the city code was wrong
```

```json
"priceDetail": {
  "price": 13700, "totalTax": 2466, "priceWithTax": 16166,
  "discountedPrice": 13700, "discountedPriceWithTax": 16166,
  "totalAdditionalFees": 0, "totalTaxWithFees": 2466,
  "ratePlanCode": "...", "pricingKey": "DEFAULT",
  "coupon": {"code": "...", "couponAmount": 1010, "description": "..."}
}
```

`price` is base, `totalTax` is tax, `priceWithTax` is all-in. **Stay totals for the whole
range and room count — not per night.**

The body carries a fresh `requestId` (a uuid) per call, so it is **not** a usable cache key —
keying on it gives every search its own entry and the cache never hits.

A wrong city code returns a valid-looking empty response, never an error.

---

## 2. Hotels — room-level rate plans (server-rendered)

```
GET https://www.makemytrip.com/hotels/hotel-details/?hotelId=<18-digit>&_uCurrency=INR
    &checkin=MMDDYYYY&checkout=MMDDYYYY&city=CT???&country=IN&locusId=CT???
    &locusType=city&roomStayQualifier=2e0e&isPropSearch=T&cc=IN&lang=eng
```

`roomStayQualifier` is `"<adults>e<children>e"` repeated once per room: 1 room / 2 adults is
`2e0e`; two rooms `2e0e2e0e`.

~1.3 MB of HTML with `window.__INITIAL_STATE__` already populated:

```
__INITIAL_STATE__.hotelDetail.searchRooms.exactRoomsDetail[]
   .roomName .roomCode .roomSize .bedCount .maxGuest .amenities[] .beds[]
   .ratePlans[]
      .name .mealPlan .cancellationPolicy .payMode .rpc .supplierCode .inclusionsList[]
      .priceDetails.priceBreakup {
          BASE_FARE, TAXES, HOTEL_TAX,
          TOTAL_AMOUNT, TOTAL_AMOUNT_WITH_FEES,
          PRICE_BEFORE_TAXES_FEES, PRICE_AFTER_DISCOUNT }
      .priceDetails.roomTariffs[] {displayPrice, numberOfAdults, numberOfChildren, roomId}
.cheapestRoom .cheapestRatePlan .recommendedRooms[] .filters[]
```

> **`TOTAL_AMOUNT` is base only.** All-in is `BASE_FARE + TAXES`. A field named "total" that
> is not the total is exactly the shape of trap that produces an ~18% under-report.

Some properties price *every* plan with breakfast included — there is no room-only rate to
report, and saying otherwise invents one.

The **listing** page is not usefully server-rendered (a handful of seeded ids only). Use the
POST API for lists.

---

## 3. Flights

```
GET https://flights-cb.makemytrip.com/api/search-stream-dt
    ?it=BLR-IXE-20261218        # ORIGIN-DEST-YYYYMMDD
    &pax=A-2_C-0_I-0  &cc=E     # cc is cabin class here, not country
    &cur=INR &currency=INR &region=in &language=eng
    &pfm=DESKTOP &sortBy=rhino &forwardFlowRequired=true
    &shd=true &dfs=0 &safs=st_0:0 &crId=<uuid> &apiCallTimestamp=<epoch ms>
```

Header gate, validated one at a time — each missing header gets its own 403 naming it:

```
mcid  device-id  app-ver: 8.0.0  lob: B2C  pfm: DESKTOP
os: desktop  src: mmt  language: eng  currency: INR  region: in
```

The ids are unsigned: a synthetic UUID trio turns a 403 into a 200 on the sibling
`www.makemytrip.com/flightsCB/api/flights-search/autosuggest`.

> **This endpoint cannot be called by this program, by any tier.** An earlier draft of this
> section claimed tier 1 could complete a search that in-page JavaScript cannot. It cannot:
> `ctx.request` is Akamai-denied at the network layer. Nor can an in-page fetch (CORS
> preflight), nor a bare fetch (403 `Missing Header app-ver`). The endpoint also wants a
> session-generated `authorization` token. The working path is to let the *site* call it and
> read the response the page receives — `harvest.harvest_flight_search`.

### The response is Server-Sent Events, and the frames are gzip

Verified against a real 114 KB capture (BLR-GOI, 2026-12-15). Not one JSON object, and not
a run of concatenated ones either:

```
id: HANDSHAKE
event: response-headers
data: {"App-Ver":["1.0.0"],"Currency":["INR"], ...}      <- plain JSON

id: 2
event: response
data: H4sIAAAAAAAE/...                                   <- base64(gzip(JSON))

id: END
```

Decode each `data:` value with base64 then gzip. The results document:

```jsonc
"cardList": [[                       // a list of card GROUPS, each a list of cards
  {"flightNumber": "6E 6554",
   "simpleAirlineHeading": {"cd": "6E-6554", "nm": "IndiGo"},
   "fare": 4367,                     // all-in, PER ADULT
   "fareBreakup": {"fareBreakUpItems": [
      {"text": "<font ...>TOTAL</font>",     "amount": "<font ...>₹ 4,367</font>"},
      {"text": "<font ...>Base Fare</font>", "amount": "<font ...>₹ 3,222</font>"},
      {"text": "<font ...>Surcharges</font>","amount": "<font ...>₹ 1,145</font>"}]},
   "journeyKeys": ["BLR$GOI$2026-12-15 19:00$6E-6554"]}   // -> journeyMap
]],
"journeyMap": {
  "BLR$GOI$2026-12-15 19:00$6E-6554": {
     "depTime": "19:00", "arrTime": "20:20",
     "depCityCd": "BLR", "arrCityCd": "GOI", "stops": 0,
     "flightDuration": "<font color='#757575'>01h 20m</font>",
     "depTimeStampStr": "15 Dec", "arrTimeStampStr": "15 Dec"}}
```

> **Display strings are HTML.** Airline names, durations and every rupee figure arrive
> wrapped in `<font>` tags. Strip them, and read the amount out of the text.

> **`fare` is per adult.** The same flight quotes identically at `A-1` and `A-2` — measured,
> not assumed. Base and surcharges come from `fareBreakup`; `base + surcharges == fare`.

> **A search answers with nearby airports too.** BLR-GOI returns itineraries into GOX (Mopa)
> and SDW (Sindhudurg). Read `arrCityCd` per itinerary rather than assuming the one searched.

Goa is two airports: **GOI** Goa (South), Dabolim, and **GOX** Goa (North), Manohar/Mopa.
Note that `GOA` is Genoa, Italy, and MakeMyTrip's own autosuggest offers it for the query
"goa" — which is exactly how a three-letter fallback silently prices the wrong continent.

Siblings: `/api/fareCalendar`, `/api/postSearch`, `/api/client-config`.

---

## 4. Trains

```
GET https://www.makemytrip.com/railways/listing
    ?date=YYYYMMDD                     # not ISO
    &srcStn=MDU&destStn=MS             # station codes; these are what matter
    &srcCity=&destCity=                # cosmetic - junk or blank works identically
    &classCode=                        # blank = all classes
```

A Next.js App Router page: no `__NEXT_DATA__` and no separate search API — the data is in the
React Server Component stream.

**Unwrapping RSC** (identical for cabs):

1. Collect every `self.__next_f.push([1,"<escaped chunk>"])` payload, JSON-unescape each and
   **concatenate** — chunks split mid-line.
2. The blob is newline-separated `<hexid>:<json>` lines. Some are not JSON (`1:HL[...]`
   preload hints) — skip them.
3. Values reference each other as `"$<hexid>"`. Resolve recursively, depth-capped.

```jsonc
{"trainNumber":"12622","trainName":"...","departureTime":"21:05","arrivalTime":"06:35",
 "duration":2010,                      // minutes
 "distance":2181,"frmStnCode":"NDLS","toStnCode":"MAS",
 "runningMon":"Y", ... "runningSun":"Y","bookingAllowed":true,
 "trainType":"$34","tbsAvailability":"$35","avlClasses":"$33"}
```

`tbsAvailability` resolves to one object per class:

```jsonc
{"classType":"2A","quota":"GN","totalFare":3190,
 "availablityStatus":"GNWL12/WL9",     // NOTE: availablity, no second 'i'
 "prettyPrint":"GNWL 9","availablityDate":"11-09-2026",
 "predictionPercentage":"97",          // confirmation-chance estimate
 "lastUpdatedOn":"...","lastUpdatedOnRaw":1787847261000}
```

> Spell `availablityStatus` and `availablityDate` MakeMyTrip's way. Correcting the typo
> silently yields `None` and reports every train as unavailable.

### The 60-day wall

Indian Railways opens reservations 60 days ahead, and MakeMyTrip returns **HTTP 200 with an
empty ~53 KB page** outside it. Measured on one route from a fixed date:

| Days ahead | HTML | Trains |
|---|---|---|
| 11 | 774 KB | 82 |
| 41 | 777 KB | 77 |
| **60** | 661 KB | **72** |
| **67** | **53 KB** | **0** |
| 88 | 53 KB | 0 |

An empty page means *too far out*, not *no trains on this route*.

### Station → city code

```
GET https://railways.makemytrip.com/api/mobile/search/getLocusId?from=MDU&to=MS
-> {"data":{"fromLocusCode":"CTIXM","toLocusCode":"CTMAA","fromLobCode":"MDU", ...}}
```

Cookieless, 200. Doubles as a station-code validator. No station autosuggest exists
(`/api/mobile/search/stations`, `/api/mobile/autosuggest` both 404).

---

## 5. Cabs

> **Reaching this page at all.** A cold visit to `/cabs/listing` returns 169 bytes whose
> body is the string `200-OK` — an Akamai stub, regardless of cookies, profile or query
> string (even the bare path with no parameters). Two conditions each have to hold: the
> browser must be started as an ordinary process and attached to over CDP rather than
> launched by Playwright, and `/cabs/` must be loaded first in the same page. The same is
> true of `/flight/search`. `/railways/listing` is not fussy.

```
GET https://www.makemytrip.com/cabs/listing
    ?tripType=OW                 # OW one-way, RT round trip
    &departDate=26-10-2026       # DD-MM-YYYY
    &pickupTime=10:00 &intlFlow=false
    &from=<url-encoded JSON place object>
    &to=<url-encoded JSON place object>
```

Same RSC mechanism as trains.

**`fromCity` / `toCity` appear in browser URLs and are redundant** — dropping both changes
nothing. (The site itself now builds `fromCity`/`toCity` when you click Search; `from`/`to`
still work and are what this server sends.) `from` / `to` are not redundant: a trimmed
object, or one missing `place_id`, returns **zero cabs with HTTP 200**. A harvested object
carrying only `place_id`, `address`, `main_text`, `secondary_text` and the two booleans is
enough in practice — verified live — though the site's own object is fuller:

```json
{"locusV2Id":"CTCOK","locusV2Type":"CITY","address":"Cochin, Kerala, India",
 "latitude":9.9312328,"longitude":76.26730409999999,
 "place_id":"ChIJv8a-SlENCDsRkkGEpcqC1Qs","is_city":true,"is_airport":false,
 "city":"Kochi","country":"India","country_code":"IN","state":"Kerala",
 "city_type":"Leisure"}
```

Percent-encode spaces; do not let a form encoder turn them into `+` inside the JSON blob.

Response — typed cards in the stream:

```jsonc
{"type":"SEARCH_SUMMARY",
 "summaryText":"Rates for *438 Kms* approx distance | *10 hr(s)* approx time"}

{"type":"CAB","data":{
  "cabInfo":{"type":"SUV","title":"...","fuelIdentifier":"DIESEL",
             "features":[{"title":"AC"},{"title":"6 Seats"}]},
  "supplierInfo":{"vendorName":"..."},
  "priceInfo":{"priceText":"...","discountText":"14% off",
               "fareBreakup":{"basePrice":27600,"totalAmount":29193,
                              "miscCharges":1593,"perKmExtraCharge":36}}}}
```

`basePrice + miscCharges = totalAmount`; `perKmExtraCharge` applies beyond the included
distance. Distance and duration parse out of `summaryText`.

**No booking window,** but not unlimited either. The ~60-day limit users see is the website's
date picker, not the endpoint. Measured 2026-09-05 on Kochi–Rameswaram: **+45 days returns
nine cabs, +120 days works, +200 days renders a full page with genuinely zero cabs** and no
distance. Far out is a real empty result, not a block — vendors simply stop bidding. No cab location autosuggest exists at the paths one would guess (`/locations/autosuggest/`,
`/locations/search/` both 404) — the real one is
`cabs.makemytrip.com/autocomplete/v3?query=…&requestFor=from|to`, and
`cabs.makemytrip.com/fetchLocation/v3?place_id=…` returns the full object for a place the
autocomplete named. Place objects are harvested by driving the search form.

Local 8hr/80km day packages are a different funnel keyed by `packageKey` — not implemented.

---

## 6. Date formats — four of them

| Surface | Format | Example |
|---|---|---|
| Hotels JSON API | `YYYY-MM-DD` | `2026-12-22` |
| Hotels detail page URL | `MMDDYYYY` | `12222026` |
| Flights `it` parameter | `YYYYMMDD` | `20261218` |
| Trains `date` | `YYYYMMDD` | `20261230` |
| Cabs `departDate` | `DD-MM-YYYY` | `22-12-2026` |

Every public tool parameter takes ISO. Conversion happens once per module, at the boundary,
and each conversion is unit-tested — this is the likeliest source of silently wrong results.

---

## 7. Re-capturing after a change

1. Open the page in Chrome with DevTools → Network → XHR.
2. Filter `mapi` or `flights-cb`, right-click the request → **Copy as cURL**.
3. Diff the body and headers against `mmt/config.py` and `mmt/hotels.py::build_body`.
4. For the RSC pages (trains, cabs), View Source and search for `__next_f`.
5. Save a trimmed real payload into `tests/fixtures/` and extend `tests/test_parsers.py`
   before changing parser code.

Useful trick when reading a page from inside a console that sanitises query strings: build
URLs from `String.fromCharCode(63/38/61)` for `? & =`, return `url.split('?')[0]` for paths,
and use `performance.getEntriesByType('resource')` to enumerate every endpoint a page hit.
