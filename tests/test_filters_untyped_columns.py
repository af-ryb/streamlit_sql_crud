"""Columns without a Python type must not crash the filters (#13).

`NullType` (e.g. `literal_column`, untyped `func.*`) raises NotImplementedError
from `python_type`; such columns are simply not filterable.
"""

from unittest.mock import MagicMock

import pytest
from sqlalchemy import func, literal_column, select

from streamlit_pydantic_crud import filter_ui, params
from streamlit_pydantic_crud.sa_model import safe_python_type
from tests.conftest import Department

UNTYPED_CTE = select(
    Department.id,
    Department.name,
    literal_column("'x'").label("tag"),
    func.upper(Department.name).label("calc"),
).cte()


def test_safe_python_type_returns_none_for_nulltype() -> None:
    """NullType has no Python type; typed columns keep theirs."""
    assert safe_python_type(UNTYPED_CTE.c.tag) is None
    assert safe_python_type(UNTYPED_CTE.c.calc) is None
    assert safe_python_type(UNTYPED_CTE.c.name) is str


def test_existing_cond_skips_untyped_columns() -> None:
    """Untyped columns get no existing-values query."""
    assert filter_ui.get_existing_cond(UNTYPED_CTE.c.tag) is False
    assert filter_ui.get_existing_cond(UNTYPED_CTE.c.name) is True


def test_col_filter_skips_untyped_columns() -> None:
    """ColFilter renders no widget for untyped columns."""
    col_filter = filter_ui.ColFilter(
        MagicMock(),
        cte=UNTYPED_CTE,
        existing_values={"tag": ["x"], "calc": ["A"]},
        available_col_filter=["tag", "calc"],
    )

    assert col_filter.dt_filters == {}
    assert col_filter.no_dt_filters == {}


def test_no_dt_param_untyped_column(monkeypatch: pytest.MonkeyPatch) -> None:
    """A query param for an untyped column resolves to no index."""
    monkeypatch.setattr(params.st, "query_params", {"tag": "x"})
    assert params.get_no_dt_param(UNTYPED_CTE.c.tag, ["x"]) is None


def test_sql_ui_renders_with_untyped_columns(run_app) -> None:
    """A SqlUi read select with untyped columns renders without exceptions."""
    at = run_app("sql_ui_untyped_app.py")

    assert not at.exception
    assert any(m.value == "QTTY=3" for m in at.markdown)
