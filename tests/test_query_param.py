"""get_no_dt_param must not crash on a stale string query param (#7).

A value left in the URL that is no longer among the column's options used
to raise ValueError via list.index and crash the filter render.
"""

import pytest

from streamlit_pydantic_crud import params
from tests.conftest import Department


def test_stale_string_param_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """An unknown query-param value yields None instead of raising."""
    col = Department.__table__.c.name
    monkeypatch.setattr(params.st, "query_params", {"name": "ghost"})
    assert params.get_no_dt_param(col, ["Dept 1", "Dept 2"]) is None


def test_known_string_param_returns_index(monkeypatch: pytest.MonkeyPatch) -> None:
    """A known value still resolves to its option index."""
    col = Department.__table__.c.name
    monkeypatch.setattr(params.st, "query_params", {"name": "Dept 2"})
    assert params.get_no_dt_param(col, ["Dept 1", "Dept 2"]) == 1
