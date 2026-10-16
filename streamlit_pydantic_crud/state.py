"""Session state of one `SqlUi` instance, keyed by its widget key.

Each instance keeps its own filters, notification and dialog flag so several
`SqlUi` on one page do not disturb each other. The cache-busting counter
`stsql_updated` stays global on purpose (see `UPDATED_KEY`).
"""

from dataclasses import dataclass, field
from typing import Any

from streamlit import session_state as ss

"""Global on purpose: a write through one instance must invalidate caches of
every instance, which may read the same table or reference it by FK."""
UPDATED_KEY = "stsql_updated"


@dataclass
class UiState:
    """Per-instance UI state of a `SqlUi` and the dialogs it opens.

    Attributes:
        update_ok: Outcome of the last create/update/delete, None when shown.
        update_message: Message of the last create/update/delete.
        opened: True while a dialog of this instance is open.
        filters: Filters applied on the previous run, to detect changes.
    """

    update_ok: bool | None = None
    update_message: str | None = None
    opened: bool = False
    filters: dict[str, Any] = field(default_factory=dict)


def get_ui_state(key: str) -> UiState:
    """Return the state of the instance with widget key `key`, creating it."""
    state_key = state_key_for(key)
    if state_key not in ss:
        ss[state_key] = UiState()
    return ss[state_key]


def state_key_for(key: str) -> str:
    """Return the session-state key holding the state of instance `key`."""
    return f"stsql_state_{key}"
