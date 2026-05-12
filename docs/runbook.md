# Runbook

## Common Failures and Recovery

### `401 Unauthorized` from TomTom or TollGuru
- Check `TOMTOM_API_KEY` / `TOLLGURU_API_KEY` env vars are set and not expired
- Regenerate keys at [developer.tomtom.com](https://developer.tomtom.com) or [tollguru.com](https://tollguru.com)

### TomTom returns empty `routes` array
- Source or destination coordinates are likely outside routable area or in a body of water
- Verify geocode step returned valid lat/lon before calling the routing endpoint
- Check TomTom API status at [developer.tomtom.com/status](https://developer.tomtom.com/status)

### TollGuru returns `{"message": "..."}`
- Polyline is malformed or empty — check the encoding step
- Vehicle type string is invalid — see [TollGuru vehicle types](https://github.com/mapup/tollguru-tolltally-vehicle-coverage-api/wiki/Vehicle-types-supported-by-TollGuru)
- Route has no tolls in TollGuru's database — response `route.costs` will be `{}`; this is expected, not an error

### Python `KeyError` / `IndexError` on geocode step
- TomTom geocoder returned zero results for the address string
- Use a more specific address or pass lat/lon directly instead of geocoding

### PHP SSL errors
- PHP implementation disables SSL verification — if this causes issues in hardened environments, remove `CURLOPT_SSL_VERIFYHOST`/`CURLOPT_SSL_VERIFYPEER` overrides from `php_curl_tomtom.php`

### Ruby `LoadError` / bundler issues
- Run `bundle install` inside the `ruby/` directory
- Gemfile locks Ruby 2.6.10; use `rbenv` or `rvm` to switch versions if needed

## Rollback

No deployed service exists. To roll back:
- Revert to previous git commit: `git checkout <sha> -- <file>`
- Re-run the script with previous code

## Logs / Monitoring

No centralized logging. Scripts print to stdout/stderr. To capture:
```bash
python TomTom.py 2>&1 | tee run.log
```

For production use, pipe output to your existing log aggregator (CloudWatch, Datadog, etc.).

API-level monitoring:
- TomTom status: [developer.tomtom.com/status](https://developer.tomtom.com/status)
- TollGuru status: contact TollGuru support or monitor response codes

## Cron / Scheduled Jobs

No scheduled jobs in this repo. If you add one (e.g., nightly batch via the test CSV harness), record it here with its schedule and the command.

## Data Backfill Scripts

The test CSV harnesses (`python/Testing/Test_TomTom.py`, `ruby/TestCases/test_ruby.rb`) can be repurposed for batch processing:
- Populate `testCases.csv` with source/destination pairs
- Run the test script; results append to the output CSV
- No database to backfill; output is a flat CSV file
