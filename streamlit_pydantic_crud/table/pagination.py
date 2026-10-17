"""Page-size selector and pager shared by SqlUi and one-to-many panels.

Native `st.selectbox` + `st.pagination` with stable keys: the page is moved
through its session-state key (page 1 on a reset or size change, clamped to
the last page when rows disappear) instead of remounting the widget.
"""

from math import ceil

import streamlit as st
from streamlit import session_state as ss

SHOW_ALL = "Show All"

OPTS_ITEMS_PAGE: tuple[int | None, ...] = (50, 100, 200, 500, 1000, None)
"""SqlUi page sizes; None is "Show All" (``items_per_page_default`` indexes it)."""

REL_OPTS_ITEMS_PAGE: tuple[int | None, ...] = (50, 100, 200, 500, 1000)
"""One-to-many panel page sizes; deliberately without "Show All"."""


def show_pagination(
    count: int,
    opts_items_page: tuple[int | None, ...],
    key: str = "",
    default_index: int = 0,
    reset: bool = False,
) -> tuple[int, int]:
    """Render the page-size selectbox and pager; return (page size, page).

    A None option in `opts_items_page` is shown as "Show All". `reset` moves
    the pager back to page 1 (e.g. after a filter change).
    """
    page_key = f"{key}_pagination"
    size_col, pag_col, total_col = st.columns(
        [0.2, 0.6, 0.2], vertical_alignment="center"
    )

    labels = [option_label(item) for item in opts_items_page]
    with size_col:
        selected = st.selectbox(
            "Items per page",
            labels,
            index=min(default_index, len(labels) - 1),
            key=f"{key}_page_size",
            label_visibility="collapsed",
            on_change=handle_page_size_change,
            args=(page_key,),
        )

    items_per_page = resolve_page_size(selected or labels[0], count)
    num_pages = page_count(count, items_per_page)
    sync_page_state(page_key, num_pages, reset)

    with pag_col:
        page = st.pagination(num_pages, key=page_key)

    with total_col:
        st.caption(page_range_text(count, items_per_page, page))

    return items_per_page, page


def handle_page_size_change(page_key: str) -> None:
    """Go back to page 1 when the page size changes."""
    set_page(page_key, 1)


def sync_page_state(page_key: str, num_pages: int, reset: bool) -> None:
    """Reset the stored page to 1, or clamp it to `num_pages` when beyond.

    Writes only on a real change: each write is pushed to the frontend.
    """
    current = ss.get(page_key)
    if not isinstance(current, int):
        return
    if reset:
        set_page(page_key, 1)
    elif current > num_pages:
        set_page(page_key, num_pages)


def set_page(page_key: str, page: int) -> None:
    """Store `page` for the pager unless it already shows that page."""
    if ss.get(page_key, 1) != page:
        ss[page_key] = page


def option_label(item: int | None) -> str:
    """Return the selectbox label of a page-size option."""
    return SHOW_ALL if item is None else str(item)


def resolve_page_size(selected: str | int, count: int) -> int:
    """Map a page-size option to rows per page; "Show All" means all rows.

    Never 0: the page count and the page OFFSET divide by it.
    """
    if selected == SHOW_ALL:
        return max(count, 1)
    return int(selected)


def page_count(count: int, items_per_page: int) -> int:
    """Return the number of pages for `count` rows; at least one."""
    return max(1, ceil(count / items_per_page))


def page_range_text(count: int, items_per_page: int, page: int) -> str:
    """Return the "first-last / total" caption of the shown rows."""
    if count == 0:
        return "0 / 0"
    first = (page - 1) * items_per_page + 1
    last = min(page * items_per_page, count)
    return f"{first}-{last} / {count}"
