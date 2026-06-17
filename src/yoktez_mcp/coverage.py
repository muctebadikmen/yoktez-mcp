"""yoktez_mcp.coverage — YÖK'ün 2000 sonuç/sorgu sınırını talep üzerine aşar.

YÖKTEZ pagination sunmaz ve her sorguda en fazla 2000 kart döndürür. Tek bir
``islem=2`` sorgusu bu sınıra takılırsa (``coverage_complete=False``), burada
sorgu **yıl bazında** dilimlenir; bir yıl hâlâ cap'e takılırsa **Dil** ve son
çare **izin** ekseninde alt-bölünür. Böylece bir üniversite/filtre için 2000'i
aşan tam kapsam elde edilir.

Politeness: tüm istekler ``search.search_advanced`` → ``http`` üzerinden (sıralı,
≥1 req/s throttle). İstek sayısı ``max_requests`` ile sınırlanır; sınıra ulaşılırsa
kapsam dürüstçe ``complete=False`` raporlanır (asla sessiz kesme yok).
"""
from __future__ import annotations

from . import search
from .models import SearchHit

# Alt-bölme eksenleri (cap aşıldığında devreye girer) — facets.ENUMS ile uyumlu.
_DIL_CODES = [str(i) for i in range(1, 15)]  # 1..14
_IZIN_CODES = ["1", "2"]  # 1=İzinli, 2=İzinsiz

# list_university exhaustive varsayılan yıl aralığı (YÖK'te tezler ~1980'lerden).
DEFAULT_YEAR_FROM = 1985
DEFAULT_YEAR_TO = 2025


async def collect_all_advanced(
    *,
    university_kod: str = "",
    university_yoksis: str = "",
    university_name: str = "",
    tur: str = "0",
    year_from: int,
    year_to: int,
    max_requests: int = 200,
) -> tuple[list[SearchHit], bool, int]:
    """islem=2 sorgusunu yıl-dilimleyerek 2000-cap'i aşar.

    Döner: ``(benzersiz hit listesi, complete: bool, request_count: int)``.
    ``complete=False`` → ``max_requests`` sınırına ulaşıldı veya bir dilim hâlâ
    2000-cap'e takılı (kapsam tam değil; dürüstçe bildirilir).
    """
    collected: dict[str, SearchHit] = {}
    reqs = 0
    all_complete = True

    async def adv(year: int, dil: str = "0", izin: str = "0"):
        return await search.search_advanced(
            university_kod=university_kod,
            university_yoksis=university_yoksis,
            university_name=university_name,
            tur=tur,
            year_from=str(year),
            year_to=str(year),
            dil=dil,
            izin=izin,
        )

    def absorb(hits: list[SearchHit]) -> None:
        for h in hits:
            if h.kayit_no:
                collected[h.kayit_no] = h

    for year in range(year_from, year_to + 1):
        if reqs >= max_requests:
            all_complete = False
            break

        res = await adv(year)
        reqs += 1
        absorb(res.hits)
        if res.coverage_complete:
            continue

        # Yıl cap'e takıldı → Dil ekseninde böl.
        for dil in _DIL_CODES:
            if reqs >= max_requests:
                all_complete = False
                break
            dres = await adv(year, dil=dil)
            reqs += 1
            absorb(dres.hits)
            if dres.coverage_complete:
                continue

            # Dil dilimi de cap'e takılı → izin ekseninde böl.
            for izin in _IZIN_CODES:
                if reqs >= max_requests:
                    all_complete = False
                    break
                ires = await adv(year, dil=dil, izin=izin)
                reqs += 1
                absorb(ires.hits)
                if not ires.coverage_complete:
                    all_complete = False  # hâlâ cap → dürüstçe eksik işaretle

    return list(collected.values()), all_complete, reqs
