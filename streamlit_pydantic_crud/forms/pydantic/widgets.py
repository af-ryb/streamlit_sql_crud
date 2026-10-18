"""Streamlit widget renderers for Pydantic form fields.

Each renderer takes a label, its configuration, the current value and the
widget key, and returns the widget's value. Generator state (foreign-key and
many-to-many options, operation type) is passed in explicitly.
"""

from typing import Any

import streamlit as st
from loguru import logger

from streamlit_pydantic_crud.config_types import (
    ForeignKeyData,
    ManyToManyData,
    OperationType,
)
from streamlit_pydantic_crud.forms.pydantic.option_resolve import (
    enum_list_defaults,
    is_float_number_kwargs,
    known_defaults,
    resolve_multiselect_default,
    resolve_select_index,
)
from streamlit_pydantic_crud.helpers.typing import (
    enum_member,
    list_item_type,
    unwrap_optional,
)
from streamlit_pydantic_crud.helpers.values import (
    json_to_text,
    keep_unchanged_datetime,
    to_list,
)


def render_id_field(
    label: str, existing_value: Any, key: str, operation_type: OperationType
) -> Any:
    """Render the primary key read-only when editing; hide it (None) on create."""
    is_update = operation_type == "update" or (
        existing_value is not None and existing_value != ""
    )

    if is_update:
        seed_widget_state(key, "" if existing_value is None else str(existing_value))
        return st.text_input(
            label,
            value="" if existing_value is None else str(existing_value),
            disabled=True,
            key=key,
            help="ID field (read-only)",
        )
    """Create operation: no ID field, so it stays out of the form data."""
    return None


def render_foreign_key_selectbox(
    label: str, fk_data: ForeignKeyData, existing_value: Any, key: str
) -> Any:
    """Render a selectbox over preloaded foreign-key options.

    `fk_data` holds `options` and an optional `display_map` (value → label).
    """
    options = fk_data["options"]
    display_map = fk_data["display_map"]

    current_index = None
    if existing_value in options:
        current_index = options.index(existing_value)
    seed_widget_state(key, None if current_index is None else options[current_index])

    if display_map:
        return st.selectbox(
            label,
            options=options,
            index=current_index,
            format_func=lambda x: display_map.get(x, str(x)),
            key=key,
            help=f"Select from {len(options)} available options",
        )
    return st.selectbox(
        label,
        options=options,
        index=current_index,
        key=key,
        help=f"Select from {len(options)} available options",
    )


def render_foreign_key_fallback(label: str, existing_value: Any, key: str) -> Any:
    """Render a text input for a relation field whose options were not loaded."""
    seed_widget_state(key, str(existing_value) if existing_value is not None else "")
    return st.text_input(
        label,
        value=str(existing_value) if existing_value is not None else "",
        key=key,
        help="Foreign key options not loaded",
    )


def render_many_to_many_multiselect(
    label: str, m2m_data: ManyToManyData, existing_value: Any, key: str
) -> Any:
    """Render a multiselect of related-row primary keys from preloaded options.

    The current value may be PKs, display names (copy mode) or related objects.
    """
    options = m2m_data["options"]
    display_field = m2m_data["display_field"]
    pk = m2m_data["pk_name"]

    id_to_display = {
        getattr(option, pk): getattr(option, display_field) for option in options
    }

    current_selection_ids = []
    if existing_value is not None:
        if isinstance(existing_value, list) and existing_value:
            first_item = existing_value[0]
            if isinstance(first_item, (int, str)):
                if first_item in id_to_display:
                    current_selection_ids = existing_value
                else:
                    """Display names (copy mode): map them back to PKs."""
                    name_to_id = {v: k for k, v in id_to_display.items()}
                    current_selection_ids = [
                        name_to_id.get(name)
                        for name in existing_value
                        if name in name_to_id
                    ]
            elif hasattr(first_item, pk):
                current_selection_ids = [getattr(obj, pk) for obj in existing_value]
        elif hasattr(existing_value, "__iter__") and not isinstance(
            existing_value, str
        ):
            """Relationship collection: extract the PKs."""
            current_selection_ids = [
                getattr(obj, pk) for obj in existing_value if hasattr(obj, pk)
            ]

    option_ids = list(id_to_display.keys())
    default = known_defaults(current_selection_ids, option_ids, label)
    seed_widget_state(key, default)
    return st.multiselect(
        label,
        options=option_ids,
        default=default,
        format_func=lambda x: id_to_display.get(x, str(x)),
        key=key,
        help=f"Select from {len(options)} available options",
    )


