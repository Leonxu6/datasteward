# Repository maintenance gates

DataSteward keeps repository-integrity checks side-effect free so maintainers can run them before a full application environment exists.

## Local command

Run the complete audit suite from the repository root:

```bash
python -m scripts.run_maintenance_audits
```

The runner checks the existing CI, documentation, packaging, source-layout, sensitive-data and text-integrity contracts, plus syntax and security boundaries for JSON/TOML, Markdown fences, merge markers, bidirectional Unicode controls, dynamic code execution, subprocess shells, unsafe deserialization, weak hashes, disabled TLS verification, insecure temporary files, direct dependency sources, unsafe YAML loading, Unicode-normalized path collisions and escaping symlinks.

## Failure policy

An audit failure should be treated as a concrete repository defect. Fix the source problem or, when the rule is genuinely wrong for the project, change the audit together with a regression test that explains the intended exception. Do not silence a gate merely to make CI green.

## Adding a gate

A new audit should be deterministic, offline where practical, bounded in runtime, and accompanied by focused tests for both an accepted case and the failure it prevents. Register it in `scripts/run_maintenance_audits.py` so local checks and CI share the same contract.
