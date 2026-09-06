# Troubleshooting runbook

Start with the smallest layer that can explain the symptom. Avoid restarting the whole stack until configuration, connectors, warehouse access, and generated artifacts have been checked independently.

## Connector onboarding fails

Run the connector readiness path and note the reported stage. Invalid host, port, schema, table, credential reference, or incremental cursor settings should fail before a driver is loaded. If introspection succeeds but reads fail, compare the schema-qualified name produced by both paths.

## Warehouse reads fail

Check connection configuration and reproduce with a read-only query. Cursor cleanup errors should not mask the original driver exception. When a transaction has partially executed, use the explicit rollback path before retrying.

## Audit persistence is degraded

Read-only business results are kept separate from audit-storage availability. A completed SQL or metric query may therefore still return valid data when the audit sink fails; structured query responses include an `audit_warning` when that happens. Catalog reads also remain available so operators can diagnose the system instead of receiving a false data-service failure.

Treat the warning as an observability incident, not as proof that the underlying query failed. Check the audit-store path or database independently, restore persistence, and verify a fresh operation creates an audit record. Do not retry a successful read merely to manufacture an audit entry, and do not suppress the warning at the agent boundary.

## Health page shows failures

Read the structured `actual` value and message. A data-quality failure is different from malformed monitoring configuration. For parity, compare source and sink counts; for freshness, inspect source timezone/clock; for schema, review missing and extra columns separately.

## dbt health is unknown

Confirm the configured dbt directory and whether `target/run_results.json` exists. A missing artifact, a run containing no tests, and failing tests are distinct states. Run `dbt parse` or `dbt build` as appropriate rather than creating target artifacts by hand.

## Compose configuration fails

Render the Compose configuration first and resolve missing variables, invalid mounts, or service references before starting containers. Keep local credentials out of committed deployment files.

## Reporting a bug

Include the component, sanitized configuration shape, exact command, focused traceback, and smallest reproduction. Remove passwords, tokens, production hostnames, customer data, and private extracts.
