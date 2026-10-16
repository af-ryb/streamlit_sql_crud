"""No-schema InputFields: nullable numbers can be cleared, labels, arrays."""

from decimal import Decimal
from types import SimpleNamespace

import pytest
from streamlit.testing.v1 import AppTest

from streamlit_pydantic_crud import input_fields
from streamlit_pydantic_crud.input_fields import InputFields
from streamlit_pydantic_crud.utils import parse_pg_array
from tests.test_input_fields_enum import RunMode

NULLABLE = ("qty", "score", "price")


def test_nullable_numbers_render_empty_and_keep_value(run_mode: RunMode) -> None:
    """A nullable number widget has no default, yet returns the row value."""
    at = run_mode("fields_row")

    assert not at.exception
    texts = [m.value for m in at.markdown]
    assert "VAL_r_qty=1" in texts
    assert "VAL_r_score=0.5" in texts
    assert f"VAL_r_price={Decimal('1.00')!r}" in texts
    for name in NULLABLE:
        assert not at.number_input(key=f"r_{name}").proto.HasField("default"), name


def test_nullable_numbers_can_be_cleared(run_mode: RunMode) -> None:
    """Clearing a pre-filled nullable number yields None (NULL)."""
    at = run_mode("fields_row")
    for name in NULLABLE:
        at.number_input(key=f"r_{name}").set_value(None)
    at.run()

    texts = [m.value for m in at.markdown]
    for name in NULLABLE:
        assert f"VAL_r_{name}=None" in texts


def test_required_number_keeps_default(run_mode: RunMode) -> None:
    """A non-nullable number still starts with the row value."""
    at = run_mode("fields_row")

    assert at.number_input(key="r_count").proto.HasField("default")


def test_datalist_label_is_pretty(monkeypatch: pytest.MonkeyPatch) -> None:
    """The free-text datalist is labelled like the other inputs."""
    labels: list[str] = []

    def fake_datalist(label: str, *args: object, **kwargs: object) -> str:
        labels.append(label)
        return ""

    monkeypatch.setattr(input_fields, "stDatalist", fake_datalist)
    existing = SimpleNamespace(text={"first_name": set()})
    fields = InputFields(object, "p", {}, existing)  # ty: ignore[invalid-argument-type]

    assert fields.input_str("first_name") is None
    assert labels == ["First Name"]


def _array_app() -> None:
    from types import SimpleNamespace  # noqa: PLC0415 - AppTest serialises this

    from sqlalchemy import ARRAY, String  # noqa: PLC0415

    from streamlit_pydantic_crud.input_fields import InputFields  # noqa: PLC0415

    existing = SimpleNamespace(text={})
    fields = InputFields(object, "a", {}, existing)  # ty: ignore[invalid-argument-type]
    fields.input_array("tags", ARRAY(String), '{a,"b,c"}')


def test_array_string_value_uses_shared_parser() -> None:
    """A PostgreSQL array literal is parsed by utils.parse_pg_array."""
    at = AppTest.from_function(_array_app).run()

    assert not at.exception
    assert at.multiselect(key="a_tags").value == parse_pg_array('{a,"b,c"}')
    assert at.multiselect(key="a_tags").value == ["a", "b,c"]
