# Configuration validation

Configuration is a public API. A typo should fail early with a stable message rather than reaching a driver, HTTP client, or deployment process.

## Text

Reject non-string values, empty required text, surrounding whitespace, and control characters. Optional secrets may be empty but should still reject header-breaking controls and accidental padding.

## Numbers

Ports, batch sizes, row limits, and timeouts should reject booleans even though Python treats them as integers. Numeric strings should use ASCII digits where appropriate. Validate defaults and min/max bounds before comparing them.

## URLs

Service URLs should use an expected scheme, include a hostname, and reject ambiguous backslashes, embedded credentials, whitespace, query strings, or fragments when the value represents a base URL.

## Identifiers

Database schema, table, and cursor identifiers require driver-appropriate quoting and validation. Never interpolate unvalidated free-form identifiers into SQL.

## Environment references

Credential environment-variable names should follow a predictable identifier format. Resolve secrets only after the reference itself has been validated.

## Testing

For each validator, cover good defaults, environment overrides, type errors, boundary values, and the guarantee that invalid configuration fails before external driver access.
