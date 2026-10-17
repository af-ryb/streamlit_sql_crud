# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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

## Common Development Commands

### Code Quality and Formatting
```bash
# Lint (auto-fix), format and type-check (most common)
task fix
# OR directly with uv
uv run -- ruff check --fix && uv run -- ruff format && uv run -- ty check
# Non-mutating check (what CI runs): ruff, ruff format --check, ty, pytest
task check
```
CI (`.github/workflows/ci.yml`) runs the same checks on push/PR. Enable the
pre-commit hook (ruff + ty on staged files) with
`git config core.hooksPath .githooks`.

### Running Tests
```bash
# Run the full suite (pytest testpaths = ["tests"], quiet mode via addopts)
uv run -- pytest   # OR task test
# Run a single test file
uv run -- pytest tests/test_pk_helpers.py
# Run a single test by name
uv run -- pytest -k pagination
```
Tests run against in-memory/temp SQLite (no PostgreSQL or Docker needed).
Most tests drive the real Streamlit runtime through `streamlit.testing.v1.AppTest`:
`tests/conftest.py` provides `engine`/`session` fixtures (seeded Department/Employee
models) and a `run_app` fixture that renders apps from `tests/_apps/` and clears
`st.cache_data` between runs to prevent memoized queries leaking across tests.

### Releasing
Consumers install from git and pin by tag. Bump `version` in `pyproject.toml`, run
`uv lock`, commit and push to `master`, then:
```bash
scripts/release.sh 0.6.0 --dry-run   # run every gate, no tag
scripts/release.sh 0.6.0 --push      # tag v0.6.0 and push it (OR task release -- 0.6.0 --push)
```
Published tags never move; ship the next patch instead.

### Development Server
This repo has no app of its own. To run a live UI, use the example project
below (`./run.sh`).

## Architecture Overview

This is a **Streamlit-based CRUD library** that creates database interfaces with Pydantic validation. The core architecture consists of:

### Main Components

1. **SqlUi** (`sql_ui.py`) - Main CRUD interface class
   - Combines SQLAlchemy queries with Streamlit UI
   - Supports CREATE, READ, UPDATE, DELETE operations
   - Handles JOIN queries and filtering
   - Manages many-to-many relationships

2. **PydanticUi** / **PydanticCrudUi** (`pydantic_ui.py`) - Standalone form generators
   - Creates forms from Pydantic schemas
   - Database-agnostic form component
   - Session state management for form persistence
   - These three classes are the public API (`streamlit_pydantic_crud.__init__`)

3. **Package layout** — the root holds only the public classes and shared state:
   ```
   streamlit_pydantic_crud/
   ├── __init__.py        # public API: SqlUi, PydanticUi, PydanticCrudUi
   ├── sql_ui.py          # SqlUi; action buttons
   ├── pydantic_ui.py     # PydanticUi / PydanticCrudUi
   ├── config_types.py    # ForeignKeyOptions, ManyToManyFields, OperationType
   ├── state.py           # per-instance UI state, UPDATED_KEY, cache TTL,
   │                      #   set_state, clear_state_keys
   ├── helpers/           # leaf modules, no Streamlit state
   │   ├── typing.py      # annotation inspection (Optional, enum, list, model_fields)
   │   ├── sa_model.py    # SQLAlchemy introspection (PK, table name, column
   │   │                  #   label/types, related_model)
   │   ├── values.py      # value coercion (PG arrays, numpy/DataFrame cells, enum, JSON)
   │   ├── display.py     # labels and table formatting (get_pretty_name, convert_arrow)
   │   ├── logs.py        # CRUD action logging, set_logging
   │   └── db_errors.py   # user-friendly database error messages
   ├── table/             # read side of SqlUi
   │   ├── query.py       # CTE wrapping, filters, row count, paging (to_cte,
   │   │                  #   get_stmt_no_pag, get_qtty_rows, apply_active_filters)
   │   ├── filter_ui.py   # ColFilter widgets, cached filter values, hash_funcs
   │   ├── params.py      # mirror filter values to URL query params and restore them
   │   └── pagination.py  # page-size selector and pager, OPTS_ITEMS_PAGE tuples
   ├── forms/             # form fields in both modes
   │   ├── sa_fields.py   # InputFields: plain (no-schema) widgets, one per column
   │   ├── options.py     # FK / M2M options: load_form_options (Pydantic forms),
   │   │                  #   ExistingData, FkOpt, custom_foreign_opts (plain forms)
   │   ├── schema_builder.py  # dynamic Pydantic models from JSON schemas
   │   ├── schema_check.py    # validate_schema_compatibility (schema vs model)
   │   └── pydantic/      # Pydantic form generation
   │       ├── generator.py       # PydanticInputGenerator: routes fields to
   │       │                      #   widgets, builds form data (PydanticUi)
   │       ├── widgets.py         # renderers per widget kind; nullable_number_input
   │       ├── field_info.py      # get_pydantic_field_info, get_streamlit_input_type,
   │       │                      #   is_optional_field
   │       └── option_resolve.py  # UI-free default/option resolution (match_option,
   │                              #   resolve_select_index, known_defaults, ...)
   └── dialogs/           # CRUD dialogs
       ├── frame.py       # shared dialog wrapper (show_crud_dialog)
       ├── create.py / edit.py / delete.py  # CreateRow / UpdateRow / DeleteRows
       ├── persist.py     # M2M split/load, selectinload options, form session
       │                  #   key, handle_save_error
       └── one_to_many.py # related-rows panels in the edit dialog (opens
                          #   create/delete dialogs, reads via table/)
   ```
   - **Sub-package `__init__.py` files are docstring-only** — no imports, no
     re-exports; import submodules directly (`from streamlit_pydantic_crud.table
     import query`). Eager imports there would create cycles.
   - `helpers/typing.py` is always imported absolutely
     (`from streamlit_pydantic_crud.helpers.typing import ...`); it does not
     shadow the stdlib `typing`.

