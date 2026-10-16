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

- [x] Filter values are mirrored to URL query params named by column (global): two
  `SqlUi` instances filtering a same-named column share the filter — prefix with `key`
- [ ] `stDatalist` labels use the raw column name (no-schema mode)
- [ ] Unify the array parser in `input_fields.input_array` with `utils.parse_pg_array`

- [ ] IDE `deprecated_instance_property` on `model_fields`: one typed helper
  `model_fields(schema) -> dict[str, FieldInfo]`
- [ ] Make `_render_field_input` public (`render_field`) — used by `PydanticUi` and tests
- [ ] Deduplicate: `_load_foreign_key_data`/`_load_many_to_many_data` (Create/UpdateRow),
  3× `show_dialog` wrappers, 3× schema validation in `SqlUi.__init__`,
  ~12× `getattr(model, '__tablename__', ...)`, 3× `is_optional`, 3× enum detection,
  `render` vs `render_with_columns`
- [ ] Dead code: `get_fields`, `get_updates`, `save`, `_get_column_info`,
  `pydantic_to_sqlalchemy`, `sqlalchemy_to_pydantic`, `layout`, `id_to_object`,
  unreachable `elif` in `generate_form_data`, `lib.__main__`, commented `logger.debug`
- [ ] Typing: `Literal` for `operation_type`, `TypedDict` for `foreign_key_options` /
  `many_to_many_fields`, return types everywhere
- [ ] Fragile checks: `hasattr(v, 'value')` → `isinstance(v, Enum)`; `'JSON' in str(type)`;
  private `registry._class_registry` → `registry.mappers`; `rel.direction.value == 1`
  → `ONETOMANY`; `assert` used for control flow
- [ ] Portuguese names `inicio`/`final` (also visible UI labels)
- [ ] `get_pretty_name` → `functools.cache` instead of `st.cache_data`
- [ ] Pydantic mode still builds `ExistingData`/`InputFields` (extra DB queries per dialog)
- [ ] Tests for schema_builder, type detection, many-to-many, delete

## Step 4 — API decisions

- [ ] Remove deprecated `base_key` and `read_instance` + `edit_create_model` (before 1.0?)
