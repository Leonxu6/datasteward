# Security and trust boundaries

DataSteward crosses several trust boundaries: environment configuration, database drivers, SQL identifiers, model gateways, audit records, file-system paths, and user-facing APIs. Maintenance should make each boundary explicit rather than relying on downstream libraries to reject bad input.

## Credentials

Credentials belong in environment variables or an external secret manager. Validate the reference name before resolving a credential, never interpolate secrets into logs, and keep `.env` files out of Git. Error messages should identify the failing setting without echoing its value.

## SQL and identifiers

Values belong in driver parameters. Schema, table, and cursor identifiers require validated, dialect-appropriate quoting. Never accept arbitrary SQL fragments from an API field that is intended to represent an identifier.

## Files

File connectors should remain inside their configured root, reject ambiguous dataset names, and handle symlinks deliberately. Temporary office files and platform metadata should not become datasets merely because their extensions look readable.

## HTTP and model gateways

Base URLs must use the expected scheme, include a hostname, and reject credentials or ambiguous syntax. API keys must not contain control characters that can alter headers.

## Audit data

Audit records must be durable enough to diagnose actions but should avoid secret values and unbounded argument serialization. Treat audit serialization failures as operational problems, not a reason to silently drop records.

## Review rule

A new boundary should arrive with a validator, a focused regression test, and an error message that tells an operator what to fix without disclosing protected data.
