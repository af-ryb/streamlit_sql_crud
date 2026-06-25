"""Stateful query caches must carry a TTL (issue #3).

Without a TTL these caches only refresh when the library's own update
counter changes, so values added outside the library (ETL, agents, direct
writes) stay invisible until the app restarts.
"""

from streamlit_pydantic_crud import read_cte
from streamlit_pydantic_crud.create_delete_model import DeleteRows
from streamlit_pydantic_crud.filters import ExistingData


def _ttl(cached_func: object) -> object:
    """Read the configured ttl of a st.cache_data-decorated function."""
    return cached_func._info.ttl  # type: ignore[attr-defined]


def test_get_existing_values_has_ttl() -> None:
    assert _ttl(read_cte.get_existing_values) is not None


def test_get_qtty_rows_has_ttl() -> None:
    assert _ttl(read_cte.get_qtty_rows) is not None


def test_get_text_has_ttl() -> None:
    assert _ttl(ExistingData.get_text) is not None


def test_get_dt_has_ttl() -> None:
    assert _ttl(ExistingData.get_dt) is not None


def test_get_rows_str_has_ttl() -> None:
    assert _ttl(DeleteRows.get_rows_str) is not None
