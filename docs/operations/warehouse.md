# Warehouse operations

Warehouse helpers sit underneath API, health, and transformation workflows, so resource handling must be predictable.

## Connections and cursors

Close cursors after reads, writes, and failed fetches. Context-manager support should guarantee connection cleanup. Keep rollback available for callers that need to recover from a failed multi-step operation.

## Fetching

Validate fetch batch sizes before touching the driver. Incremental `fetchmany` loops should close the cursor even if a later batch raises. Avoid loading unbounded result sets into memory when streaming is sufficient.

## Logging

Append-only JSONL logs should use safe paths and durable serialization. Complex values should either be normalized or rejected with useful errors; one malformed record must not corrupt the entire log. Append targets are opened non-blocking and validated from the open file descriptor, so FIFOs and other special files cannot stall or capture an audit writer. Supported platforms also refuse symbolic-link targets. Existing log permissions are narrowed to at most `0640` without making a more restrictive file broader.

All JSON emitted across agent traces, tool responses, worker arguments, and health-alert cursors uses the strict JSON number contract. Python's non-standard `NaN` and `Infinity` tokens are rejected at the boundary instead of being handed to downstream parsers that may accept, reinterpret, or reject them inconsistently.

Persisted Agent traces and governed Action records use second-precision ISO 8601 timestamps with an explicit UTC offset. Consumers may convert those timestamps for display, but storage and correlation must never depend on a host's implicit local timezone.

## Read-only paths

Health checks and query previews should use read-only connections when possible. A helper named `connect_ro` should never gain hidden write behavior.

## Failure handling

Driver errors should retain enough context to diagnose the operation while avoiding credentials or full query payloads in logs. Cleanup failures should not mask the original database error unless cleanup itself is the primary failure.
