"""Page-size selector and pager shared by SqlUi and one-to-many panels.

Native `st.selectbox` + `st.pagination` with stable keys: the page is moved
through its session-state key (page 1 on a reset or size change, clamped to
the last page when rows disappear) instead of remounting the widget.
"""

from collections.abc import Sequence
from math import ceil

import streamlit as st
from streamlit import session_state as ss

SHOW_ALL = "Show All"

PageSizes = tuple[int | None, ...]
"""Page-size options; None is the "Show All" entry."""

OPTS_ITEMS_PAGE: PageSizes = (50, 100, 200, 500, 1000, None)
"""SqlUi default page sizes; the deprecated ``items_per_page_default`` indexes it."""

DEFAULT_PAGE_SIZE = 50
"""Rows per page selected by default in SqlUi and the one-to-many panels."""

REL_OPTS_ITEMS_PAGE: PageSizes = (50, 100, 200, 500, 1000)
"""One-to-many panel page sizes; deliberately without "Show All"."""


def show_pagination(
    count: int,
    options: PageSizes,
    page_size: int | None,
    key: str = "",
    reset: bool = False,
) -> tuple[int, int]:
    """Render the page-size selectbox and pager; return (page size, page).

    `options` come from `merge_page_sizes` (`page_size` among them). No
    options: no selectbox, fixed `page_size`; None then shows all rows, no pager.
    """
    page_key = f"{key}_pagination"
    size_col, pag_col, total_col = st.columns(
        [0.2, 0.6, 0.2], vertical_alignment="center"
    )

    if options:
        with size_col:
            selected = page_size_select(options, page_size, key, page_key)
    else:
        selected = option_label(page_size)

    items_per_page = resolve_page_size(selected, count)
    num_pages = page_count(count, items_per_page)
    sync_page_state(page_key, num_pages, reset)

    page = 1
    if options or page_size is not None:
        with pag_col:
            page = st.pagination(num_pages, key=page_key)

    with total_col:
        st.caption(page_range_text(count, items_per_page, page))

    return items_per_page, page


def page_size_select(
    options: PageSizes, page_size: int | None, key: str, page_key: str
) -> str:
    """Render the page-size selectbox; return the selected label.

    Options are string labels, as before: a stored label stays valid.
    """
    labels = [option_label(item) for item in options]
    default = option_label(page_size)
    selected = st.selectbox(
        "Items per page",
        labels,
        index=labels.index(default) if default in labels else 0,
        key=f"{key}_page_size",
        label_visibility="collapsed",
        on_change=handle_page_size_change,
        args=(page_key,),
    )
    return selected or labels[0]


def merge_page_sizes(
    page_size: int | None, options: Sequence[int | None] | None
) -> PageSizes:
    """Validate the page sizes; return the options with `page_size` among them.

    Ints ascend, None ("Show All") goes last; empty or None options stay empty.
    """
    check_page_size(page_size, "page_size")
    if options is None:
        return ()
    if isinstance(options, str | bytes) or not isinstance(options, Sequence):
        msg = (
            "page_size_options must be a sequence of positive ints and/or None, "
            f"got {options!r}"
        )
        raise ValueError(msg)
    for item in options:
        check_page_size(item, "page_size_options item")
    if not options:
        return ()
    merged = {*options, page_size}
    ints = sorted(item for item in merged if item is not None)
    return (*ints, None) if None in merged else tuple(ints)


def check_page_size(value: object, name: str) -> None:
    """Raise ValueError unless `value` is a positive int (not bool) or None."""
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        msg = f"{name} must be a positive int or None (show all), got {value!r}"
        raise ValueError(msg)


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
