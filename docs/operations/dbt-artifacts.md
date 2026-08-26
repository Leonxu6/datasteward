# dbt artifact handling

DataSteward consumes dbt metadata as an integration boundary, so artifact parsing must be defensive.

## Manifest

Treat `manifest.json` as external structured data. Validate top-level collections before iterating, ignore malformed individual entries when safe, and avoid assuming optional fields are always present. Dataset and lineage registration should be deterministic for the same manifest.

## Run results

`run_results.json` may be missing, malformed, contain no tests, or contain failed/error tests. These cases have different operational meanings and should remain distinguishable in data-health output.

## Paths

Honor the configured dbt directory, resolve paths deliberately, and avoid silently reading artifacts from an unexpected working directory. Generated `target/` content is runtime state and should not be committed merely to make tests pass.

## Validation loop

When models or macros change, run `dbt parse` before the full stack. When health behavior changes, use small synthetic artifacts in tests rather than depending on a developer's local target directory.
