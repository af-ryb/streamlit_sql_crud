"""The built wheel ships every module of the package, and nothing else.

Consumers install from git, so a sub-package missing from the wheel only shows
up as an ImportError on their machine. Set SKIP_WHEEL_BUILD=1 to skip offline.
"""

import os
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PKG_NAME = "streamlit_pydantic_crud"
SOURCE_FILES = ("pyproject.toml", "README.md", "LICENSE")

pytestmark = pytest.mark.skipif(
    os.environ.get("SKIP_WHEEL_BUILD") == "1" or shutil.which("uv") is None,
    reason="wheel build disabled (SKIP_WHEEL_BUILD=1) or uv not installed",
)


def test_wheel_contains_every_package_module(tmp_path: Path) -> None:
    """Every .py under the package dir is in the wheel; no stray modules."""
    wheel = build_wheel(tmp_path)
    with zipfile.ZipFile(wheel) as zf:
        shipped = {
            name
            for name in zf.namelist()
            if name.endswith(".py") and ".dist-info/" not in name
        }
    on_disk = {
        path.relative_to(REPO_ROOT).as_posix()
        for path in (REPO_ROOT / PKG_NAME).rglob("*.py")
        if "__pycache__" not in path.parts
    }
    assert on_disk - shipped == set(), "modules missing from the wheel"
    assert shipped - on_disk == set(), "wheel ships files not in the package"


def build_wheel(tmp_path: Path) -> Path:
    """Build from a clean copy, as a fresh checkout would.

    An in-tree egg-info keeps stale file lists that would mask a missing package.
    """
    src = tmp_path / "src"
    shutil.copytree(
        REPO_ROOT / PKG_NAME,
        src / PKG_NAME,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    for name in SOURCE_FILES:
        shutil.copy2(REPO_ROOT / name, src / name)
    out_dir = tmp_path / "dist"
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    subprocess.run(
        ["uv", "build", "--wheel", "--quiet", "--out-dir", str(out_dir), str(src)],
        check=True,
        env=env,
        cwd=src,
    )
    wheels = list(out_dir.glob("*.whl"))
    assert len(wheels) == 1, wheels
    return wheels[0]
