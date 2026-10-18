# Development

The project uses **uv** and requires **Python >= 3.12**. Configuration lives in
`pyproject.toml` (dependencies, ruff, ty, pytest, vulture); exact versions in
`uv.lock`; task shortcuts in `Taskfile.yml`.

## Code quality

```bash
task fix      # ruff check --fix, ruff format, ty check
task check    # non-mutating: ruff check, ruff format --check, ty check, pytest
```

Directly with uv: `uv run -- ruff check --fix && uv run -- ruff format && uv run -- ty check`.

- **ruff**: line length 88, extensive rule set (UP, E, F, B, C4, ...).
- **ty**: checks `streamlit_pydantic_crud/` and `tests/` (`[tool.ty.src]`).
- **vulture**: dead-code scan of `streamlit_pydantic_crud/` (`uv run -- vulture`).
- Pre-commit hook (ruff + ty on staged files): `git config core.hooksPath .githooks`.

CI (`.github/workflows/ci.yml`) runs ruff, ty and pytest on push / PR, plus
pytest on SQLAlchemy 2.1 (`uv run --with 'sqlalchemy>=2.1,<2.2' -- pytest`).

## Tests

```bash
uv run -- pytest                          # full suite (task test)
uv run -- pytest tests/test_pk_helpers.py # one file
uv run -- pytest -k pagination            # by name
```

- Tests run against in-memory / temp SQLite — no PostgreSQL or Docker.
- Most tests drive the real Streamlit runtime through
  `streamlit.testing.v1.AppTest`: `tests/conftest.py` provides `engine` /
  `session` fixtures (seeded Department / Employee models) and a `run_app`
  fixture that renders apps from `tests/_apps/` and clears `st.cache_data`
  between runs.
- Models used by AppTest harness apps live in importable modules (e.g.
  `tests/_apps/*_models.py`), not in the script: a rerun would redefine them.
- The library's own "removed in 0.10.0" deprecations are errors in tests unless
  the test expects them (`filterwarnings` in `pyproject.toml`).

## Verifying in a browser

The repo has no app of its own. New functionality is verified with the companion
example project `~/repo/streamlit_sql_crud_example` (`./run.sh`; setup guide in
its `GETTING_STARTED.md`, checklist in `VERIFICATION.md`):

- Departments — text areas, enums, decimals, booleans; one-to-many panel
- Employees — FK selectboxes, date and email validation
- Test Data Types — arrays, JSON, all field types
- Many-to-Many, Projects with JOIN, No-Schema Numbers, Support Tickets

To run it against a library branch, start streamlit from the example directory
with `PYTHONPATH=<library checkout or worktree>`. AppTest misses frontend-only
behavior (widget reset, number input clearing), so browser checks matter.

## Releasing

Consumers install from git and pin by tag (no PyPI). Bump `version` in
`pyproject.toml`, run `uv lock`, commit and push to `master`, then:

```bash
scripts/release.sh 0.9.0 --dry-run   # run every gate, no tag
scripts/release.sh 0.9.0 --push      # tag v0.9.0 and push it (OR task release -- 0.9.0 --push)
```

The script checks the tag is free, `master` is in sync, `pyproject.toml` /
`uv.lock` agree with the version, runs ruff / ty / pytest and installs the wheel
built from a clean export. Published tags never move; ship the next patch
instead.

## Key dependencies

- **streamlit** (>= 1.58) — native `st.pagination`,
  `st.selectbox(accept_new_options=True)`, `st.column_config`; no third-party
  components
- **sqlalchemy** (2.0 and 2.1 supported)
- **pydantic** (>= 2.0)
- **pandas** — only for the deprecated Styler path until 0.10.0
- **loguru** — logging
- **sqlmodel** (dev only) — SQLModel compatibility tests
