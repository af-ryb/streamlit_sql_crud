# TODO: cleanup & review backlog

Results of the code review (2026-10-16). Work is split into steps; each step is a
separate PR/commit series.

Baseline: pytest 56 passed · pyright 0 (via 8 `# pyright: ignore`) · ty 8 diagnostics ·
ruff 199 violations · 14 files unformatted · vulture 15 candidates.

## Step 1 — Tooling (mechanical)

- [x] `ruff check --fix` + `ruff format` as a separate mechanical commit
- [x] Replace pyright with ty: dev deps, `[tool.ty]` config, drop `[tool.pyright]`
- [x] Fix ty diagnostics:
  - [x] `lib.py` `logger._core` — the library should not add log sinks
  - [x] `read_cte.py` `sac.cascader` items type (list invariance)
  - [x] `schema_builder.py` `List[items_type]` / `create_model(**fields)`
  - [x] `sql_ui.py` `df_style_formatter` type for `Styler.format`
  - [x] `tests/test_cache_ttl.py` `_info` access
- [x] Remove `# pyright: ignore` comments; remove removed rule `PD901` from ruff ignore
- [x] Remaining manual ruff violations (ERA001, EM10x, SIM, B007, E721, F841, ...)
- [x] `task fix`: ruff + ty (Makefile removed; `task check`/`task test` added)
- [x] `.githooks/pre-commit`: black/isort/pycln/pyright → ruff + ty
- [x] CI (GitHub Actions): ruff, ty, pytest
- [x] `pyproject.toml`: drop `[metadata]`, empty `classifiers`, unused dev deps (isort, vermin, pyright)
- [x] Makefile/Taskfile: `st`/`docker` targets point to missing `app/` and `CHANGEME` (removed; Makefile and `publish` dropped)

## Step 2 — Bugs (regression test first, then fix)

Confirmed by probes:
1. [x] PEP 604 `X | None` is not treated as Optional (`get_origin` is `types.UnionType`,
   not `Union`): `int | None` → `text_input`, `Enum | None`/`list | None` lose
   selectbox/multiselect. `pydantic_utils.py` — introduce one `unwrap_optional()` helper.
2. [x] `schema_builder`: datetime → `str` (pydantic emits format `"date-time"`, code
   checks `"datetime"`).
3. [x] `schema_builder`: required field with `widget`/`kw` becomes optional
   (`default=None`); `$ref`/`$defs` (nested models, enums) unsupported.
4. [x] `_parse_array_string` regex uses `\\b` in a raw string: `'{"a,b",c,d}'` →
   `['a,b']`. Unify with the duplicate parser in `input_fields.input_array`.
5. [x] `InputFields.input_enum` (no-schema mode): `opts.index(Status.ACTIVE)` raises
   `ValueError` (`enums` holds names); label is the enum type name; no widget `key`.

From reading (verify with a test first):
6. [x] Cache keys miss inputs: `ExistingData.get_text/get_dt` keyed by
   `(table_name, updated)` but depend on `default_values` and current row;
   `DeleteRows.get_rows_str` keyed by `rows_id` only (other model, same ids).
7. [x] Global `stsql_*` session-state keys are shared between `SqlUi` instances on one
   page (pagination reset via `stsql_filters`, notifications, `opened`).
8. [x] `DeleteRows`: failure logged as success (no `success=False`); `s.get()` may
   return `None` → `s.delete(None)`.
9. [x] Falsy defaults (`False`, `0`) ignored: `if default_value:` in
   `CreateRow.get_sqlalchemy_fields` / `UpdateRow.get_sqlalchemy_updates`.
10. [x] Widget key collisions: no `key` on number/date/checkbox/enum inputs;
    `input_array` key lacks prefix; update form key lacks `key_prefix`.
11. [x] `input_str` returns the string `"None"` when nothing is selected.
12. [x] `@logger.catch()` on `generate_form_data` swallows errors and returns `None`.
13. [x] `col.type.python_type` raises `NotImplementedError` for `NullType`/custom types
    (e.g. `literal_column`) → filters crash.
14. [x] `_render_id_field` checks `key_prefix == "update"` (never true);
    `PydanticUndefined` detected via `repr`; `default_factory` ignored.

## Step 3 — Code cleanliness

- [x] No-schema `InputFields` number inputs (int/float/Numeric) start with the existing
  value, so nullable columns likely cannot be emptied on edit (same fix as pydantic M1)

- [x] Filter values are mirrored to URL query params named by column (global): two
  `SqlUi` instances filtering a same-named column share the filter — prefix with `key`
