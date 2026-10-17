"""Filter helpers must not rely on `assert` for control flow.

Asserts vanish under `python -O`, silently changing behaviour; unknown
filter columns raise a clear ValueError and a cleared date input drops
its query param instead of failing.
"""

from datetime import date
from unittest.mock import MagicMock

import pytest
from sqlalchemy import select

from streamlit_pydantic_crud.table import params, query
from tests.conftest import Department

CTE = select(Department).cte()


def test_unknown_no_dt_filter_column_raises_value_error() -> None:
    """A non-date filter on a column missing from the CTE is a ValueError."""
    with pytest.raises(ValueError, match="ghost"):
        query.get_stmt_no_pag_dt(CTE, {"ghost": "x"})


def test_unknown_dt_filter_column_raises_value_error() -> None:
    """A date filter on a column missing from the CTE is a ValueError."""
    col_filter = MagicMock(no_dt_filters={}, dt_filters={"ghost": (None, None)})
    with pytest.raises(ValueError, match="ghost"):
        query.get_stmt_no_pag(CTE, col_filter)


def test_known_filter_columns_build_where() -> None:
    """Known columns still produce WHERE clauses."""
    col_filter = MagicMock(
        no_dt_filters={"name": "Dept 1"},
        dt_filters={"id": (1, 3)},
    )
    sql = str(query.get_stmt_no_pag(CTE, col_filter))
    assert "WHERE" in sql
    assert sql.count("anon_1.id") >= 2


def test_set_dt_param_stores_date(monkeypatch: pytest.MonkeyPatch) -> None:
    """A picked date is written to the query params as ISO text."""
    query: dict[str, str] = {}
    monkeypatch.setattr(params.st, "query_params", query)
    monkeypatch.setattr(params, "ss", {"k": date(2024, 5, 6)})

    params.set_dt_param("born", "k", "start")

    assert query == {"born_start": "2024-05-06"}


def test_set_dt_param_cleared_input_drops_param(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A cleared date input (None) removes the query param, no crash."""
    query = {"born_start": "2024-05-06"}
    monkeypatch.setattr(params.st, "query_params", query)
    monkeypatch.setattr(params, "ss", {"k": None})

    params.set_dt_param("born", "k", "start")

    assert query == {}
