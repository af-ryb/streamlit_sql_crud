"""Deprecated pandas rendering of the SqlUi table (removed in 0.10.0).

The only pandas code path: ``df_style_formatter`` / ``style_fn`` render through a
``Styler`` here, and the deprecated ``SqlUi.df`` frame is built here.
"""

from collections.abc import Callable, Iterable
from typing import Any

import pandas as pd
from pandas.io.formats.style import Styler
from streamlit.elements.lib.column_types import ColumnConfig

"""Per-column formatter accepted by pandas ``Styler.format``."""
DfStyleFormatter = dict[Any, str | Callable[[object], str] | None]
"""Row function for ``Styler.apply(axis=1)``: one CSS string per cell."""
StyleFn = Callable[[pd.Series], list[str]]


def styled_table(
    records: list[dict[str, Any]],
    defaults: dict[str, ColumnConfig],
    formatter: DfStyleFormatter,
    style_fn: StyleFn | None,
) -> tuple[Styler, dict[str, ColumnConfig]]:
    """Return the display `records` styled, and the column configs to keep.

    A default column format would override the Styler format: it is dropped.
    Missing cells skip the formatter (``na_rep``): None is not NaN ("{:.2f}").
    """
    styler = records_frame(records).style.format(formatter, na_rep="None")
    if style_fn is not None:
        styler = styler.apply(style_fn, axis=1)
    return styler, without_columns(defaults, formatter)


def records_frame(records: list[dict[str, Any]]) -> pd.DataFrame:
    """Return the display `records` as a DataFrame, one column per key."""
    return pd.DataFrame(records)


def without_columns(
    configs: dict[str, ColumnConfig], names: Iterable[Any]
) -> dict[str, ColumnConfig]:
    """Return `configs` minus the columns in `names`."""
    dropped = set(names)
    return {name: config for name, config in configs.items() if name not in dropped}
