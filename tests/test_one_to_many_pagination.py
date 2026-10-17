"""The one-to-many panel pages its child rows with the shared pager.

Its pager key does not include the parent id, so switching to a parent with
fewer children must clamp the stored page.
"""

from collections.abc import Callable

import pytest
from streamlit.testing.v1 import AppTest

PAGE = "stsql_read_many_pag_parent_parent_id_child_pagination"


def child_ids(at: AppTest) -> list[int]:
    """Return the child ids shown in the panel's Read tab."""
    return at.dataframe[0].value.index.to_list()


@pytest.fixture
def app(run_app: Callable[[str], AppTest]) -> AppTest:
    """Render the panel of parent 1 (120 children)."""
    at = run_app("one_to_many_app.py")
    assert not at.exception
    return at


def test_panel_pages_children(app: AppTest) -> None:
    assert app.pagination(key=PAGE).proto.num_pages == 3
    assert child_ids(app)[0] == 1

    app.pagination(key=PAGE).set_value(2).run()

    assert child_ids(app)[0] == 51
    assert any(c.value == "51-100 / 120" for c in app.caption)


def test_panel_page_clamps_for_smaller_parent(app: AppTest) -> None:
    app.pagination(key=PAGE).set_value(3).run()
    app.session_state["PARENT"] = 2
    app.run()

    assert not app.exception
    assert app.pagination(key=PAGE).value == 1
    assert child_ids(app) == list(range(121, 131))
