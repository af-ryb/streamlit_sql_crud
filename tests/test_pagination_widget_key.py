"""The pagination widget key must change when page size or total changes.

sac.pagination caches page_size/total in frontend state on mount and does
not re-sync on prop change, so the widget must be remounted (new key) when
either changes; otherwise the page-count display goes stale.
"""

from streamlit_pydantic_crud.read_cte import pagination_widget_key


def test_key_changes_when_page_size_changes() -> None:
    assert pagination_widget_key("k", 50, 58) != pagination_widget_key("k", 100, 58)


def test_key_changes_when_total_changes() -> None:
    assert pagination_widget_key("k", 50, 58) != pagination_widget_key("k", 50, 120)


def test_key_stable_for_same_inputs() -> None:
    assert pagination_widget_key("k", 50, 58) == pagination_widget_key("k", 50, 58)
