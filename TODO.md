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

## Step 5 — Module reorganization

- [x] Stage 1: core helper modules — `typing_helpers`, `sa_model`, `values`, `display`;
  constants and `set_state` in `state`; `utils.py` dissolved, duplicates merged
- [ ] Stage 2: dissolve `lib`/`read_cte`/`filters`/`many` into `query.py`,
  `pagination.py`, `filter_ui.py`, `form_options.py`, `one_to_many.py`
- [ ] Stage 3: `dialogs/` package (create, edit, delete, `persist.py` with the shared
  M2M save + error block); `action_btns` → `sql_ui`
- [ ] Stage 4: split `pydantic_utils` into `pydantic_form/` (field_info,
  option_resolve, widgets, generator)

Side findings (stage 1, not fixed — behavior-preserving refactor):
- [ ] `update_model.py` (~line 115) applies the PK-typed `convert_numpy_to_python` to
  every column value, not only the primary key
- [ ] `stsql_updated` is seeded with 1 by `SqlUi` but with 0 by the dialogs and
  `show_crud_dialog` (`set_state(UPDATED_KEY, ...)`)
- [ ] `PydanticCrudUi.__init__` builds `PydanticInputGenerator` and session state twice
- [ ] Dead code: `UpdateRow` `dt_filters`/`no_dt_filters`; unreachable guards in
  `_render_foreign_key_selectbox`/`_render_many_to_many_multiselect`;
  `if operation == "read": pass`; `if col_name is None` after `column_label`
- [ ] `many.ReadManyRel.other_model` looks the model up inline (raises
  StopIteration/AttributeError) instead of `sa_model.model_by_tablename` (returns None)
- [ ] `InputFields.get_input_value` uses `col.description` (raises when None) rather
  than `column_label`
