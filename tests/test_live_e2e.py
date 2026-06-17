"""Uçtan uca canlı smoke testi — gerçek YÖKTEZ trafiği.

Çalıştırmak için: uv run pytest -m live -q tests/test_live_e2e.py

Sıra:
  1. search_theses("yapay zeka") → ilk sonucu al
  2. get_thesis(kayit_no, tez_no) → zengin kayıt + atıflar
  3a. Açık tez: get_thesis_fulltext → has_fulltext veya güvenilir not
  3b. Kısıtlı tez: get_thesis_fulltext → has_fulltext=False + access_reason sarılı, PDF metni YOK

YÖK'e karşı kibar davranılır — throttle http.py'de yönetilir.
"""

from __future__ import annotations

import pytest

import yoktez_mcp.server as srv


@pytest.mark.live
@pytest.mark.asyncio
async def test_e2e_search_and_get_thesis():
    """search_theses → get_thesis — canlı YÖKTEZ ile uçtan uca."""
    # 1. Arama
    search_result = await srv.search_theses("yapay zeka", limit=5)

    assert "results" in search_result, "Arama sonucu results içermeli"
    assert "source_notice" in search_result, "source_notice eksik"
    # Sonuç yoksa uyarı ver ama testi geç (indeks boş + canlı sorun olabilir)
    if not search_result["results"]:
        pytest.skip("Canlı YÖKTEZ aramasından sonuç gelmedi — site erişilemez olabilir")

    first = search_result["results"][0]
    kayit_no = first["kayit_no"]
    tez_no = first["tez_no"]

    assert kayit_no, "kayit_no boş"
    assert tez_no, "tez_no boş"

    # 2. Tez kaydı
    thesis_result = await srv.get_thesis(kayit_no, tez_no)

    assert "citations" in thesis_result, "citations eksik"
    assert "apa" in thesis_result["citations"], "APA atıf formatı eksik"
    assert thesis_result.get("source_notice"), "source_notice boş"

    access = thesis_result.get("access_status")
    assert access in ("open", "restricted", "unknown"), f"Beklenmeyen access_status: {access}"

    # EXTERNAL CONTENT: özet varsa sarılmış olmalı
    if thesis_result.get("abstract_tr"):
        assert "[EXTERNAL CONTENT" in thesis_result["abstract_tr"], \
            "abstract_tr [EXTERNAL CONTENT] ile sarılmamış"

    # 3. Tam metin
    fulltext_result = await srv.get_thesis_fulltext(kayit_no, tez_no)

    assert "has_fulltext" in fulltext_result, "has_fulltext alanı eksik"
    assert "source_notice" in fulltext_result, "source_notice eksik (fulltext)"

    if access == "open":
        # Açık tez: markdown sarılı VEYA erişilemedi (PDF anahtarı eksik olabilir)
        if fulltext_result["has_fulltext"]:
            assert "[EXTERNAL CONTENT" in fulltext_result.get("markdown", ""), \
                "Açık tez markdown'u [EXTERNAL CONTENT] ile sarılmamış"
        # Aksi hâlde not alanı dürüstçe açıklamalı
        else:
            assert fulltext_result.get("note"), "has_fulltext=False iken note alanı boş"
    else:
        # Kısıtlı tez: PDF metni asla dönmemeli
        assert fulltext_result["has_fulltext"] is False, \
            "Kısıtlı tez için has_fulltext=True olamaz!"
        assert "markdown" not in fulltext_result, \
            "Kısıtlı tez markdown içermemeli!"
        if fulltext_result.get("access_reason"):
            assert "[EXTERNAL CONTENT" in fulltext_result["access_reason"], \
                "access_reason [EXTERNAL CONTENT] ile sarılmamış"
