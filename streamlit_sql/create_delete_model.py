from typing import Optional, Type, Union
import streamlit as st
from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import DeclarativeBase
from streamlit import session_state as ss
from streamlit.connections.sql_connection import SQLConnection

from streamlit_sql.filters import ExistingData
from streamlit_sql.input_fields import InputFields
from streamlit_sql.lib import get_pretty_name, log, set_state
from streamlit_sql.pydantic_utils import PydanticSQLAlchemyConverter, PydanticInputGenerator


class CreateRow:
    def __init__(
        self,
        conn: SQLConnection,
        Model: type[DeclarativeBase],
        default_values: dict | None = None,
        base_key: str = "create",
        create_schema: Optional[Type[BaseModel]] = None,
    ) -> None:
        self.conn = conn
        self.Model = Model
        self.create_schema = create_schema

        self.default_values = default_values or {}
        self.base_key = base_key

        set_state("stsql_updated", 0)

        with conn.session as s:
            self.existing_data = ExistingData(s, Model, self.default_values)
            self.input_fields = InputFields(
                Model, base_key, self.default_values, self.existing_data
            )
            
        # Initialize Pydantic input generator if schema provided
        if self.create_schema:
            self.pydantic_generator = PydanticInputGenerator(
                self.create_schema, base_key
            )
    
    def _preprocess_form_data(self, form_data: dict) -> dict:
        """Preprocess form data to handle enum conversions and other transformations"""
        processed_data = form_data.copy()
        
        if not self.create_schema:
            return processed_data
            
        # Get schema field information
        schema_fields = self.create_schema.model_fields
        
        for field_name, field_info in schema_fields.items():
            if field_name in processed_data:
                value = processed_data[field_name]
                annotation = field_info.annotation
                
                # Handle List[Enum] types
                if hasattr(annotation, '__origin__') and annotation.__origin__ is list:
                    args = getattr(annotation, '__args__', ())
                    if args and len(args) > 0:
                        enum_type = args[0]
                        if hasattr(enum_type, '__members__') and isinstance(value, list):
                            # Convert string values to enum objects
                            try:
                                processed_data[field_name] = [enum_type(item) for item in value]
                            except (ValueError, KeyError):
                                # If conversion fails, try by name
                                processed_data[field_name] = [getattr(enum_type, item.upper(), item) for item in value]
                
                # Handle Optional[List[Enum]] types  
                elif hasattr(annotation, '__origin__') and annotation.__origin__ is Union:
                    args = getattr(annotation, '__args__', ())
                    if len(args) == 2 and type(None) in args:
                        # This is Optional[T], get the non-None type
                        non_none_type = next(arg for arg in args if arg is not type(None))
                        if hasattr(non_none_type, '__origin__') and non_none_type.__origin__ is list:
                            list_args = getattr(non_none_type, '__args__', ())
                            if list_args and len(list_args) > 0:
                                enum_type = list_args[0]
                                if hasattr(enum_type, '__members__') and isinstance(value, list):
                                    # Convert string values to enum objects
                                    try:
                                        processed_data[field_name] = [enum_type(item) for item in value]
                                    except (ValueError, KeyError):
                                        # If conversion fails, try by name
                                        processed_data[field_name] = [getattr(enum_type, item.upper(), item) for item in value]
        
        return processed_data

    def get_fields(self):
        if self.create_schema:
            return self.get_pydantic_fields()
        else:
            return self.get_sqlalchemy_fields()
    
    def get_pydantic_fields(self):
        """Generate fields using Pydantic schema"""
        form_data = self.pydantic_generator.generate_form_data(self.default_values)
        return form_data
    
    def get_sqlalchemy_fields(self):
        """Original SQLAlchemy field generation logic"""
        cols = self.Model.__table__.columns
        created = {}
        for col in cols:
            col_name = col.description or col.name
            if col_name is None:
                continue
                
            default_value = self.default_values.get(col_name)

            if default_value:
                input_value = default_value
            else:
                input_value = self.input_fields.get_input_value(col, None)

            created[col_name] = input_value

        return created

    def show(self, pretty_name: str):
        st.subheader(pretty_name)

        with st.form(f"create_model_form_{pretty_name}_{self.base_key}", border=False):
            created = self.get_fields()
            create_btn = st.form_submit_button("Save", type="primary")

        if create_btn:
            if self.create_schema:
                return self.save_pydantic(created)
            else:
                return self.save_sqlalchemy(created)
        else:
            return None, None
    
    def save_pydantic(self, form_data: dict):
        """Save using Pydantic validation"""
        try:
            # Preprocess form data to handle enum conversions
            processed_data = self._preprocess_form_data(form_data)
            
            # Validate data using Pydantic schema
            validated_data = self.create_schema(**processed_data)
            
            # Convert to SQLAlchemy model
            row = PydanticSQLAlchemyConverter.pydantic_to_sqlalchemy(
                validated_data, self.Model
            )
            
            with self.conn.session as s:
                s.add(row)
                s.commit()
                ss.stsql_updated += 1
                table_name = getattr(self.Model, '__tablename__', self.Model.__name__)
                log("CREATE", table_name, row)
                return True, f"Created successfully {row}"
                
        except ValidationError as e:
            error_msg = "; ".join([f"{err['loc'][0]}: {err['msg']}" for err in e.errors()])
            ss.stsql_updated += 1
            table_name = getattr(self.Model, '__tablename__', self.Model.__name__)
            log("CREATE", table_name, form_data, success=False)
            return False, f"Validation error: {error_msg}"
        except Exception as e:
            ss.stsql_updated += 1
            table_name = getattr(self.Model, '__tablename__', self.Model.__name__)
            log("CREATE", table_name, form_data, success=False)
            return False, str(e)
    
    def save_sqlalchemy(self, created: dict):
        """Original SQLAlchemy save logic"""
        try:
            row = self.Model(**created)
            with self.conn.session as s:
                s.add(row)
                s.commit()
                ss.stsql_updated += 1
                table_name = getattr(self.Model, '__tablename__', self.Model.__name__)
                log("CREATE", table_name, row)
                return True, f"Created successfully {row}"
        except Exception as e:
            ss.stsql_updated += 1
            table_name = getattr(self.Model, '__tablename__', self.Model.__name__)
            log("CREATE", table_name, created, success=False)
            return False, str(e)

    def show_dialog(self):
        pretty_name = get_pretty_name(self.Model.__tablename__)

        @st.dialog(f"Create {pretty_name}", width="large")  # pyright: ignore
        def wrap_show_update():
            set_state("stsql_updated", 0)
            updated_before = ss.stsql_updated
            status, msg = self.show(pretty_name)

            ss.stsql_update_ok = status
            ss.stsql_update_message = msg
            ss.stsql_opened = True

            if ss.stsql_updated > updated_before:
                st.rerun()

        wrap_show_update()


