# Maintainer review checklist

Use this checklist for changes that affect production-facing behavior.

## Correctness

- The change solves a reproducible problem or advances a documented capability.
- Invalid configuration fails before external driver or network access.
- Database cursors, connections, files, and responses close on success and failure.
- Incremental and bounded-read semantics are covered by tests.

## Data contracts

- Schema and table identifiers use safe quoting.
- dbt artifacts are parsed defensively.
- Health checks return structured results instead of crashing dashboards.
- Precision-sensitive numeric and timestamp values are preserved.

## Security and privacy

- Credentials are not logged or committed.
- Audit output is useful but bounded and secret-safe.
- File paths cannot escape configured roots unexpectedly.
- URL and header values are validated before use.

## Verification

- Focused regression tests cover the contract.
- The full unit suite passes.
- `dbt parse` succeeds when transform metadata changed.
- Docker Compose configuration validates when deployment assets changed.
- Documentation and `.env.example` match runtime configuration.

## Repository hygiene

Do not commit generated target directories, production extracts, local databases, debug dumps, or placeholder changes made only to create activity.
