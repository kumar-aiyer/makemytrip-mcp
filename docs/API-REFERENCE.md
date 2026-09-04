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

In a browser **page** the `app-ver` header trips CORS preflight on the cross-origin host.
Playwright's `context.request` is not a page origin, so it is not subject to CORS — this is
why tier 1 can complete a search that in-page JavaScript cannot.

The response is a **stream of concatenated JSON documents**, not one object. The itinerary
field names in `mmt/flights.py` are **inferred and unproven**; capture a real payload and
rewrite `parse_stream` from it. Siblings: `/api/fareCalendar`, `/api/postSearch`,
`/api/client-config`.

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
nothing. `from` / `to` are not: a trimmed object, or one missing `place_id`, returns **zero
cabs with HTTP 200**. Required shape:

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

**No booking window.** The ~60-day limit users see is the website's date picker, not the
endpoint — dates months out quote fine, typically at a seasonal premium with fewer vendors
bidding. No cab location autosuggest exists (`/locations/autosuggest/`, `/locations/search/`
404), so place objects must be harvested from the search form.

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
