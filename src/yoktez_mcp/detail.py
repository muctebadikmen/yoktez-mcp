"""detail.py — YÖKTEZ tez detayı + erişim ayrıştırma.

İki AJAX endpoint'i tüketir:

* ``tezBilgiDetay.jsp?kayitNo=...&tezNo=...``  → JSON (metin/html olarak gelir)
  Alanlar: danisman, yer, trOzet, enOzet, anahtarKelimeTr, anahtarKelimeEn,
  apa_ref, ieee_ref, mla_ref, chicago_ref, harvard_ref.

* ``getTezPdf.jsp?kayitNo=...&tezNo=...`` → küçük HTML parçası
  İzinli ⇔ ``TezGoster?key=<ŞIFRELI>`` bağlantısı ve ``pdfizinli.png`` mevcut.
  İzinsiz ⇔ ``pdf-info-msg`` sınıflı span mevcut; TezGoster bağlantısı yok.

Dürüstlük ilkeleri (ürünün omurgası):
- Kısıtlı tezin özeti JSON'da boş gelir → None döndürülür, asla uydurulmaz.
- Erişim nedeni (restriction reason) verbatim YÖK metninden alınır.
- ``text_reliable`` bayrağı bu modülün sorumluluğu değildir (pdf.py sorumluluğu).
"""

from __future__ import annotations

import json
import re

from .http import BASE_URL, get_text
from .models import AccessStatus, SearchHit, Thesis

# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------

_RE_STRIP_TAGS = re.compile(r"<[^>]+>")
_RE_PDF_KEY = re.compile(r"TezGoster\?key=([^'\"&\s]+)")
_RE_WHITESPACE = re.compile(r"\s+")


def _strip_html(text: str) -> str:
    """HTML etiketlerini kaldırır, boşlukları normalleştirir."""
    return _RE_WHITESPACE.sub(" ", _RE_STRIP_TAGS.sub("", text)).strip()


def _split_keywords(raw: str) -> list[str]:
    """Anahtar kelime HTML alanını ayrıştırır ve liste döndürür.

    Kılavuz değerler: ``<strong></strong>`` (boş) veya
    ``<strong>kelime1; kelime2</strong>`` benzeri.
    Ayırıcıyı ; ya da , olarak dener; boşsa [] döner.
    """
    text = _strip_html(raw)
    if not text:
        return []
    # Noktalı virgül önce, sonra virgül
    for sep in (";", ","):
        parts = [p.strip() for p in text.split(sep)]
        if len(parts) > 1:
            return [p for p in parts if p]
    return [text] if text else []


# ---------------------------------------------------------------------------
# parse_detail
# ---------------------------------------------------------------------------


def parse_detail(json_text: str) -> dict:
    """``tezBilgiDetay.jsp`` JSON metnini ayrıştırır; normalize edilmiş dict döndürür.

    Döndürülen anahtarlar:
      advisor, university, institute, department, science_branch,
      abstract_tr, abstract_en, keywords_tr, keywords_en, server_citations.

    Kısıtlı tezlerde özet alanları boş string gelir → None döndürülür.
    Anahtar kelimeler genellikle boş HTML gelir → [] döndürülür.
    """
    data = json.loads(json_text)

    # --- Danışman: '<strong>Danışman: </strong>AD SOYAD' biçimindeki HTML alanı.
    # <strong> etiketi kaldırıldığında içerik metni ("Danışman: ") de kalır,
    # bu yüzden tag'i içeriğiyle birlikte silerek sadece sonrasındaki adı alıyoruz.
    danisman_raw = data.get("danisman", "")
    # <strong>...</strong> bloğunu (içeriğiyle birlikte) kaldır
    danisman_no_label = re.sub(r"<strong[^>]*>.*?</strong>", "", danisman_raw, flags=re.DOTALL)
    advisor = _strip_html(danisman_no_label) or None

    # --- Yer: 'ÜNİV / ENSTİTÜ / ANABİLİM DALI / Bilim Dalı' → 4 parça ---
    # Ayırıcı tam olarak ' / ' (boşluk-eğik çizgi-boşluk).
    # Bazı kayıtlarda bilim dalı eksik olabilir (3 parça).
    yer = data.get("yer", "")
    parts = [p.strip() for p in yer.split(" / ")] if yer else []

    university = parts[0] if len(parts) > 0 else None
    institute = parts[1] if len(parts) > 1 else None
    department = parts[2] if len(parts) > 2 else None
    science_branch = parts[3] if len(parts) > 3 else None

    # --- Özetler: boş string → None (uydurma yok) ---
    abstract_tr = data.get("trOzet") or None
    abstract_en = data.get("enOzet") or None

    # --- Anahtar kelimeler: HTML ayrıştır, liste yap ---
    keywords_tr = _split_keywords(data.get("anahtarKelimeTr", ""))
    keywords_en = _split_keywords(data.get("anahtarKelimeEn", ""))

    # --- Sunucu atıf metinleri: cross-check için sakla ---
    server_citations = {
        "apa": data.get("apa_ref", ""),
        "ieee": data.get("ieee_ref", ""),
        "mla": data.get("mla_ref", ""),
        "chicago": data.get("chicago_ref", ""),
        "harvard": data.get("harvard_ref", ""),
    }

    return {
        "advisor": advisor,
        "university": university,
        "institute": institute,
        "department": department,
        "science_branch": science_branch,
        "abstract_tr": abstract_tr,
        "abstract_en": abstract_en,
        "keywords_tr": keywords_tr,
        "keywords_en": keywords_en,
        "server_citations": server_citations,
    }