- [x] `stDatalist` labels use the raw column name (no-schema mode)
- [x] Unify the array parser in `input_fields.input_array` with `utils.parse_pg_array`

- [x] IDE `deprecated_instance_property` on `model_fields`: one typed helper
  `model_fields(schema) -> dict[str, FieldInfo]`
- [x] Make `_render_field_input` public (`render_field`) — used by `PydanticUi` and tests
- [x] Deduplicate: `_load_foreign_key_data`/`_load_many_to_many_data` (Create/UpdateRow),
  3× `show_dialog` wrappers, 3× schema validation in `SqlUi.__init__`,
  ~12× `getattr(model, '__tablename__', ...)`, 3× `is_optional`, 3× enum detection,
  `render` vs `render_with_columns`
- [x] Dead code: `get_fields`, `get_updates`, `save`, `_get_column_info`,
  `pydantic_to_sqlalchemy`, `sqlalchemy_to_pydantic`, `layout`, `id_to_object`,
  unreachable `elif` in `generate_form_data`, `lib.__main__`, commented `logger.debug`
- [x] Typing: `Literal` for `operation_type`, `TypedDict` for `foreign_key_options` /
  `many_to_many_fields`, return types everywhere
- [x] Fragile checks: `hasattr(v, 'value')` → `isinstance(v, Enum)`; `'JSON' in str(type)`;
  private `registry._class_registry` → `registry.mappers`; `rel.direction.value == 1`
  → `ONETOMANY`; `assert` used for control flow
- [x] Portuguese names `inicio`/`final` (also visible UI labels)
- [x] `get_pretty_name` → `functools.cache` instead of `st.cache_data`
- [x] Pydantic mode still builds `ExistingData`/`InputFields` (extra DB queries per dialog)
- [x] Tests for schema_builder, type detection, many-to-many, delete

Leftovers:
- [x] FK/M2M option-load errors are only logged (invisible with `disable_log=True`) —
  consider `st.warning` — done: also shown as `st.warning`
- [x] No-schema nullable-number row-switching not browser-verified (example app has no
  no-schema page) — done: example page `no_schema_numbers.py`, all checks pass
- [x] Stale example-repo scripts `test_final_verification.py`/`test_null_value_fix.py`
  patch the removed `_render_field_input` — done: deleted (untracked), with
  `test_render_with_submit.py`
- [x] Unsaved edits reappear when the edit dialog is reopened on the same row (closed
  with ×): widget keys lack the row id (`update_model.py:65`, `input_fields.py:180`)
  — done: dialogs rerun on dismiss and opening edit/create resets the form state
- [x] No-schema edit save overwrites an untouched JSON column with JSON `null`
  (data loss; seen on `test_data_types.metadata_json` in the example app) —
  columns without a widget now return `NO_INPUT` and are left out of the save
- [x] No-schema edit save truncates an untouched datetime to whole minutes
  (`created_datetime` 09:33:25.08 → 09:33:00) — `keep_unchanged_datetime`
  keeps the stored value when the minute-precision widget is unchanged (also
  in Pydantic mode)

## Step 4 — API decisions

- [ ] Remove deprecated `base_key` and `read_instance` + `edit_create_model` (before 1.0?)

## Step 5 — Module reorganization (done)

- [x] Stage 1: core helper modules — `typing_helpers`, `sa_model`, `values`, `display`;
  constants and `set_state` in `state`; `utils.py` dissolved, duplicates merged
- [x] Stage 2: dissolve `lib`/`read_cte`/`filters`/`many` into `query.py`,
  `pagination.py`, `filter_ui.py`, `form_options.py`, `one_to_many.py`; `lib` split
  into `logs.py`, `dialogs.py`, `db_errors.py`
- [x] Drop third-party Streamlit components (0.7.0): `table/pagination.py` uses
  `st.selectbox` (page size, "Show All" kept) + `st.pagination` with stable keys
  `{key}_page_size` / `{key}_pagination`; the remount trick is gone — the page goes
  to 1 on a filter or page-size change and is clamped to the last page when rows
  disappear, through `st.session_state`; the row range is an `st.caption`. Not
  `bind="query-params"`: the page param would be named by the widget key and share
  the `{key}_{column}` namespace of the filter params, a page is meaningless without
  the page size and filters, and the one-to-many panels live in dialogs.
  `InputFields.input_str` uses `st.selectbox(accept_new_options=True)`; nullable
  string columns seed their state and pass `index=None` so a stored value stays
  clearable (an index hides the clear button), NULL is no longer offered as a
  "None" option; `streamlit_antd_components` and `streamlit_datalist` dropped,
  `streamlit>=1.58` (lock: 1.66; AppTest tests adapted). Browser-verified on the
  example (pagination, panels, No-Schema string inputs, JSON clear)
