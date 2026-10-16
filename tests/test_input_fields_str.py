"""Free-text inputs return None, not the string "None", when left empty."""

from tests.test_input_fields_enum import RunMode


def test_empty_text_input_returns_none(run_mode: RunMode) -> None:
    """An untouched free-text column yields None."""
    at = run_mode("fields")

    assert not at.exception
    assert "VAL_f_note=None" in [m.value for m in at.markdown]


def test_prefilled_text_input_returns_value(run_mode: RunMode) -> None:
    """A free-text column pre-filled from the row keeps its value."""
    at = run_mode("fields_row")

    assert "VAL_r_note='n1'" in [m.value for m in at.markdown]