# ---------------------------------------------------------------------------
# parse_access
# ---------------------------------------------------------------------------


def parse_access(fragment_html: str) -> tuple[AccessStatus, str | None, str | None]:
    """``getTezPdf.jsp`` HTML parçasından erişim durumunu çıkarır.

    Dönüş: ``(status, reason, pdf_key)``

    * İzinli ⇔ ``TezGoster?key=<ŞIFRELI>`` bağlantısı mevcut
      → ``(OPEN, None, <anahtar>)``
    * İzinsiz ⇔ ``pdf-info-msg`` sınıflı span mevcut
      → ``(RESTRICTED, <verbatim YÖK metni>, None)``
    * Hiçbiri → ``(UNKNOWN, None, None)``
    """
    # İzinli: TezGoster?key= regex'i ara
    m = _RE_PDF_KEY.search(fragment_html)
    if m:
        return (AccessStatus.OPEN, None, m.group(1))

    # İzinsiz: pdf-info-msg sınıfını ara, içeriği çıkar
    msg_match = re.search(
        r"class=['\"]pdf-info-msg['\"][^>]*>(.*?)</span>",
        fragment_html,
        re.DOTALL,
    )
    if msg_match:
        reason = _strip_html(msg_match.group(1))
        return (AccessStatus.RESTRICTED, reason, None)

    return (AccessStatus.UNKNOWN, None, None)


# ---------------------------------------------------------------------------
# get_thesis
# ---------------------------------------------------------------------------


async def get_thesis(
    kayit_no: str,
    tez_no: str,
    *,
    base_meta: SearchHit | None = None,
) -> Thesis:
    """Tez detayını + erişim durumunu alır, birleştirerek ``Thesis`` döndürür.

    İki AJAX çağrısı yapar:
      1. ``tezBilgiDetay.jsp`` → JSON meta (danışman, yer, özetler, atıflar)
      2. ``getTezPdf.jsp``     → HTML parçası (izin durumu + PDF anahtarı)

    ``base_meta`` (SearchHit) varsa; author, year, title, thesis_type gibi
    arama kartından gelen alanlar Thesis'e taşınır.
    """
    params = {"kayitNo": kayit_no, "tezNo": tez_no}

    detail_url = f"{BASE_URL}/tezBilgiDetay.jsp"
    pdf_url = f"{BASE_URL}/getTezPdf.jsp"

    detail_json, pdf_html = (
        await get_text(detail_url, params=params),
        await get_text(pdf_url, params=params),
    )

    detail = parse_detail(detail_json)
    status, reason, pdf_key = parse_access(pdf_html)

    thesis = Thesis(
        kayit_no=kayit_no,
        tez_no=tez_no,
        # Detaydan gelen alanlar
        advisor=detail["advisor"],
        university=detail["university"],
        institute=detail["institute"],
        department=detail["department"],
        science_branch=detail["science_branch"],
        abstract_tr=detail["abstract_tr"],
        abstract_en=detail["abstract_en"],
        keywords_tr=detail["keywords_tr"],
        keywords_en=detail["keywords_en"],
        # Erişim durumu
        access_status=status,
        access_reason=reason,
        pdf_key=pdf_key,
    )

    # base_meta'dan gelen arama kartı alanlarını uygula (boş değilse)
    if base_meta is not None:
        if base_meta.thesis_no is not None:
            thesis.thesis_no = base_meta.thesis_no
        if base_meta.title_tr is not None:
            thesis.title_tr = base_meta.title_tr
        if base_meta.title_en is not None:
            thesis.title_en = base_meta.title_en
        if base_meta.author is not None:
            thesis.author = base_meta.author
        if base_meta.year is not None:
            thesis.year = base_meta.year
        if base_meta.thesis_type is not None:
            thesis.thesis_type = base_meta.thesis_type
        # university from base_meta overrides only if detail didn't have one
        if thesis.university is None and base_meta.university is not None:
            thesis.university = base_meta.university

    return thesis
