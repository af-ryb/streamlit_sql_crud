# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Conventions

Project-specific rules (the rest is enforced by ruff/pyright — see config):
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
# Run all quality checks, auto-fix, and format (most common)
make fix
# OR using Task
task fix
# OR directly with uv
uv run -- pyright && uv run -- ruff check --fix && uv run -- ruff format
```

### Running Tests
```bash
# Run the full suite (pytest testpaths = ["tests"], quiet mode via addopts)
uv run -- pytest
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

### Building and Publishing
```bash
# Build and publish to PyPI
make publish
# OR
task publish
# OR directly
uv build && uv publish
```

### Documentation
```bash
# Serve documentation locally
task show-docs
# Deploy documentation to GitHub Pages
task deploy-docs
```

### Development Server
```bash
# NOTE: this repo has no app/ directory; `make st`/`task st` target app/webapp.py
# and only work where that file exists. To run a live UI, use the example project
# below (./run.sh) instead.
make st
```

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

3. **Core Modules**:
   - `filters.py` - Advanced filtering for JOIN queries and complex conditions
   - `input_fields.py` - Custom Streamlit input widgets with Pydantic integration
   - `pydantic_utils.py` - Utilities for Pydantic-SQLAlchemy conversion
   - `schema_builder.py` - Dynamic Pydantic model creation from JSON schemas
   - `create_delete_model.py` - Handles create/delete operations
   - `update_model.py` - Manages update operations
   - `read_cte.py` - Complex read queries with CTEs (Common Table Expressions)
   - `many.py` - Many-to-many relationship management

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

### Type Checking (Pyright)
- Configured in `pyproject.toml`
- Virtual environment: `.venv`
- Includes: `streamlit_pydantic_crud/`

### Linting and Formatting (Ruff)
- Line length: 88 characters
- Extensive rule set including UP, E, F, B, C4, etc.
- Auto-fixes available with `--fix` flag

### Dead Code Detection (Vulture)
- Configured to scan `streamlit_pydantic_crud/`
- Sorts by size for easier review

## Important File Patterns

- Main package: `streamlit_pydantic_crud/` (import name differs from repo/PyPI name `streamlit_sql_crud`)
- Tests: `tests/test_*.py` with shared fixtures in `tests/conftest.py` and harness apps in `tests/_apps/`
- Documentation: `docs/` with MkDocs configuration
- Config files: `pyproject.toml`, `Makefile`, `Taskfile.yml`

## Development Workflow

1. Make changes to code in `streamlit_pydantic_crud/`
2. Run quality checks: `make fix` or `task fix`
3. **Test all new functionality** using the test project (see Testing section below)
4. For documentation changes: `task show-docs` to preview
5. Build and publish: `make publish` or `task publish`

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