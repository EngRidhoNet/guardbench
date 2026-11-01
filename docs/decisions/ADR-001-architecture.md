# ADR-001: Python-first modular monorepo

**Status:** Accepted

The deterministic evaluation core lives in one importable Python package and has no dependency on FastAPI or React. The CLI and API invoke the same runner and metric functions. The dashboard is a separate TypeScript application. This prevents scoring drift across interfaces while preserving a simple installation path.

