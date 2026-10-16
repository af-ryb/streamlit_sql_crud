"""Two forms for the same model on one page must not collide.

Regression: number/date/checkbox/enum inputs had no `key`, `input_array` used
an unprefixed key and the update form key lacked the key prefix.
"""

from tests.test_input_fields_enum import RunMode


def test_two_forms_same_model_render(run_mode: RunMode) -> None:
    """Two InputFields and two UpdateRow forms of one model render cleanly."""
    at = run_mode("two")

    assert not at.exception


def test_every_widget_key_is_prefixed(run_mode: RunMode) -> None:
    """Each input widget carries a `<prefix>_<column>` key."""
    at = run_mode("fields")

    keys = {
        w.key
        for w in [
            *at.number_input,
            *at.checkbox,
            *at.selectbox,
            *at.multiselect,
            *at.date_input,
        ]
    }
    expected = {"f_count", "f_ratio", "f_amount", "f_done", "f_status", "f_tags"}
    expected |= {"f_due"}
    assert expected <= keys


def test_fk_label_is_pretty(run_mode: RunMode) -> None:
    """A foreign key selectbox is labelled with the column's pretty name."""
    at = run_mode("fields")

    assert at.selectbox(key="f_owner_id").label == "Owner Id"
