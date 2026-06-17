"""YÖKTEZ anahtar kelime araması — islem=4 flow + sonuç kartı parse.

İki genel işlev sunar:
  * ``parse_results(html)``  — ham HTML'den ``SearchResult`` üretir (saf/senkron).
  * ``search_keyword(query)`` — POST yapar, 302 takip eder, parse eder (async).

Tasarım kararları:
  - Tüm ağ trafiği ``yoktez_mcp.http`` üzerinden geçer (throttle/session ortak).
  - İzin/Tur/yıl islem=4 POST'a EKLENMEMELİ — eklenirse "Geçersiz sorgulama".
  - 2000-sınırı dürüstçe raporlanır: ``coverage_complete = shown >= total_found``.
  - Eksik alan → None (savunmacı parse); hiçbir zaman uydurma içerik döndürme.
"""

from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup

from .http import post_form
from .models import SearchHit, SearchResult

# ---------------------------------------------------------------------------
# Sabitler
# ---------------------------------------------------------------------------

# nevi kodu: hangi alanda aranacak (islem=4 POST'u)
_FIELD_TO_NEVI: dict[str, str] = {
    "title": "1",
    "author": "2",
    "advisor": "3",
    "subject": "4",
    "keyword": "5",
    "abstract": "6",
    "all": "7",
}

# tip kodu: eşleşme modu (islem=4 POST'u)
_MATCH_TO_TIP: dict[str, str] = {
    "exact": "1",
    "contains": "2",
}

# Hata sayfasını saptamak için belirleyici metin
_ERROR_MARKER = "Geçersiz sorgulama"


# ---------------------------------------------------------------------------
# Özel istisna
# ---------------------------------------------------------------------------


class SearchError(Exception):
    """YÖKTEZ arama hatası (Geçersiz sorgulama veya beklenmedik hata sayfası)."""


# ---------------------------------------------------------------------------
# Yardımcı: sayı parse (Türkçe binlik ayracı nokta)
# ---------------------------------------------------------------------------


def _parse_turkish_int(s: str) -> int | None:
    """'2.059' → 2059; '2.000' → 2000. Hata durumunda None döner."""
    cleaned = s.strip().replace(".", "")
    if cleaned.isdigit():
        return int(cleaned)
    return None


# ---------------------------------------------------------------------------
# Yardımcı: referenceData JS nesnesini çıkar
# ---------------------------------------------------------------------------


def _extract_reference_data(html: str) -> dict:
    """Sayfa içindeki ``referenceData = {...};`` JS bloğunu parse eder.

    Bulunamazsa ya da parse edilemezse boş dict döner — savunmacı.
    """
    # JS sayfasında: `const referenceData = { ... };`
    # Blok büyük olabilir; re.DOTALL ile tüm sayfaya bakıyoruz.
    match = re.search(
        r"(?:const|var|let)\s+referenceData\s*=\s*(\{.*?\});\s*\n",
        html,
        re.DOTALL,
    )
    if not match:
        return {}
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}


# ---------------------------------------------------------------------------
# Yardımcı: yer → üniversite
# ---------------------------------------------------------------------------


def _yer_to_university(yer: str | None) -> str | None:
    """'FIRAT ÜNİVERSİTESİ / ' → 'FIRAT ÜNİVERSİTESİ'."""
    if not yer:
        return None
    return yer.split(" / ")[0].strip() or None


# ---------------------------------------------------------------------------
# Ana parse işlevi
# ---------------------------------------------------------------------------


