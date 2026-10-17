"""PostgreSQL array literal parsing used for list/multiselect defaults."""

import pytest

from streamlit_pydantic_crud.values import parse_pg_array, to_list

CASES = [
    ("{a,b}", ["a", "b"]),
    ('{"a,b",c,d}', ["a,b", "c", "d"]),
    ("{}", []),
    ("", []),
    ("a, b", ["a", "b"]),
    ('{"x"}', ["x"]),
    ('{"say \\"hi\\"",y}', ['say "hi"', "y"]),
    ('{ a , "b c" }', ["a", "b c"]),
    ("{NULL,a}", ["NULL", "a"]),
]


@pytest.mark.parametrize(("value", "expected"), CASES)
def test_parse_pg_array(value: str, expected: list[str]) -> None:
    assert parse_pg_array(value) == expected


def test_generator_uses_pg_array_parser() -> None:
    assert to_list('{"a,b",c,d}') == ["a,b", "c", "d"]
