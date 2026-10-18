"""pandas stays behind the deprecated Styler adapter until it is dropped (0.10.0).

The allowlists are exact: a module that gains or loses pandas must update them.
"""

import ast
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parent.parent / "streamlit_pydantic_crud"
"""Modules importing pandas at runtime, with the reason they still may."""
RUNTIME_PANDAS = {
    "table/styler_compat.py": "deprecated df_style_formatter / style_fn / SqlUi.df",
    "table/filter_ui.py": "removed by Task 7 (pd.Series hash func)",
    "dialogs/one_to_many.py": "removed by Task 7 (related-rows DataFrame)",
}
"""Modules importing pandas only under ``if TYPE_CHECKING:`` (annotations)."""
TYPE_ONLY_PANDAS = {
    "sql_ui.py": "SqlUi.df return type and the Styler passed to st.dataframe",
}


def test_runtime_pandas_imports_match_allowlist() -> None:
    found = {name for name, (runtime, _) in pandas_imports().items() if runtime}
    assert found == set(RUNTIME_PANDAS), (
        "pandas belongs in table/styler_compat.py only; update RUNTIME_PANDAS if "
        "a listed module dropped pandas (e.g. after Task 7 merged)"
    )


def test_type_only_pandas_imports_match_allowlist() -> None:
    found = {
        name
        for name, (runtime, type_only) in pandas_imports().items()
        if type_only and not runtime
    }
    assert found == set(TYPE_ONLY_PANDAS)


def test_scanner_tells_runtime_from_type_checking_imports() -> None:
    source = (
        "from typing import TYPE_CHECKING\n"
        "import pandas.io\n"
        "if TYPE_CHECKING:\n"
        "    from pandas import DataFrame\n"
    )
    assert scan(ast.parse(source)) == (True, True)
    assert scan(ast.parse("import pandastic\nimport numpy")) == (False, False)


def pandas_imports() -> dict[str, tuple[bool, bool]]:
    """Map package modules importing pandas to (runtime, type-only) flags."""
    found = {}
    for path in sorted(PKG_DIR.rglob("*.py")):
        flags = scan(ast.parse(path.read_text()))
        if any(flags):
            found[path.relative_to(PKG_DIR).as_posix()] = flags
    return found


def scan(tree: ast.Module) -> tuple[bool, bool]:
    """Return whether `tree` imports pandas at runtime / under TYPE_CHECKING."""
    guarded = {
        id(node)
        for block in tree.body
        if isinstance(block, ast.If) and is_type_checking(block.test)
        for node in ast.walk(block)
    }
    runtime = type_only = False
    for node in ast.walk(tree):
        if imports_pandas(node):
            if id(node) in guarded:
                type_only = True
            else:
                runtime = True
    return runtime, type_only


def is_type_checking(test: ast.expr) -> bool:
    """True for ``TYPE_CHECKING`` or ``typing.TYPE_CHECKING``."""
    if isinstance(test, ast.Name):
        return test.id == "TYPE_CHECKING"
    return isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"


def imports_pandas(node: ast.AST) -> bool:
    """True if `node` is an import of pandas or one of its submodules."""
    if isinstance(node, ast.Import):
        return any(alias.name.split(".")[0] == "pandas" for alias in node.names)
    if isinstance(node, ast.ImportFrom):
        return node.level == 0 and (node.module or "").split(".")[0] == "pandas"
    return False
