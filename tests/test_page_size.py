"""SqlUi `page_size` / `page_size_options` drive the page-size selector.

`items_per_page_default` (an index) is deprecated (0.10.0) and maps to a value.
"""

import os
import warnings
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from streamlit_pydantic_crud import SqlUi
from streamlit_pydantic_crud.table.pagination import (
    OPTS_ITEMS_PAGE,
    SHOW_ALL,
    merge_page_sizes,
)

APP = str(Path(__file__).parent / "_apps" / "pagination_app.py")
PAGE = "p_pagination"
SIZE = "p_page_size"
DEFAULT_LABELS = ["50", "100", "200", "500", "1000", SHOW_ALL]
DEPRECATED_MSG = (
    r"'items_per_page_default' is deprecated .* 0\.10\.0\. "
    r"Use page_size=None \(None shows all rows\)"
)
BOTH_MSG = r"removed in 0\.10\.0.* Both given: 'page_size' \(5\) is used"

Render = Callable[..., AppTest]


@pytest.fixture
def render(tmp_path: Path) -> Render:
    """Return a callable rendering the 150-row harness with SqlUi kwargs."""

    def _render(**table_kw: Any) -> AppTest:
        os.environ["CRUD_TEST_DB"] = str(tmp_path / "page_size.db")
        st.cache_data.clear()
        at = AppTest.from_file(APP, default_timeout=30)
        at.session_state["TABLE_KW"] = table_kw
        at.run()
        return at

    return _render


def line(at: AppTest, name: str) -> str:
    """Return the value printed by the harness after `name=`."""
    assert not at.exception, [e.message for e in at.exception]
    prefix = f"{name}="
    value = next(m.value for m in at.markdown if m.value.startswith(prefix))
    return value.removeprefix(prefix)


def total(at: AppTest) -> str:
    """Return the row-range caption of the pager."""
    return next(c.value for c in at.caption if "/" in c.value)


def test_defaults_unchanged_without_warning(render: Render) -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        at = render()
    assert not [w for w in caught if "0.10.0" in str(w.message)]
    assert line(at, "RANGE") == "1-50"
    box = at.selectbox(key=SIZE)
    assert box.options == DEFAULT_LABELS
    assert box.value == "50"
    assert at.pagination(key=PAGE).proto.num_pages == 3


def test_page_size_not_in_options_is_inserted_and_selected(render: Render) -> None:
    at = render(page_size=5)
    assert line(at, "RANGE") == "1-5"
    box = at.selectbox(key=SIZE)
    assert box.options == ["5", *DEFAULT_LABELS]
    assert box.value == "5"
    assert at.pagination(key=PAGE).proto.num_pages == 30
    at.pagination(key=PAGE).set_value(2).run()
    assert line(at, "RANGE") == "6-10"


def test_page_size_none_shows_all_rows(render: Render) -> None:
    at = render(page_size=None)
    assert line(at, "RANGE") == "1-150"
    assert at.selectbox(key=SIZE).value == SHOW_ALL
    assert at.pagination(key=PAGE).proto.num_pages == 1


def test_no_options_hide_selector_and_page_by_page_size(render: Render) -> None:
    at = render(page_size=40, page_size_options=())
    assert line(at, "RANGE") == "1-40"
    assert SIZE not in [box.key for box in at.selectbox]
    assert at.pagination(key=PAGE).proto.num_pages == 4
    assert total(at) == "1-40 / 150"
    at.pagination(key=PAGE).set_value(4).run()
    assert line(at, "RANGE") == "121-150"


def test_no_options_and_page_size_none_show_all_without_pager(
    render: Render,
) -> None:
    at = render(page_size=None, page_size_options=None)
    assert line(at, "RANGE") == "1-150"
    assert SIZE not in [box.key for box in at.selectbox]
    assert len(at.pagination) == 0
    assert total(at) == "1-150 / 150"


def test_options_without_none_have_no_show_all(render: Render) -> None:
    at = render(page_size_options=[100, 25, 25])
    assert line(at, "RANGE") == "1-50"
    box = at.selectbox(key=SIZE)
    assert box.options == ["25", "50", "100"]
    assert box.value == "50"


