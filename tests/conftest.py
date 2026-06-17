import os
from pathlib import Path

import pytest

# Testlerde arka-plan yenileme / canlı ağ çağrısı olmasın → offline testler ağa çıkmaz.
os.environ.setdefault("YOKTEZ_DIRECTORY_REFRESH", "0")

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def _reset_shared_async_state():
    """Her testten sonra loop'a bağlı paylaşılan durumu sıfırla → testler arası
    'Event loop is closed' sızıntılarını önler (offline + live birlikte çalışınca).
    Modüller henüz yoksa (scaffold aşaması) sessizce devam et."""
    yield
    try:
        from yoktez_mcp import http as _http

        _http._client = None  # httpx istemcisi loop'a bağlı; süreç sonunda serbest kalır
        _http._semaphore = None
        _http._rate_lock = None
        _http._last_request_ts = 0.0
        _http._session_seeded = False
    except ImportError:
        pass

    try:
        from yoktez_mcp.cache import default_cache as _cache

        _cache._locks.clear()  # asyncio.Lock'lar loop'a bağlı; temizle
    except ImportError:
        pass


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


def read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")
