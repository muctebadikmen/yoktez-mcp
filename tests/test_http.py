"""session-aware polite HTTP istemcisi — offline mock testleri.

Kapsam:
  * Throttle: ardışık iki get() çağrısı arasında MIN_INTERVAL kadar bekleme.
  * post_form: Referer/Origin başlıkları gönderir; 302'de Location'ı GET eder.
  * ensure_session: JSESSIONID yokken tarama.jsp'yi tam bir kez çeker; varken hiç çekmez.
  * 429 → backoff + retry.
  * @pytest.mark.live: gerçek siteye bağlanıp JSESSIONID cookie alır.
"""

from __future__ import annotations

import time

import httpx
import pytest

from yoktez_mcp import http

# ---------------------------------------------------------------------------
# Yardımcı — test başlangıcında modül durumunu sıfırla + hızlı parametreler
# ---------------------------------------------------------------------------


@pytest.fixture
def fast_client(monkeypatch):
    """Throttle/backoff'u sıfırla, istemciyi temizle."""
    monkeypatch.setattr(http, "MIN_INTERVAL", 0.0)
    monkeypatch.setattr(http, "BACKOFF_BASE", 0.0)
    http._client = None
    http._semaphore = None
    http._rate_lock = None
    http._last_request_ts = 0.0
    http._session_seeded = False


def _install_transport(handler) -> None:
    """MockTransport kurar; semaphore/lock _ensure() tarafından yeni yaratılır."""
    jar = httpx.Cookies()
    http._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        cookies=jar,
        follow_redirects=False,
    )
    http._semaphore = None
    http._rate_lock = None
    http._session_seeded = False


# ---------------------------------------------------------------------------
# Throttle testi
# ---------------------------------------------------------------------------


async def test_throttle_min_interval(monkeypatch):
    """İki ardışık get() çağrısı MIN_INTERVAL'dan az sürmemeli."""
    monkeypatch.setattr(http, "MIN_INTERVAL", 0.05)  # 50 ms — testi yavaşlatmaz, kanıtlar
    monkeypatch.setattr(http, "BACKOFF_BASE", 0.0)
    http._client = None
    http._semaphore = None
    http._rate_lock = None
    http._last_request_ts = 0.0

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="ok")

    _install_transport(handler)

    t0 = time.monotonic()
    await http.get(f"{http.BASE_URL}/tarama.jsp")
    await http.get(f"{http.BASE_URL}/tarama.jsp")
    elapsed = time.monotonic() - t0

    assert elapsed >= 0.05, f"Throttle beklenmedik şekilde atlandı: {elapsed:.3f}s"


# ---------------------------------------------------------------------------
# post_form: Referer + Origin başlıkları ve 302 takibi
# ---------------------------------------------------------------------------


async def test_post_form_headers_and_redirect_follow(fast_client):
    """post_form:
    - Referer ve Origin başlıklarını doğru gönderir.
    - 302 yanıtında Location'a GET yapar ve o yanıtı döndürür.
    """
    requests_seen: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        requests_seen.append(req)
        if req.method == "GET" and "tarama.jsp" in str(req.url):
            # ensure_session çağrısı — JSESSIONID ver
            return httpx.Response(
                200,
                headers={"Set-Cookie": "JSESSIONID=TESTID; Path=/"},
                text="tarama",
            )
        if req.method == "POST":
            return httpx.Response(
                302,
                headers={"Location": f"{http.BASE_URL}/tezSorguSonucYeni.jsp?q=test"},
            )
        # Redirect GET
        return httpx.Response(200, text="sonuc sayfasi")

    _install_transport(handler)

    resp = await http.post_form("SearchTez", {"Tur": "1", "islem": "4"})

    # Sonuç, redirect'in sonundaki 200 olmalı
    assert resp.status_code == 200
    assert "sonuc sayfasi" in resp.text

    # POST isteğinde Referer ve Origin olmalı
    post_req = next(r for r in requests_seen if r.method == "POST")
    assert "Referer" in post_req.headers
    assert "tarama.jsp" in post_req.headers["Referer"]
    assert post_req.headers.get("Origin") == "https://tez.yok.gov.tr"


# ---------------------------------------------------------------------------
# post_form: root-relative ve protocol-relative Location çözümlemesi
# ---------------------------------------------------------------------------


