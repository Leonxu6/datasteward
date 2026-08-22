# Deployment validation

Deployment changes should be verifiable before containers are started. DataSteward keeps Compose, image build, Dagster, smoke-test, and role-map assets under version control, so changes to one layer should not silently invalidate another.

## Before startup

Render the Docker Compose configuration and resolve interpolation errors first. Review volume paths, ports, health checks, and service dependencies. Keep credentials in environment configuration rather than embedding them in YAML.

## Image changes

When the Dockerfile changes, confirm the build still installs the declared Python dependencies and copies only required runtime files. Avoid using local caches or generated secrets as build inputs.

## Dagster

Workspace and instance configuration should reference paths and services that exist in the composed environment. Validate configuration syntax before assuming a scheduler/runtime failure is an application bug.

## Smoke tests

Smoke checks should prove that the stack is reachable and basic application paths work without mutating production-like data. A smoke script should return non-zero on failure and print the failing stage.

## Rollout discipline

Prefer reversible configuration changes, explicit migrations, and documented environment-variable additions. A deployment fix is complete only when CI/Compose validation passes and the runbook reflects any new operator action.