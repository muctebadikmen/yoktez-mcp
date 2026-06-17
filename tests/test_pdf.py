"""pdf.py — offline (sentetik) ve isteğe bağlı live testler.

Offline testler: gerçek PDF indirmez. Minimal geçerli PDF in-memory üretilir.
Live testler: @pytest.mark.live ile işaretli, varsayılan olarak çalıştırılmaz.
"""

import pytest

from yoktez_mcp import pdf
from yoktez_mcp.models import AccessStatus

# ---------------------------------------------------------------------------
# Yardımcı: minimal, geçerli PDF baytları (tek sayfa, custom metin)
# ---------------------------------------------------------------------------


def _minimal_pdf_bytes(content: str = "Hello YokTez") -> bytes:
    """Tek sayfalı, Type1/Helvetica fontlu, belirtilen metni içeren geçerli PDF üretir."""
    text_bytes = content.encode("latin-1", errors="replace")
    stream = b"BT /F1 12 Tf 72 700 Td (" + text_bytes + b") Tj ET"
    objs = []
    objs.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    objs.append(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
    objs.append(
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>\nendobj\n"
    )
    objs.append(
        b"4 0 obj\n<< /Length " + str(len(stream)).encode() + b" >>\nstream\n"
        + stream + b"\nendstream\nendobj\n"
    )
    objs.append(
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
    )
    header = b"%PDF-1.4\n"
    body = b""
    offsets = []
    pos = len(header)
    for o in objs:
        offsets.append(pos)
        body += o
        pos += len(o)
    xref_pos = len(header) + len(body)
    xref = b"xref\n0 6\n0000000000 65535 f \n"
    for off in offsets:
        xref += (f"{off:010d} 00000 n \n").encode()
    trailer = (
        b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n"
        + str(xref_pos).encode()
        + b"\n%%EOF"
    )
    return header + body + xref + trailer


# ---------------------------------------------------------------------------
# split_sections — tez bölüm başlıkları
# ---------------------------------------------------------------------------


def test_split_sections_thesis_headings():
    """Sentetik tez metni: 5 standart başlık → hepsini sırasıyla bulur."""
    text = (
        "Yazar: Mehmet Yılmaz, Danışman: Prof. Dr. Ayşe Kaya\n\n"
        "ÖZET\n"
        "Bu tez makine öğrenmesi yöntemlerini incelemektedir.\n\n"
        "GİRİŞ\n"
        "Giriş metni burada. Bu bölüm araştırmanın amacını açıklar.\n\n"
        "YÖNTEM\n"
        "Nitel ve nicel yöntemler birlikte kullanılmıştır.\n\n"
        "BULGULAR\n"
        "Elde edilen bulgular aşağıda sunulmaktadır.\n\n"
        "KAYNAKÇA\n"
        "Yazar A. (2020). Başlık. Yayınevi.\n"
        "Yazar B. (2021). Diğer Başlık. Dergi, 5(2), 10-20."
    )
    secs = pdf.split_sections(text)
    headings = [s["heading"] for s in secs]

    assert any("ÖZET" in h for h in headings), "ÖZET bölümü bulunamadı"
    assert any("GİRİŞ" in h for h in headings), "GİRİŞ bölümü bulunamadı"
    assert any("YÖNTEM" in h for h in headings), "YÖNTEM bölümü bulunamadı"
    assert any("BULGULAR" in h for h in headings), "BULGULAR bölümü bulunamadı"
    assert any("KAYNAKÇA" in h for h in headings), "KAYNAKÇA bölümü bulunamadı"

    # Sıra korunmalı
    idx = {h: i for i, h in enumerate(headings)}
    keys = [k for k in headings if any(kw in k for kw in ["ÖZET", "GİRİŞ", "YÖNTEM", "BULGULAR", "KAYNAKÇA"])]
    assert keys == sorted(keys, key=lambda k: idx[k])


def test_split_sections_kaynakca_body():
    """KAYNAKÇA bölümünün içeriği doğru çıkarılır."""
    text = (
        "ÖZET\nÖzet metni.\n\n"
        "KAYNAKÇA\n"
        "Yazar A. (2020). Başlık Bir. Yayınevi.\n"
        "Yazar B. (2021). Başlık İki. Dergi, 5(2), 10-20."
    )
    secs = pdf.split_sections(text)
    kaynak = next((s for s in secs if "KAYNAKÇA" in s["heading"]), None)
    assert kaynak is not None
    assert "Yazar A." in kaynak["text"]
    assert "Yazar B." in kaynak["text"]


def test_split_sections_gereç_ve_yöntem():
    """Çok kelimeli 'GEREÇ VE YÖNTEM' başlığını tanır."""
    text = (
        "GİRİŞ\nGiriş metni.\n\n"
        "GEREÇ VE YÖNTEM\n"
        "Kullanılan gereçler ve yöntemler burada açıklanmıştır.\n\n"
        "BULGULAR\nBulgular."
    )
    secs = pdf.split_sections(text)
    headings = [s["heading"] for s in secs]
    assert any("GEREÇ VE YÖNTEM" in h for h in headings)


def test_split_sections_numbered_heading():
    """Numaralı başlıklar (ör. '1. GİRİŞ') tanınır."""
    text = (
        "1. GİRİŞ\nGiriş metni.\n\n"
        "2. YÖNTEM\nYöntem açıklaması."
    )
    secs = pdf.split_sections(text)
    headings = [s["heading"] for s in secs]
    assert any("GİRİŞ" in h for h in headings)
    assert any("YÖNTEM" in h for h in headings)


def test_split_sections_no_headings():
    """Başlık içermeyen düz metin → boş liste döner."""
    result = pdf.split_sections("başlık yok, sadece düz metin paragrafı burada bulunuyor.")
    assert result == []


def test_split_sections_ozgecmis():
    """ÖZGEÇMİŞ bölümünü tanır."""
    text = (
        "SONUÇ VE ÖNERİLER\nSonuç metni.\n\n"
        "ÖZGEÇMİŞ\nAd Soyad: Fatma Demir. Doğum Tarihi: 1990."
    )
    secs = pdf.split_sections(text)
    headings = [s["heading"] for s in secs]
    assert any("ÖZGEÇMİŞ" in h for h in headings)


# ---------------------------------------------------------------------------
# readable_ratio — garbled font tespiti
# ---------------------------------------------------------------------------


def test_readable_ratio_clean_turkish():
    """Temiz Türkçe metin → oran yüksek (> 0.95)."""
    clean = "Makine öğrenmesi yöntemleriyle doğal dil işleme çalışmaları incelenmiştir."
    assert pdf.readable_ratio(clean) > 0.95


def test_readable_ratio_garbled():
    """Bozuk font karakterleri → oran düşük (< 0.50)."""
    # Gerçek bozuk-font çıktısı: harfler egzotik Latin-Extended glyph'lerine düşer
    garbled = "zŦůŵĂǌ dŽƉůƵŵƵŶ ^ŝǇĂƐĞƚŝ DĂŬĂůĞ ƂŶĚĞƌŝŵ ,ĂďĞƌŵĂƐ ƚĂƌƨƔŦŵ ǇĂǌĂƌ"
    assert pdf.readable_ratio(garbled) < 0.50


def test_readable_ratio_empty():
    """Boş metin → 1.0 döner (default safe value)."""
    assert pdf.readable_ratio("") == 1.0


# ---------------------------------------------------------------------------
# _assess — güvenilirlik kararı
# ---------------------------------------------------------------------------


def test_assess_real_prose_is_reliable():
    pages = [
        "Bu tez makine öğrenmesi yöntemleriyle Türkçe doğal dil işleme üzerine "
        "odaklanmaktadır. Araştırma nicel ve nitel yöntemler kullanılarak yürütülmüştür."
    ]
    has_text, reliable, note = pdf._assess(pages)
    assert has_text is True
    assert reliable is True
    assert note is None


def test_assess_garbled_font_is_unreliable():
    pages = ["zŦůŵĂǌ dŽƉůƵŵƵŶ ^ŝǇĂƐĞƚŝ DĂŬĂůĞ ƂŶĚĞƌŝŵ ,ĂďĞƌŵĂƐ ƚĂƌƨƔŦŵ ǇĂǌĂƌ"]
    has_text, reliable, note = pdf._assess(pages)
    assert reliable is False
    assert note is not None
    assert "güvenilir" in note.lower()


def test_assess_page_numbers_only_is_unreliable():
    """Yalnızca sayfa numaraları çıkan taranmış PDF → güvenilmez."""
    pages = ["17", "18", "19", "20", "21", "22", "23", "24", "25", "26", "27"]
    has_text, reliable, note = pdf._assess(pages)
    assert has_text is False
    assert reliable is False
    assert note is not None
    assert "taranmış" in note.lower()


def test_assess_empty_pages_is_unreliable():
    has_text, reliable, note = pdf._assess(["", "  ", "\n"])
    assert has_text is False
    assert reliable is False


# ---------------------------------------------------------------------------
# _normalize — metin temizleme
# ---------------------------------------------------------------------------


def test_normalize_dehyphenation():
    """Satır sonu tire birleştirme."""
    raw = "bu bir cüm-\nle ve devamı\n\n\n\nyeni paragraf"
    out = pdf._normalize(raw)
    assert "cümle" in out
    assert "\n\n\n" not in out


# ---------------------------------------------------------------------------
# extract — minimal PDF ile
# ---------------------------------------------------------------------------


def test_extract_minimal_pdf():
    """Minimal, metin içeren PDF → has_text=True, içerik markdown'da yer alır."""
    data = _minimal_pdf_bytes("Hello YokTez Tez")
    result = pdf.extract(data, "http://x/tez/1")
    assert result.page_count == 1
    assert result.has_text is True
    assert "Hello YokTez Tez" in result.markdown


def test_extract_pagination_out_of_range():
    """start_page belge dışında → has_text=False, has_more_pages=False."""
    data = _minimal_pdf_bytes()
    result = pdf.extract(data, "http://x/tez/1", start_page=2)
    assert result.page_count == 1
    assert result.start_page == 2
    assert result.has_text is False
    assert result.has_more_pages is False


def test_extract_sets_source_url():
    """source_url doğru aktarılır."""
    data = _minimal_pdf_bytes()
    url = "https://tez.yok.gov.tr/UlusalTezMerkezi/TezGoster?key=abc123"
    result = pdf.extract(data, url)
    assert result.source_url == url
    assert url in result.markdown


# ---------------------------------------------------------------------------
# references_section — KAYNAKÇA dilimleme
# ---------------------------------------------------------------------------


def test_references_section_found():
    """ExtractedPDF içinde KAYNAKÇA bölümü varsa metnini döndürür."""
    extracted = pdf.ExtractedPDF(
        source_url="http://x/1",
        page_count=1,
        sections=[
            {"heading": "ÖZET", "text": "Özet metni burada."},
            {"heading": "GİRİŞ", "text": "Giriş metni burada."},
            {"heading": "KAYNAKÇA", "text": "Yazar A. (2020).\nYazar B. (2021)."},
        ],
    )
    result = pdf.references_section(extracted)
    assert result is not None
    assert "Yazar A." in result
    assert "Yazar B." in result


def test_references_section_kaynaklar_variant():
    """'KAYNAKLAR' başlığını da tanır."""
    extracted = pdf.ExtractedPDF(
        source_url="http://x/1",
        page_count=1,
        sections=[
            {"heading": "KAYNAKLAR", "text": "Smith, J. (2019). Title. Journal."},
        ],
    )
    result = pdf.references_section(extracted)
    assert result is not None
    assert "Smith" in result


def test_references_section_not_found():
    """KAYNAKÇA bölümü yoksa None döner."""
    extracted = pdf.ExtractedPDF(
        source_url="http://x/1",
        page_count=1,
        sections=[
            {"heading": "ÖZET", "text": "Özet metni."},
            {"heading": "GİRİŞ", "text": "Giriş."},
        ],
    )
    result = pdf.references_section(extracted)
    assert result is None


def test_references_section_no_sections():
    """sections listesi boş → None döner."""
    extracted = pdf.ExtractedPDF(source_url="http://x/1", page_count=1)
    assert pdf.references_section(extracted) is None


def test_references_section_full_pipeline():
    """split_sections + references_section uçtan uca çalışır."""
    text = (
        "ÖZET\nÖzet metni.\n\n"
        "GİRİŞ\nGiriş metni.\n\n"
        "KAYNAKÇA\n"
        "Demir, F. (2023). Makine Öğrenmesi. Ankara Üni.\n"
        "Yıldız, A. (2022). Derin Öğrenme. İTÜ."
    )
    secs = pdf.split_sections(text)
    extracted = pdf.ExtractedPDF(source_url="http://x/1", page_count=5, sections=secs)
    refs = pdf.references_section(extracted)
    assert refs is not None
    assert "Demir" in refs
    assert "Yıldız" in refs


# ---------------------------------------------------------------------------
# download_and_extract — GUARD testleri (ağ çağrısı yapılmamalı)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_guard_restricted_raises_before_network(monkeypatch):
    """RESTRICTED tez → PermissionError, ağ çağrısı YOK."""
    called = []

    async def boom(*args, **kwargs):
        called.append(True)
        raise AssertionError("get_bytes called — guard failed!")

    monkeypatch.setattr("yoktez_mcp.http.get_bytes", boom)

    with pytest.raises(PermissionError, match="indirilemez"):
        await pdf.download_and_extract(
            "https://tez.yok.gov.tr/UlusalTezMerkezi/TezGoster?key=abc",
            access_status=AccessStatus.RESTRICTED,
            pdf_key="abc",
        )

    assert not called, "get_bytes çağrıldı — guard ağdan önce durdurmadı!"


@pytest.mark.asyncio
async def test_guard_unknown_status_raises_before_network(monkeypatch):
    """UNKNOWN erişim durumu → PermissionError, ağ çağrısı YOK."""
    called = []

    async def boom(*args, **kwargs):
        called.append(True)
        raise AssertionError("get_bytes called — guard failed!")

    monkeypatch.setattr("yoktez_mcp.http.get_bytes", boom)

    with pytest.raises(PermissionError, match="indirilemez"):
        await pdf.download_and_extract(
            "https://tez.yok.gov.tr/UlusalTezMerkezi/TezGoster?key=abc",
            access_status=AccessStatus.UNKNOWN,
            pdf_key="abc",
        )

    assert not called


@pytest.mark.asyncio
async def test_guard_missing_pdf_key_raises_before_network(monkeypatch):
    """pdf_key eksik → ValueError, ağ çağrısı YOK."""
    called = []

    async def boom(*args, **kwargs):
        called.append(True)
        raise AssertionError("get_bytes called — guard failed!")

    monkeypatch.setattr("yoktez_mcp.http.get_bytes", boom)

    with pytest.raises(ValueError, match="pdf_key eksik"):
        await pdf.download_and_extract(
            "https://tez.yok.gov.tr/UlusalTezMerkezi/TezGoster?key=abc",
            access_status=AccessStatus.OPEN,
            pdf_key=None,
        )

    assert not called


@pytest.mark.asyncio
async def test_guard_no_status_no_key_raises_before_network(monkeypatch):
    """access_status=None ve pdf_key eksik → guard erken durdurur."""
    called = []

    async def boom(*args, **kwargs):
        called.append(True)
        raise AssertionError("get_bytes called — guard failed!")

    monkeypatch.setattr("yoktez_mcp.http.get_bytes", boom)

    with pytest.raises((PermissionError, ValueError)):
        await pdf.download_and_extract(
            "https://tez.yok.gov.tr/UlusalTezMerkezi/TezGoster?key=abc",
        )

    assert not called


@pytest.mark.asyncio
async def test_download_and_extract_open_with_key(monkeypatch):
    """OPEN + pdf_key → get_bytes çağrılır, extract başarılı döner."""
    data = _minimal_pdf_bytes("Tez tam metin")

    async def fake_get_bytes(url, **kwargs):
        return data

    monkeypatch.setattr("yoktez_mcp.http.get_bytes", fake_get_bytes)

    result = await pdf.download_and_extract(
        "https://tez.yok.gov.tr/UlusalTezMerkezi/TezGoster?key=abc123",
        access_status=AccessStatus.OPEN,
        pdf_key="abc123",
    )
    assert result.has_text is True
    assert "Tez tam metin" in result.markdown


# ---------------------------------------------------------------------------
# ExtractedPDF dataclass
# ---------------------------------------------------------------------------


def test_extracted_pdf_defaults():
    """ExtractedPDF varsayılan değerleri doğru."""
    e = pdf.ExtractedPDF(source_url="http://x/1", page_count=5)
    assert e.text_reliable is True
    assert e.has_text is True
    assert e.sections == []
    assert e.pages == []
    assert e.note is None
    assert e.has_more_pages is False


# ---------------------------------------------------------------------------
# Live test (isteğe bağlı — varsayılan olarak çalıştırılmaz)
# ---------------------------------------------------------------------------


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_open_thesis_extract():
    """Gerçek YÖKTEZ üzerinde küçük bir açık teze erişir ve metin çıkarır.

    Bu testin çalışması için YÖKTEZ'de açık, pdf_key'i bilinen bir tez gerekir.
    Test sadece 'not live' filtresi kaldırıldığında çalışır:
        uv run pytest tests/test_pdf.py -m live -v
    """
    # Not: Bu test gerçek bir pdf_key ve URL gerektirir.
    # Faz 0 probe çıktısından doğrulanmış bir açık tez örneği eklenmelidir.
    pytest.skip("Live tez URL ve pdf_key henüz yapılandırılmadı — Faz 0 probundan sonra doldurun.")
