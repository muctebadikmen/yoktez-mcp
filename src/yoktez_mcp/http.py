"""Paylaşılan, nazik (rate-limited + retry'li) async HTTP istemcisi — YÖKTEZ için.

YÖKTEZ (tez.yok.gov.tr) bir API sunmaz; tüm erişim JSP/HTML scraping ile yapılır.
Bu modül:
  * istekler arasında en az ``MIN_INTERVAL`` saniye boşluk bırakır,
  * eşzamanlılığı ``MAX_CONCURRENCY=1`` ile sınırlar,
  * 429 ve geçici 5xx (500/502/503/504) durumunda üstel backoff ile yeniden dener,
  * tek bir ``httpx.AsyncClient`` üzerinde ``JSESSIONID`` cookie'sini kalıcı tutar,
  * ``ensure_session()`` ile tarama.jsp'den oturum seed'ler (idempotent),
  * ``post_form()`` ile Referer+Origin başlıklı form POST yapar ve 302'yi takip eder.

Nazik kullanım parametreler ortam değişkeniyle (``YOKTEZ_`` öneki) override edilebilir.
Concurrency/throttle varsayılanlarını ASLA gevşetme — siteye saygı bir sözleşmedir.
"""

from __future__ import annotations

import asyncio
import os
import time

import httpx

from . import __version__

# ---------------------------------------------------------------------------
# Sabitler
# ---------------------------------------------------------------------------

BASE_URL = "https://tez.yok.gov.tr/UlusalTezMerkezi"

USER_AGENT = (
    f"yoktez-mcp/{__version__} "
    "(academic research MCP; +mdikment@gmail.com)"
)


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ[name])
    except (KeyError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ[name])
    except (KeyError, ValueError):
        return default


# Nazik kullanım parametreleri — ortam değişkeniyle override edilebilir.
# concurrency=1, ≥1 req/s throttle: hem dayanıklı hem de siteye saygılı.
MIN_INTERVAL: float = _env_float("YOKTEZ_MIN_INTERVAL", 1.0)    # saniye: istekler arası min boşluk
MAX_CONCURRENCY: int = _env_int("YOKTEZ_MAX_CONCURRENCY", 1)     # aynı anda en fazla istek
MAX_RETRIES: int = _env_int("YOKTEZ_MAX_RETRIES", 4)             # 429/503 için yeniden deneme sayısı
BACKOFF_BASE: float = _env_float("YOKTEZ_BACKOFF_BASE", 2.0)     # saniye: üstel backoff tabanı
DEFAULT_TIMEOUT: float = _env_float("YOKTEZ_TIMEOUT", 60.0)      # saniye

# Bu status kodlarında yeniden deneme yapılır.
_RETRY_STATUS = {429, 500, 502, 503, 504}

# ---------------------------------------------------------------------------
# Modül-düzeyi paylaşılan durum
# ---------------------------------------------------------------------------

_client: httpx.AsyncClient | None = None
_semaphore: asyncio.Semaphore | None = None
_rate_lock: asyncio.Lock | None = None
_last_request_ts: float = 0.0
_session_seeded: bool = False  # True → JSESSIONID zaten alındı, tekrar çekme


def _ensure() -> tuple[httpx.AsyncClient, asyncio.Semaphore, asyncio.Lock]:
    """Lazy başlatma: istemci, semaphore ve rate-lock'u döndürür."""
    global _client, _semaphore, _rate_lock
    if _client is None:
        _client = httpx.AsyncClient(
            headers={
                "User-Agent": USER_AGENT,
                "Accept-Encoding": "gzip, deflate",
            },
            timeout=DEFAULT_TIMEOUT,
            follow_redirects=False,  # 302'yi kendimiz takip ediyoruz (JSESSIONID görünür kalsın)
        )
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
    if _rate_lock is None:
        _rate_lock = asyncio.Lock()
    return _client, _semaphore, _rate_lock


# ---------------------------------------------------------------------------
# Yardımcı: throttle + backoff
# ---------------------------------------------------------------------------


async def _throttle() -> None:
    """İstek başlangıçları arasında MIN_INTERVAL saniye boşluk garantisi."""
    global _last_request_ts
    _, _, rate_lock = _ensure()
    async with rate_lock:
        now = time.monotonic()
        wait = MIN_INTERVAL - (now - _last_request_ts)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_request_ts = time.monotonic()


def _retry_after_seconds(resp: httpx.Response, attempt: int) -> float:
    """Retry-After başlığını oku; yoksa üstel backoff uygula."""
    header = resp.headers.get("Retry-After")
    if header:
        try:
            return float(header)
        except ValueError:
            pass
    return BACKOFF_BASE * (2**attempt)


# ---------------------------------------------------------------------------
# Genel GET
# ---------------------------------------------------------------------------


async def _get_with_retry(
    client: httpx.AsyncClient,
    url: str,
    params: dict | None = None,
) -> httpx.Response:
    """Semaphore almadan throttle + retry ile GET yapar (iç yardımcı).

    post_form gibi semaphore'u zaten elinde tutan çağrıcılar tarafından
    kullanılır — aksi halde semaphore deadlock'u oluşur.
    """
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        await _throttle()
        try:
            resp = await client.get(url, params=params)
        except (httpx.TransportError, httpx.TimeoutException) as exc:
            last_exc = exc
            if attempt >= MAX_RETRIES:
                raise
            await asyncio.sleep(BACKOFF_BASE * (2**attempt))
            continue

        if resp.status_code in _RETRY_STATUS and attempt < MAX_RETRIES:
            await asyncio.sleep(_retry_after_seconds(resp, attempt))
            continue

        resp.raise_for_status()
        return resp

    if last_exc:
        raise last_exc
    raise RuntimeError(f"İstek başarısız: {url}")


