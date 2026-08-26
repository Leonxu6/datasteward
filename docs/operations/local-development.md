# Local development

DataSteward spans connectors, metadata, dbt transforms, warehouse access, API surfaces, and operational tooling. Local work is fastest when each layer can be validated independently before the full stack is started.

## Suggested loop

1. Create the Python environment from the repository metadata.
2. Copy `.env.example` only for local use and keep real credentials untracked.
3. Run the focused unit tests for the component being changed.
4. Run the complete non-integration test suite.
5. Parse the dbt project when transforms or model metadata changed.
6. Validate Docker Compose configuration when deployment files changed.
7. Run the repository audit checks before pushing.

## Boundaries

Connector tests should fail before opening a real connection when configuration is invalid. Warehouse tests should use fakes for cursor cleanup and transaction behavior. Health checks should convert expected data-quality failures into structured results instead of crashing the monitoring page.

## Commit hygiene

Keep functional changes separate from formatting churn. Pair behavior changes with regression tests where practical. Update configuration or operations docs when a setting, schema contract, or deployment assumption changes. Never commit production credentials, generated dbt targets, local database files, or private extracts.