async def test_post_form_root_relative_redirect(fast_client):
    """302 Location root-relative (/yol) olduğunda, doğru mutlak URL'e GET yapılmalı.

    Eski `if not location.startswith("http")` kodu bu durumu kırıyordu çünkü
    '/UlusalTezMerkezi/...' gibi bir yolu 'https://tez.yok.gov.tr/UlusalTezMerkezi/...'
    olarak birleştiriyordu; resp.url.join() ise RFC-3986'ya göre origin'i korur.
    """
    requests_seen: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        requests_seen.append(req)
        if req.method == "GET" and "tarama.jsp" in str(req.url):
            return httpx.Response(
                200,
                headers={"Set-Cookie": "JSESSIONID=TESTID; Path=/"},
                text="tarama",
            )
        if req.method == "POST":
            # Root-relative Location — no host, starts with '/'
            return httpx.Response(
                302,
                headers={"Location": "/UlusalTezMerkezi/tezSorguSonucYeni.jsp"},
            )
        # Redirect GET — must land on the correct absolute URL
        return httpx.Response(200, text="redirect-sonuc")

    _install_transport(handler)

    resp = await http.post_form("SearchTez", {"Tur": "1", "islem": "4"})

    assert resp.status_code == 200
    assert "redirect-sonuc" in resp.text

    # The redirect GET must have been made to the fully-resolved absolute URL.
    redirect_get = next(
        (r for r in requests_seen if r.method == "GET" and "tezSorguSonucYeni" in str(r.url)),
        None,
    )
    assert redirect_get is not None, "Redirect GET isteği bulunamadı"
    resolved = str(redirect_get.url)
    assert resolved.startswith("https://tez.yok.gov.tr"), (
        f"Redirect URL beklenen host'ta değil: {resolved}"
    )
    assert "/UlusalTezMerkezi/tezSorguSonucYeni.jsp" in resolved


# ---------------------------------------------------------------------------
# ensure_session: idempotent — cookie varsa tarama.jsp'ye gitme
# ---------------------------------------------------------------------------


async def test_ensure_session_fetches_once_when_no_cookie(fast_client):
    """JSESSIONID yokken tarama.jsp tam bir kez çekilmeli."""
    tarama_calls = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        if "tarama.jsp" in str(req.url):
            tarama_calls["n"] += 1
            return httpx.Response(
                200,
                headers={"Set-Cookie": "JSESSIONID=TESTID; Path=/"},
                text="tarama",
            )
        return httpx.Response(200, text="ok")

    _install_transport(handler)

    await http.ensure_session()
    await http.ensure_session()  # ikinci çağrı — cookie zaten var

    assert tarama_calls["n"] == 1, "tarama.jsp sadece bir kez çekilmeli"


async def test_ensure_session_noop_when_cookie_present(fast_client):
    """JSESSIONID cookie jar'da mevcutsa tarama.jsp HİÇ çekilmemeli."""
    tarama_calls = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        if "tarama.jsp" in str(req.url):
            tarama_calls["n"] += 1
        return httpx.Response(200, text="ok")

    _install_transport(handler)

    # Cookie'yi elle ekle
    http._client.cookies.set("JSESSIONID", "EXISTING_ID", domain="tez.yok.gov.tr")
    http._session_seeded = True  # flag'i de set et

    await http.ensure_session()

    assert tarama_calls["n"] == 0, "Cookie varken tarama.jsp çekilmemeli"


async def test_ensure_session_noop_when_cookie_present_but_flag_false(fast_client):
    """_session_seeded=False olsa bile cookie jar'da JSESSIONID varsa
    tarama.jsp HİÇ çekilmemeli (sadece flag set edilmeli).

    Bu, process restart sonrası cookie'nin başka yoldan enjekte edildiği
    durumu kapsar — ensure_session() gereksiz yere tarama.jsp çekmemeli.
    """
    tarama_calls = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        if "tarama.jsp" in str(req.url):
            tarama_calls["n"] += 1
        return httpx.Response(200, text="ok")

    _install_transport(handler)

    # Cookie mevcut ama flag henüz False
    http._client.cookies.set("JSESSIONID", "INJECTED_ID", domain="tez.yok.gov.tr")
    assert http._session_seeded is False  # pre-condition

    await http.ensure_session()

    assert tarama_calls["n"] == 0, (
        "_session_seeded=False iken mevcut JSESSIONID varsa tarama.jsp çekilmemeli"
    )
    assert http._session_seeded is True, "ensure_session() flag'i True yapmalıydı"


# ---------------------------------------------------------------------------
# 429 → retry
# ---------------------------------------------------------------------------


async def test_429_triggers_retry(fast_client, monkeypatch):
    """429 alındığında en az bir kez daha denenmeli."""
    monkeypatch.setattr(http, "MAX_RETRIES", 2)
    calls = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, text="rate limited")
        return httpx.Response(200, text="ok")

    _install_transport(handler)
    resp = await http.get(f"{http.BASE_URL}/tarama.jsp")
    assert resp.status_code == 200
    assert calls["n"] == 2


async def test_persistent_429_raises(fast_client, monkeypatch):
    """MAX_RETRIES'i aşan kalıcı 429 → HTTPStatusError."""
    monkeypatch.setattr(http, "MAX_RETRIES", 2)

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="rate limited")

    _install_transport(handler)
    with pytest.raises(httpx.HTTPStatusError):
        await http.get(f"{http.BASE_URL}/tarama.jsp")


# ---------------------------------------------------------------------------
# Live test — gerçek siteye bağlanır (CI'da atlanır: -m "not live")
# ---------------------------------------------------------------------------


@pytest.mark.live
async def test_live_ensure_session_yields_jsessionid():
    """Gerçek YÖKTEZ sunucusuna bağlanıp JSESSIONID cookie almalı."""
    await http.ensure_session()
    client, _, _ = http._ensure()
    cookies = dict(client.cookies)
    assert "JSESSIONID" in cookies, f"JSESSIONID bulunamadı; mevcut cookie'ler: {cookies}"
    await http.aclose()