- [x] Stage 3: `dialogs/` package (`frame`, `create`, `edit`, `delete`, `persist.py`
  with the shared M2M save + error block); `action_btns` → `sql_ui`;
  `create_delete_model.py`, `update_model.py`, `dialogs.py` removed
- [x] Stage 4: split `pydantic_utils` into `pydantic_form/` (field_info,
  option_resolve, widgets, generator); `validate_schema_compatibility` →
  `schema_check.py`; `PydanticSQLAlchemyConverter` and `pydantic_utils.py` removed;
  `state.clear_state_keys` and `widgets.nullable_number_input` shared
- [x] Stage 5: sub-packages so the public classes stand out; root keeps only
  `__init__`, `sql_ui`, `pydantic_ui`, `config_types`, `state`. `helpers/` (`typing`
  ← `typing_helpers`, `sa_model`, `values`, `display`, `logs`, `db_errors`), `table/`
  (`query`, `filter_ui`, `params`, `pagination`), `forms/` (`sa_fields` ←
  `input_fields`, `options` ← `form_options`, `schema_builder`, `schema_check`,
  `pydantic/` ← `pydantic_form/`), `dialogs/` (+ `one_to_many`: it opens the
  create/delete dialogs, so in `table/` it was a back-edge). Sub-package `__init__`
  files are docstring-only. `tests/test_import_layers.py` enforces state/config_types
  < helpers < table, forms < pydantic_ui < dialogs < sql_ui and no cycles
  (`pydantic_ui` sits below `dialogs/`, which build `PydanticCrudUi`;
  `forms/options` imports it only under `TYPE_CHECKING`). Packaging fixed first: the
  wheel shipped no sub-packages (`tests/test_packaging.py` + a wheel install/import
  gate in `scripts/release.sh`)

Side findings (stage 1, not fixed — behavior-preserving refactor):
- [ ] `update_model.py` (~line 115) applies the PK-typed `convert_numpy_to_python` to
  every column value, not only the primary key
- [x] `stsql_updated` is seeded with 1 by `SqlUi` but with 0 by the dialogs and
  `show_crud_dialog` (`set_state(UPDATED_KEY, ...)`) — 0.7.1: no longer seeded;
  `record_write` increments it and `session_writes` reads it with default 0
- [ ] `PydanticCrudUi.__init__` builds `PydanticInputGenerator` and session state twice
- [ ] Dead code: `UpdateRow` `dt_filters`/`no_dt_filters`;
  `if col_name is None` after `column_label` (the guards in
  `_render_foreign_key_selectbox`/`_render_many_to_many_multiselect` and
  `if operation == "read": pass` were removed in stage 4)
- [ ] `one_to_many.ReadManyRel.other_model` looks the model up inline (raises
  StopIteration/AttributeError) instead of `sa_model.model_by_tablename` (returns None)
- [ ] `InputFields.get_input_value` uses `col.description` (raises when None) rather
  than `column_label`

Side findings (stage 2, not fixed — behavior-preserving refactor):
- [ ] An enum-array column shows as `DepartmentTypeEnum.ENGINEERING` in the table
  (`_execute_with_pydantic_schema` list branch applies `str()`), seen on the
  example's No-Schema Numbers page
- [ ] `one_to_many.ReadManyRel.get_qtty_rows` is uncached and counts the PK, unlike
  `query.get_qtty_rows` (cached per `updated`); unify once the panel's refresh
  after create/delete is covered by a test
- [ ] `one_to_many` panels page without ORDER BY, so rows may move between pages
- [ ] `ReadManyRel.suffix_key` uses `__table__.name` while elsewhere `tablename()`
  uses `__tablename__`; `model` is untyped (`Any`) there because of it

Side findings (stage 3, not fixed — behavior-preserving refactor):
- [ ] A create/delete from a one-to-many panel keeps the edit dialog open and its
  Read tab stays stale (empty) until the dialog is reopened; same on stage 2
- [ ] Inside an edit dialog the panel's `CreateRow` form keeps the entered values
  after a successful save (plain `st.form`, no `clear_on_submit`)
- [ ] `handle_save_error` logs from `dialogs.persist` now, so the loguru record's
  module/function in "… failed for <table>" changed (message text unchanged)
- [ ] `CreateRow`/`UpdateRow` success paths still repeat `ss[UPDATED_KEY] += 1`,
  `log(...)` and the form-data cleanup; a `handle_save_ok` could share them
