#!/usr/bin/env python3
"""scripts/build_facets.py — YÖKTEZ facets.json oluşturucu.

İki mod:
    --from-fixtures   Kayıtlı test fixture'larından okur (ağ bağlantısı gerektirmez).
                      Taahhüt edilen data/facets.json bu modla oluşturulur.
    (varsayılan)      Canlı YÖKTEZ'den veriyi nazikçe çeker (yoktez_mcp.http üzerinden).

Yazılan dosya: src/yoktez_mcp/data/facets.json
    {
        "enums": {...},        # ENUMS kod tabloları (FINDINGS §3'ten doğrulanmış)
        "universities": [...], # 260+ üniversite {kod, name, yoksis_id}
        "abd": [...],          # 5 132+ ABD {kod, name}
        "built_at": "ISO8601"  # oluşturma zamanı
    }

Polite kullanım notu:
    Canlı mod yoktez_mcp.http.get() kullanır → tüm throttle/session/retry
    mekanizmaları devreye girer. Concurrency veya throttle değerlerini
    asla gevşetme (CLAUDE.md §Good Citizen).

Kullanım:
    uv run python scripts/build_facets.py              # canlı çekme
    uv run python scripts/build_facets.py --from-fixtures  # fixture'dan
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Yol sabitleri
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent
SRC_DATA = REPO_ROOT / "src" / "yoktez_mcp" / "data"
FIXTURES_FAZ0 = REPO_ROOT / "tests" / "fixtures" / "faz0"

OUTPUT_PATH = SRC_DATA / "facets.json"


# ---------------------------------------------------------------------------
# Yardımcı: parse modülünü içe aktar (build sırasında package kurulu olmalı)
# ---------------------------------------------------------------------------

def _import_facets():
    """yoktez_mcp.facets'i içe aktarır; gerekirse src/'yi sys.path'a ekler."""
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from yoktez_mcp.facets import ENUMS, parse_abd, parse_universities
    return ENUMS, parse_abd, parse_universities


# ---------------------------------------------------------------------------
# Fixture modunda veri okuma
# ---------------------------------------------------------------------------


def build_from_fixtures() -> dict:
    """Kayıtlı fixture dosyalarından facets.json verisi oluşturur."""
    ENUMS, parse_abd, parse_universities = _import_facets()

    # ABD — 2.7MB HTML, gitignored raw fixture
    abd_path = FIXTURES_FAZ0 / "getAllABD.html"
    if not abd_path.exists():
        raise FileNotFoundError(
            f"{abd_path} bulunamadı. "
            "Bu dosya gitignore'da; çalıştırmadan önce "
            "tests/fixtures/faz0/'a kopyala veya --from-fixtures yerine canlı modu kullan."
        )
    abd_html = abd_path.read_text(encoding="utf-8")
    abd = parse_abd(abd_html)
    print(f"  ABD: {len(abd)} giriş ayrıştırıldı.")

    # Üniversiteler TR — fixture'dan
    uni_path = FIXTURES_FAZ0 / "getUniversities_TR.html"
    uni_json = uni_path.read_text(encoding="utf-8")
    universities = parse_universities(uni_json)
    print(f"  Üniversiteler (TR): {len(universities)} giriş ayrıştırıldı.")

    return {
        "enums": {k: {str(code): label for code, label in v.items()} for k, v in ENUMS.items()},
        "universities": universities,
        "abd": abd,
        "built_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Canlı mod — yoktez_mcp.http üzerinden nazik çekme
# ---------------------------------------------------------------------------

async def _fetch_live() -> dict:
    """Canlı YÖKTEZ'den ABD + üniversite verisi çeker."""
    ENUMS, parse_abd, parse_universities = _import_facets()

    from yoktez_mcp import http  # noqa: PLC0415

    base = http.BASE_URL

    print("  Oturum açılıyor (JSESSIONID)...")
    await http.ensure_session()

    # ABD
    print("  getAllABD çekiliyor (2.7MB — sabırlı olun)...")
    abd_resp = await http.get(
        f"{base}/tarama.jsp",
        params={"ajax": "getAllABD", "ensGrubu": ""},
    )
    abd = parse_abd(abd_resp.text)
    print(f"  ABD: {len(abd)} giriş.")

    # Üniversiteler TR
    print("  getUniversities TR çekiliyor...")
    uni_tr_resp = await http.get(
        f"{base}/getUniversities.jsp",
        params={"type": "TR"},
    )
    universities = parse_universities(uni_tr_resp.text)
    print(f"  Üniversiteler (TR): {len(universities)} giriş.")

    # Üniversiteler INT (opsiyonel — mevcut değerlere ekle)
    try:
        print("  getUniversities INT çekiliyor...")
        uni_int_resp = await http.get(
            f"{base}/getUniversities.jsp",
            params={"type": "INT"},
        )
        uni_int = parse_universities(uni_int_resp.text)
        print(f"  Üniversiteler (INT): {len(uni_int)} giriş.")
        # Tekrar eden kod yoksa ekle
        existing_kods = {u["kod"] for u in universities}
        for u in uni_int:
            if u["kod"] not in existing_kods:
                universities.append(u)
                existing_kods.add(u["kod"])
        print(f"  Üniversiteler (toplam): {len(universities)} giriş.")
    except Exception as exc:  # noqa: BLE001
        print(f"  UYARI: INT üniversiteleri çekilemedi: {exc}")

    await http.aclose()

    return {
        "enums": {k: {str(code): label for code, label in v.items()} for k, v in ENUMS.items()},
        "universities": universities,
        "abd": abd,
        "built_at": datetime.now(timezone.utc).isoformat(),
    }


def build_live() -> dict:
    return asyncio.run(_fetch_live())


# ---------------------------------------------------------------------------
# Ana giriş noktası
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="YÖKTEZ facets.json oluşturucu",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--from-fixtures",
        action="store_true",
        help="Kayıtlı fixture'lardan okur (ağ gerekmez; varsayılan: canlı çekme).",
    )
    args = parser.parse_args()

    SRC_DATA.mkdir(parents=True, exist_ok=True)

    if args.from_fixtures:
        print("Fixture modunda çalışıyor...")
        data = build_from_fixtures()
    else:
        print("Canlı YÖKTEZ'den çekiliyor...")
        data = build_live()

    print(f"  Yazılıyor: {OUTPUT_PATH}")
    OUTPUT_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    size_kb = OUTPUT_PATH.stat().st_size / 1024
    print(
        f"Tamam. facets.json: {size_kb:.1f} KB, "
        f"{len(data['abd'])} ABD, "
        f"{len(data['universities'])} üniversite, "
        f"oluşturma: {data['built_at']}"
    )


if __name__ == "__main__":
    main()
