# Warehouse operations

Warehouse helpers sit underneath API, health, and transformation workflows, so resource handling must be predictable.

## Connections and cursors

Close cursors after reads, writes, and failed fetches. Context-manager support should guarantee connection cleanup. Keep rollback available for callers that need to recover from a failed multi-step operation.

## Fetching

Validate fetch batch sizes before touching the driver. Incremental `fetchmany` loops should close the cursor even if a later batch raises. Avoid loading unbounded result sets into memory when streaming is sufficient.

## Logging

Append-only JSONL logs should use safe paths and durable serialization. Complex values should either be normalized or rejected with useful errors; one malformed record must not corrupt the entire log.

## Read-only paths

Health checks and query previews should use read-only connections when possible. A helper named `connect_ro` should never gain hidden write behavior.

## Failure handling

Driver errors should retain enough context to diagnose the operation while avoiding credentials or full query payloads in logs. Cleanup failures should not mask the original database error unless cleanup itself is the primary failure.