"""Intra-package imports follow the layer order and form no cycles.

Layers, lowest first: state/config_types < helpers < table < forms < pydantic_ui
< dialogs < sql_ui < the package __init__. A module may import its own layer or
any lower one; imports under ``if TYPE_CHECKING:`` are not runtime edges.
"""

import ast
from collections.abc import Iterator
from pathlib import Path

PKG_NAME = "streamlit_pydantic_crud"
PKG_DIR = Path(__file__).resolve().parent.parent / PKG_NAME
ROOT_INIT = "__init__"
LAYERS: tuple[tuple[str, ...], ...] = (
    ("state", "config_types"),
    ("helpers",),
    ("table",),
    ("forms",),
    ("pydantic_ui",),
    ("dialogs",),
    ("sql_ui",),
    (ROOT_INIT,),
)
type Graph = dict[str, set[str]]


def test_every_module_has_a_layer() -> None:
    """A new top-level module or sub-package must be placed in LAYERS."""
    unplaced = [name for name in discover_modules() if layer_of(name) is None]
    assert unplaced == []


def test_imports_follow_layer_order() -> None:
    assert layer_violations(build_graph()) == []


def test_import_graph_has_no_cycles() -> None:
    assert find_cycle(build_graph()) is None


def test_subpackage_inits_import_nothing() -> None:
    """Sub-package __init__ files stay docstring-only so they cannot cycle."""
    graph = build_graph()
    subpackages = [name for name in discover_modules() if is_subpackage(name)]
    assert subpackages, "no sub-packages found"
    assert {name: graph[name] for name in subpackages if graph[name]} == {}


def test_checker_flags_back_edge() -> None:
    graph: Graph = {"helpers.values": {"table.query"}, "table.query": set()}
    assert layer_violations(graph) == ["helpers.values -> table.query"]


def test_checker_flags_table_importing_forms() -> None:
    """table/ sits strictly below forms/, so it may not import from it."""
    graph: Graph = {"table.params": {"forms.options"}, "forms.options": set()}
    assert layer_violations(graph) == ["table.params -> forms.options"]


def test_checker_flags_cycle() -> None:
    graph: Graph = {"forms.options": {"table.params"}, "table.params": set()}
    assert find_cycle(graph) is None
    graph["table.params"].add("forms.options")
    assert find_cycle(graph) == ["forms.options", "table.params", "forms.options"]


def test_checker_ignores_type_checking_imports() -> None:
    source = (
        "from typing import TYPE_CHECKING\n"
        f"from {PKG_NAME}.helpers import values\n"
        "if TYPE_CHECKING:\n"
        f"    from {PKG_NAME}.pydantic_ui import PydanticCrudUi\n"
    )
    modules = discover_modules()
    assert imported_modules(ast.parse(source), "forms.options", modules) == {
        "helpers.values"
    }


def build_graph() -> Graph:
    """Map each package module (dotted, relative to the package) to its imports."""
    modules = discover_modules()
    return {
        name: imported_modules(ast.parse(path.read_text()), name, modules)
        for name, path in modules.items()
    }


def layer_violations(graph: Graph) -> list[str]:
    """Edges that import from a higher layer than the importing module's."""
    violations = []
    for importer, imported in sorted(graph.items()):
        for target in sorted(imported):
            src_layer, dst_layer = layer_of(importer), layer_of(target)
            if src_layer is None or dst_layer is None or dst_layer > src_layer:
                violations.append(f"{importer} -> {target}")
    return violations


def find_cycle(graph: Graph) -> list[str] | None:
    """Return one import cycle as a closed path, or None if the graph is a DAG."""
    done: set[str] = set()
    for start in sorted(graph):
        cycle = walk_for_cycle(graph, start, [], done)
        if cycle is not None:
            return cycle
    return None


def walk_for_cycle(
    graph: Graph, node: str, path: list[str], done: set[str]
) -> list[str] | None:
    """Depth-first search; ``path`` holds the modules currently being visited."""
    if node in path:
        return [*path[path.index(node) :], node]
    if node in done:
        return None
    path.append(node)
    for target in sorted(graph.get(node, set())):
        cycle = walk_for_cycle(graph, target, path, done)
        if cycle is not None:
            return cycle
    path.pop()
    done.add(node)
    return None


def discover_modules() -> dict[str, Path]:
    """Dotted module names relative to the package; the root __init__ is special."""
    modules = {}
    for path in sorted(PKG_DIR.rglob("*.py")):
        parts = path.relative_to(PKG_DIR).with_suffix("").parts
        if parts[-1] == "__init__":
            parts = parts[:-1]
        modules[".".join(parts) or ROOT_INIT] = path
    return modules


def layer_of(module: str) -> int | None:
    """Index in LAYERS of the module's top-level component."""
    top = module.split(".", maxsplit=1)[0]
    return next((i for i, names in enumerate(LAYERS) if top in names), None)


def is_subpackage(module: str) -> bool:
    return module != ROOT_INIT and (PKG_DIR / module.replace(".", "/")).is_dir()


def imported_modules(
    tree: ast.AST, importer: str, modules: dict[str, Path]
) -> set[str]:
    """Package modules imported by ``tree``, skipping TYPE_CHECKING blocks."""
    found = set()
    for node in runtime_nodes(tree):
        if isinstance(node, ast.Import):
            found |= {
                resolve(alias.name, modules)
                for alias in node.names
                if is_package_path(alias.name)
            }
        elif isinstance(node, ast.ImportFrom):
            base = absolute_from(node, importer, modules)
            if base is None:
                continue
            for alias in node.names:
                found.add(resolve(f"{base}.{alias.name}", modules))
    found.discard(importer)
    return found


def runtime_nodes(tree: ast.AST) -> Iterator[ast.AST]:
    """Walk the tree like ast.walk, but not into ``if TYPE_CHECKING:`` bodies."""
    stack = [tree]
    while stack:
        node = stack.pop()
        yield node
        if isinstance(node, ast.If) and is_type_checking(node.test):
            stack.extend(node.orelse)
            continue
        stack.extend(ast.iter_child_nodes(node))


def is_type_checking(test: ast.expr) -> bool:
    if isinstance(test, ast.Name):
        return test.id == "TYPE_CHECKING"
    return isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"


def absolute_from(
    node: ast.ImportFrom, importer: str, modules: dict[str, Path]
) -> str | None:
    """Absolute dotted base of a ``from X import`` inside the package, else None."""
    if node.level == 0:
        name = node.module or ""
        return name if is_package_path(name) else None
    is_pkg = modules[importer].name == "__init__.py"
    parts = [] if importer == ROOT_INIT else importer.split(".")
    package = parts if is_pkg else parts[:-1]
    package = package[: len(package) - (node.level - 1)]
    base = ".".join([PKG_NAME, *package])
    return f"{base}.{node.module}" if node.module else base


def is_package_path(name: str) -> bool:
    return name == PKG_NAME or name.startswith(f"{PKG_NAME}.")


def resolve(dotted: str, modules: dict[str, Path]) -> str:
    """Longest package module that ``dotted`` names or lives in."""
    parts = dotted.split(".")[1:]
    while parts:
        candidate = ".".join(parts)
        if candidate in modules:
            return candidate
        parts.pop()
    return ROOT_INIT
