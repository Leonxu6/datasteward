# Connector maintenance

Connectors are trust boundaries between configuration, external systems, and the internal dataset contract.

## Configuration

Validate host, port, timeout, schema, table identifiers, credential references, and incremental-read arguments before loading drivers or opening connections. Defaults are part of the contract and should be validated too.

## Resource lifecycle

Cursors and connections must close on success and on exceptions. Incremental readers should not leak cursors when iteration stops early. Transaction-capable paths should expose explicit commit/rollback behavior rather than relying on driver-specific surprises.

Local CSV and Excel sources are reopened through a non-blocking, no-follow file descriptor immediately before parsing and accepted only when descriptor metadata identifies a regular file. This closes the gap between directory discovery and parsing: a source swapped for a symlink, FIFO, device, or other special file is rejected instead of being followed or blocking a worker.

The CDC mutation demo accepts only a finite positive `--interval`. Its cursor
and source connection are closed when the worker is interrupted or exits with
an error, so repeated demonstrations do not accumulate abandoned sessions.

## Incremental reads

Treat `since` and cursor-column configuration as a pair. Reject incomplete combinations. Apply filtering before limits so previews do not silently skip eligible rows. Preserve numeric and timestamp precision across extraction and loading.

PostgreSQL and SQL Server incremental reads return rows in ascending cursor order. This makes bounded batches deterministic and lets callers advance a watermark from the last row rather than depending on a database's unspecified scan order. A cursor used with a limit must be unique as well as monotonic; otherwise rows tied at the batch boundary require a compound cursor that the current connector API does not yet provide.

## Introspection

Introspection should agree with the later read path about schema qualification, dataset naming, and ambiguous files. A dataset advertised during onboarding should be readable with the same logical name.

## Tests

Use fake drivers to assert that malformed configuration fails before driver access. Add regression tests for identifier quoting, cleanup, schema qualification, cursor boundaries, and ambiguous file names.