def parse_results(html: str) -> SearchResult:
    """Ham HTML'den ``SearchResult`` üretir.

    - Hata sayfası → ``SearchError`` yükseltir.
    - Kart yok → ``hits=[]``, sayaçlar 0, ``coverage_complete=True``.
    - Eksik alan → None (hiçbir zaman uydurma veri döndürme).
    """
    if _ERROR_MARKER in html:
        raise SearchError(
            "YÖKTEZ arama hatası: 'Geçersiz sorgulama'. "
            "islem=4 POST'una izin/Tur/yıl eklendi mi?"
        )

    soup = BeautifulSoup(html, "lxml")

    # --- referenceData JS nesnesi ---
    ref_data = _extract_reference_data(html)

    # --- Sonuç kartları ---
    cards = soup.select("div.result-card")

    # --- 2000-cap metin bloğu ---
    count_div = soup.select_one("div.result-count-text")
    total_found: int | None = None
    shown: int | None = None

    if count_div:
        # Örnek: "Arama sonucunda  2.059 kayıt bulundu.\n2.000 tanesi görüntülenmektedir."
        # veya küçük setlerde: "Arama sonucunda  42 kayıt bulundu."
        text = count_div.get_text(" ", strip=True)
        numbers = re.findall(r"[\d.]+", text)
        parsed = [_parse_turkish_int(n) for n in numbers]
        parsed_valid = [x for x in parsed if x is not None]
        if len(parsed_valid) >= 2:
            total_found = parsed_valid[0]
            shown = parsed_valid[1]
        elif len(parsed_valid) == 1:
            total_found = parsed_valid[0]
            shown = None  # aşağıda kart sayısından doldurulacak

    # shown hâlâ None ise kart sayısından al
    if shown is None:
        shown = len(cards)
    if total_found is None:
        total_found = shown

    coverage_complete = shown >= total_found

    # --- Her kartı parse et ---
    hits: list[SearchHit] = []
    for card in cards:
        idx = card.get("data-index", "")
        kayit_no = card.get("data-kayitno", "")
        tez_no_enc = card.get("data-tezno")

        # .card-title → Türkçe başlık
        title_el = card.select_one("div.card-title")
        title_tr = title_el.get_text(strip=True) if title_el else None

        # İtalik .card-info → İngilizce başlık (style içinde font-style:italic)
        title_en: str | None = None
        for el in card.select("div.card-info"):
            style = el.get("style", "")
            if "italic" in style:
                title_en = el.get_text(strip=True)
                break

        # Tez No → <strong>Tez No:</strong> 1009908
        thesis_no: str | None = None
        for strong in card.select("strong"):
            if "Tez No" in strong.get_text():
                # Metni strong'un parent'ından al, strong metnini çıkar
                parent_text = strong.parent.get_text(strip=True) if strong.parent else ""
                # "Tez No: 1009908" → "1009908"
                no_match = re.search(r"Tez No:\s*(\d+)", parent_text)
                if no_match:
                    thesis_no = no_match.group(1)
                break

        # referenceData'dan meta al
        meta: dict = {}
        if idx and idx in ref_data:
            meta = ref_data[idx].get("meta", {})

        author = meta.get("author") or None
        year_str = meta.get("year")
        try:
            year = int(year_str) if year_str else None
        except (ValueError, TypeError):
            year = None
        university = _yer_to_university(meta.get("yer"))
        thesis_type = meta.get("type") or None

        if not kayit_no:
            # Kimliksiz kart atla (savunmacı)
            continue

        hits.append(
            SearchHit(
                kayit_no=kayit_no,
                tez_no=tez_no_enc,
                thesis_no=thesis_no,
                title_tr=title_tr,
                title_en=title_en,
                author=author,
                year=year,
                university=university,
                thesis_type=thesis_type,
            )
        )

    return SearchResult(
        hits=hits,
        total_found=total_found,
        shown=shown,
        coverage_complete=coverage_complete,
        source="live",
        notes=[],
    )


# ---------------------------------------------------------------------------
# Async arama işlevi
# ---------------------------------------------------------------------------


async def search_keyword(
    query: str,
    *,
    field: str = "title",
    match: str = "contains",
) -> SearchResult:
    """YÖKTEZ islem=4 anahtar kelime araması yapar.

    Parametreler
    ------------
    query : str
        Aranacak metin.
    field : str
        Hangi alanda aranacak. Geçerli değerler:
        ``title`` (varsayılan), ``author``, ``advisor``,
        ``subject``, ``keyword``, ``abstract``, ``all``.
    match : str
        Eşleşme modu: ``contains`` (varsayılan) veya ``exact``.

    Geri döner
    ----------
    SearchResult
        ``source="live"``, kapsam sayaçları ile birlikte.

    Hata
    ----
    SearchError
        Sunucu hata sayfası döndürürse (örn. geçersiz POST şekli).
    ValueError
        Geçersiz ``field`` veya ``match`` değeri.
    """
    nevi = _FIELD_TO_NEVI.get(field)
    if nevi is None:
        raise ValueError(
            f"Geçersiz field={field!r}. "
            f"Geçerli değerler: {list(_FIELD_TO_NEVI)}"
        )
    tip = _MATCH_TO_TIP.get(match)
    if tip is None:
        raise ValueError(
            f"Geçersiz match={match!r}. "
            f"Geçerli değerler: {list(_MATCH_TO_TIP)}"
        )

    # Doğrulanmış minimal islem=4 POST — izin/Tur/yıl EKLENMEMELİ.
    data = {
        "keyword": query,
        "keyword1": "",
        "keyword2": "",
        "ops_field": "and",
        "ops_field1": "and",
        "nevi": nevi,
        "tip": tip,
        "islem": "4",
    }

    resp = await post_form("SearchTez", data)
    html = resp.text
    return parse_results(html)
