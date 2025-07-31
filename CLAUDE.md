# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Core Development Rules

### Code Quality
Type hints required for all code  
Public APIs must have docstrings  
Functions must be focused and small  
Follow existing patterns exactly  
Line length: 88 chars maximum  
Comments: two lines maximum, always use triple quotes, written in english  

### Code Style
PEP 8 naming (snake_case for functions/variables)  
Class names in PascalCase  
Constants in UPPER_SNAKE_CASE  
Document with docstrings  
Use f-strings for formatting  

### Testing Requirements
New features require tests  
Tests must be written in pytest  
Keep test files in separate directory, with name `tests` 

## Development Philosophy
- **Simplicity**: Write simple, straightforward code
- **Readability**: Make code easy to understand
- **Performance**: Consider performance without sacrificing readability
- **Maintainability**: Write code that's easy to update
- **Testability**: Ensure code is testable
- **Reusability**: Create reusable components and functions
- **Less Code = Less Debt**: Minimize code footprint

## Coding Best Practices
- **Make import on the top** of the file, never make import inside the function
- **Use comments**: Use comments to explain your code
- **Early Returns**: Use to avoid nested conditions
- **Descriptive Names**: Use clear variable/function names (prefix handlers with "handle")
- **Constants Over Functions**: Use constants where possible
- **DRY Code**: Don't repeat yourself
- **Functional Style**: Prefer functional, immutable approaches when not verbose
- **Minimal Changes**: Only modify code related to the task at hand
- **Function Ordering**: Define composing functions before their components
- **Simplicity**: Prioritize simplicity and readability over clever solutions
- **Build Iteratively** Start with minimal functionality and verify it works before adding complexity
- **Run Tests**: Test your code frequently with realistic inputs and validate outputs
- **Functional Code**: Use functional and stateless approaches where they improve clarity
- **Clean logic**: Keep core logic clean and push implementation details to the edges
- **File Organisation**: Balance file organization with simplicity - use an appropriate number of files for the project scale

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
# Run Streamlit app locally (if app/webapp.py exists)
make st
# OR
task st
# OR directly
uv run -- streamlit run app/webapp.py
```

## Architecture Overview

This is a **Streamlit-based CRUD library** that creates database interfaces with Pydantic validation. The core architecture consists of:

### Main Components

1. **SqlUi** (`sql_ui.py`) - Main CRUD interface class
   - Combines SQLAlchemy queries with Streamlit UI
   - Supports CREATE, READ, UPDATE, DELETE operations
   - Handles JOIN queries and filtering
   - Manages many-to-many relationships

2. **PydanticUi** (`pydantic_ui.py`) - Standalone form generator
   - Creates forms from Pydantic schemas
   - Database-agnostic form component
   - Session state management for form persistence

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

This project uses **uv** as the package manager. Key files:
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

- Main package: `streamlit_pydantic_crud/`
- Test files: `test_*.py` in root (should be moved to `tests/` directory)
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
`/home/miniserver/repo/streamlit_sql_crud_example`

### Quick Test Setup
```bash
cd /home/miniserver/repo/streamlit_sql_crud_example
./run.sh  # Automated setup and launch
```

### Key Test Resources
- **Setup Guide**: `/home/miniserver/repo/streamlit_sql_crud_example/GETTING_STARTED.md`
- **Launch Script**: `/home/miniserver/repo/streamlit_sql_crud_example/run.sh`
- **Manual Setup**: `/home/miniserver/repo/streamlit_sql_crud_example/setup_test.sh`

### Test Coverage
The example project tests all major features:
- **Basic CRUD**: Departments page (text areas, enums, decimals, booleans)
- **Foreign Keys**: Employees page (custom selectboxes, date validation, email validation)
- **Advanced Data Types**: Test Data Types page (arrays, JSON, all field types)
- **Relationships**: Many-to-many and one-to-many relationships
- **Validation**: Pydantic schemas with comprehensive validation rules

### Testing Workflow
1. Make changes to main library code
2. Run `cd /home/miniserver/repo/streamlit_sql_crud_example && ./run.sh`
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

Do what has been asked; nothing more, nothing less.
NEVER create files unless they're absolutely necessary for achieving your goal.
ALWAYS prefer editing an existing file to creating a new one.
NEVER proactively create documentation files (*.md) or README files. Only create documentation files if explicitly requested by the User.