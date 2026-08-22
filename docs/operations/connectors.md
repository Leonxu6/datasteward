# Connector maintenance

Connectors are trust boundaries between configuration, external systems, and the internal dataset contract.

## Configuration

Validate host, port, timeout, schema, table identifiers, credential references, and incremental-read arguments before loading drivers or opening connections. Defaults are part of the contract and should be validated too.

## Resource lifecycle

Cursors and connections must close on success and on exceptions. Incremental readers should not leak cursors when iteration stops early. Transaction-capable paths should expose explicit commit/rollback behavior rather than relying on driver-specific surprises.

## Incremental reads

Treat `since` and cursor-column configuration as a pair. Reject incomplete combinations. Apply filtering before limits so previews do not silently skip eligible rows. Preserve numeric and timestamp precision across extraction and loading.

## Introspection

Introspection should agree with the later read path about schema qualification, dataset naming, and ambiguous files. A dataset advertised during onboarding should be readable with the same logical name.

## Tests

Use fake drivers to assert that malformed configuration fails before driver access. Add regression tests for identifier quoting, cleanup, schema qualification, cursor boundaries, and ambiguous file names.