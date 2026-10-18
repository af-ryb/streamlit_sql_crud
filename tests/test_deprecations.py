"""Deprecated SqlUi API (removed in 0.10.0) warns and keeps working.

`df_style_formatter`, `style_fn`, `base_key` and `SqlUi.df` each warn.
"""

import os
import warnings
from collections.abc import Callable
from pathlib import Path

import pandas as pd
import pytest
import streamlit as st
from pandas.io.formats.style import Styler
from streamlit.testing.v1 import AppTest

from tests._apps.read_path_models import ID_BRAVO

APP = str(Path(__file__).parent / "_apps" / "read_path_app.py")
FORMATTER_MSG = r"'df_style_formatter' is deprecated .* 0\.10\.0\. Use 'column_config'"
STYLE_FN_MSG = r"'style_fn' is deprecated .* 0\.10\.0 without replacement"
DF_MSG = r"'SqlUi\.df' is deprecated .* 0\.10\.0\. Use 'SqlUi\.rows'"
BASE_KEY_MSG = r"'base_key' parameter is deprecated .* 0\.10\.0\. Use 'key'"
BOTH_KEYS_MSG = r"'base_key' is deprecated, using 'key' .* removed in 0\.10\.0"


@pytest.fixture
def run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Callable[..., AppTest]:
    """Return a callable rendering the read-path harness in a mode."""
    monkeypatch.setenv("CRUD_TEST_DB", str(tmp_path / "deprecations.db"))
    monkeypatch.setenv("CRUD_TEST_MODE", "")

    def _run(mode: str, read_df: bool = False) -> AppTest:
        os.environ["CRUD_TEST_MODE"] = mode
        st.cache_data.clear()
        at = AppTest.from_file(APP, default_timeout=30)
        at.session_state["READ_DF"] = read_df
        at.run()
        assert not at.exception, [e.message for e in at.exception]
        return at

    return _run


def removals(caught: list[warnings.WarningMessage]) -> list[warnings.WarningMessage]:
    """The library's "removed in 0.10.0" DeprecationWarnings in `caught`."""
    return [
        w
        for w in caught
        if issubclass(w.category, DeprecationWarning) and "0.10.0" in str(w.message)
    ]


def test_style_params_warn_and_still_render_a_styler(
    run: Callable[..., AppTest],
) -> None:
    with (
        pytest.warns(DeprecationWarning, match=FORMATTER_MSG),
        pytest.warns(DeprecationWarning, match=STYLE_FN_MSG),
    ):
        at = run("styled")
    assert at.session_state["DATA_TYPE"] is Styler


def test_styled_render_warns_at_caller_without_touching_df(
    run: Callable[..., AppTest],
) -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        at = run("styled")

    ours = removals(caught)
    """One per deprecated param; the Styler is not built through `SqlUi.df`."""
    assert len(ours) == 2
    assert not [w for w in ours if "SqlUi.df" in str(w.message)]
    assert {Path(w.filename).name for w in ours} == {"read_path_app.py"}
    assert at.session_state["DF_BUILT"] is False


def test_default_path_emits_no_deprecation(run: Callable[..., AppTest]) -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        run("plain")
    assert removals(caught) == []


def test_df_access_warns_once_and_returns_display_frame(
    run: Callable[..., AppTest],
) -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        at = run("plain", read_df=True)

    """The app reads `ui.df` twice: built and warned on first access only."""
    ours = removals(caught)
    assert len(ours) == 1
    assert "SqlUi.df" in str(ours[0].message)
    assert Path(ours[0].filename).name == "read_path_app.py"
    df = at.session_state["DF"]
    assert isinstance(df, pd.DataFrame)
    assert at.session_state["DF_AGAIN"] is df
    assert df["id"].iloc[0] == ID_BRAVO
    assert list(df.columns) == list(at.session_state["ROWS"][0])


def test_df_access_warning_text(run: Callable[..., AppTest]) -> None:
    with pytest.warns(DeprecationWarning, match=DF_MSG):
        run("plain", read_df=True)


def test_base_key_warns_removed_in_0_10_0(run: Callable[..., AppTest]) -> None:
    with pytest.warns(DeprecationWarning, match=BASE_KEY_MSG):
        run("base_key")


def test_base_key_with_key_warns_removed_in_0_10_0(
    run: Callable[..., AppTest],
) -> None:
    with pytest.warns(DeprecationWarning, match=BOTH_KEYS_MSG):
        run("both_keys")