async def get(url: str, params: dict | None = None) -> httpx.Response:
    """Nazik GET: throttle + eşzamanlılık sınırı + 429/5xx retry.

    Başarılı (2xx/3xx) yanıtı döndürür; kalıcı hata durumunda
    ``httpx.HTTPStatusError`` yükseltir.
    """
    client, sem, _ = _ensure()
    async with sem:
        return await _get_with_retry(client, url, params=params)


async def get_text(url: str, params: dict | None = None) -> str:
    resp = await get(url, params=params)
    return resp.text


async def get_bytes(url: str, params: dict | None = None) -> bytes:
    resp = await get(url, params=params)
    return resp.content


# ---------------------------------------------------------------------------
# Oturum yönetimi
# ---------------------------------------------------------------------------


async def ensure_session() -> None:
    """JSESSIONID cookie'si yoksa tarama.jsp'den oturum seed'le (idempotent).

    YÖKTEZ, POST /SearchTez çağrısından önce geçerli bir JSESSIONID bekler.
    Bu fonksiyon, cookie jar'da JSESSIONID yoksa GET tarama.jsp yaparak
    sunucunun cookie set etmesini sağlar. Cookie zaten varsa hiçbir şey yapmaz.
    """
    global _session_seeded

    # Hızlı kontrol: modül flag'i set edilmişse çık.
    if _session_seeded:
        return

    client, _, _ = _ensure()

    # Cookie jar'da zaten JSESSIONID varsa flag'i set et ve çık.
    existing = client.cookies.get("JSESSIONID")
    if existing:
        _session_seeded = True
        return

    # JSESSIONID yok → tarama.jsp'yi çek (sunucu Set-Cookie gönderir).
    # Doğrudan get() kullan — semaphore henüz kimse elinde tutmuyor.
    await get(f"{BASE_URL}/tarama.jsp")
    _session_seeded = True


# ---------------------------------------------------------------------------
# Form POST (302 redirect takipli)
# ---------------------------------------------------------------------------


async def post_form(path: str, data: dict) -> httpx.Response:
    """Referer+Origin başlıklı application/x-www-form-urlencoded POST yapar.

    Akış:
      1. ``ensure_session()`` — JSESSIONID'nin var olduğundan emin ol.
      2. POST ``{BASE_URL}/{path}`` — Referer + Origin başlıkları ile.
      3. 302 yanıtı gelirse ``Location`` başlığındaki URL'ye GET yap
         (aynı session/cookie ile) ve o yanıtı döndür.
      4. 302 değilse yanıtı doğrudan döndür.

    Throttle + retry POST'a da uygulanır.
    """
    await ensure_session()

    client, sem, _ = _ensure()
    post_url = f"{BASE_URL}/{path}"
    headers = {
        "Referer": f"{BASE_URL}/tarama.jsp",
        "Origin": "https://tez.yok.gov.tr",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    last_exc: Exception | None = None

    async with sem:
        for attempt in range(MAX_RETRIES + 1):
            await _throttle()
            try:
                resp = await client.post(post_url, data=data, headers=headers)
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                last_exc = exc
                if attempt >= MAX_RETRIES:
                    raise
                await asyncio.sleep(BACKOFF_BASE * (2**attempt))
                continue

            if resp.status_code in _RETRY_STATUS and attempt < MAX_RETRIES:
                await asyncio.sleep(_retry_after_seconds(resp, attempt))
                continue

            # 302 → Location'a GET yap (aynı session ile; follow_redirects=False olduğundan
            # istemci otomatik takip etmiyor).
            # Semaphore zaten elimizde — get() değil, _get_with_retry() kullan (deadlock önlemi).
            if resp.status_code == 302:
                location = resp.headers.get("Location", "")
                if not location.startswith("http"):
                    # Göreceli URL → mutlak yap
                    location = f"https://tez.yok.gov.tr{location}"
                return await _get_with_retry(client, location)

            resp.raise_for_status()
            return resp

    if last_exc:
        raise last_exc
    raise RuntimeError(f"Form POST başarısız: {post_url}")


# ---------------------------------------------------------------------------
# Temizlik
# ---------------------------------------------------------------------------


async def aclose() -> None:
    """İstemciyi kapatır ve loop'a bağlı durumu sıfırlar.

    Semaphore/lock sıfırlanır ki (testlerde) farklı bir event loop'ta
    yeniden yaratılabilsinler; aksi halde 'bound to a different event loop' hatası olur.
    """
    global _client, _semaphore, _rate_lock, _last_request_ts, _session_seeded
    if _client is not None:
        try:
            await _client.aclose()
        except RuntimeError:
            # Farklı/kapalı bir event loop'ta yaratılmış olabilir (test izolasyonu).
            pass
        _client = None
    _semaphore = None
    _rate_lock = None
    _last_request_ts = 0.0
    _session_seeded = False
