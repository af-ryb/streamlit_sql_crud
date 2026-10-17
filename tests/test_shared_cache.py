"""Caches shared by all sessions must see writes made by any session.

They were keyed by the per-session `stsql_updated` counter, which every new
session restarts, so other sessions got stale counts and filter options.
"""

from collections.abc import Callable

from streamlit.testing.v1 import AppTest

from tests.conftest import APP_DIR

APP = "shared_cache_app.py"


def test_write_in_one_session_refreshes_the_others(
    run_app: Callable[[str], AppTest],
) -> None:
    """Session B deletes a row; A on rerun and a new C see the new count."""
    session_a = run_app(APP)
    assert markdown(session_a, "QTTY") == "5"

    session_b = new_session()
    delete_in(session_b, [5])
    assert not session_b.exception
    assert markdown(session_b, "QTTY") == "4"

    session_a.run()
    session_c = new_session()

    for at in (session_a, session_c):
        assert not at.exception
        assert markdown(at, "QTTY") == "4"
        assert markdown(at, "NAMES") == "P1,P2,P3,P4"


def test_selection_resets_only_in_the_writing_session(
    run_app: Callable[[str], AppTest],
) -> None:
    """The writer's dataframe remounts; a bystander keeps its selection."""
    session_a = run_app(APP)
    session_b = new_session()
    a_before, b_before = df_id(session_a), df_id(session_b)

    delete_in(session_b, [5])
    session_a.run()

    assert df_id(session_b) != b_before
    assert df_id(session_a) == a_before


def new_session() -> AppTest:
    """Render the app in a fresh session, keeping the shared caches."""
    at = AppTest.from_file(str(APP_DIR / APP), default_timeout=30)
    at.run()
    return at


def delete_in(at: AppTest, ids: list[int]) -> None:
    """Delete rows `ids` through the library's delete dialog of session `at`."""
    at.session_state["DELETE_IDS"] = ids
    at.run()
    at.button(key="pet_delete_del_btn").click().run()
    at.session_state["DELETE_IDS"] = None
    at.run()


def markdown(at: AppTest, prefix: str) -> str:
    """Return the value of the first `PREFIX=value` markdown line."""
    for md in at.markdown:
        if md.value.startswith(f"{prefix}="):
            return md.value.removeprefix(f"{prefix}=")
    msg = f"no markdown line starting with {prefix}="
    raise AssertionError(msg)


def df_id(at: AppTest) -> str:
    """Return the element id of the SqlUi dataframe."""
    return at.get("dataframe")[0].proto.id