4. **Layering rule** (enforced by `tests/test_import_layers.py`): a module may
   import its own layer or a lower one, never a higher one, and the module graph
   has no cycles. Lowest first:
   `state`, `config_types` < `helpers/` < `table/`, `forms/` (peers) <
   `pydantic_ui` < `dialogs/` < `sql_ui` < `__init__`.
   `pydantic_ui` sits below `dialogs/` because the dialogs build `PydanticCrudUi`
   forms. Type-only imports go under `if TYPE_CHECKING:` (not runtime edges),
   e.g. `forms/options.py` annotating `PydanticCrudUi`. A new top-level module or
   sub-package must be added to `LAYERS` in that test.

### Key Architectural Patterns

1. **Pydantic Integration**: Separate schemas for create/read/update operations with type-safe validation
2. **JOIN Field Support**: Efficient handling of fields from joined tables without loading full relationships
3. **Many-to-Many Management**: Multiselect widgets for association tables with custom display fields
4. **Foreign Key Selectboxes**: User-friendly dropdowns with custom queries and display fields
5. **Session State Persistence**: Forms maintain state across Streamlit reruns

### Data Flow

1. **Read Operations**: SQLAlchemy query → Pandas DataFrame → Streamlit dataframe with filters
2. **Create/Update**: Pydantic form validation → SQLAlchemy model → Database commit
3. **Many-to-Many**: Two-stage filtering (base query + relationship loading) for performance
4. **JOIN Queries**: CTE-based filtering with labeled columns for conflict resolution

## Package Management

This project uses **uv** as the package manager and requires **Python >=3.12**. Key files:
- `pyproject.toml` - Project configuration, dependencies, and tool settings
- `uv.lock` - Lock file with exact dependency versions

## Quality Tools Configuration

### Type Checking (ty)
- Configured in `pyproject.toml` (`[tool.ty.src]`)
- Checks `streamlit_pydantic_crud/` and `tests/`
- Run with `uv run -- ty check`

### Linting and Formatting (Ruff)
- Line length: 88 characters
- Extensive rule set including UP, E, F, B, C4, etc.
- Auto-fixes available with `--fix` flag

### Dead Code Detection (Vulture)
- Configured to scan `streamlit_pydantic_crud/`
- Sorts by size for easier review

## Important File Patterns

- Main package: `streamlit_pydantic_crud/` (import name differs from repo name `streamlit_sql_crud`)
- Tests: `tests/test_*.py` with shared fixtures in `tests/conftest.py` and harness apps in `tests/_apps/`
- Config files: `pyproject.toml`, `Taskfile.yml`

## Development Workflow

1. Make changes to code in `streamlit_pydantic_crud/`
2. Run quality checks: `task fix` (or `task check` before pushing)
3. **Test all new functionality** using the test project (see Testing section below)

## Testing with Example Project

**ALL new functionality MUST be verified** using the companion test project at:
`~/repo/streamlit_sql_crud_example`

### Quick Test Setup
```bash
cd ~/repo/streamlit_sql_crud_example
./run.sh  # Automated setup and launch
```

### Key Test Resources
- **Setup Guide**: `~/repo/streamlit_sql_crud_example/GETTING_STARTED.md`
- **Launch Script**: `~/repo/streamlit_sql_crud_example/run.sh`
- **Manual Setup**: `~/repo/streamlit_sql_crud_example/setup_test.sh`

### Test Coverage
The example project tests all major features:
- **Basic CRUD**: Departments page (text areas, enums, decimals, booleans)
- **Foreign Keys**: Employees page (custom selectboxes, date validation, email validation)
- **Advanced Data Types**: Test Data Types page (arrays, JSON, all field types)
- **Relationships**: Many-to-many and one-to-many relationships
- **Validation**: Pydantic schemas with comprehensive validation rules

### Testing Workflow
1. Make changes to main library code
2. Run `cd ~/repo/streamlit_sql_crud_example && ./run.sh`
3. Test affected functionality in the web interface at http://localhost:8501
4. Verify CRUD operations work correctly
5. Check validation and error handling

## Key Dependencies

- **streamlit** - Web app framework
- **sqlalchemy** - Database ORM
- **pydantic** (≥2.0) - Data validation
- **pandas** - Data manipulation
- **loguru** - Logging
- **streamlit_datalist** - Enhanced UI components
- **streamlit_antd_components** - Additional UI widgets