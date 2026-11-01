# Contributing

Thanks for helping make guardrail evaluation more reproducible.

1. Create an issue with acceptance criteria and a minimal reproduction.
2. Work in a focused branch and keep public fixtures synthetic.
3. Add behavior-focused tests and documentation with each change.
4. Run `pytest`, `ruff check .`, and `npm run build` in `apps/web`.
5. Explain compatibility or metric changes in the pull request.

Adapters must return an explicit canonical decision and must never convert timeouts, malformed responses, or exceptions into ALLOW. Changes to metric definitions require a versioned decision record and known-fixture tests.

