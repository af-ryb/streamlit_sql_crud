"""Row selection must reset after a write (create/copy/edit/delete).

The dataframe kept its positional selection across data changes, so after
a create the checkbox pointed at a different record.
"""

from collections.abc import Callable

from streamlit.testing.v1 import AppTest

from streamlit_pydantic_crud.state import UPDATED_KEY


def df_id(at: AppTest) -> str:
    """Return the element id of the SqlUi dataframe."""
    return at.get("dataframe")[0].proto.id


def test_dataframe_remounts_after_write(run_app: Callable[[str], AppTest]) -> None:
    """A write of this session renews the key; a new id drops the selection."""
    at = run_app("sql_ui_app.py")
    before = df_id(at)
    at.run()
    assert df_id(at) == before

    at.session_state[UPDATED_KEY] = 1
    at.run()

    assert not at.exception
    assert df_id(at) != before
