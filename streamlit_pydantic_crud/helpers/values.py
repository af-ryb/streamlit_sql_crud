"""Coerce values between the database and Streamlit widgets.

Leaf module: no Streamlit, no numpy.
"""

import json
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any


def enum_value(value: Any) -> Any:
    """Return ``value.value`` for an enum member, else `value` unchanged."""
    return value.value if isinstance(value, Enum) else value


def json_to_text(value: Any) -> str:
    """Render a JSON value as text: dicts and lists indented, others via str()."""
    if isinstance(value, (dict, list)):
        return json.dumps(value, indent=2)
    return str(value)


def to_list(value: Any) -> list:
    """Coerce a value into a list: None → [], a PG array literal is parsed.

    Lists and tuples are copied; any other value becomes a one-item list.
    """
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    if isinstance(value, str):
        return parse_pg_array(value)
    return [value]


def parse_pg_array(value: str) -> list[str]:
    """Parse a PostgreSQL array literal (``{a,"b,c"}``) into a list of strings.

    Braces are optional, so ``a, b`` also works. Quoted items keep commas,
    spaces and backslash-escaped characters; unquoted items are stripped and
    empty ones dropped. Nested arrays and NULL are not interpreted.
    """
    text = value.strip()
    if text.startswith("{") and text.endswith("}"):
        text = text[1:-1]

    items: list[str] = []
    current: list[str] = []
    quoted = in_quotes = escaped = False
    for char in text:
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == '"':
            in_quotes = not in_quotes
            quoted = True
        elif char == "," and not in_quotes:
            _append_item(items, current, quoted)
            current, quoted = [], False
        elif in_quotes or not char.isspace() or (current and not quoted):
            current.append(char)
    _append_item(items, current, quoted)
    return items


def _append_item(items: list[str], chars: list[str], quoted: bool) -> None:
    """Append a parsed array item; unquoted items are stripped, empty dropped."""
    item = "".join(chars)
    if not quoted:
        item = item.strip()
    if quoted or item:
        items.append(item)


def coerce_decimal(value: float | int | None, step: float | None) -> Decimal | None:
    """Convert a numeric input to Decimal, preserving 0 and quantizing.

    Returns None only when value is None, so a literal 0 is kept.
    """
    if value is None:
        return None
    value_dec = Decimal(str(value))
    if step:
        value_dec = value_dec.quantize(Decimal(str(step)))
    return value_dec


def keep_unchanged_datetime(new: Any, original: Any) -> Any:
    """Return `original` when the widget value `new` is it at minute precision.

    `st.datetime_input` drops seconds, microseconds and tzinfo, so an untouched
    widget must not overwrite the stored value with that truncated copy.
    """
    if not isinstance(new, datetime) or not isinstance(original, datetime):
        return new
    truncated = original.replace(second=0, microsecond=0, tzinfo=None)
    return original if new == truncated else new


def to_python_scalar(value: Any) -> Any:
    """Return a numpy scalar as its Python equivalent, other values unchanged.

    Duck-typed (a 0-d value from the ``numpy`` module with ``item()``), so the
    package needs no numpy import; e.g. a custom TypeDecorator may load one.
    """
    if type(value).__module__ == "numpy" and getattr(value, "ndim", None) == 0:
        return value.item()
    return value
