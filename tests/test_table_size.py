"""SqlUi `width` / `height` reach the main table's st.dataframe as given.

`read_use_container_width` is deprecated (0.10.0) and maps to width="stretch".
"""

import os
import warnings
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).parent / "_apps" / "read_path_app.py")
DEPRECATED_MSG = (
    r"'read_use_container_width' is deprecated .* 0\.10\.0\. Use width='stretch'"
)


@pytest.fixture
def render(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Callable[..., tuple[Any, Any]]:
    """Return a callable rendering the plain harness with SqlUi kwargs.

    It returns the (width, height) the table's st.dataframe received.
    """
    monkeypatch.setenv("CRUD_TEST_DB", str(tmp_path / "size.db"))
    monkeypatch.setenv("CRUD_TEST_MODE", "plain")

    def _render(**table_kw: Any) -> tuple[Any, Any]:
        os.environ["CRUD_TEST_MODE"] = "plain"
        st.cache_data.clear()
        at = AppTest.from_file(APP, default_timeout=30)
        at.session_state["TABLE_KW"] = table_kw
        at.run()
        assert not at.exception, [e.message for e in at.exception]
        return at.session_state["SIZE"]

    return _render


def test_defaults_are_content_width_and_650_height_without_warning(
    render: Callable[..., tuple[Any, Any]],
) -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        size = render()
    assert size == ("content", 650)
    assert not [w for w in caught if "0.10.0" in str(w.message)]


@pytest.mark.parametrize("width", ["stretch", "content", 480])
def test_width_passes_through(
    render: Callable[..., tuple[Any, Any]], width: Any
) -> None:
    assert render(width=width) == (width, 650)


@pytest.mark.parametrize("height", [300, "auto", "stretch", "content"])
def test_height_passes_through(
    render: Callable[..., tuple[Any, Any]], height: Any
) -> None:
    assert render(height=height) == ("content", height)


def test_deprecated_use_container_width_still_stretches(
    render: Callable[..., tuple[Any, Any]],
) -> None:
    with pytest.warns(DeprecationWarning, match=DEPRECATED_MSG) as caught:
        size = render(read_use_container_width=True)
    assert size == ("stretch", 650)
    ours = [w for w in caught if "read_use_container_width" in str(w.message)]
    assert {Path(w.filename).name for w in ours} == {"read_path_app.py"}


def test_width_wins_over_deprecated_flag_with_warning(
    render: Callable[..., tuple[Any, Any]],
) -> None:
    with pytest.warns(DeprecationWarning, match=r"Both given: 'width' is used"):
        size = render(read_use_container_width=True, width=600)
    assert size == (600, 650)
