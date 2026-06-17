"""YÖKTEZ seed-index harvester — nazik, dirençli (resumable), tam kapsamlı.

Strateji (canlı probe ile doğrulandı, FINDINGS §2 addendum):
  * Pagination YOK; sorgu başına en fazla ~2000 kart tek sayfada döner.
  * islem=2 (gelişmiş arama) sunucu-taraflı filtreleme yapar → Üniversite×Tur×yıl
    dilimleme çoğu dilimi 2000-cap altında tutar (örn. İstanbul×Doktora×2023 = 586).
  * Bir dilim yine de cap'e takılırsa Dil, sonra izin ekseninde alt-bölünür;
    hâlâ cap varsa dürüstçe "incomplete" işaretlenir (asla sessiz kesme yok).

Politeness: tüm trafik ``yoktez_mcp.http`` üzerinden (concurrency=1, ≥1 req/s
throttle, session reuse, UA, 429/5xx backoff). Bu script bu sözleşmeyi GEVŞETMEZ.

Resume: her tamamlanan dilim bir checkpoint JSON'una yazılır; yeniden çalıştırma
kaldığı yerden devam eder.

Kullanım:
    uv run python scripts/build_index.py --turler 1,2 --years 2015-2025 \
        --limit-universities 15 \
        --out src/yoktez_mcp/data/seed_index.db \
        --checkpoint .harvest_checkpoint.json --gzip
"""
from __future__ import annotations

import argparse
import asyncio
import gzip
import json
import shutil
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from yoktez_mcp import facets, search
from yoktez_mcp.index import SearchIndex
from yoktez_mcp.models import SearchHit

# Dil ve izin alt-bölme eksenleri (cap aşıldığında devreye girer).
_DIL_CODES = [str(i) for i in range(1, 15)]  # 1..14 (facets.ENUMS["Dil"])
_IZIN_CODES = ["1", "2"]  # 1=İzinli, 2=İzinsiz


def log(message: str) -> None:
    """İlerleme mesajı (anında flush — uzun harvest'te canlı görünür)."""
    print(message, flush=True)


# ---------------------------------------------------------------------------
# Dilim (slice) modeli + üretici
# ---------------------------------------------------------------------------


@dataclass
class Slice:
    """Tek bir harvest dilimi: bir üniversite × tez türü × yıl."""

    uni: dict
    tur: str
    year: int

    def key(self) -> str:
        """Checkpoint için kararlı anahtar."""
        return f"{self.uni['kod']}|{self.tur}|{self.year}"


def iter_slices(universities: list[dict], turler: list[str], years: list[int]) -> Iterator[Slice]:
    """Üniversite × Tur × yıl kartezyen çarpımını dilim olarak üretir."""
    for uni in universities:
        for tur in turler:
            for year in years:
                yield Slice(uni=uni, tur=tur, year=year)


# ---------------------------------------------------------------------------
# Checkpoint (resume)
# ---------------------------------------------------------------------------


