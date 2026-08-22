# Data health runbook

Data-health checks should distinguish bad data from broken monitoring code.

## Result contract

Each check returns a structured result with an id, type, table, description, severity, status, actual value, and human-readable message. Expected quality failures become `warn` or `fail`; malformed check definitions and unexpected execution errors should still be reportable instead of crashing the page.

## Volume and parity

Row counts must be non-negative integers. Missing source or sink counts are failures, not zeros. Parity mismatches should report both counts and the absolute difference so CDC lag is visible.

## Freshness

Accept valid naive and timezone-aware timestamps. Invalid or empty timestamps should fail the check. Future timestamps indicate source-clock or timezone problems and should be surfaced as warnings rather than interpreted as extremely fresh data.

## Schema

Compare normalized column names and report missing and extra columns separately. Avoid hiding drift by converting unexpected metadata into an empty set.

## dbt tests

A missing `run_results.json` is different from a failed dbt test. Report missing artifacts as an actionable warning, explicit test failures as failures, and a run with no tests as a distinct warning.

## On-call workflow

Start with the structured result, reproduce the underlying query against a non-production fixture when possible, and verify whether the failure is source data, CDC, warehouse metadata, or the monitoring definition itself.