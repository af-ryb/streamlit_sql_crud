# CLAUDE.md

Guidance for Claude Code in this repository: a Streamlit CRUD library
(`streamlit_pydantic_crud`, repo `streamlit_sql_crud`). Project documentation
lives in `docs/` — read the relevant file before changing code:

- `docs/architecture.md` — public API, package layout, layering rule, data flow
- `docs/development.md` — commands, tests, CI, browser verification, releasing

## Conventions

Project-specific rules (the rest is enforced by ruff/ty — see config):
- **Type hints on all code**; public APIs need docstrings.
- **Line length: 88 chars** (ruff).
- **Comments**: triple-quoted, English, two lines maximum.
- **Imports at the top of the file** — never inside a function.
- **Function ordering**: define composing functions before the helpers they call.
- **Naming**: handler functions are prefixed with `handle`; `snake_case` functions,
  `PascalCase` classes, `UPPER_SNAKE_CASE` constants; f-strings for formatting.
- **Tests** live in `tests/` and use pytest; new features require tests.
- **Layering**: respect the import layers in `docs/architecture.md` (enforced by
  `tests/test_import_layers.py`); a new module or sub-package goes into `LAYERS`.
- **Docs**: keep `docs/architecture.md` in sync when modules move or the data
  flow changes, and `README.md` when the public API changes.

## Essential commands

```bash
task fix      # ruff --fix, ruff format, ty
task check    # what CI runs: ruff, ruff format --check, ty, pytest
uv run -- pytest -k <name>   # one test
```

## Verification

All new functionality must be verified in a browser with the example project
`~/repo/streamlit_sql_crud_example` (see `docs/development.md`), not only with
AppTest.
