"""SqlUi paginates with the native st.pagination and a page-size selectbox.

The page follows filters, page size and row count through its session-state
key: page 1 after a filter or size change, clamped after rows disappear.
"""

from collections.abc import Callable

import pytest
from streamlit.testing.v1 import AppTest

from streamlit_pydantic_crud.table.pagination import SHOW_ALL, page_count

APP = "pagination_app.py"
PAGE = "p_pagination"
SIZE = "p_page_size"
GRP = "p_create_no_dt_filter_Grp"


def line(at: AppTest, name: str) -> str:
    """Return the value printed by the harness after `name=`."""
    prefix = f"{name}="
    value = next(m.value for m in at.markdown if m.value.startswith(prefix))
    return value.removeprefix(prefix)


def total(at: AppTest) -> str:
    """Return the row-range caption of the pager."""
    return next(c.value for c in at.caption if "/" in c.value)


@pytest.fixture
def app(run_app: Callable[[str], AppTest]) -> AppTest:
    """Render the 150-row harness on page 1 with 50 rows per page."""
    at = run_app(APP)
    assert not at.exception
    return at


def test_first_page_shows_pages_and_total(app: AppTest) -> None:
    assert app.pagination(key=PAGE).proto.num_pages == 3
    assert app.pagination(key=PAGE).value == 1
    assert line(app, "RANGE") == "1-50"
    assert total(app) == "1-50 / 150"


def test_second_page(app: AppTest) -> None:
    app.pagination(key=PAGE).set_value(2).run()
    assert line(app, "RANGE") == "51-100"
    assert total(app) == "51-100 / 150"


def test_size_change_resets_page(app: AppTest) -> None:
    """Page 2 still exists with 100 rows per page; it must reset anyway."""
    app.pagination(key=PAGE).set_value(2).run()
    app.selectbox(key=SIZE).set_value("100").run()
    assert not app.exception
    assert app.pagination(key=PAGE).value == 1
    assert app.pagination(key=PAGE).proto.num_pages == 2
    assert line(app, "RANGE") == "1-100"


def test_show_all(app: AppTest) -> None:
    app.pagination(key=PAGE).set_value(2).run()
    app.selectbox(key=SIZE).set_value(SHOW_ALL).run()
    assert app.pagination(key=PAGE).proto.num_pages == 1
    assert line(app, "RANGE") == "1-150"
    assert total(app) == "1-150 / 150"


def test_filter_change_resets_page(app: AppTest) -> None:
    app.pagination(key=PAGE).set_value(2).run()
    app.selectbox(key=GRP).set_value("y").run()
    assert not app.exception
    assert app.pagination(key=PAGE).value == 1
    assert line(app, "RANGE") == "76-125"
    assert total(app) == "1-50 / 75"


def test_page_clamps_when_rows_disappear(app: AppTest) -> None:
    app.pagination(key=PAGE).set_value(3).run()
    app.session_state["KEEP_ROWS"] = 90
    app.run()
    assert not app.exception
    assert app.pagination(key=PAGE).proto.num_pages == 2
    assert app.pagination(key=PAGE).value == 2
    assert line(app, "RANGE") == "51-90"


def test_page_survives_reruns(app: AppTest) -> None:
    app.pagination(key=PAGE).set_value(2).run()
    app.run()
    assert line(app, "RANGE") == "51-100"


def test_page_size_none_preselects_show_all(
    run_app: Callable[[str], AppTest],
) -> None:
    """page_size=None preselects the "Show All" option."""
    at = run_app("sql_ui_empty_show_all_app.py")
    assert not at.exception
    assert at.selectbox(key="note_page_size").value == SHOW_ALL
    assert at.pagination(key="note_pagination").proto.num_pages == 1


@pytest.mark.parametrize(
    ("count", "size", "pages"),
    [(0, 50, 1), (1, 50, 1), (50, 50, 1), (51, 50, 2), (150, 50, 3)],
)
def test_page_count(count: int, size: int, pages: int) -> None:
    assert page_count(count, size) == pages
