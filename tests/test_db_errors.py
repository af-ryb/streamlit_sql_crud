"""format_database_error maps SQLite and PostgreSQL errors to friendly text."""

import pytest

from streamlit_pydantic_crud.helpers.db_errors import format_database_error


@pytest.mark.parametrize(
    "raw",
    [
        "NOT NULL constraint failed: child.name",
        '(psycopg.errors.NotNullViolation) null value in column "name" of relation '
        '"projects" violates not-null constraint',
    ],
)
def test_not_null_is_missing_required_fields(raw: str) -> None:
    assert "Missing Required Fields" in format_database_error(RuntimeError(raw))