def render_enum_select(
    label: str, annotation: Any, existing_value: Any, key: str
) -> Any:
    """Render selectbox for single enum"""
    enum_type, _ = unwrap_optional(annotation)

    enum_values = [member.value for member in enum_type.__members__.values()]
    current_index = None
    member = enum_member(existing_value, enum_type)
    if member is not None:
        current_index = enum_values.index(member.value)
    seed_widget_state(
        key, None if current_index is None else enum_values[current_index]
    )

    return st.selectbox(label, enum_values, index=current_index, key=key)


def render_enum_multiselect(
    label: str, annotation: Any, existing_value: Any, key: str
) -> Any:
    """Render multiselect for list of enums"""
    enum_type = list_item_type(annotation)

    if not enum_type:
        return st.multiselect(label, [], key=key, accept_new_options=True)

    enum_values = [member.value for member in enum_type.__members__.values()]

    current_values = enum_list_defaults(existing_value, enum_type)
    seed_widget_state(key, current_values)

    return st.multiselect(
        label,
        enum_values,
        default=current_values,
        key=key,
        help=f"Available options: {', '.join(enum_values)}",
    )


def render_list_multiselect(label: str, existing_value: Any, key: str) -> Any:
    """Render multiselect for regular lists, accepting new options.

    Items are stringified; a scalar other than str gives no values.
    """
    current_values = (
        [str(item) for item in to_list(existing_value)]
        if isinstance(existing_value, (list, tuple, str))
        else []
    )
    seed_widget_state(key, current_values)

    return st.multiselect(
        label,
        current_values,
        default=current_values,
        accept_new_options=True,
        key=key,
        help="Select existing options or type new ones",
    )


def render_text_input(
    label: str, widget_kwargs: dict[str, Any], existing_value: Any, key: str
) -> Any:
    """Render text input widget"""
    default_value = str(existing_value) if existing_value is not None else ""
    seed_widget_state(key, default_value)
    return st.text_input(label, value=default_value, key=key, **widget_kwargs)


def render_text_area(
    label: str, widget_kwargs: dict[str, Any], existing_value: Any, key: str
) -> Any:
    """Render text area widget"""
    default_value = str(existing_value) if existing_value is not None else ""
    seed_widget_state(key, default_value)
    return st.text_area(label, value=default_value, key=key, **widget_kwargs)


def render_json_text_area(
    label: str, widget_kwargs: dict[str, Any], existing_value: Any, key: str
) -> Any:
    """Render text area widget for JSON input"""
    json_value = ""
    if existing_value is not None:
        try:
            json_value = json_to_text(existing_value)
        except Exception as e:
            logger.warning(f"Got exception while render JSON, {e}")
            json_value = str(existing_value)
    seed_widget_state(key, json_value)
    return st.text_area(label, value=json_value, key=key, **widget_kwargs)


def render_checkbox(
    label: str, widget_kwargs: dict[str, Any], existing_value: Any, key: str
) -> Any:
    """Render checkbox widget"""
    default_val = bool(existing_value) if existing_value is not None else False
    seed_widget_state(key, default_val)
    return st.checkbox(label, value=default_val, key=key, **widget_kwargs)


def render_date_input(
    label: str, widget_kwargs: dict[str, Any], existing_value: Any, key: str
) -> Any:
    """Render date input widget"""
    seed_widget_state(key, existing_value)
    return st.date_input(label, value=existing_value, key=key, **widget_kwargs)


def render_datetime_input(
    label: str, widget_kwargs: dict[str, Any], existing_value: Any, key: str
) -> Any:
    """Render datetime input widget.

    An untouched widget returns `existing_value` with its full precision.
    """
    seed_widget_state(key, existing_value)
    value = st.datetime_input(
        label,
        value=existing_value,
        key=key,
        **widget_kwargs,
    )
    return keep_unchanged_datetime(value, existing_value)


def render_selectbox(
    label: str,
    widget_kwargs: dict[str, Any],
    existing_value: Any,
    key: str,
    field_default: Any = None,
) -> Any:
    """Render selectbox widget with default resolution."""
    kwargs = dict(widget_kwargs)
    options = kwargs.pop("options", [])
    explicit_index = kwargs.pop("index", None)
    index = resolve_select_index(existing_value, explicit_index, field_default, options)
    seed_widget_state(key, None if index is None else options[index])
    return st.selectbox(label, options=options, index=index, key=key, **kwargs)


def render_radio(
    label: str,
    widget_kwargs: dict[str, Any],
    existing_value: Any,
    key: str,
    field_default: Any = None,
) -> Any:
    """Render radio widget with default resolution."""
    kwargs = dict(widget_kwargs)
    options = kwargs.pop("options", [])
    explicit_index = kwargs.pop("index", None)
    index = resolve_select_index(existing_value, explicit_index, field_default, options)
    if index is None:
        index = 0
    seed_widget_state(key, options[index] if options else None)
    return st.radio(label, options=options, index=index, key=key, **kwargs)


