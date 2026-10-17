""" "Show All" must never hand a zero page size to the pagination widget.

With an empty result, page_size=count=0 reaches sac.pagination, whose antd
frontend divides total by page size to compute the page count.
"""

from streamlit_pydantic_crud.pagination import SHOW_ALL, resolve_page_size


def test_show_all_with_empty_result_is_positive() -> None:
    assert resolve_page_size(SHOW_ALL, 0) == 1


def test_show_all_uses_row_count() -> None:
    assert resolve_page_size(SHOW_ALL, 58) == 58


def test_numeric_option_is_parsed() -> None:
    assert resolve_page_size("100", 0) == 100


def test_sql_ui_show_all_on_empty_table(run_app) -> None:
    """An empty table with "Show All" preselected renders without errors."""
    at = run_app("sql_ui_empty_show_all_app.py")

    assert not at.exception
    assert any(m.value == "QTTY=0" for m in at.markdown)
    assert any(m.value == "PAGE_SIZE_OK" for m in at.markdown)
