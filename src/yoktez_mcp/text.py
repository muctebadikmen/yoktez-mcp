"""yoktez_mcp.text — Türkçe-duyarlı metin yardımcıları.

Bu modül, hem facets.py (find_university / find_abd) hem de ileride index.py
tarafından içe aktarılır; böylece katlama simetrisi garanti altına alınır.

Algoritma:
    tr_fold: Türkçe özgün harfleri ASCII karşılıklarına indirger, ardından
    casefold uygular. DergiPark MCP'deki aynı _TR_MAP + tr_fold kalıbından
    uyarlanmıştır; iki proje tutarlı davranır.

    Eşlemeler:
        ı → i   İ → i   I → i
        ş → s   Ş → s
        ğ → g   Ğ → g
        ü → u   Ü → u
        ö → o   Ö → o
        ç → c   Ç → c
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Türkçe karakter → ASCII eşlemesi
# ---------------------------------------------------------------------------

_TR_MAP = str.maketrans({
    "ı": "i", "İ": "i", "I": "i",
    "ş": "s", "Ş": "s",
    "ğ": "g", "Ğ": "g",
    "ü": "u", "Ü": "u",
    "ö": "o", "Ö": "o",
    "ç": "c", "Ç": "c",
})


def tr_fold(s: str | None) -> str:
    """Türkçe-duyarlı katlama: Türkçe harfleri ASCII'ye indirger, küçük harfe çevirir.

    None veya boş string → "" döndürür.
    Simetrik: aynı fonksiyon hem indeks tarafına hem sorgu tarafına uygulandığında
    İSTANBUL == istanbul == Istanbul eşleşmesi sağlanır.
    """
    if not s:
        return ""
    return s.translate(_TR_MAP).casefold()


def fold_contains(haystack: str | None, needle: str) -> bool:
    """Türkçe-duyarlı alt dizi testi: needle, haystack içinde geçiyor mu?

    İkisi de tr_fold ile normalleştirilir; None haystack → False.
    """
    if haystack is None:
        return False
    return tr_fold(needle) in tr_fold(haystack)
