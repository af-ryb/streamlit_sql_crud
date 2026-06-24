"""Tests for numeric coercion in InputFields (Numeric/Decimal columns).

Regression: entering 0 must be preserved, not silently turned into None.
"""

from decimal import Decimal

from streamlit_pydantic_crud.input_fields import InputFields


def test_zero_is_preserved() -> None:
    """A literal 0 must stay 0, not become None."""
    assert InputFields.coerce_decimal(0, None) == Decimal("0")


def test_none_stays_none() -> None:
    """Absent value stays None."""
    assert InputFields.coerce_decimal(None, None) is None


def test_value_is_quantized_to_step() -> None:
    """A value is rounded to the column scale defined by step."""
    assert InputFields.coerce_decimal(1.5, 0.01) == Decimal("1.50")
