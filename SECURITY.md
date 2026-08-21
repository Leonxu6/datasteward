# Security Policy

DataSteward connects to databases, file systems, model gateways, identity providers, and operational infrastructure. Treat connector credentials, authorization policy, generated SQL, and action execution as security-sensitive boundaries.

## Supported version

Security fixes are applied to the `main` branch while the project is pre-1.0.

## Reporting a vulnerability

Please report vulnerabilities privately to the repository owner instead of opening a public issue containing credentials, production data, tokens, or exploit details. Include the affected component, impact, reproduction conditions, and a minimal sanitized proof of concept when possible.

## Security expectations

- Never commit real credentials or customer data.
- Validate values before they cross into SQL, shell, HTTP headers, filesystem paths, or identity-provider requests.
- Keep database connectors read-only unless a write path is explicitly designed and audited.
- Preserve least-privilege defaults in Docker, CI, and service configuration.
- Tests must use synthetic fixtures and mocks for external systems.
