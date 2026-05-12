# toll-tomtom

Multi-language examples showing how to enrich a [TomTom](https://docs.tomtom.com/) route with real-time toll costs using the [TollGuru API](https://tollguru.com/). Given a source and destination, the code fetches the route from TomTom, encodes it as a polyline, and queries TollGuru for toll costs across all payment types (tag, cash, credit card). Implementations in Python, JavaScript, Ruby, and PHP.

## TollGuru Capabilities

- [Supported geographies](https://github.com/mapup/tollguru_country_coverage/wiki/Countries-supported-by-TollGuru) — North America, Europe, Asia, Australia, Latin America
- [Supported vehicle types](https://github.com/mapup/tollguru_vehicle_coverage/wiki/Vehicle-types-supported-by-TollGuru) — car, truck, motorcycle, bus, RV, and more
- Payment options — tag transponder, cash, licence plate, credit card, prepaid (in local currencies)
- Time-based tolls — pass `departure_time` for accurate rates on express lanes and time-of-day pricing
- All toll system types — barrier, ticket system, and distance-based tolling
- [Supported map services](https://github.com/mapup/toll-tomtom/wiki/2.-Map-platform-service-supported-by-TollGuru) — edit the `source` param to use a different mapping platform
- [Truck parameters](https://github.com/mapup/toll-tomtom/wiki/4.-Truck-parameters-supported-by-TollGuru) — height, weight, hazardous goods, tunnel category, etc.
- [API parameter examples](https://github.com/mapup/tollguru-api-parameter-examples/tree/main/request-bodies/02-Complete-Polyline-To-Toll) — full request body variations

## Architecture

- Client geocodes source/destination via TomTom Geocoding API (address → lat/lon)
- Client calls TomTom Routing API to get ordered route points
- Route points encoded into a Google-format polyline
- Polyline POSTed to TollGuru `/complete-polyline-from-mapping-service` endpoint
- TollGuru returns toll costs per payment type (tag, cash, credit card) per toll plaza
- All calls are synchronous HTTP — no server, no datastore, no queue
- Auth via API keys in environment variables (`TOMTOM_API_KEY`, `TOLLGURU_API_KEY`)
- Test harness reads source/destination pairs from CSV, writes results to CSV
- See [docs/architecture.md](docs/architecture.md) for details

## Prerequisites

- **TomTom API key** — [sign up at developer.tomtom.com](https://developer.tomtom.com/user/login), find your key at [developer.tomtom.com/user/me/apps](https://developer.tomtom.com/user/me/apps)
- **TollGuru API key** — [get a free key at platforms.mapup.ai/](https://platforms.mapup.ai/)
- Language runtime for your chosen implementation:
  - Python 3.8+
  - Node.js 14+
  - Ruby 2.6+
  - PHP 7+ with cURL enabled

## Local Setup

Set environment variables first:

```bash
export TOMTOM_API_KEY=your_tomtom_key
export TOLLGURU_API_KEY=your_tollguru_key
```

**Python**
```bash
cd python
pip install -r requirements.txt
python TomTom.py
```

**JavaScript**
```bash
cd javascript
npm install
node index.js
```

**Ruby**
```bash
cd ruby
bundle install
ruby main.rb
```

**PHP**
```bash
cd php
php php_curl_tomtom.php
```

## Running Tests

**Python** — reads `python/Testing/testCases.csv`, writes `testCases_result.csv`
```bash
cd python/Testing
python Test_TomTom.py
```

**Ruby** — reads `ruby/TestCases/testCases.csv`, writes `testCases_output.csv`
```bash
cd ruby/TestCases
ruby test_ruby.rb
```

JavaScript and PHP have no automated test suite.

## Deployment

No server component. Scripts run as one-shot CLI tools. To deploy in CI or a scheduled job:

1. Set `TOMTOM_API_KEY` and `TOLLGURU_API_KEY` as secrets in your environment
2. Install dependencies for the target language
3. Run the entry-point script for that language

## Config

All configuration is via environment variables. No config files.

| Variable | Required | Description |
|---|---|---|
| `TOMTOM_API_KEY` | Yes | TomTom Routing/Geocoding API key |
| `TOLLGURU_API_KEY` | Yes | TollGuru toll calculation API key |

Source/destination and vehicle type are set as constants in each implementation's entry-point file.

## Known Limitations

- No caching — every run makes live API calls
- No retry logic on transient failures
- PHP disables SSL peer/host verification (`CURLOPT_SSL_VERIFYPEER`, `CURLOPT_SSL_VERIFYHOST` set to `false`)
- Ruby Gemfile locks to Ruby 2.6.10
- Single route per invocation; no batch mode in main scripts (test harness does batch via CSV)
- TollGuru returns costs for the first route leg only if multiple legs exist
- Supported geographies and vehicle types depend on TollGuru coverage — see [country coverage](https://github.com/mapup/tollguru_country_coverage/wiki/Countries-supported-by-TollGuru) and [vehicle types](https://github.com/mapup/tollguru_vehicle_coverage/wiki/Vehicle-types-supported-by-TollGuru)

## Docs

- [docs/architecture.md](docs/architecture.md) — services, data flow, third-party dependencies, auth
- [docs/runbook.md](docs/runbook.md) — failure recovery, rollback, monitoring

## License

ISC License. Copyright 2020 TollGuru. See individual language READMEs for full text.
