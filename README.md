# toll-tomtom

Multi-language examples for calculating toll costs on a TomTom route using the [TollGuru API](https://tollguru.com/). Implementations in Python, JavaScript, Ruby, and PHP.

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

- TomTom API key
- TollGuru API key 
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
