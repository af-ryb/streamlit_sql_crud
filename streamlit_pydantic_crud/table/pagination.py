"""Page-size selector and pager shared by SqlUi and one-to-many panels."""

import streamlit as st
import streamlit_antd_components as sac

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
) -> tuple[int, int]:
    """Render the page-size cascader and pager; return (page size, page).

    A None option in `opts_items_page` is shown as "Show All".
    """
    pag_col1, pag_col2 = st.columns([0.2, 0.8])

    # Convert options to strings, replacing None with "Show All"
    items_page_display: list[str] = []
    for item in opts_items_page:
        if item is None:
            items_page_display.append(SHOW_ALL)
        else:
            items_page_display.append(str(item))

    # Initialize session state for cascader if not exists
    cascader_key = f"{key}_menu_cascader"
    if cascader_key not in st.session_state and default_index < len(items_page_display):
        # Set initial value in session state based on default_index
        st.session_state[cascader_key] = [items_page_display[default_index]]

    # Determine default value
    if default_index < len(items_page_display):
        default_value = items_page_display[default_index]
    else:
        default_value = items_page_display[0] if items_page_display else "50"

    """sac.cascader expects a list of str | dict | CasItem (list is invariant)."""
    cascader_items: list[str | dict | sac.CasItem] = list(items_page_display)
    with pag_col1:
        menu_cas = sac.cascader(
            items=cascader_items,
            placeholder="Items per page",
            index=default_index,
            key=cascader_key,
        )

    # Get selected value
    selected_str = menu_cas[0] if menu_cas else default_value

    items_per_page = resolve_page_size(selected_str, count)

    """Key encodes page size and total so the widget remounts (and resets to
    page 1) when either changes, picking up the new page-count display."""
    pagination_key = pagination_widget_key(key, items_per_page, count)

    with pag_col2:
        page = sac.pagination(
            total=count,
            page_size=items_per_page,
            show_total=True,
            jump=True,
            key=pagination_key,
        )

    return (items_per_page, int(page))


def pagination_widget_key(key: str, items_per_page: int, count: int) -> str:
    """Build a pagination widget key that encodes page size and total.

    sac.pagination caches these in frontend state on mount, so changing the
    key forces a remount that picks up the new page size and total.
    """
    return f"{key}_pagination_{items_per_page}_{count}"


def resolve_page_size(selected: str | int, count: int) -> int:
    """Map a page-size option to rows per page; "Show All" means all rows.

    Never 0: the pagination frontend divides the total by the page size.
    """
    if selected == SHOW_ALL:
        return max(count, 1)
    return int(selected)
