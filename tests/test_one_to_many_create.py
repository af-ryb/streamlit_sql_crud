"""The one-to-many panel's Create tab reports the result of the save.

A failed create shows the user-friendly database error and keeps the form; a
successful one shows a success message and empties the form.
"""

from collections.abc import Callable

import pytest
from streamlit.testing.v1 import AppTest

CREATE = "stsql_create_many_parent_parent_id_child"


@pytest.fixture
def app(run_app: Callable[[str], AppTest]) -> AppTest:
    """Render the panel of parent 1 (120 children)."""
    at = run_app("one_to_many_app.py")
    assert not at.exception
    return at


def submit(at: AppTest) -> AppTest:
    """Click the Save button of the panel's create form."""
    return at.button[0].click().run()


def test_failed_create_shows_db_error(app: AppTest) -> None:
    submit(app)

    assert not app.exception
    assert any("Missing Required Fields" in e.value for e in app.error)
    assert not app.success


def test_successful_create_shows_success_and_clears_form(app: AppTest) -> None:
    name = app.selectbox(key=f"{CREATE}_0_create_name")
    name.set_value(name.options[0])
    submit(app)

    assert not app.exception
    assert any("Created successfully" in s.value for s in app.success)
    assert not app.error
    assert app.selectbox(key=f"{CREATE}_1_create_name").value is None
