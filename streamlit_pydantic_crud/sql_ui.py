import warnings
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Literal

import pandas as pd
import streamlit as st
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import CTE, Select
from sqlalchemy.orm import DeclarativeBase
from streamlit.connections import SQLConnection
from streamlit.delta_generator import DeltaGenerator
from streamlit.elements.arrow import DataframeState

from streamlit_pydantic_crud.config_types import ForeignKeyOptions, ManyToManyFields
from streamlit_pydantic_crud.dialogs.create import CreateRow
from streamlit_pydantic_crud.dialogs.delete import DeleteRows
from streamlit_pydantic_crud.dialogs.edit import UpdateRow
from streamlit_pydantic_crud.dialogs.persist import m2m_load_options
from streamlit_pydantic_crud.forms.schema_check import validate_schema_compatibility
from streamlit_pydantic_crud.helpers import logs
from streamlit_pydantic_crud.helpers.display import (
    DfStyleFormatter,
    convert_arrow,
    get_pretty_name,
    numeric_formatters,
)
from streamlit_pydantic_crud.helpers.sa_model import (
    column_label,
    is_json_type,
    pk_attr,
    pk_name,
    tablename,
)
from streamlit_pydantic_crud.helpers.typing import model_fields
from streamlit_pydantic_crud.helpers.values import (
    convert_numpy_list_to_python,
    convert_numpy_to_python,
    enum_value,
    json_to_text,
    row_to_python,
)
from streamlit_pydantic_crud.state import (
    OPTIONS_NOTICE_KEYS,
    UiState,
    data_version,
    get_ui_state,
    session_writes,
)
from streamlit_pydantic_crud.table import filter_ui, pagination, query


@dataclass(frozen=True)
class Containers:
    """Streamlit containers laid out once per render by `SqlUi.set_structure`."""

    header: DeltaGenerator
    data: DeltaGenerator
    pag: DeltaGenerator
    expander: DeltaGenerator
    filter: DeltaGenerator
    btns: DeltaGenerator


