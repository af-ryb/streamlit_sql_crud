"""Optional numeric fields without a value stay None, not 0 (M1)."""

from decimal import Decimal

from pydantic import BaseModel, Field
from streamlit.testing.v1 import AppTest


class Nums(BaseModel):
    count: int | None = None
    ratio: float | None = None
    amount: Decimal | None = None
    limit: int | None = Field(
        None, json_schema_extra={"widget": "number_input", "kw": {"min_value": 1}}
    )
    req: int
    req_ratio: float


def _app() -> None:
    import streamlit as st  # noqa: PLC0415 - AppTest serialises the function

    from streamlit_pydantic_crud.pydantic_form.generator import (  # noqa: PLC0415
        PydanticInputGenerator,
    )
    from tests.test_optional_number import Nums  # noqa: PLC0415

    for op in ("create", "update"):
        gen = PydanticInputGenerator(Nums, key_prefix=op, operation_type=op)
        st.write(f"{op.upper()}={gen.generate_form_data()!r}")
    gen = PydanticInputGenerator(Nums, key_prefix="e", operation_type="update")
    st.write(f"EXISTING={gen.generate_form_data({'count': 3, 'limit': 5})!r}")


def _lines(at: AppTest) -> dict[str, str]:
    return dict(m.value.split("=", 1) for m in at.markdown)


def test_optional_numbers_empty_stay_none() -> None:
    at = AppTest.from_function(_app).run()
    assert not at.exception
    lines = _lines(at)
    assert lines["CREATE"] == "{'req': 0, 'req_ratio': 0.0}"
    assert lines["UPDATE"] == (
        "{'count': None, 'ratio': None, 'amount': None, 'limit': None,"
        " 'req': 0, 'req_ratio': 0.0}"
    )
    assert "'count': 3" in lines["EXISTING"]
    assert "'limit': 5" in lines["EXISTING"]
    assert "'ratio': None" in lines["EXISTING"]


def _edit_app() -> None:
    from decimal import Decimal  # noqa: PLC0415 - AppTest serialises the function

    import streamlit as st  # noqa: PLC0415

    from streamlit_pydantic_crud.pydantic_form.generator import (  # noqa: PLC0415
        PydanticInputGenerator,
    )
    from tests.test_optional_number import Nums  # noqa: PLC0415

    gen = PydanticInputGenerator(Nums, key_prefix="e", operation_type="update")
    existing = {"count": 3, "ratio": 0.5, "amount": Decimal("2.50")}
    st.write(f"EXISTING={gen.generate_form_data(existing)!r}")


def test_optional_numbers_can_be_cleared_on_edit() -> None:
    """A widget started with a value reverted on blur, so NULL was unsavable."""
    at = AppTest.from_function(_edit_app).run()
    assert not at.exception
    for name in ("count", "ratio", "amount"):
        widget = at.number_input(key=f"e_{name}")
        assert not widget.proto.HasField("default"), name
    assert "'count': 3" in _lines(at)["EXISTING"]
    assert "'ratio': 0.5" in _lines(at)["EXISTING"]

    for name in ("count", "ratio", "amount"):
        at.number_input(key=f"e_{name}").set_value(None)
    at.run()
    lines = _lines(at)
    assert "'count': None" in lines["EXISTING"]
    assert "'ratio': None" in lines["EXISTING"]
    assert "'amount': None" in lines["EXISTING"]
