"""The process-wide data version keys the caches shared by all sessions."""

from concurrent.futures import ThreadPoolExecutor

from streamlit_pydantic_crud.state import DataVersion, bump_data_version, data_version

THREADS = 8
BUMPS = 1000


def test_bump_moves_the_global_version() -> None:
    before = data_version()
    bump_data_version()
    assert data_version() == before + 1


def test_bumps_from_many_threads_are_not_lost() -> None:
    """Sessions run in their own threads; concurrent writes all count."""
    version = DataVersion()
    start = version.current

    def handle_bumps() -> None:
        for _ in range(BUMPS):
            version.bump()

    with ThreadPoolExecutor(THREADS) as pool:
        for _ in range(THREADS):
            pool.submit(handle_bumps)

    assert version.current == start + THREADS * BUMPS


def test_new_counter_does_not_reuse_old_values() -> None:
    """A re-created counter (module reload) must not collide with cached keys."""
    old = DataVersion()
    old.bump()
    assert DataVersion().current > old.current