- [ ] Code comments in the dialogs still use `#` instead of the triple-quoted style

Side findings (stage 4, not fixed — behavior-preserving refactor):
- [ ] `PydanticCrudUi.__init__` still builds the generator twice (kept: each build
  runs `get_pydantic_field_info`, which calls user `default_factory`s, so dropping
  one is observable)
- [ ] The M2M fallback (options not loaded) logs two warnings; the second ("not found
  in foreign_key_options") always fires there and is misleading. Loguru records of
  the moved warnings now come from `pydantic_form.*` / `schema_check`
- [x] Clearing an optional JSON field on edit stores JSON `null`, not SQL NULL
  (SQLAlchemy `JSON` without `none_as_null=True`), seen on `metadata_json` — fixed
  in 0.7.0: `dialogs.persist.json_none_as_sql_null` writes `null()` on every save
  path (not for an attribute already None on the edited row: no needless UPDATE)
- [x] Example "Session State Demo": after `update_session_data` the text inputs and
  selectbox show stale/blank values while session data holds the loaded record
  (number inputs update); same on the stage 3 base — fixed: the browser keeps a
  keyed widget's value over `value=`, so every Pydantic widget now seeds its
  session state when it has none (`widgets.seed_widget_state`), which pushes it
- [ ] `render_field` takes `annotation` separately though `field_info["annotation"]`
  holds it; `foreign_key_data` / `many_to_many_data` are untyped dicts
- [ ] `pydantic_ui.py` comments still use `#` instead of the triple-quoted style

Side findings (stage 5, not fixed — behavior-preserving refactor):
- [ ] `table/` and `forms/` are peers only because `table/params` uses
  `forms.options.FkOpt` while `forms/options` uses `table.query`; moving `FkOpt`
  (a two-field dataclass) to `helpers/` or `config_types` would allow table < forms
- [ ] Loguru records of moved modules now carry the new module paths
  (`streamlit_pydantic_crud.helpers.logs`, …); `logger.disable` is prefix-based, so
  `set_logging` is unaffected
- [ ] Example project: `test_slider_interaction.py`, `test_number_input_widget.py`,
  `test_integration_null_fix.py` import removed modules (`pydantic_utils`,
  `update_model`, `create_delete_model`) — broken since stages 3–4
- [ ] A local `uv build` leaves `streamlit_pydantic_crud.egg-info/` in the tree; its
  stale `SOURCES.txt` makes a later sdist→wheel build ship files the config would
  not (it masked the packaging bug), hence the clean-copy build in the guards

Side findings (code review, not fixed):
- [ ] `SqlUi.set_structure` creates instance attributes outside `__init__`
  (`header_container`, `data_container`, `pag_container`, `expander_container`,
  `filter_container`, `btns_container`; IDE: "defined outside `__init__`"). Root
  cause: `__init__` renders the whole UI; declare them in `__init__` (or have
  `set_structure` return a containers dataclass) so the class shape is explicit
- [ ] One-to-many panel Create tab ignores `CreateRow.show()`'s result: no success
  or error message (a NOT NULL failure shows only in the server log); its Read tab
  stays stale until the dialog is reopened (example: Departments → Projects)
- [x] No-schema forms turn a string column with ≤ `string_enum_threshold` (10)
  distinct values into a selectbox of existing values, so a new value can't be
  typed (example: project name in the one-to-many Create tab) — 0.7.0:
  `input_str_enum` accepts new options too (a String column is not an Enum)
- [ ] `st.dataframe` logs an Arrow conversion traceback when a JSON column holds
  mixed-type lists (`convert_arrow` leaves list JSON as Python objects)
- [ ] Unconfirmed: a ticket saved `opened_on` 2025-12-07 while the date widget showed
  12-31 after an earlier attempt in the same dialog (may be a browser-tool artefact)

Side findings (0.7.0, not fixed):
- [x] Count/option caches are keyed by `stsql_updated`, which every new session
  restarts at 1, so a reloaded page can show a stale row count from another
  session for up to `CACHE_TTL_SECONDS` (seen twice: tickets after delete + reload,
  and Departments showing `1-5 / 5` with 4 rows right after a delete)
  — 0.7.1: keyed by a process-wide, thread-safe data version (`state.DATA_VERSION`)
  bumped by every write attempt (`record_write`); `stsql_updated` stays per session
  for dataframe keys and dialog reruns (`tests/test_shared_cache.py`)
- [ ] Moving the page through session state logs Streamlit's one-time "created with
  a default value but also had its value set via the Session State API" warning
  (with stack) once per server process; harmless, `st.pagination` always has a default
