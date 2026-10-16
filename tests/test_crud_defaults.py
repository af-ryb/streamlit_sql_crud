"""Falsy default values (False, 0) must be used, not rendered as inputs.

Regression: `if default_value:` skipped `False`/`0` defaults in CreateRow and
UpdateRow, so the user got an input for a field meant to be fixed.
"""

from streamlit.testing.v1 import AppTest

from tests.test_input_fields_enum import RunMode


def test_falsy_defaults_render_no_input(run_mode: RunMode) -> None:
    """Columns with `False`/`0` defaults get no widget in create or update."""
    at: AppTest = run_mode("defaults")

    assert not at.exception
    labels = {w.label for w in [*at.checkbox, *at.number_input]}
    assert "Done" not in labels
    assert "Count" not in labels
    assert "Ratio" in labels