class DeleteRows:
    def __init__(
        self,
        conn: SQLConnection,
        Model: type[DeclarativeBase],
        rows_id: list[int],
        base_key: str = "stsql_delete_rows",
    ) -> None:
        self.conn = conn
        self.Model = Model
        self.rows_id = rows_id
        self.base_key = base_key

    @st.cache_data
    def get_rows_str(_self, rows_id: list[int]):
        id_col = _self.Model.__table__.columns.get("id")
        assert id_col is not None
        stmt = select(_self.Model).where(id_col.in_(rows_id))

        with _self.conn.session as s:
            rows = s.execute(stmt).scalars()
            rows_str = [str(row) for row in rows]

        return rows_str

    def show(self, pretty_name):
        st.subheader("Delete selected items?")

        rows_str = self.get_rows_str(self.rows_id)
        st.dataframe({pretty_name: rows_str}, hide_index=True)

        btn = st.button("Delete", key=self.base_key)
        if btn:
            id_col = self.Model.__table__.columns.get("id")
            assert id_col is not None
            lancs = []
            with self.conn.session as s:
                try:
                    for row_id in self.rows_id:
                        lanc = s.get(self.Model, row_id)
                        lancs.append(str(lanc))
                        s.delete(lanc)

                    s.commit()
                    ss.stsql_updated += 1
                    qtty = len(self.rows_id)
                    lancs_str = ", ".join(lancs)
                    table_name = getattr(self.Model, '__tablename__', self.Model.__name__)
                    log("DELETE", table_name, lancs_str)
                    return True, f"Successfully deleted {qtty}"
                except Exception as e:
                    ss.stsql_updated += 1
                    table_name = getattr(self.Model, '__tablename__', self.Model.__name__)
                    log("DELETE", table_name, "")
                    return False, str(e)
        else:
            return None, None

    def show_dialog(self):
        pretty_name = get_pretty_name(self.Model.__tablename__)

        @st.dialog(f"Delete {pretty_name}", width="large")  # pyright: ignore
        def wrap_show_update():
            set_state("stsql_updated", 0)
            updated_before = ss.stsql_updated
            status, msg = self.show(pretty_name)

            ss.stsql_update_ok = status
            ss.stsql_update_message = msg
            ss.stsql_opened = True

            if ss.stsql_updated > updated_before:
                st.rerun()

        wrap_show_update()
