"""The rolling-balance feature is removed from SqlUi.

RED until the rolling parameters and the Balance column are gone.
"""

import inspect

from streamlit_pydantic_crud import SqlUi


def test_rolling_params_removed_from_signature() -> None:
    """SqlUi no longer accepts the rolling-balance parameters."""
    params = inspect.signature(SqlUi.__init__).parameters
    assert "rolling_total_column" not in params
    assert "rolling_orderby_colsname" not in params


def test_no_balance_column_in_rendered_df(run_app) -> None:
    """Rendered table has no 'Balance' column (safety net for the removal)."""
    at = run_app()
    assert not at.exception
    cols_line = next(m.value for m in at.markdown if m.value.startswith("COLS="))
    assert "Balance" not in cols_line
    assert "amount" in cols_line


def test_app_renders_seeded_rows(run_app) -> None:
    """Basic rendering keeps working after the removal."""
    at = run_app()
    assert any("QTTY=5" in m.value for m in at.markdown)
