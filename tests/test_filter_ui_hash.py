"""The ColFilter hasher must stay keyed to the class wherever it lives.

Streamlit matches a string key against ``module.qualname``; a stale string left
behind by a module move would silently disable the hasher.
"""

import importlib

from streamlit_pydantic_crud.filter_ui import ColFilter, hash_funcs


def test_col_filter_hash_key_matches_class() -> None:
    """ColFilter is keyed by the class or by its current qualified name."""
    qualified = f"{ColFilter.__module__}.{ColFilter.__qualname__}"
    assert ColFilter in hash_funcs or qualified in hash_funcs


def test_string_hash_keys_resolve_to_classes() -> None:
    """Every string key names a class that still exists at that path."""
    for key in (k for k in hash_funcs if isinstance(k, str)):
        module_name, _, attr = key.rpartition(".")
        module = importlib.import_module(module_name)
        assert isinstance(getattr(module, attr, None), type), key
