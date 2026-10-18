# Architecture

`streamlit_pydantic_crud` is a Streamlit CRUD library: it renders a table over a
SQLAlchemy query with filters and paging, plus create / edit / delete dialogs
validated by Pydantic schemas (or plain per-column widgets without schemas).
The repository name is `streamlit_sql_crud`; the import name is
`streamlit_pydantic_crud`.

## Public API

`streamlit_pydantic_crud.__init__` exports three classes; everything else is
internal and may change between minor versions.

- **`SqlUi`** (`sql_ui.py`) — the whole CRUD page: table, filters, pagination,
  action buttons and dialogs. Takes either `model=` (a mapped class) or
  `read_instance` (a custom `Select` / `CTE` / model, e.g. with JOINs and labeled
  columns) + `edit_create_model`; optional `read_schema` / `create_schema` /
  `update_schema`, `foreign_key_options`, `many_to_many_fields`,
  `column_config`, `width` / `height`, `page_size` / `page_size_options`.
- **`PydanticUi`** (`pydantic_ui.py`) — a standalone form generated from a
  Pydantic schema (or a JSON schema via `from_json_schema`), with session-state
  persistence. Database-agnostic.
- **`PydanticCrudUi`** (`pydantic_ui.py`) — `PydanticUi` with FK / M2M options;
  used by the dialogs.

Accepted inputs are typed by protocols in `config_types.py`: `MappedModel`
(a `DeclarativeBase` subclass or a SQLModel table) and `SessionSource`
(anything with a `session` property returning a `Session` — `st.connection("sql")`
or a duck-typed wrapper).

## Package layout

The root holds only the public classes and shared state:

```
streamlit_pydantic_crud/
├── __init__.py        # public API: SqlUi, PydanticUi, PydanticCrudUi
├── sql_ui.py          # SqlUi; action buttons
├── pydantic_ui.py     # PydanticUi / PydanticCrudUi
├── config_types.py    # config TypedDicts (ForeignKeyOptions, ManyToManyFields),
│                      #   protocols (MappedModel, SessionSource), FkOpt,
│                      #   OperationType, TableWidth / TableHeight
├── state.py           # per-instance UI state, data version, cache TTL,
│                      #   set_state, clear_state_keys
├── helpers/           # leaf modules, no Streamlit state
│   ├── typing.py      # annotation inspection (Optional, enum, list, model_fields)
│   ├── sa_model.py    # SQLAlchemy introspection (PK, table name, column label,
│   │                  #   safe_python_type, related_model, m2m_load_options)
│   ├── values.py      # value coercion (PG arrays, numpy-like scalars, enum, JSON)
│   ├── display.py     # labels and table display (get_pretty_name,
│   │                  #   display_records, column_configs)
│   ├── logs.py        # CRUD action logging, set_logging
│   └── db_errors.py   # user-friendly database error messages
├── table/             # read side of SqlUi
│   ├── query.py       # CTE wrapping (+ hidden ORDER BY columns), filters,
│   │                  #   row count, paging order (to_cte, paging_order,
│   │                  #   get_stmt_no_pag, get_qtty_rows, apply_active_filters)
│   ├── read.py        # read_records: the single read path (raw records)
│   ├── filter_ui.py   # ColFilter widgets, cached filter values, hash_funcs
│   ├── params.py      # mirror filter values to URL query params and restore them
│   ├── pagination.py  # page-size selector and pager (page_size / options)
│   └── styler_compat.py  # deprecated pandas Styler path (df_style_formatter,
│                         #   style_fn, SqlUi.df); removed in 0.10.0
├── forms/             # form fields in both modes
│   ├── sa_fields.py   # InputFields: plain (no-schema) widgets, one per column
│   ├── options.py     # FK / M2M options: load_form_options (Pydantic forms),
│   │                  #   ExistingData, custom_foreign_opts (plain forms)
│   ├── schema_builder.py  # dynamic Pydantic models from JSON schemas
│   ├── schema_check.py    # validate_schema_compatibility (schema vs model)
│   └── pydantic/      # Pydantic form generation
│       ├── generator.py       # PydanticInputGenerator: routes fields to
│       │                      #   widgets, builds form data (PydanticUi)
│       ├── widgets.py         # renderers per widget kind; nullable_number_input,
│       │                      #   seed_widget_state
│       ├── field_info.py      # get_pydantic_field_info, get_streamlit_input_type,
│       │                      #   is_optional_field
│       └── option_resolve.py  # UI-free default/option resolution (match_option,
│                              #   resolve_select_index, known_defaults, ...)
└── dialogs/           # CRUD dialogs
    ├── frame.py       # shared dialog wrapper (show_crud_dialog)
    ├── create.py / edit.py / delete.py  # CreateRow / UpdateRow / DeleteRows
    ├── persist.py     # M2M split/load, JSON None as SQL NULL, form session key,
    │                  #   handle_save_ok / handle_save_error
    └── one_to_many.py # related-rows panels in the edit dialog
```

