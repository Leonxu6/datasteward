# Security and trust boundaries

DataSteward crosses several trust boundaries: environment configuration, database drivers, SQL identifiers, model gateways, audit records, file-system paths, and user-facing APIs. Maintenance should make each boundary explicit rather than relying on downstream libraries to reject bad input.

## Credentials

Credentials belong in environment variables or an external secret manager. Validate the reference name before resolving a credential, never interpolate secrets into logs, and keep `.env` files out of Git. Error messages should identify the failing setting without echoing its value.

## SQL and identifiers

Values belong in driver parameters. Schema, table, and cursor identifiers require validated, dialect-appropriate quoting. Never accept arbitrary SQL fragments from an API field that is intended to represent an identifier.

## Files

File connectors should remain inside their configured root, reject ambiguous dataset names, and handle symlinks deliberately. Temporary office files and platform metadata should not become datasets merely because their extensions look readable.

The legacy Claude/MCP fallback writes its per-session MCP configuration with exclusive creation and owner-only permissions. It refuses an existing or symbolic-link target, completes and syncs the JSON before launching the subprocess, and removes the file after the session. These temporary files contain operator identity and purpose metadata even though they do not contain database credentials.

That fallback consumes child stderr concurrently with stdout. It drains the pipe to completion so verbose CLI failures cannot deadlock the agent, but retains only a bounded prefix for diagnostics. Never replace this with sequential full-stream reads or persist the complete child output: stderr can be both unbounded and sensitive.

## HTTP and model gateways

Base URLs must use the expected scheme, include a hostname, and reject credentials or ambiguous syntax. API keys must not contain control characters that can alter headers.

## Administrative previews

Administrative pages are still user-facing trust boundaries. Metric trials compile through the shared metric registry, fetch at most 200 rows, and close both the result cursor and read-only warehouse connection on success or failure. Display a stable error category in the page rather than raw driver text, which can contain credentials, hosts, SQL fragments, or other deployment details.

Agent metric queries enforce their compiled limit twice: the registry emits a SQL `LIMIT` of at most 500 rows, and the execution layer requests one sentinel row beyond that budget. An oversized or non-materialized driver batch is rejected before serialization, while cursors and read-only connections are still closed. This prevents a changed compiler or non-conforming database driver from silently turning a bounded tool response into an unbounded allocation.

## Audit data

Audit records must be durable enough to diagnose actions but should avoid secret values and unbounded argument serialization. Treat audit serialization failures as operational problems, not a reason to silently drop records.

JSONL readers accept at most 64 MiB and 100,000 valid records per file. The byte budget is enforced both before and during the read so a concurrently growing log cannot bypass it. Reaching either limit fails visibly instead of materializing an unbounded Python object graph; archive or rotate the log before retrying.

## Review rule

A new boundary should arrive with a validator, a focused regression test, and an error message that tells an operator what to fix without disclosing protected data.
