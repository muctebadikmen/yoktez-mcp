"""yoktez_mcp.facets — YÖKTEZ facet verileri: ABD, üniversiteler, enum kod tabloları.

Hem bellekte sabit tutulan ENUMS sözlüğünü hem de ``data/facets.json``'dan yüklenen
büyük listeleri (5 132 ABD + 260+ üniversite) sağlar.

Temel arayüzler:
    ENUMS          : dict — Tur/izin/Durum/Dil/nevi/tip kod→etiket tabloları
    parse_abd(html) -> list[dict]   — getAllABD HTML'inden {kod, name} listesi
    parse_universities(json_text) -> list[dict] — getUniversities JSON'undan {kod, name, yoksis_id}
    load_facets() -> dict           — data/facets.json'u okur
    find_university(query) -> list[dict]  — Türkçe-duyarlı isim araması
    find_abd(query) -> list[dict]         — Türkçe-duyarlı ABD araması
"""

from __future__ import annotations

import importlib.resources
import json
import re

from .text import tr_fold

# ---------------------------------------------------------------------------
# ENUMS — YÖKTEZ form kod tabloları (FINDINGS.md §3'ten doğrulanmış)
# ---------------------------------------------------------------------------

ENUMS: dict[str, dict[int, str]] = {
    # Tez türü (thesis type)
    "Tur": {
        1: "Yüksek Lisans",
        2: "Doktora",
        3: "Tıpta Uzmanlık",
        4: "Sanatta Yeterlik",
        5: "Diş Hekimliği Uzmanlık",
        6: "Tıpta Yan Dal Uzmanlık",
        7: "Eczacılıkta Uzmanlık",
    },
    # Erişim izni (access permission)
    "izin": {
        0: "Seçiniz",
        1: "İzinli",
        2: "İzinsiz",
    },
    # Onay durumu (approval status)
    "Durum": {
        0: "Tümü",
        1: "Hazırlanıyor",
        3: "Onaylandı",
    },
    # Dil (language) — YÖKTEZ'de 1-46 arası aralıklı; yaygın olanlar dahil
    "Dil": {
        1: "Türkçe",
        2: "İngilizce",
        3: "Arapça",
        4: "Fransızca",
        5: "Almanca",
        6: "İspanyolca",
        7: "İtalyanca",
        8: "Rusça",
        9: "Japonca",
        10: "Çince",
        11: "Farsça",
        12: "Kürtçe",
        13: "Azerbaycanca",
        14: "Osmanlıca",
    },
    # Arama alanı (search field — islem=4 GForm2'ye özgü)
    "nevi": {
        1: "Tez Adı",
        2: "Yazar",
        3: "Danışman",
        4: "Konu",
        5: "Anahtar Kelime",
        6: "Özet",
        7: "Tümü",
    },
    # Eşleşme modu (match mode — islem=4 GForm2'ye özgü)
    "tip": {
        1: "exact",
        2: "contains",
    },
}

# ---------------------------------------------------------------------------
# HTML/JSON ayrıştırıcılar
# ---------------------------------------------------------------------------

# <label class="option-item">
#   <input ... ad="ABD ADI" kod="NUMERIC" ...>
#   <span>...</span>
# </label>
_ABD_PATTERN = re.compile(
    r'<input\b[^>]*\bad="([^"]+)"[^>]*\bkod="(\d+)"[^>]*/?>',
    re.IGNORECASE,
)
# Alternatif sıra: kod önce gelebilir
_ABD_PATTERN_ALT = re.compile(
    r'<input\b[^>]*\bkod="(\d+)"[^>]*\bad="([^"]+)"[^>]*/?>',
    re.IGNORECASE,
)


def parse_abd(html: str) -> list[dict]:
    """``getAllABD`` HTML yanıtından ABD listesi oluşturur.

    Her ``<input>`` etiketinin ``ad`` ve ``kod`` niteliklerini çıkarır.
    Sonuç: ``[{"kod": "2821", "name": "ABAZA DİLİ VE EDEBİYATI ANABİLİM DALI"}, ...]``

    Sadece ``option-item`` etiketlerini hedefler; başka girdi elemanları varsa
    onları atlar.
    """
    if not html:
        return []

    # option-item label bloklarını bul
    label_blocks = re.findall(
        r'<label\s+class="option-item">.*?</label>',
        html,
        re.DOTALL,
    )

    result: list[dict] = []
    for block in label_blocks:
        m = _ABD_PATTERN.search(block)
        if m:
            name, kod = m.group(1), m.group(2)
            result.append({"kod": kod, "name": name})
            continue
        # Alternatif sıra
        m2 = _ABD_PATTERN_ALT.search(block)
        if m2:
            kod, name = m2.group(1), m2.group(2)
            result.append({"kod": kod, "name": name})

    return result


def parse_universities(json_text: str) -> list[dict]:
    """``getUniversities.jsp`` JSON yanıtından üniversite listesi oluşturur.

    Giriş: ``[{"kod": "<encrypted>", "displayName": "...", "yoksisId": "<encrypted>"}, ...]``
    Çıkış: ``[{"kod": "<encrypted>", "name": "...", "yoksis_id": "<encrypted>"}, ...]``

    Alan adı dönüşümü: ``displayName → name``, ``yoksisId → yoksis_id``.
    ``kod`` şifreli token olarak aynen korunur (sayısal değil).
    """
    if not json_text or not json_text.strip():
        return []

    raw = json.loads(json_text)
    result: list[dict] = []
    for item in raw:
        result.append({
            "kod": item["kod"],
            "name": item["displayName"],
            "yoksis_id": item["yoksisId"],
        })
    return result


# ---------------------------------------------------------------------------
# Gömülü facets.json yükleyici
# ---------------------------------------------------------------------------

_facets_cache: dict | None = None


def load_facets() -> dict:
    """Gömülü ``data/facets.json``'u yükler; ikinci çağrıda önbellekten döner.

    Dönen sözlük: ``{"enums": {...}, "universities": [...], "abd": [...], "built_at": "..."}``
    """
    global _facets_cache
    if _facets_cache is not None:
        return _facets_cache

    pkg = importlib.resources.files("yoktez_mcp") / "data" / "facets.json"
    with importlib.resources.as_file(pkg) as path:
        with open(path, encoding="utf-8") as fh:
            _facets_cache = json.load(fh)

    return _facets_cache


def _reset_facets_cache() -> None:
    """Test izolasyonu için önbelleği sıfırlar (üretimde kullanılmaz)."""
    global _facets_cache
    _facets_cache = None


# ---------------------------------------------------------------------------
# Keşif araçları — Türkçe-duyarlı substring araması
# ---------------------------------------------------------------------------


def find_university(query: str) -> list[dict]:
    """İsme göre üniversite arar; Türkçe-duyarlı, büyük/küçük harf gözetmez.

    Dönen liste: ``[{"kod", "name", "yoksis_id"}, ...]``
    Eşleşme yok → boş liste.
    """
    if not query:
        return []
    facets = load_facets()
    needle = tr_fold(query)
    return [
        u for u in facets["universities"]
        if needle in tr_fold(u["name"])
    ]


def find_abd(query: str) -> list[dict]:
    """İsme göre Anabilim Dalı arar; Türkçe-duyarlı, büyük/küçük harf gözetmez.

    Dönen liste: ``[{"kod", "name"}, ...]``
    Eşleşme yok → boş liste.
    """
    if not query:
        return []
    facets = load_facets()
    needle = tr_fold(query)
    return [
        a for a in facets["abd"]
        if needle in tr_fold(a["name"])
    ]
