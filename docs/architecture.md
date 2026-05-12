# Architecture

## Major Services

| Service | Role |
|---|---|
| TomTom Geocoding API | Converts address strings to lat/lon coordinates |
| TomTom Routing API | Returns ordered route points between two coordinates |
| TollGuru Toll API | Accepts encoded polyline, returns toll costs per plaza and payment type |

All three are external HTTP APIs. There is no internal server.

## Data Flow

```
address strings
    → TomTom Geocoding API → lat/lon pairs
    → TomTom Routing API   → list of {lat, lon} route points
    → polyline encoder     → Google-encoded polyline string
    → TollGuru API         → toll costs {tag, cash, credit_card, ...}
```

## Datastore

None. Scripts are stateless. Test results written to local CSV files (`testCases_result.csv`, `testCases_output.csv`).

## Third-Party Dependencies

See each language's dependency file:

- Python: `python/requirements.txt`
- JavaScript: `javascript/package.json`
- Ruby: `ruby/Gemfile`
- PHP: no package manager; only built-in cURL extension required

## Auth Model

API key auth only. Keys passed as:
- TomTom: query parameter `?key=` in URL
- TollGuru: HTTP header `x-api-key`

Keys read from environment variables `TOMTOM_API_KEY` and `TOLLGURU_API_KEY`. No OAuth, no sessions, no user accounts.

## Tenancy Model

Not applicable. Single-tenant scripts. No user data stored or isolated.