- **Sub-package `__init__.py` files are docstring-only** — no imports, no
  re-exports; import submodules directly (`from streamlit_pydantic_crud.table
  import query`). Eager imports there would create cycles.
- `helpers/typing.py` is always imported absolutely
  (`from streamlit_pydantic_crud.helpers.typing import ...`); it does not shadow
  the stdlib `typing`.

## Layering

Enforced by `tests/test_import_layers.py`: a module may import its own layer or
a lower one, never a higher one, and the module graph has no cycles. Lowest
first:

`state`, `config_types` < `helpers/` < `table/` < `forms/` < `pydantic_ui` <
`dialogs/` < `sql_ui` < `__init__`

`pydantic_ui` sits below `dialogs/` because the dialogs build `PydanticCrudUi`
forms. Type-only imports go under `if TYPE_CHECKING:` (not runtime edges), e.g.
`forms/options.py` annotating `PydanticCrudUi`. A new top-level module or
sub-package must be added to `LAYERS` in that test.

`tests/test_pandas_boundary.py` keeps pandas behind `table/styler_compat.py`
(runtime) and `sql_ui.py` (type-only) until 0.10.0 removes it.

## Data flow

**Read** (`SqlUi`):
1. `table/query.to_cte` wraps `read_instance` in a CTE; ORDER BY expressions of
   a `Select` become hidden `_stsql_order_<i>` columns.
2. Active filters (`table/filter_ui`, mirrored to URL params by `table/params`)
   narrow the CTE; the count is cached per statement and process-wide data
   version (`state`).
3. `table/query.paging_order` orders the page by the query's ORDER BY, then the
   PK as tiebreaker; `table/pagination` picks the page.
4. `table/read.read_records` executes the page and returns raw Python records;
   with M2M the entities are reloaded by PK (query-row columns win over entity
   attributes); with `read_schema` each row is validated `from_attributes`.
5. `helpers/display.display_records` normalizes values for Arrow (enum → value,
   JSON → text, ARRAY → list) and `column_configs` formats numbers by scale;
   `st.dataframe` renders the records. `SqlUi.rows` keeps the raw records.

**Write** (dialogs): selection positions index `SqlUi.rows`; edit / delete use
the record's PK, copy passes the raw record. Pydantic forms validate input,
`dialogs/persist` splits M2M values and maps JSON `None` to SQL NULL, the model
is committed, and `record_write` bumps the data version so cached counts and
options refresh.

## Key patterns

- Separate create / read / update schemas; read schemas may expose model
  `@property` values via `from_attributes`.
- JOIN fields: labeled columns in a custom `Select`, filterable like any column.
- Many-to-many: multiselects over association tables; two-stage read (page
  query, then entity reload with `selectinload`).
- Foreign keys: selectboxes from a custom query and display field.
- Session-state persistence: forms keep their values across reruns; widget
  state is seeded so programmatic updates reach the browser.
