""" "Show All" must never yield a zero page size.

With an empty result the page size would be count=0; the page count and the
OFFSET of the page query divide by it.
"""

from streamlit_pydantic_crud.table.pagination import SHOW_ALL, resolve_page_size


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
    assert at.pagination[0].proto.num_pages == 1
    assert any(c.value == "0 / 0" for c in at.caption)
