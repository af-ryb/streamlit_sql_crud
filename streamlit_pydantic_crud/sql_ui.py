import json
import pandas as pd
import streamlit as st
from collections.abc import Callable
from typing import Optional, Type
from loguru import logger

from pydantic import BaseModel
from sqlalchemy import CTE, Select, select
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import Enum as SQLEnum
from streamlit import session_state as ss
from streamlit.connections import SQLConnection
from streamlit.elements.arrow import DataframeState

from streamlit_pydantic_crud import create_delete_model, lib, read_cte, update_model
from streamlit_pydantic_crud.pydantic_utils import PydanticSQLAlchemyConverter
from streamlit_pydantic_crud.utils import convert_numpy_to_python, convert_numpy_list_to_python

OPTS_ITEMS_PAGE = (50, 100, 200, 500, 1000)


class SqlUi:
    """Show A CRUD interface in a Streamlit Page

    See in __init__ method detailed descriptions of arguments and properties

    It also offers the following properties:


    """

    def __init__(
        self,
        conn: SQLConnection,
        read_instance = None,
        edit_create_model: type[DeclarativeBase] = None,
        model: type[DeclarativeBase] = None,
        available_filter: list[str] | None = None,
        edit_create_default_values: dict | None = None,
        rolling_total_column: str | None = None,
        rolling_orderby_colsname: list[str] | None = None,
        df_style_formatter: dict[str, str] | None = None,
        read_use_container_width: bool = False,
        key: str | None = None,
        base_key: str | None = None,
        style_fn: Callable[[pd.Series], list[str]] | None = None,
        update_show_many: bool = False,
        disable_log: bool = False,
        create_schema: Optional[Type[BaseModel]] = None,
        update_schema: Optional[Type[BaseModel]] = None,
        read_schema: Optional[Type[BaseModel]] = None,
        foreign_key_options: dict | None = None,
        many_to_many_fields: dict | None = None,
    ):
        """The CRUD interface will be displayes just by initializing the class

        Arguments:
            conn (SQLConnection): A sqlalchemy connection created with st.connection("sql", url="<sqlalchemy url>")
            model (type[DeclarativeBase]): SQLAlchemy model class used for both read and write operations. Recommended over separate read_instance and edit_create_model parameters.
            edit_create_default_values (dict, optional): A dict with column name as keys and values to be default. When the user clicks to create a row, those columns will not show on the form and its value will be added to the model object
            available_filter (list[str], optional): Define which columns the user will be able to filter in the top expander. Defaults to all
            rolling_total_column (str, optional): A numeric column name of the read_instance. A new column will be displayed with the rolling sum of these column
            rolling_orderby_colsname (list[str], optional): A list of columns name of the read_instance. It should contain a group of columns that ensures uniqueness of the rows and the order to calculate rolling sum. Usually, it should a date and id column. If not informed, rows will be sorted by id only. Defaults to None
            df_style_formatter (dict[str, str]): a dictionary where each key is a column name and the associated value is the formatter arg of df.style.format method. See pandas docs for details.
            read_use_container_width (bool, optional): add use_container_width to st.dataframe args. Default to False
            key (str, optional): A unique key prefix for all widgets in this SqlUi instance. This follows Streamlit's standard convention and is needed when creating multiple instances on the same page. Defaults to None
            style_fn (Callable[[pd.Series], list[str]], optional): A function that goes into the *func* argument of *df.style.apply*. The apply method also receives *axis=1*, so it works on rows. It can be used to apply conditional css formatting on each column of the row. See Styler.apply info on pandas docs. Defaults to None
            update_show_many (bool, optional): Show a st.expander of one-to-many relations in edit or create dialog
            disable_log (bool): Every change in the database (READ, UPDATE, DELETE) is logged to stderr by default. If this is *true*, nothing is logged. To customize the logging format and where it logs to, use loguru as add a new sink to logger. See loguru docs for more information. Dafaults to False
            create_schema (Optional[Type[BaseModel]]): Pydantic schema for create operations. If provided, uses Pydantic validation for creation forms. Defaults to None
            update_schema (Optional[Type[BaseModel]]): Pydantic schema for update operations. If provided, uses Pydantic validation for update forms. Defaults to None
            read_schema (Optional[Type[BaseModel]]): Pydantic schema for read operations. If provided, uses Pydantic model_validate for data processing and avoids pandas read_sql issues with JSON columns. Defaults to None
            foreign_key_options (dict, optional): Custom foreign key selectbox configuration. Dict with field names as keys and config dicts as values. Each config should have 'query' (SQLAlchemy select statement), 'display_field' (column name for display), and 'value_field' (column name for value). Defaults to None
            many_to_many_fields (dict, optional): Custom many-to-many multiselect configuration. Dict with relationship names as keys and config dicts as values. Each config should have 'relationship' (SQLAlchemy relationship name), 'display_field' (column name for display), and 'filter' (optional lambda for filtering options). Defaults to None

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
                rolling_total_column="amount",
                rolling_orderby_colsname=["date", "id"],
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
                import warnings
                warnings.warn(
                    "When 'model' parameter is provided, 'read_instance' and 'edit_create_model' are ignored. "
                    "Use either 'model' (recommended) or the legacy 'read_instance'+'edit_create_model' combination.",
                    DeprecationWarning,
                    stacklevel=2
                )
            # Use model for both read and write operations
            self.read_instance = model
            self.edit_create_model = model
        else:
            # Legacy mode - require both parameters
            if read_instance is None or edit_create_model is None:
                raise ValueError(
                    "Either provide 'model' parameter (recommended) or both 'read_instance' and 'edit_create_model' parameters. "
                    "The 'model' parameter simplifies the API when using the same model for read and write operations."
                )
            self.read_instance = read_instance
            self.edit_create_model = edit_create_model
        
        self.conn = conn
        self.available_filter = available_filter or []
        self.edit_create_default_values = edit_create_default_values or {}
        self.rolling_total_column = rolling_total_column
        self.rolling_orderby_colsname = rolling_orderby_colsname or ["id"]
        self.df_style_formatter = df_style_formatter or {}
        self.read_use_container_width = read_use_container_width
        # Handle key parameter compatibility - key takes precedence over base_key
        if key is not None and base_key is not None:
            import warnings
            warnings.warn(
                "Both 'key' and 'base_key' specified. 'base_key' is deprecated, using 'key' instead. "
                "Remove 'base_key' parameter in future versions.",
                DeprecationWarning,
                stacklevel=2
            )
            self.key = key
        elif base_key is not None:
            import warnings
            warnings.warn(
                "'base_key' parameter is deprecated and will be removed in v1.0.0. "
                "Use 'key' parameter instead for Streamlit compatibility.",
                DeprecationWarning,
                stacklevel=2
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

        # Validate schema compatibility if provided
        if self.create_schema:
            if not PydanticSQLAlchemyConverter.validate_schema_compatibility(
                self.create_schema, self.edit_create_model, 'create'
            ):
                table_name = getattr(self.edit_create_model, '__tablename__', self.edit_create_model.__name__)
                raise ValueError(f"Create schema {self.create_schema.__name__} is not compatible with {table_name}")
        
        if self.update_schema:
            if not PydanticSQLAlchemyConverter.validate_schema_compatibility(
                self.update_schema, self.edit_create_model, 'update'
            ):
                table_name = getattr(self.edit_create_model, '__tablename__', self.edit_create_model.__name__)
                raise ValueError(f"Update schema {self.update_schema.__name__} is not compatible with {table_name}")
        
        if self.read_schema:
            if not PydanticSQLAlchemyConverter.validate_schema_compatibility(
                self.read_schema, self.edit_create_model, 'read'
            ):
                table_name = getattr(self.edit_create_model, '__tablename__', self.edit_create_model.__name__)
                raise ValueError(f"Read schema {self.read_schema.__name__} is not compatible with {table_name}")

        self.cte = self.get_cte()
        self.rolling_pretty_name = lib.get_pretty_name(self.rolling_total_column or "")

        # Bootstrap
        self.set_initial_state()
        self.set_structure()
        self.notification()
        lib.set_logging(self.disable_log)

        # Create UI
        col_filter = self.filter()
        stmt_no_pag = read_cte.get_stmt_no_pag(self.cte, col_filter)
        qtty_rows = read_cte.get_qtty_rows(self.conn, stmt_no_pag)
        items_per_page, page = self.pagination(qtty_rows, col_filter)
        stmt_pag = read_cte.get_stmt_pag(stmt_no_pag, items_per_page, page)
        initial_balance = self.get_initial_balance(
            self.cte,
            stmt_pag,
            col_filter.no_dt_filters,
            rolling_total_column,
            self.rolling_orderby_colsname,
        )
        df = self.get_df(stmt_pag, initial_balance)
        selection_state = self.show_df(df)
        rows_selected = self.get_rows_selected(selection_state)

        # CRUD
        self.crud(df, rows_selected)
        ss.stsql_opened = False

        # Returns
        self.df = df
        self.rows_selected = rows_selected
        self.qtty_rows = qtty_rows

    def set_initial_state(self):
        lib.set_state("stsql_updated", 1)
        lib.set_state("stsql_update_ok", None)
        lib.set_state("stsql_update_message", None)
        lib.set_state("stsql_opened", False)
        lib.set_state("stsql_filters", {})

    def set_structure(self):
        self.header_container = st.container()
        self.data_container = st.container()
        self.pag_container = st.container()

        table_name = getattr(self.edit_create_model, '__tablename__', self.edit_create_model.__name__)
        table_name = lib.get_pretty_name(table_name)
        self.header_container.header(table_name, divider="orange")

        self.expander_container = self.header_container.expander(
            "Filter",
            icon=":material/search:",
        )

        self.filter_container = self.header_container.container()

        if self.rolling_total_column:
            self.saldo_toggle_col, self.saldo_value_col = self.header_container.columns(
                2
            )

        self.btns_container = self.header_container.container()

    def notification(self):
        if ss.stsql_update_ok is True:
            self.header_container.success(
                ss.stsql_update_message, icon=":material/thumb_up:"
            )
        if ss.stsql_update_ok is False:
            self.header_container.error(
                ss.stsql_update_message, icon=":material/thumb_down:"
            )

    def get_cte(self):
        if isinstance(self.read_instance, Select):
            cte = self.read_instance.cte()
        elif isinstance(self.read_instance, CTE):
            cte = self.read_instance
        else:
            cte = select(self.read_instance).cte()

        if self.rolling_total_column:
            orderby_cols = [
                cte.columns.get(colname) for colname in self.rolling_orderby_colsname
            ]
            orderby_cols = [col for col in orderby_cols if col is not None]
            cte = select(cte).order_by(*orderby_cols).cte()

        return cte

    @staticmethod
    def _get_column_info(col) -> tuple[str, str]:
        """Helper method to get column information for joined columns
        
        Returns a tuple of (display_name, col_name)
        """
        display_name = col.description or col.name

        return display_name, col.name

    def _stmt_has_orm_options(self, stmt: Select) -> bool:
        """Check if the statement has ORM options like selectinload"""
        # Check if the original read_instance has options applied
        if isinstance(self.read_instance, Select):
            return hasattr(self.read_instance, '_with_options') and self.read_instance._with_options
        return False
    
    def _stmt_has_explicit_columns(self, stmt: Select) -> bool:
        """Check if statement uses explicit column selection (expression-based entities)"""
        if isinstance(self.read_instance, Select):
            # Check if the statement selects specific columns rather than entire entities
            selected_columns = self.read_instance.selected_columns
            if selected_columns:
                # If any selected item is not a full table/entity, it's expression-based
                from sqlalchemy import Table
                from sqlalchemy.orm import DeclarativeBase
                for col in selected_columns:
                    # If it's a column attribute rather than a full table/entity
                    if hasattr(col, 'table') or hasattr(col, 'element'):
                        return True
        return False

    def filter(self):
        filter_cols_name = self.available_filter
        if len(filter_cols_name) == 0:
            # Include both columns with description and those without (joined columns)
            filter_cols_name = [
                col.description or col.name for col in self.cte.columns
            ]

        with self.conn.session as s:
            existing = read_cte.get_existing_values(
                _session=s,
                cte=self.cte,
                updated=ss.stsql_updated,
                available_col_filter=filter_cols_name,
            )

        col_filter = read_cte.ColFilter(
            self.expander_container,
            cte=self.cte,
            existing_values=existing,
            available_col_filter=filter_cols_name,
            key=self.key,
        )
        if str(col_filter) != "":
            self.filter_container.write(col_filter)

        return col_filter

    def pagination(self, qtty_rows: int, col_filter: read_cte.ColFilter):
        with self.pag_container:
            items_per_page, page = read_cte.show_pagination(
                qtty_rows,
                OPTS_ITEMS_PAGE,
                self.key,
            )

        filters = {**col_filter.no_dt_filters, **col_filter.dt_filters}
        if filters != ss.stsql_filters:
            page = 1
            ss.stsql_filters = filters

        return items_per_page, page

    def get_initial_balance(
        self,
        base_cte: CTE,
        stmt_pag: Select,
        no_dt_filters: dict,
        rolling_total_column: str | None,
        rolling_orderby_colsname: list[str],
    ):
        if rolling_total_column is None:
            return 0

        saldo_toggle = self.saldo_toggle_col.toggle(
            f"Add Previous Balance in {self.rolling_pretty_name}",
            value=True,
            key=f"{self.key}_saldo_toggle_sql_ui",
        )

        if not saldo_toggle:
            return 0

        stmt_no_pag_dt = read_cte.get_stmt_no_pag_dt(base_cte, no_dt_filters)

        orderby_cols = [
            base_cte.columns.get(col_name) for col_name in rolling_orderby_colsname
        ]
        orderby_cols = [col for col in orderby_cols if col is not None]
        with self.conn.session as s:
            initial_balance = read_cte.initial_balance(
                _session=s,
                stmt_no_pag_dt=stmt_no_pag_dt,
                stmt_pag=stmt_pag,
                rolling_total_column=rolling_total_column,
                orderby_cols=orderby_cols,
            )

        self.saldo_value_col.subheader(
            f"Previous Balance {self.rolling_pretty_name}: {initial_balance:,.2f}"
        )

        return initial_balance

    def convert_arrow(self, df: pd.DataFrame):
        cols = self.cte.columns
        for col in cols:
            col_name = col.name
            if col_name in df.columns:
                if isinstance(col.type, SQLEnum):
                    df[col_name] = df[col_name].map(lambda v: v.value if hasattr(v, 'value') else v)
                elif 'JSON' in str(col.type).upper():
                    # Handle JSON columns for display
                    df[col_name] = df[col_name].apply(lambda x: 
                        json.dumps(x, indent=2) if x is not None and isinstance(x, (dict, list)) 
                        else str(x) if x is not None else None
                    )
                elif 'ARRAY' in str(col.type).upper():
                    # Handle ARRAY columns for display
                    df[col_name] = df[col_name].apply(lambda x: 
                        ', '.join(map(str, x)) if x is not None and isinstance(x, (list, tuple)) 
                        else str(x) if x is not None else None
                    )

        return df

    def get_df(
        self,
        stmt_pag: Select,
        initial_balance: float,
    ):
        # Check if we have ORM options but explicit column selection (incompatible combination)
        has_orm_options = self._stmt_has_orm_options(stmt_pag)
        has_explicit_columns = self._stmt_has_explicit_columns(stmt_pag)
        
        if has_orm_options and has_explicit_columns:
            logger.warning(
                "selectinload() options detected with explicit column selection. "
                "ORM options will be ignored as they're incompatible with expression-based SELECT statements. "
                "Consider using separate queries for many-to-many relationships or select full entities instead of individual columns."
            )
        
        # Check if we need special handling for many-to-many fields or specific statement types
        needs_orm_execution = (
            self.read_schema or 
            self.many_to_many_fields or 
            (has_orm_options and not has_explicit_columns)  # Only use ORM execution if compatible
        )
        
        if needs_orm_execution:
            df = self._execute_with_pydantic_schema(stmt_pag)
        else:
            with self.conn.connect() as c:
                df = pd.read_sql(stmt_pag, c)
            df = self.convert_arrow(df)
        if self.rolling_total_column is None:
            return df

        rolling_col_name = f"Balance {self.rolling_pretty_name}"
        df[rolling_col_name] = df[self.rolling_total_column].cumsum() + initial_balance

        return df

    def _execute_with_pydantic_schema(self, stmt: Select):
        """Execute query using ORM execution for many-to-many or selectinload support"""
        with self.conn.session as s:
            has_orm_options = self._stmt_has_orm_options(stmt)
            has_explicit_columns = self._stmt_has_explicit_columns(stmt)
            
            # For many-to-many or selectinload, we need ORM objects, not Row objects
            if self.many_to_many_fields or (has_orm_options and not has_explicit_columns):
                from sqlalchemy.orm import selectinload
                
                # Build options for eager loading
                options = []
                
                # Add selectinload options if original statement has them and is compatible
                if has_orm_options and not has_explicit_columns:
                    # Use the original statement with options - but we need to modify it
                    # to be compatible with CTE pagination
                    base_query = s.query(self.edit_create_model)
                    
                    # Copy options from original statement if possible
                    if hasattr(self.read_instance, '_with_options'):
                        for option in self.read_instance._with_options:
                            options.append(option)
                    
                    result = base_query.options(*options).all()
                else:
                    # Add many_to_many options  
                    for field_name, config in self.many_to_many_fields.items():
                        relationship_attr = getattr(self.edit_create_model, config['relationship'])
                        options.append(selectinload(relationship_attr))
                    
                    # Use ORM query instead of raw SQL
                    result = s.query(self.edit_create_model).options(*options).all()
            else:
                result = s.execute(stmt).all()

            validated_rows = []
            for row in result:
                if self.read_schema:
                    # Use Pydantic validation if schema is provided
                    validated_data = self.read_schema.model_validate(row, from_attributes=True).model_dump()
                else:
                    # Convert ORM/Row object to dict directly
                    if hasattr(row, '__dict__'):
                        # ORM object
                        validated_data = {key: value for key, value in row.__dict__.items() 
                                        if not key.startswith('_')}
                    else:
                        # Row object  
                        validated_data = row._asdict()

                # Ensure 'id' is always present for CRUD operations
                if 'id' not in validated_data and hasattr(row, 'id'):
                    validated_data['id'] = row.id

                # Convert enum objects to strings for PyArrow compatibility
                for key, value in validated_data.items():
                    if isinstance(value, list):
                        # Handle list of enums
                        validated_data[key] = [
                            item.value if hasattr(item, 'value') else str(item)
                            for item in value
                        ]
                    elif hasattr(value, 'value'):
                        # Handle single enum
                        validated_data[key] = value.value

                validated_rows.append(validated_data)

            # Create DataFrame from validated data
            df = pd.DataFrame(validated_rows)
            return df

    def add_balance_formatter(self, df_style_formatter: dict[str, str]):
        formatter = {}
        for k, v in df_style_formatter.items():
            formatter[k] = v
            if k == self.rolling_total_column:
                rolling_col_name = f"Balance {self.rolling_pretty_name}"
                formatter[rolling_col_name] = v

        return formatter

    def show_df(self, df: pd.DataFrame):
        if df.empty:
            st.header(":red[Table is Empty]")
            return None

        column_order = None
        if self.read_schema:
            # Display only the columns specified in the schema
            column_order = list(self.read_schema.model_fields.keys())

        df_style = df.style
        formatter = self.add_balance_formatter(self.df_style_formatter)
        df_style = df_style.format(formatter)  # pyright: ignore
        if self.style_fn is not None:
            df_style = df_style.apply(self.style_fn, axis=1)

        selection_state = self.data_container.dataframe(
            df_style,
            use_container_width=self.read_use_container_width,
            height=650,
            hide_index=True,
            column_order=column_order,
            on_select="rerun",
            selection_mode="multi-row",
            key=f"{self.key}_df_sql_ui",
        )
        return selection_state

    @staticmethod
    def get_rows_selected(selection_state: DataframeState | None):
        """Get rows selected from Streamlit dataframe selection state"""
        rows_pos = []
        if (
            selection_state
            and "selection" in selection_state
            and "rows" in selection_state["selection"]
        ):
            rows_pos = selection_state["selection"]["rows"]

        return rows_pos

    def crud(self, df: pd.DataFrame, rows_selected: list[int]):
        qtty_rows = len(rows_selected)
        action = update_model.action_btns(
            self.btns_container,
            qtty_rows,
            ss.stsql_opened,
            key=self.key,
        )

        if action == "add":
            create_row = create_delete_model.CreateRow(
                conn=self.conn,
                model=self.edit_create_model,
                default_values=self.edit_create_default_values,
                create_schema=self.create_schema,
                foreign_key_options=self.foreign_key_options,
                many_to_many_fields=self.many_to_many_fields,
                key=self.key,
            )
            create_row.show_dialog()
        elif action == "copy":
            selected_pos = rows_selected[0]
            initial_data = df.iloc[selected_pos].to_dict()
            create_row = create_delete_model.CreateRow(
                conn=self.conn,
                model=self.edit_create_model,
                default_values=self.edit_create_default_values,
                create_schema=self.create_schema,
                foreign_key_options=self.foreign_key_options,
                many_to_many_fields=self.many_to_many_fields,
                key=self.key,
                initial_data=initial_data,
            )
            create_row.show_dialog()
        elif action == "edit":
            selected_pos = rows_selected[0]
            row_id = convert_numpy_to_python(df.iloc[selected_pos]["id"], self.edit_create_model)
            update_row = update_model.UpdateRow(
                conn=self.conn,
                model=self.edit_create_model,
                row_id=row_id,
                default_values=self.edit_create_default_values,
                update_show_many=self.update_show_many,
                update_schema=self.update_schema,
                foreign_key_options=self.foreign_key_options,
                many_to_many_fields=self.many_to_many_fields,
                key=self.key
            )
            update_row.show_dialog()
        elif action == "delete":
            rows_id = convert_numpy_list_to_python(df.iloc[rows_selected].id.to_list(), self.edit_create_model)
            delete_rows = create_delete_model.DeleteRows(
                conn=self.conn,
                model=self.edit_create_model,
                rows_id=rows_id,
                key=self.key,
            )
            delete_rows.show_dialog()
