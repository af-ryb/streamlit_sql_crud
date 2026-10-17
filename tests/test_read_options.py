"""ORM options on read_instance are ignored (CTE-wrapped) and noticed once."""

from collections.abc import Callable, Iterator

import pytest
from loguru import logger
from streamlit.testing.v1 import AppTest

from streamlit_pydantic_crud import sql_ui

NOTICE = "ORM options on read_instance are ignored"


@pytest.fixture
def messages() -> Iterator[list[str]]:
    """Capture loguru messages and reset the once-per-key notice registry."""
    sql_ui.OPTIONS_NOTICE_KEYS.clear()
    captured: list[str] = []
    sink_id = logger.add(lambda m: captured.append(str(m)), level="DEBUG")
    yield captured
    logger.remove(sink_id)
    sql_ui.OPTIONS_NOTICE_KEYS.clear()


def markdown(at: AppTest, prefix: str) -> str:
    """Return the first markdown value starting with prefix."""
    return next(m.value for m in at.markdown if m.value.startswith(prefix))


def render(
    run_app: Callable[[str], AppTest],
    monkeypatch: pytest.MonkeyPatch,
    options: bool,
) -> AppTest:
    """Render the options app with or without loader options."""
    monkeypatch.setenv("CRUD_TEST_OPTIONS", "1" if options else "0")
    at = run_app("sql_ui_options_app.py")
    assert not at.exception
    return at


def test_options_do_not_change_rows(
    run_app: Callable[[str], AppTest],
    monkeypatch: pytest.MonkeyPatch,
    messages: list[str],
) -> None:
    plain = render(run_app, monkeypatch, options=False)
    with_opts = render(run_app, monkeypatch, options=True)
    assert markdown(with_opts, "ROWS=") == markdown(plain, "ROWS=")
    assert markdown(with_opts, "COLS=") == markdown(plain, "COLS=")
    assert markdown(plain, "ROWS=") == "ROWS=1:T1;2:T2;3:T3"


def test_notice_logged_once(
    run_app: Callable[[str], AppTest],
    monkeypatch: pytest.MonkeyPatch,
    messages: list[str],
) -> None:
    at = render(run_app, monkeypatch, options=True)
    at.run()
    render(run_app, monkeypatch, options=True)
    notices = [m for m in messages if NOTICE in m]
    assert len(notices) == 1
    assert not any("selectinload() options detected" in m for m in messages)


def test_no_notice_without_options(
    run_app: Callable[[str], AppTest],
    monkeypatch: pytest.MonkeyPatch,
    messages: list[str],
) -> None:
    render(run_app, monkeypatch, options=False)
    assert not any(NOTICE in m for m in messages)