class Checkpoint:
    """Tamamlanan dilim anahtarlarını JSON'da tutar; resume sağlar."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._done: set[str] = set()
        if self.path.exists():
            try:
                self._done = set(json.loads(self.path.read_text(encoding="utf-8")))
            except Exception:  # noqa: BLE001 — bozuk checkpoint → sıfırdan
                self._done = set()

    def done(self, key: str) -> bool:
        return key in self._done

    def mark(self, key: str) -> None:
        self._done.add(key)
        self.path.write_text(
            json.dumps(sorted(self._done), ensure_ascii=False), encoding="utf-8"
        )


# ---------------------------------------------------------------------------
# Dilim harvest'i + cap alt-bölme
# ---------------------------------------------------------------------------


async def _query(sl: Slice, *, dil: str = "0", izin: str = "0") -> search.SearchResult:
    return await search.search_advanced(
        university_kod=sl.uni["kod"],
        university_yoksis=sl.uni["yoksis_id"],
        university_name=sl.uni["name"],
        tur=sl.tur,
        year_from=str(sl.year),
        year_to=str(sl.year),
        dil=dil,
        izin=izin,
    )


async def harvest_slice(sl: Slice, *, subdivide: bool = True) -> tuple[list[SearchHit], bool]:
    """Bir dilimi harvest eder; cap aşılırsa Dil→izin ekseninde alt-bölünür.

    Döner: (benzersiz hit listesi, complete_flag). ``complete_flag=False`` →
    dilim hâlâ 2000-cap'e takılı (kapsam eksik); dürüstçe raporlanır.
    """
    res = await _query(sl)
    if res.coverage_complete or not subdivide:
        return list(res.hits), res.coverage_complete

    # Cap aşıldı → Dil ekseninde böl. İlk (capped) sonuçları da tut (dedup eder).
    collected: dict[str, SearchHit] = {h.kayit_no: h for h in res.hits}
    all_complete = True

    for dil in _DIL_CODES:
        dres = await _query(sl, dil=dil)
        for h in dres.hits:
            collected[h.kayit_no] = h
        if not dres.coverage_complete:
            # Dil dilimi de cap'e takılı → izin ekseninde böl.
            for izin in _IZIN_CODES:
                ires = await _query(sl, dil=dil, izin=izin)
                for h in ires.hits:
                    collected[h.kayit_no] = h
                if not ires.coverage_complete:
                    all_complete = False  # hâlâ cap → dürüstçe eksik işaretle

    return list(collected.values()), all_complete


# ---------------------------------------------------------------------------
# Orkestrasyon
# ---------------------------------------------------------------------------


async def build(
    *,
    out_path: str | Path,
    universities: list[dict],
    turler: list[str],
    years: list[int],
    checkpoint_path: str | Path,
    limit_universities: int | None = None,
) -> int:
    """Tüm dilimleri (resume-aware) harvest eder ve ``out_path`` SQLite'ına yazar.

    Toplam indekslenen tez sayısını döndürür.
    """
    if limit_universities:
        universities = universities[:limit_universities]

    cp = Checkpoint(checkpoint_path)
    ix = SearchIndex(str(out_path))
    slices = list(iter_slices(universities, turler, years))

    total = 0
    incomplete = 0

    log(
        f"Harvest planı: {len(universities)} üniversite × {len(turler)} tür × "
        f"{len(years)} yıl = {len(slices)} dilim. Politeness: concurrency=1, ≥1 req/s."
    )

    for i, sl in enumerate(slices, 1):
        key = sl.key()
        if cp.done(key):
            continue
        try:
            hits, complete = await harvest_slice(sl)
        except Exception as exc:  # noqa: BLE001 — bir dilim çökerse devam et
            log(f"[{i}/{len(slices)}] HATA {key}: {type(exc).__name__}: {exc}")
            continue
        n = ix.upsert_hits(hits)
        total += n
        if not complete:
            incomplete += 1
            log(f"  ! EKSİK kapsam (>2000) dilim {key} — daha fazla eksen gerekebilir.")
        cp.mark(key)
        log(
            f"[{i}/{len(slices)}] {sl.uni['name']} Tur={sl.tur} {sl.year}: "
            f"+{n} tez (toplam {total})"
        )

    ix.close()
    log(f"BİTTİ: toplam {total} tez, {incomplete} eksik-kapsam dilim.")
    return total


def gzip_db(db_path: str | Path, gz_path: str | Path) -> None:
    """SQLite dosyasını gzip'leyerek paket data dizinine yazar."""
    with open(db_path, "rb") as src, gzip.open(gz_path, "wb") as dst:
        shutil.copyfileobj(src, dst)
    log(f"gzip → {gz_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_years(spec: str) -> list[int]:
    """'2015-2025' → [2015..2025]; '2023' → [2023]; '2020,2022' → [2020,2022]."""
    spec = spec.strip()
    if "-" in spec:
        lo, hi = spec.split("-", 1)
        return list(range(int(lo), int(hi) + 1))
    return [int(y) for y in spec.split(",") if y.strip()]


def _parse_turler(spec: str) -> list[str]:
    """'1,2' → ['1','2']."""
    return [t.strip() for t in spec.split(",") if t.strip()]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="YÖKTEZ seed-index harvester (nazik, resumable).")
    p.add_argument("--turler", default="1,2", help="Tez türü kodları, ör. '1,2' (YL,Doktora).")
    p.add_argument("--years", default="2015-2025", help="Yıl aralığı, ör. '2015-2025' veya '2023'.")
    p.add_argument("--limit-universities", type=int, default=None,
                   help="İlk N üniversite ile sınırla (gösterimlik/küçük harvest).")
    p.add_argument("--out", default="src/yoktez_mcp/data/seed_index.db",
                   help="Çıktı SQLite yolu.")
    p.add_argument("--checkpoint", default=".harvest_checkpoint.json",
                   help="Resume checkpoint JSON yolu.")
    p.add_argument("--gzip", action="store_true",
                   help="Bitince <out>.gz olarak gzip'le (paket için).")
    args = p.parse_args(argv)

    universities = facets.load_facets()["universities"]
    turler = _parse_turler(args.turler)
    years = _parse_years(args.years)

    total = asyncio.run(build(
        out_path=args.out,
        universities=universities,
        turler=turler,
        years=years,
        checkpoint_path=args.checkpoint,
        limit_universities=args.limit_universities,
    ))

    if args.gzip:
        gzip_db(args.out, f"{args.out}.gz")

    return 0 if total >= 0 else 1


if __name__ == "__main__":
    sys.exit(main())