class SqlUi:
    """Show A CRUD interface in a Streamlit Page

    See in __init__ method detailed descriptions of arguments and properties

    It also offers the following properties:


    """

    def __init__(
        self,
        conn: SQLConnection,
        read_instance: Select | CTE | type[DeclarativeBase] | None = None,
        edit_create_model: type[DeclarativeBase] | None = None,
        model: type[DeclarativeBase] | None = None,
        available_filter: list[str] | None = None,
        edit_create_default_values: dict | None = None,
        df_style_formatter: DfStyleFormatter | None = None,
        read_use_container_width: bool = False,
        key: str | None = None,
        base_key: str | None = None,
        style_fn: Callable[[pd.Series], list[str]] | None = None,
        update_show_many: bool = False,
        disable_log: bool = False,
        create_schema: type[BaseModel] | None = None,
        update_schema: type[BaseModel] | None = None,
        read_schema: type[BaseModel] | None = None,
        foreign_key_options: ForeignKeyOptions | None = None,
        many_to_many_fields: ManyToManyFields | None = None,
        show_delete_btn: bool = True,
        show_create_btn: bool = True,
        items_per_page_default: int = 0,
    ) -> None:
        """The CRUD interface will be displayes just by initializing the class

        Arguments:
            conn (SQLConnection): A sqlalchemy connection created with st.connection("sql", url="<sqlalchemy url>")
            model (type[DeclarativeBase]): SQLAlchemy model class used for both read and write operations. Recommended over separate read_instance and edit_create_model parameters.
            edit_create_default_values (dict, optional): A dict with column name as keys and values to be default. When the user clicks to create a row, those columns will not show on the form and its value will be added to the model object
            available_filter (list[str], optional): Define which columns the user will be able to filter in the top expander. Defaults to all. Active filters also narrow foreign-key options in the create/copy dialog (applied to related models having a column of the same name); the edit dialog always lists all options
            df_style_formatter (dict): a dictionary where each key is a column name and the associated value (format string or callable) is the formatter arg of df.style.format method. See pandas docs for details.
            read_use_container_width (bool, optional): when True, sets width='stretch' in st.dataframe. Default to False
            key (str, optional): A unique key prefix for all widgets in this SqlUi instance. This follows Streamlit's standard convention and is needed when creating multiple instances on the same page. Defaults to None
            style_fn (Callable[[pd.Series], list[str]], optional): A function that goes into the *func* argument of *df.style.apply*. The apply method also receives *axis=1*, so it works on rows. It can be used to apply conditional css formatting on each column of the row. See Styler.apply info on pandas docs. Defaults to None
            update_show_many (bool, optional): Show a st.expander of one-to-many relations in edit or create dialog
            disable_log (bool): Every change in the database (READ, UPDATE, DELETE) is logged to stderr by default. If this is *true*, nothing is logged. To customize the logging format and where it logs to, use loguru as add a new sink to logger. See loguru docs for more information. Dafaults to False
            create_schema (Optional[Type[BaseModel]]): Pydantic schema for create operations. If provided, uses Pydantic validation for creation forms. Defaults to None
            update_schema (Optional[Type[BaseModel]]): Pydantic schema for update operations. If provided, uses Pydantic validation for update forms. Defaults to None
            read_schema (Optional[Type[BaseModel]]): Pydantic schema for read operations. If provided, uses Pydantic model_validate for data processing and avoids pandas read_sql issues with JSON columns. Defaults to None
            foreign_key_options (dict, optional): Custom foreign key selectbox configuration. Dict with field names as keys and config dicts as values. Each config should have 'query' (SQLAlchemy select statement), 'display_field' (column name for display), and 'value_field' (column name for value). Defaults to None
            many_to_many_fields (dict, optional): Custom many-to-many multiselect configuration. Dict with relationship names as keys and config dicts as values. Each config should have 'relationship' (SQLAlchemy relationship name), 'display_field' (column name for display), and 'filter' (optional lambda for filtering options). Defaults to None
            show_delete_btn (bool, optional): Show delete button. Defaults to True
            show_create_btn (bool, optional): Show create button. Defaults to True
            items_per_page_default (int, optional): Index (0-5) for default items per page selection. Options are: 0=50, 1=100, 2=200, 3=500, 4=1000, 5=Show All. Defaults to 0 (50 items per page)

        Attributes:
            df (pd.Dataframe): The Dataframe displayed in the screen
            selected_rows (list[int]): The position of selected rows. This is not the row id.
            qtty_rows (int): The quantity of all rows after filtering


        Examples:
            ```python
            def style_fn(row):
                if row.amount > 0:
                    bg = "background-color: rgba(0, 255, 0, 0.1)"
                else:
                    bg = "background-color: rgba(255, 0, 0, 0.2)"

                result = [bg] * len(row)
                return result


            db_url = "sqlite:///data.db"
            conn = st.connection("sql", db_url)

            stmt = (
                select(
                    db.Invoice.id,
                    db.Invoice.date,
                    db.Invoice.amount,
                    db.Client.name,
                )
                .join(db.Client)
                .where(db.Invoice.amount > 1000)
                .order_by(db.Invoice.date)
            )

            # Recommended approach with new 'model' parameter
            sql_ui = SqlUi(
                conn=conn,
                model=db.Invoice,  # Simplified: uses same model for read and write
                available_filter=["name"],
                df_style_formatter={"amount": "{:,.2f}"},
                read_use_container_width=True,
                key="my_sql_ui",
                style_fn=style_fn,
                update_show_many=True,
                disable_log=False,
                foreign_key_options={
                    'client_id': {
                        'query': select(db.Client),
                        'display_field': 'name',
                        'value_field': 'id'
                    }
                },
            )
            ```

        """
        # Handle model parameter consolidation
        if model is not None:
            if read_instance is not None or edit_create_model is not None:
                warnings.warn(
                    "When 'model' parameter is provided, 'read_instance' and 'edit_create_model' are ignored. "
                    "Use either 'model' (recommended) or the legacy 'read_instance'+'edit_create_model' combination.",
                    DeprecationWarning,
                    stacklevel=2,
                )
            # Use model for both read and write operations
            self.read_instance = model
            self.edit_create_model = model
        else:
            # Legacy mode - require both parameters
            if read_instance is None or edit_create_model is None:
                msg = (
                    "Either provide 'model' parameter (recommended) or both 'read_instance' and 'edit_create_model' parameters. "
                    "The 'model' parameter simplifies the API when using the same model for read and write operations."
                )
                raise ValueError(msg)
            self.read_instance = read_instance
            self.edit_create_model = edit_create_model

        self.conn = conn
        self.available_filter = available_filter or []
        self.edit_create_default_values = edit_create_default_values or {}
        self.df_style_formatter: DfStyleFormatter = df_style_formatter or {}
        self.read_use_container_width = read_use_container_width
        self.show_delete_btn = show_delete_btn
        self.show_create_btn = show_create_btn

        # Validate items_per_page_default
        if not isinstance(items_per_page_default, int):
            msg = f"items_per_page_default must be an integer index (0-{len(pagination.OPTS_ITEMS_PAGE) - 1}), got {type(items_per_page_default)}"
            raise ValueError(msg)
        if items_per_page_default < 0 or items_per_page_default >= len(
            pagination.OPTS_ITEMS_PAGE
        ):
            msg = f"items_per_page_default must be between 0 and {len(pagination.OPTS_ITEMS_PAGE) - 1}, got {items_per_page_default}"
            raise ValueError(msg)
        self.items_per_page_default = items_per_page_default

        if key is not None and base_key is not None:
            warnings.warn(
                "Both 'key' and 'base_key' specified. 'base_key' is deprecated, using 'key' instead. "
                "Remove 'base_key' parameter in future versions.",
                DeprecationWarning,
                stacklevel=2,
            )
            self.key = key
        elif base_key is not None:
            warnings.warn(
                "'base_key' parameter is deprecated and will be removed in v1.0.0. "
                "Use 'key' parameter instead for Streamlit compatibility.",
                DeprecationWarning,
                stacklevel=2,
            )
            self.key = base_key
        else:
            self.key = key or ""
        self.style_fn = style_fn
        self.update_show_many = update_show_many
        self.disable_log = disable_log
        self.create_schema = create_schema
        self.update_schema = update_schema
        self.read_schema = read_schema
        self.foreign_key_options = foreign_key_options or {}
        self.many_to_many_fields = many_to_many_fields or {}

        """Fail fast when a Pydantic schema does not fit the edited model."""
        for schema, operation in (
            (self.create_schema, "create"),
            (self.update_schema, "update"),
            (self.read_schema, "read"),
        ):
            if schema is not None:
                self._validate_schema(schema, operation)

        self.cte = self.get_cte()
        self.notice_ignored_options()

        # Bootstrap
        self.state: UiState = get_ui_state(self.key)
        self.containers: Containers = self.set_structure()
        self.notification()
        logs.set_logging(self.disable_log)

        # Create UI
        self.col_filter = self.filter()
        stmt_no_pag = query.get_stmt_no_pag(self.cte, self.col_filter)
        qtty_rows = query.get_qtty_rows(self.conn, stmt_no_pag, data_version())
        items_per_page, page = self.pagination(qtty_rows, self.col_filter)
        order_col = self.cte.columns.get(pk_name(self.edit_create_model))
        stmt_pag = query.get_stmt_pag(stmt_no_pag, items_per_page, page, order_col)
        df = self.get_df(stmt_pag)
        selection_state = self.show_df(df)
        rows_selected = self.get_rows_selected(selection_state)

        # CRUD
        self.crud(df, rows_selected)
        self.state.opened = False

        # Returns
        self.df = df
        self.rows_selected = rows_selected
        self.qtty_rows = qtty_rows

    def _validate_schema(self, schema: type[BaseModel], operation: str) -> None:
        """Raise ValueError if `schema` is incompatible with the edited model."""
        if not validate_schema_compatibility(schema, self.edit_create_model, operation):
            table_name = tablename(self.edit_create_model)
            msg = (
                f"{operation.capitalize()} schema {schema.__name__} "
                f"is not compatible with {table_name}"
            )
            raise ValueError(msg)

    def set_structure(self) -> Containers:
        """Lay out the page skeleton and return its containers."""
        header = st.container()
        data = st.container()
        pag = st.container()

        table_name = get_pretty_name(tablename(self.edit_create_model))
        header.header(table_name, divider="orange")

        expander = header.expander(
            "Filter",
            icon=":material/search:",
        )

        filter_container = header.container()

        btns = header.container()

        return Containers(
            header=header,
            data=data,
            pag=pag,
            expander=expander,
            filter=filter_container,
            btns=btns,
        )

    def notification(self) -> None:
        if self.state.update_ok is True:
            self.containers.header.success(
                self.state.update_message, icon=":material/thumb_up:"
            )
        if self.state.update_ok is False:
            self.containers.header.error(
                self.state.update_message, icon=":material/thumb_down:"
            )
        # Clear so the banner shows once, not on every following rerun.
        self.state.update_ok = None
        self.state.update_message = None

    def get_cte(self) -> CTE:
        return query.to_cte(self.read_instance)

    def notice_ignored_options(self) -> None:
        """Log once per key that ORM options on read_instance are ignored."""
        if not isinstance(self.read_instance, Select):
            return
        if not self.read_instance._with_options or self.key in OPTIONS_NOTICE_KEYS:
            return
        OPTIONS_NOTICE_KEYS.add(self.key)
        logger.info(
            f"SqlUi '{self.key}': ORM options on read_instance are ignored "
            "because the query is wrapped in a CTE; use many_to_many_fields "
            "for relationship loading."
        )

    def filter(self) -> filter_ui.ColFilter:
        filter_cols_name = self.available_filter
        if len(filter_cols_name) == 0:
            # Include both columns with description and those without (joined columns)
            filter_cols_name = [column_label(col) for col in self.cte.columns]

        with self.conn.session as s:
            existing = filter_ui.get_existing_values(
                _session=s,
                cte=self.cte,
                version=data_version(),
                available_col_filter=filter_cols_name,
            )

        col_filter = filter_ui.ColFilter(
            self.containers.expander,
            cte=self.cte,
            existing_values=existing,
            available_col_filter=filter_cols_name,
            key=self.key,
        )
        if str(col_filter) != "":
            self.containers.filter.write(col_filter)

        return col_filter

    def pagination(
        self, qtty_rows: int, col_filter: filter_ui.ColFilter
    ) -> tuple[int, int]:
        """A filter change sends the pager back to page 1."""
        filters = {**col_filter.no_dt_filters, **col_filter.dt_filters}
        filters_changed = filters != self.state.filters
        self.state.filters = filters

        with self.containers.pag:
            return pagination.show_pagination(
                qtty_rows,
                pagination.OPTS_ITEMS_PAGE,
                self.key,
                self.items_per_page_default,
                reset=filters_changed,
            )

    def get_df(
        self,
        stmt_pag: Select,
    ) -> pd.DataFrame:
        needs_orm_execution = bool(self.read_schema or self.many_to_many_fields)
        if needs_orm_execution:
            df = self._execute_with_pydantic_schema(stmt_pag)
        else:
            with self.conn.session as s:
                df = pd.read_sql(stmt_pag, s.connection())
            df = convert_arrow(self.cte.columns, df)

        return df

    def _execute_with_pydantic_schema(self, stmt: Select) -> pd.DataFrame:
        """Execute query using ORM execution for many-to-many or selectinload support"""
        with self.conn.session as s:
            if self.many_to_many_fields:
                # Use the filtered statement first to get the correct data
                filtered_result = s.execute(stmt).all()

                # If we have many-to-many fields and filtered results, load relationships separately
                if self.many_to_many_fields and filtered_result:
                    pk = pk_name(self.edit_create_model)
                    # Extract entity PKs from filtered results
                    entity_ids = [getattr(row, pk) for row in filtered_result]

                    options = m2m_load_options(
                        self.edit_create_model, self.many_to_many_fields
                    )

                    # Load entities with relationships for just the filtered PKs
                    entities_with_relations = (
                        s.query(self.edit_create_model)
                        .filter(pk_attr(self.edit_create_model).in_(entity_ids))
                        .options(*options)
                        .all()
                    )

                    # Create a mapping of pk -> entity with relationships
                    entity_map = {
                        getattr(entity, pk): entity
                        for entity in entities_with_relations
                    }

                    # Merge filtered data with relationship data
                    result = []
                    for row in filtered_result:
                        entity = entity_map.get(getattr(row, pk))
                        if entity:
                            # Use the entity with relationships loaded
                            result.append(entity)
                        else:
                            # Fallback to row data if entity not found
                            result.append(row)
                else:
                    # No many-to-many fields or no results, use filtered results as-is
                    result = filtered_result
            else:
                result = s.execute(stmt).all()

            json_cols = {c.name for c in self.cte.columns if is_json_type(c.type)}
            validated_rows = []
            for row in result:
                if self.read_schema:
                    # Use Pydantic validation if schema is provided
                    validated_data = self.read_schema.model_validate(
                        row, from_attributes=True
                    ).model_dump()
                else:
                    # Convert ORM/Row object to dict directly
                    if hasattr(row, "__dict__"):
                        # ORM object
                        validated_data = {
                            key: value
                            for key, value in row.__dict__.items()
                            if not key.startswith("_")
                        }
                    else:
                        # Row object
                        validated_data = row._asdict()

                # Ensure the primary key is always present for CRUD operations
                pk = pk_name(self.edit_create_model)
                if pk not in validated_data and hasattr(row, pk):
                    validated_data[pk] = getattr(row, pk)

                # Convert enum objects to strings for PyArrow compatibility
                for key, value in validated_data.items():
                    if key in json_cols:
                        """JSON as text: Arrow rejects dicts/lists mixing types."""
                        validated_data[key] = (
                            None if value is None else json_to_text(value)
                        )
                    elif isinstance(value, list):
                        # Handle list of enums
                        validated_data[key] = [
                            item.value if isinstance(item, Enum) else str(item)
                            for item in value
                        ]
                    else:
                        validated_data[key] = enum_value(value)

                validated_rows.append(validated_data)

            # Create DataFrame from validated data
            df = pd.DataFrame(validated_rows)
            return df

    def show_df(self, df: pd.DataFrame) -> DataframeState | None:
        if df.empty:
            st.header(":red[Table is Empty]")
            return None

        column_order = None
        if self.read_schema:
            # Display only the columns specified in the schema
            column_order = list(model_fields(self.read_schema).keys())

        formatter = {
            **numeric_formatters(self.cte, df.columns),
            **self.df_style_formatter,
        }
        df_style = df.style.format(formatter)
        if self.style_fn is not None:
            df_style = df_style.apply(self.style_fn, axis=1)

        selection_state = self.containers.data.dataframe(
            df_style,
            width="stretch" if self.read_use_container_width else "content",
            height=650,
            hide_index=True,
            column_order=column_order,
            on_select="rerun",
            selection_mode="multi-row" if self.show_delete_btn else "single-row",
            key=self.df_key(),
        )
        return selection_state

    def df_key(self) -> str:
        """Return the dataframe key, renewed by every write of this session.

        The selection holds row positions; a new key drops it once rows shift.
        Per session, so another session's write keeps this one's selection.
        """
        return f"{self.key}_df_sql_ui_{session_writes()}"

    @staticmethod
    def get_rows_selected(selection_state: DataframeState | None) -> list[int]:
        """Get rows selected from Streamlit dataframe selection state"""
        rows_pos = []
        if (
            selection_state
            and "selection" in selection_state
            and "rows" in selection_state["selection"]
        ):
            rows_pos = selection_state["selection"]["rows"]

        return rows_pos

    def crud(self, df: pd.DataFrame, rows_selected: list[int]) -> None:
        qtty_rows = len(rows_selected)
        action = action_btns(
            self.containers.btns,
            qtty_selected=qtty_rows,
            opened=self.state.opened,
            show_delete_btn=self.show_delete_btn,
            show_create_btn=self.show_create_btn,
            key=self.key,
        )

        if action in ("add", "copy"):
            initial_data = None
            if action == "copy":
                initial_data = row_to_python(df.iloc[rows_selected[0]])
            create_row = CreateRow(
                conn=self.conn,
                model=self.edit_create_model,
                default_values=self.edit_create_default_values,
                create_schema=self.create_schema,
                foreign_key_options=self.foreign_key_options,
                many_to_many_fields=self.many_to_many_fields,
                key=self.key,
                initial_data=initial_data,
                dt_filters=self.col_filter.dt_filters,
                no_dt_filters=self.col_filter.no_dt_filters,
            )
            create_row.show_dialog()
        elif action == "edit":
            selected_pos = rows_selected[0]
            pk = pk_name(self.edit_create_model)
            row_id = convert_numpy_to_python(
                df.iloc[selected_pos][pk], self.edit_create_model
            )
            update_row = UpdateRow(
                conn=self.conn,
                model=self.edit_create_model,
                row_id=row_id,
                default_values=self.edit_create_default_values,
                update_show_many=self.update_show_many,
                update_schema=self.update_schema,
                foreign_key_options=self.foreign_key_options,
                many_to_many_fields=self.many_to_many_fields,
                key=self.key,
            )
            update_row.show_dialog()
        elif action == "delete":
            pk = pk_name(self.edit_create_model)
            rows_id = convert_numpy_list_to_python(
                df.iloc[rows_selected][pk].to_list(), self.edit_create_model
            )
            delete_rows = DeleteRows(
                conn=self.conn,
                model=self.edit_create_model,
                rows_id=rows_id,
                key=self.key,
            )
            delete_rows.show_dialog()


