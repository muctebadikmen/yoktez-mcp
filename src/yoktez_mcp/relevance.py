"""Canlı YÖKTEZ sonuçlarını sorgu-alaka düzeyine göre filtreler/sıralar.

Sorun (canlı probe ile doğrulandı): YÖKTEZ canlı sonuçları sıralamasız döner ve
"Tümü" (nevi=7) aramasında özet/dizin alanındaki rastgele eşleşmeler sızar
(ör. "yapay zeka tıp" → alakasız bir din eğitimi tezi). İndeks sonuçları zaten
BM25 + başlık bonusundan geçiyor; canlı sonuçlar geçmiyordu.

Kart düzeyinde yalnızca title/author/advisor/university var (referenceData.meta);
bu yüzden kapsam (coverage) bu alanlar üzerinden ``tr_fold``-simetrik hesaplanır.
Aynı ``_query_terms`` (stopword + fold) tek kaynaktan kullanılır → simetri korunur.
"""
from __future__ import annotations

from .index import _query_terms  # tr_fold + stopword'lü terim bölme (tek kaynak)
from .text import tr_fold


def _hit_text(h) -> str:
    """Kartta gerçekten bulunan alanları fold'lu tek metinde birleştirir."""
    parts = [
        getattr(h, "title_tr", None),
        getattr(h, "title_en", None),
        getattr(h, "author", None),
        getattr(h, "advisor", None),  # SearchHit'te yok → None (zararsız)
    ]
    return tr_fold(" ".join(p for p in parts if p))


def relevance_filter_sort(hits: list, query: str, *, require_all_terms: bool = True) -> list:
    """Canlı hit'leri sorgu-alaka düzeyine göre filtreler ve sıralar.

    - ``require_all_terms=True``: tüm sorgu terimleri title/author/advisor metninde
      geçmeyen hit'ler elenir (özet-yalnızca eşleşmeleri ayıklar).
    - Sıralama: terim kapsamı (azalan) → başlık kapsamı → yıl (azalan).
    - Sorgu yalnızca stopword ise hiçbir şey filtrelenmez (orijinal liste).
    """
    terms = _query_terms(query)
    if not terms:
        return list(hits)

    def coverage(h) -> int:
        text = _hit_text(h)
        return sum(1 for t in terms if t in text)

    scored = [(h, coverage(h)) for h in hits]
    if require_all_terms:
        scored = [(h, c) for (h, c) in scored if c == len(terms)]

    def sort_key(item):
        h, c = item
        title = tr_fold((getattr(h, "title_tr", "") or "") + " " + (getattr(h, "title_en", "") or ""))
        title_cov = sum(1 for t in terms if t in title)
        return (-c, -title_cov, -(getattr(h, "year", 0) or 0))

    scored.sort(key=sort_key)
    return [h for (h, _c) in scored]
