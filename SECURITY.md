# Security policy

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability. Send a private report to the repository security contact with reproduction steps, affected versions, impact, and any suggested mitigation. Maintainers should acknowledge a complete report within five business days.

## Deployment guidance

- Set `GUARDBENCH_API_KEY` before exposing the API beyond a trusted local environment.
- Use TLS at the reverse proxy and rotate database and target credentials.
- Never place credentials in target configuration JSON, datasets, logs, or exported reports.
- Keep the HTTP adapter host allowlist narrow. Private network access is disabled by default.
- Treat test prompts and target responses as potentially sensitive data.
- Keep public CI artifacts synthetic and run secret/dependency scanning.
- Apply an explicit retention policy to the database and exported reports.

GuardBench does not send telemetry or evaluation data to third parties by default.

