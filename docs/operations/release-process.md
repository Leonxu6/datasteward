# Release readiness

A DataSteward release should represent a coherent operational milestone, not activity for its own sake.

## Readiness checks

Run the full unit suite, dbt parse, Compose configuration validation, and repository audit jobs. Confirm connector onboarding still reports failures by stage, warehouse cleanup tests pass, and data-health results remain structured for expected failures.

## Configuration changes

Any new required environment variable needs an example entry and migration note. Renamed or removed settings should have a clear replacement. Defaults must remain validated rather than being assumed safe.

## Data contracts

Review schema, dbt model, connector, and API contract changes for compatibility. If an upgrade can change persisted state or warehouse layout, document the migration and rollback path.

## Release notes

Summarize user-visible capabilities, fixed operational failure modes, configuration migrations, data-contract changes, and known limitations. Internal refactors need mention only when they change behavior or operational risk.

## After release

Verify the default branch remains healthy, documentation links still resolve, and a clean installation can reach the documented readiness checks. Avoid empty tags or version bumps whose only purpose is to manufacture activity.