def action_btns(
    container: DeltaGenerator,
    qtty_selected: int,
    opened: bool,
    show_create_btn: bool,
    show_delete_btn: bool,
    key: str,
) -> Literal["copy", "add", "edit", "delete"] | None:
    """Render the add/copy, edit and delete buttons; return the clicked action."""
    disabled_add = (qtty_selected > 1) or not show_create_btn
    disabled_edit = qtty_selected != 1
    disabled_delete = (qtty_selected == 0) or not show_delete_btn

    if qtty_selected == 1:
        add_icon = ":material/content_copy:"
        add_help = "Copy"
    else:
        add_icon = ":material/add:"
        add_help = "Add"

    with container:
        add_col, edit_col, del_col, _empty_col = st.columns([1, 1, 1, 6])

        add_btn = add_col.button(
            "",
            help=add_help,
            icon=add_icon,
            type="secondary",
            disabled=disabled_add,
            width="stretch",
            key=f"{key}_stsql_action_add",
        )

        edit_btn = edit_col.button(
            "",
            help="Edit",
            icon=":material/edit:",
            type="secondary",
            disabled=disabled_edit,
            width="stretch",
            key=f"{key}_stsql_action_edit",
        )

        del_btn = del_col.button(
            "",
            help="Delete",
            icon=":material/delete:",
            type="primary",
            disabled=disabled_delete,
            width="stretch",
            key=f"{key}_stsql_action_delete",
        )

        if opened:
            return None
        if add_btn:
            if qtty_selected == 1:
                return "copy"
            return "add"
        if edit_btn:
            return "edit"
        if del_btn:
            return "delete"

        return None