def test_size_change_resets_page_with_custom_options(render: Render) -> None:
    at = render(page_size=10, page_size_options=(10, 20))
    at.pagination(key=PAGE).set_value(3).run()
    at.selectbox(key=SIZE).set_value("20").run()
    assert line(at, "RANGE") == "1-20"
    assert at.pagination(key=PAGE).value == 1


def test_deprecated_index_maps_to_value_and_warns_at_caller(
    render: Render,
) -> None:
    with pytest.warns(DeprecationWarning, match=DEPRECATED_MSG) as caught:
        at = render(items_per_page_default=5)
    assert line(at, "RANGE") == "1-150"
    assert at.selectbox(key=SIZE).value == SHOW_ALL
    ours = [w for w in caught if "items_per_page_default" in str(w.message)]
    assert {Path(w.filename).name for w in ours} == {"pagination_app.py"}


def test_deprecated_index_one_selects_100(render: Render) -> None:
    with pytest.warns(DeprecationWarning, match=r"Use page_size=100 "):
        at = render(items_per_page_default=1)
    assert line(at, "RANGE") == "1-100"
    assert at.selectbox(key=SIZE).value == "100"


def test_page_size_wins_over_deprecated_index_with_warning(
    render: Render,
) -> None:
    with pytest.warns(DeprecationWarning, match=BOTH_MSG):
        at = render(page_size=5, items_per_page_default=3)
    assert line(at, "RANGE") == "1-5"
    assert at.selectbox(key=SIZE).value == "5"


@pytest.mark.parametrize("index", [-1, 6, "2", True])
def test_deprecated_index_invalid_raises(index: Any) -> None:
    with pytest.raises(ValueError, match="items_per_page_default must be"):
        SqlUi.resolve_page_size(50, index)


@pytest.mark.parametrize(
    ("page_size", "options", "expected"),
    [
        (50, OPTS_ITEMS_PAGE, OPTS_ITEMS_PAGE),
        (5, OPTS_ITEMS_PAGE, (5, *OPTS_ITEMS_PAGE)),
        (300, (None, 100, 1000), (100, 300, 1000, None)),
        (None, (10, 20), (10, 20, None)),
        (20, (20, 10, 20, None, None), (10, 20, None)),
        (50, (), ()),
        (50, None, ()),
        (None, None, ()),
    ],
)
def test_merge_page_sizes(
    page_size: int | None, options: Any, expected: tuple[int | None, ...]
) -> None:
    assert merge_page_sizes(page_size, options) == expected


@pytest.mark.parametrize("page_size", [0, -5, True, 2.5, "50"])
def test_invalid_page_size_raises(page_size: Any) -> None:
    with pytest.raises(ValueError, match="page_size must be a positive int"):
        merge_page_sizes(page_size, OPTS_ITEMS_PAGE)


@pytest.mark.parametrize("options", [(50, 0), (50, -1), (50, False), (50, "100")])
def test_invalid_option_raises(options: Any) -> None:
    with pytest.raises(ValueError, match="page_size_options item must be"):
        merge_page_sizes(50, options)


@pytest.mark.parametrize("options", ["50", 50, {50, 100}])
def test_options_not_a_sequence_raises(options: Any) -> None:
    with pytest.raises(ValueError, match="page_size_options must be a sequence"):
        merge_page_sizes(50, options)


def test_invalid_page_size_fails_sql_ui_init(render: Render) -> None:
    at = render(page_size=0)
    assert at.exception
    assert "page_size must be a positive int" in at.exception[0].message


def test_stored_label_from_existing_session_is_kept(render: Render) -> None:
    """Options stay string labels: a size picked earlier survives a rerun."""
    at = render()
    at.selectbox(key=SIZE).set_value("100").run()
    at.run()
    assert line(at, "RANGE") == "1-100"
    assert at.selectbox(key=SIZE).value == "100"


def test_stored_label_no_longer_offered_falls_back(render: Render) -> None:
    """A stored "Show All" that the new options lack must not break."""
    at = render()
    at.selectbox(key=SIZE).set_value(SHOW_ALL).run()
    at.session_state["TABLE_KW"] = {"page_size_options": (50, 100)}
    at.run()
    assert line(at, "RANGE") == "1-50"
    assert at.selectbox(key=SIZE).value == "50"
