"""Multiselect defaults must always be a subset of the options (L1).

Enum lists rendered from DB rows or PG array literals used to pass
``str(member)`` as default, which Streamlit rejects and breaks the form.
"""

from enum import Enum
from types import SimpleNamespace

from pydantic import BaseModel
from streamlit.testing.v1 import AppTest

from streamlit_pydantic_crud.pydantic_form.option_resolve import (
    enum_list_defaults,
    known_defaults,
)


class Dept(Enum):
    ENGINEERING = "engineering"
    HR = "hr"


class Form(BaseModel):
    kinds: list[Dept] | None = None


def test_enum_list_defaults_map_members_values_names() -> None:
    raw = [Dept.ENGINEERING, "hr", "HR", "Dept.HR", "unknown"]
    assert enum_list_defaults(raw, Dept) == ["engineering", "hr"]


def test_enum_list_defaults_from_pg_array_literal() -> None:
    assert enum_list_defaults("{ENGINEERING,hr}", Dept) == ["engineering", "hr"]


def test_enum_list_defaults_none() -> None:
    assert enum_list_defaults(None, Dept) == []


def test_known_defaults_drops_unknown() -> None:
    assert known_defaults(["a", "zz", Dept.HR], ["a", "hr"], "lbl") == [
        "a",
        "hr",
    ]


def _render_enum_list() -> None:
    import streamlit as st  # noqa: PLC0415 - AppTest serialises the function

    from streamlit_pydantic_crud.pydantic_form.generator import (  # noqa: PLC0415
        PydanticInputGenerator,
    )
    from tests.test_multiselect_defaults import Dept, Form  # noqa: PLC0415

    gen = PydanticInputGenerator(Form, key_prefix="f")
    data = gen.generate_form_data({"kinds": [Dept.ENGINEERING, "Dept.HR"]})
    st.write(f"DATA={data!r}")
    st.write(f"MODEL={Form(**data)!r}")


def test_enum_list_form_renders_existing_members() -> None:
    at = AppTest.from_function(_render_enum_list).run()
    assert not at.exception
    texts = [m.value for m in at.markdown]
    assert "DATA={'kinds': ['engineering', 'hr']}" in texts
    assert any("Dept.ENGINEERING" in t and t.startswith("MODEL=") for t in texts)


def test_multiselect_widget_drops_unknown_default() -> None:
    def app() -> None:
        from streamlit_pydantic_crud.pydantic_form.widgets import (  # noqa: PLC0415
            render_multiselect,
        )

        render_multiselect("x", {"options": ["a", "b"]}, ["a", "zz"], "k")

    at = AppTest.from_function(app).run()
    assert not at.exception
    assert at.multiselect(key="k").value == ["a"]


def test_many_to_many_drops_unknown_ids() -> None:
    def app() -> None:
        from streamlit_pydantic_crud.pydantic_form.generator import (  # noqa: PLC0415
            PydanticInputGenerator,
        )
        from streamlit_pydantic_crud.pydantic_form.widgets import (  # noqa: PLC0415
            render_many_to_many_multiselect,
        )
        from tests.test_multiselect_defaults import Form, opts  # noqa: PLC0415

        gen = PydanticInputGenerator(Form)
        gen.set_many_to_many_options("tags", opts(), "name")
        render_many_to_many_multiselect(
            "Tags", gen.many_to_many_data["tags"], [1, 99], "m"
        )

    at = AppTest.from_function(app).run()
    assert not at.exception
    assert at.multiselect(key="m").value == [1]


def opts() -> list[SimpleNamespace]:
    """Two many-to-many options with ids 1 and 2."""
    return [SimpleNamespace(id=1, name="a"), SimpleNamespace(id=2, name="b")]
