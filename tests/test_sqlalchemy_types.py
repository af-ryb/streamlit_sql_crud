"""Type detection must not depend on the SQLAlchemy version (2.0 vs 2.1).

2.1 returns `object` from an unknown `python_type` instead of raising
NotImplementedError, and `Float` no longer subclasses `Numeric`.
"""

from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast

import numpy as np
import pytest
from sqlalchemy import Column, Float, Numeric, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator
from sqlmodel.sql.sqltypes import AutoString

from streamlit_pydantic_crud.forms.sa_fields import InputFields
from streamlit_pydantic_crud.helpers.sa_model import safe_python_type
from streamlit_pydantic_crud.helpers.values import convert_numpy_to_python


class Base(DeclarativeBase):
    """Local declarative base, kept out of the shared test metadata."""


class Code(Base):
    """Table whose primary key is SQLModel's AutoString TypeDecorator."""

    __tablename__ = "code"

    code: Mapped[str] = mapped_column(AutoString, primary_key=True)


class UpperString(TypeDecorator):
    """TypeDecorator that declares its own `python_type`."""

    impl = String
    cache_ok = True

    @property
    def python_type(self) -> type:
        return bytes


def test_safe_python_type_keeps_decorator_own_type() -> None:
    """A TypeDecorator's own `python_type` wins over its impl's."""
    assert safe_python_type(Column("c", UpperString())) is bytes


def test_safe_python_type_unwraps_autostring() -> None:
    """SQLModel's AutoString resolves to str."""
    assert safe_python_type(Column("c", AutoString())) is str


def test_convert_numpy_uses_decorated_pk_type() -> None:
    """A numpy value for an AutoString PK becomes a plain str."""
    value = convert_numpy_to_python(np.str_("a1"), Code)

    assert value == "a1"
    assert type(value) is str


@pytest.fixture
def fields() -> InputFields:
    """InputFields with no model data; only `get_input_value` routing is used."""
    existing = SimpleNamespace(text={}, fk={})
    return InputFields(cast(Any, object), "t", {}, cast(Any, existing))


@pytest.mark.parametrize(
    "col_type", [Numeric(10, 2), Float(asdecimal=True)], ids=["numeric", "float"]
)
def test_decimal_columns_get_numeric_input(
    fields: InputFields, monkeypatch: pytest.MonkeyPatch, col_type: Any
) -> None:
    """Decimal-returning Numeric and Float columns use the Decimal input."""
    calls: list[str] = []

    def fake_numeric(col_name: str, *_args: object) -> Decimal:
        calls.append(col_name)
        return Decimal(1)

    monkeypatch.setattr(fields, "input_numeric", fake_numeric)
    value = fields.get_input_value(Column("amount", col_type), None)

    assert calls == ["amount"]
    assert value == Decimal(1)


def test_float_column_gets_float_input(
    fields: InputFields, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A plain Float column uses the float number input with step 0.1."""
    steps: list[object] = []

    def fake_number(_name: str, _value: object, step: object, *_args: object) -> float:
        steps.append(step)
        return 1.0

    monkeypatch.setattr(fields, "input_number", fake_number)
    fields.get_input_value(Column("ratio", Float()), None)

    assert steps == [0.1]