def render_multiselect(
    label: str,
    widget_kwargs: dict[str, Any],
    existing_value: Any,
    key: str,
    field_default: Any = None,
) -> Any:
    """Render multiselect widget with default resolution."""
    kwargs = dict(widget_kwargs)
    options = kwargs.pop("options", [])
    explicit_default = kwargs.pop("default", None)
    default_vals = resolve_multiselect_default(
        existing_value, explicit_default, field_default
    )
    if not kwargs.get("accept_new_options"):
        default_vals = known_defaults(default_vals, options, label)
    seed_widget_state(key, default_vals)
    return st.multiselect(
        label, options=options, default=default_vals, key=key, **kwargs
    )


def render_slider(
    label: str, widget_kwargs: dict[str, Any], existing_value: Any, key: str
) -> Any:
    """Render slider widget with proper type handling"""
    min_val = widget_kwargs.get("min_value", 0)
    max_val = widget_kwargs.get("max_value", 100)
    step = widget_kwargs.get("step", 1)

    use_float = is_float_number_kwargs(widget_kwargs)

    """Convert all values to one type; ints go through float first to accept
    strings like "1.0"."""
    try:
        if use_float:
            min_val = float(min_val)
            max_val = float(max_val)
            step = float(step)
            if existing_value is not None:
                default_val = float(existing_value)
            else:
                default_val = min_val
        else:
            min_val = int(float(min_val))
            max_val = int(float(max_val))
            step = int(float(step))
            if existing_value is not None:
                default_val = int(float(existing_value))
            else:
                default_val = min_val
    except (ValueError, TypeError):
        min_val = 0 if not use_float else 0.0
        max_val = 100 if not use_float else 100.0
        step = 1 if not use_float else 1.0
        default_val = min_val

    default_val = max(min_val, min(max_val, default_val))
    seed_widget_state(key, default_val)

    return st.slider(
        label,
        min_value=min_val,
        max_value=max_val,
        value=default_val,
        step=step,
        key=key,
        **{
            k: v
            for k, v in widget_kwargs.items()
            if k not in ["min_value", "max_value", "step", "value"]
        },
    )


def render_number_input(
    label: str,
    widget_kwargs: dict[str, Any],
    existing_value: Any,
    key: str,
    use_int: bool = False,
    optional: bool = False,
) -> Any:
    """Render a number input widget with proper type handling.

    An optional field without a value renders empty and returns None.
    """
    min_val = widget_kwargs.get("min_value")
    max_val = widget_kwargs.get("max_value")
    step = widget_kwargs.get("step")

    if not use_int:
        use_int = not is_float_number_kwargs(widget_kwargs)

    try:
        if use_int:
            if min_val is not None:
                min_val = int(float(min_val))
            if max_val is not None:
                max_val = int(float(max_val))
            if step is not None:
                step = int(float(step))
            else:
                step = 1
            default_val = (
                int(float(existing_value)) if existing_value is not None else 0
            )
        else:
            if min_val is not None:
                min_val = float(min_val)
            if max_val is not None:
                max_val = float(max_val)
            if step is not None:
                step = float(step)
            else:
                step = 0.1
            default_val = float(existing_value) if existing_value is not None else 0.0
    except (ValueError, TypeError):
        step = 1 if use_int else 0.1
        default_val = 0 if use_int else 0.0

    if optional and existing_value is None:
        default_val = None
    elif min_val is not None and max_val is not None:
        default_val = max(min_val, min(max_val, default_val))
    elif min_val is not None:
        default_val = max(min_val, default_val)
    elif max_val is not None:
        default_val = min(max_val, default_val)

    """Pass the bounds with consistent types; step is never None here."""
    updated_kwargs = widget_kwargs.copy()
    if min_val is not None:
        updated_kwargs["min_value"] = min_val
    if max_val is not None:
        updated_kwargs["max_value"] = max_val
    updated_kwargs["step"] = step

    return nullable_number_input(
        label, default_val, key, nullable=optional, **updated_kwargs
    )


def nullable_number_input(
    label: str, value: Any, key: str, *, nullable: bool, **kwargs: Any
) -> Any:
    """Render `st.number_input`; a nullable one can be emptied to None.

    A widget created with a value refills a cleared field on blur, so a
    nullable one starts with `value=None`; its seeded state holds the value.
    """
    seed_widget_state(key, value)
    if nullable:
        value = None
    return st.number_input(label, value=value, key=key, **kwargs)


def seed_widget_state(key: str, value: Any) -> None:
    """Set the state of widget `key` to `value` unless it already has one.

    The browser keeps a keyed widget's last value over a new `value=` argument;
    a value set through session state is pushed to it (`set_value`) instead.
    """
    if key not in st.session_state:
        st.session_state[key] = value
