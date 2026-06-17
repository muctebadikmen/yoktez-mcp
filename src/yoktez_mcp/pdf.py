"""PDF indirme ve metne/Markdown'a dönüştürme — YÖKTEZ tezleri için.

Dijital (metin katmanı olan) PDF'ler için pypdf ile sayfa-bazlı metin çıkarımı.
Taranmış (görüntü) ya da bozuk-font PDF'lerde metin güvenilmezdir; bu durumda
DÜRÜSTÇE ``text_reliable=False`` döner. OCR YAPILMAZ: ücretsiz, anahtarsız ve
herkes için sürtünmesiz bir OCR yolu bulunmadığından bilinçli olarak kapsam dışıdır.

ERİŞİM KORUYUCU: ``download_and_extract`` yalnızca AÇIK (OPEN) tezler için
``pdf_key`` ile çağrılabilir. İzinsiz veya anahtar eksik tezlerde ağ çağrısı
YAPILMADAN hata yükseltir — kısıtlı PDF indirme asla gerçekleşmez.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field

from pypdf import PdfReader

from . import http
from .models import AccessStatus

# ---------------------------------------------------------------------------
# Sabitler
# ---------------------------------------------------------------------------

# Türkçe + yaygın Batı Avrupa harfleri. Bazı bozuk PDF fontları gerçek harfleri
# egzotik Latin-Extended glyph'lerine (ů ŵ Ă ǌ Ŧ …) eşler; bunlar teknik olarak
# "Latin"dir ama Türkçe/İngilizce'de geçmez. Bu yüzden "beklenen karakter" kümesine
# göre oran bakarız.
EXPECTED_LETTERS = set(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "çğıİöşüÇĞÖŞÜ"
    "àáâäãåèéêëìíîïòóôöõùúûüñýÿæœøÀÁÂÄÃÅÈÉÊËÌÍÎÏÒÓÔÖÕÙÚÛÜÑ"
)

# Oran bu eşiğin altındaysa metin büyük olasılıkla bozuk/yanlış kodlanmıştır.
READABLE_RATIO_THRESHOLD = 0.80

MAX_PDF_BYTES = 80 * 1024 * 1024  # 80 MB güvenlik sınırı

# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


@dataclass
class ExtractedPDF:
    source_url: str
    page_count: int
    pages: list[str] = field(default_factory=list)
    markdown: str = ""
    has_text: bool = True
    text_reliable: bool = True
    note: str | None = None
    sections: list[dict] = field(default_factory=list)
    start_page: int = 1
    end_page: int = 0
    has_more_pages: bool = False


# ---------------------------------------------------------------------------
# Tez bölüm başlıkları (Turkish thesis section headings)
# ---------------------------------------------------------------------------

# Türkçe-duyarlı büyük-harf katlama ile normalize edilmiş bölüm anahtar kelimeleri.
# Hem Türkçe tez hem de yabancı dil tezlerin İngilizce/Latince başlıklarını kapsar.
_SECTION_KEYWORDS = {
    # Özet / abstract
    "OZET", "ABSTRACT",
    # İçindekiler
    "ICINDEKILER",
    # Giriş
    "GIRIS", "INTRODUCTION",
    # Genel bilgiler / kavramsal çerçeve
    "GENEL BILGILER", "LITERATUR OZETI", "LITERATUR TARAMASI",
    "KAVRAMSAL CERCEVE", "KURAMSAL CERCEVE", "LITERATURE REVIEW",
    # Yöntem / gereç
    "YONTEM", "YONTEMLER", "GEREC VE YONTEM", "MATERYAL VE YONTEM",
    "ARASTIRMA YONTEMI",
    "METHOD", "METHODS", "METHODOLOGY", "MATERIALS AND METHODS",
    "MATERIAL AND METHODS",
    # Bulgular
    "BULGULAR", "BULGULAR VE TARTISMA",
    "RESULTS", "FINDINGS", "RESULTS AND DISCUSSION",
    # Tartışma
    "TARTISMA", "DISCUSSION",
    # Sonuç / öneriler
    "SONUC", "SONUCLAR", "SONUC VE ONERILER", "ONERILER",
    "CONCLUSION", "CONCLUSIONS", "CONCLUSION AND RECOMMENDATIONS",
    "RECOMMENDATIONS",
    # Kaynaklar
    "KAYNAKCA", "KAYNAKLAR", "REFERANSLAR",
    "REFERENCES", "BIBLIOGRAPHY",
    # Ekler
    "EKLER", "EK", "APPENDIX", "APPENDICES",
    # Özgeçmiş
    "OZGECMIS", "CURRICULUM VITAE", "CV",
    # Teşekkür
    "TESEKKUR", "ACKNOWLEDGEMENT", "ACKNOWLEDGEMENTS", "ACKNOWLEDGMENTS",
}


# ---------------------------------------------------------------------------
# Yardımcı fonksiyonlar
# ---------------------------------------------------------------------------


def _fold_upper(s: str) -> str:
    """Türkçe-duyarlı büyük-harf katlama: ı/İ/ş/ğ/ü/ö/ç → ascii muadili, sonra upper."""
    table = str.maketrans({
        "ı": "i", "İ": "i", "ş": "s", "ğ": "g", "ü": "u", "ö": "o", "ç": "c",
        "Ş": "S", "Ğ": "G", "Ü": "U", "Ö": "O", "Ç": "C", "I": "I",
    })
    return s.translate(table).upper()


def _heading_if_any(line: str) -> str | None:
    """Satır bir bölüm başlığıysa (numaralandırma toleranslı) orijinal satırı döndürür."""
    stripped = line.strip()
    if not stripped or len(stripped) > 80:
        return None
    # Baştaki "1.", "1.2", "I.", "A)" gibi numaralandırmayı at.
    core = re.sub(r"^\s*([0-9]+([.\)][0-9]*)*|[IVXLC]+|[A-Da-d])[.\)]\s*", "", stripped).strip()
    if _fold_upper(core) in _SECTION_KEYWORDS:
        return stripped
    return None


def _normalize(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Satır sonu tireleme birleştirme: "kelime-\ndevam" -> "kelimedevam"
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    # Aşırı boş satırları sadeleştir
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Kamuya açık API
# ---------------------------------------------------------------------------


def split_sections(text: str) -> list[dict]:
    """Düz metni tez bölümlerine ayırır (en iyi çaba). ``[{heading, text}]`` döndürür.

    Hiç başlık bulunamazsa boş liste döner (markdown yine tam metni içerir).
    """
    sections: list[dict] = []
    cur_head: str | None = None
    cur: list[str] = []
    found_any = False
    for line in text.split("\n"):
        h = _heading_if_any(line)
        if h is not None:
            body = "\n".join(cur).strip()
            if cur_head is not None or body:
                sections.append({"heading": cur_head or "(başlık öncesi)", "text": body})
            cur_head = h
            cur = []
            found_any = True
        else:
            cur.append(line)
    if found_any:
        body = "\n".join(cur).strip()
        if cur_head is not None or body:
            sections.append({"heading": cur_head or "(başlık öncesi)", "text": body})
    return [s for s in sections if s["text"]]


def readable_ratio(text: str, sample: int = 3000) -> float:
    """Alfabetik karakterler içinde "beklenen" (Türkçe/Batı Avrupa) harf oranı.

    Düzgün metinde ~1.0; yanlış kodlanmış (bozuk font) metinde belirgin düşer
    (gerçek dünyada temiz ~1.00, bozuk ~0.11). Hız için ilk ``sample`` alfabetik
    karakter örneklenir.
    """
    letters: list[str] = []
    for ch in text:
        if ch.isalpha():
            letters.append(ch)
            if len(letters) >= sample:
                break
    if not letters:
        return 1.0
    good = sum(1 for ch in letters if ch in EXPECTED_LETTERS)
    return good / len(letters)


def _assess(pages: list[str]) -> tuple[bool, bool, str | None]:
    """Çıkarılan sayfalardan (has_text, text_reliable, note) kararı verir.

    DÜRÜSTLÜK çekirdeği. Üç başarısızlık biçimini yakalar:
      1) Hiç/çok az içerik → taranmış (görüntü) belge.
      2) İçerik çoğunlukla RAKAM/SİMGE (gerçek kelime yok; ör. yalnızca sayfa
         numaraları çıkmış) → taranmış belge; metin GÜVENİLMEZ.
      3) Harf var ama egzotik/yanlış glyph (bozuk-font) → readable_ratio düşük.
    """
    full = "\n".join(pages)
    nonspace = sum(1 for c in full if not c.isspace())
    letters = sum(1 for c in full if c.isalpha())
    if nonspace <= 10:
        return False, False, (
            "Bu PDF'ten metin çıkarılamadı — büyük olasılıkla taranmış (görüntü) belge. "
            "Güvenilir metin elde edilemedi (OCR yapılmaz)."
        )
    # Gerçek kelime yoksa (harf oranı çok düşük) → taranmış; sadece sayfa no/parça çıkmış.
    if letters / nonspace < 0.5:
        return False, False, (
            "Anlamlı metin çıkmadı — büyük olasılıkla taranmış/görüntü belge (yalnızca sayfa "
            "numarası gibi kopuk parçalar elde edildi). Metne GÜVENMEYİN; OCR yapılmaz. "
            "Tezi orijinal kaynağından okuyun."
        )
    ratio = readable_ratio(full)
    if ratio < READABLE_RATIO_THRESHOLD:
        return True, False, (
            f"DİKKAT: Çıkarılan metin güvenilir DEĞİL (okunabilir karakter oranı %{ratio * 100:.0f}). "
            "PDF fontu düzgün Unicode (ToUnicode) eşlemesi içermiyor; çıkarılan metin bozuk/anlamsız. "
            "Bu metne güvenmeyin — tezi orijinal kaynağından okuyun."
        )
    return True, True, None


def extract(
    data: bytes,
    source_url: str,
    max_pages: int | None = None,
    start_page: int = 1,
) -> ExtractedPDF:
    """PDF'ten metin çıkarır. ``start_page`` (1-tabanlı) ve ``max_pages`` ile
    uzun tezler sayfa-sayfa gezilebilir (araç-içi sayfalama).

    ``text_reliable`` dürüstçe ayarlanır; OCR YAPILMAZ.
    """
    reader = PdfReader(io.BytesIO(data))
    total = len(reader.pages)

    start_idx = max(0, start_page - 1)
    end_idx = total if max_pages is None else min(start_idx + max_pages, total)
    start_idx = min(start_idx, total)

    pages: list[str] = []
    for i in range(start_idx, end_idx):
        try:
            raw = reader.pages[i].extract_text() or ""
        except Exception as exc:  # bozuk sayfa tek tek atlanır
            pages.append(f"[sayfa {i + 1} çıkarılamadı: {exc}]")
            continue
        pages.append(_normalize(raw))

    body = "\n\n".join(
        f"## Sayfa {start_idx + i + 1}\n\n{txt}" if txt
        else f"## Sayfa {start_idx + i + 1}\n\n_(boş veya görüntü)_"
        for i, txt in enumerate(pages)
    )
    full_text = "\n".join(pages)
    has_more = end_idx < total

    if not pages:
        has_text, text_reliable = False, False
        note = (
            f"Sayfa aralığında ({start_idx + 1}-{end_idx}/{total}) içerik yok. "
            "start_page/max_pages değerlerini belge sayfa sayısına göre ayarlayın."
        )
    else:
        has_text, text_reliable, note = _assess(pages)

    sections = split_sections(full_text) if (has_text and text_reliable) else []

    header = (
        f"# Tam metin (PDF)\n\nKaynak: {source_url}\n"
        f"Sayfa aralığı: {start_idx + 1}-{end_idx} / {total}\n\n---\n\n"
    )
    return ExtractedPDF(
        source_url=source_url,
        page_count=total,
        pages=pages,
        markdown=header + body,
        has_text=has_text,
        text_reliable=text_reliable,
        note=note,
        sections=sections,
        start_page=start_idx + 1,
        end_page=end_idx,
        has_more_pages=has_more,
    )


async def download_and_extract(
    pdf_url: str,
    *,
    access_status: AccessStatus | None = None,
    pdf_key: str | None = None,
    max_pages: int | None = None,
    start_page: int = 1,
) -> ExtractedPDF:
    """Tez PDF'ini indirir ve metin çıkarır.

    ERİŞİM KORUYUCU: Ağ çağrısı yapılmadan önce erişim durumu doğrulanır.
    - ``access_status`` ``OPEN`` değilse hata yükseltir.
    - ``pdf_key`` eksikse hata yükseltir.

    Kısıtlı (izinsiz) tez PDF'i hiçbir zaman indirilmez.
    """
    # --- Ağ öncesi kontrol: erişim durumu ---
    if access_status is not None and access_status != AccessStatus.OPEN:
        raise PermissionError(
            f"Bu tezin PDF'i indirilemez: erişim durumu '{access_status.value}'. "
            "Yalnızca OPEN (izinli/açık) tezlerin PDF'leri indirilebilir. "
            "YÖK'ün erişim kısıtlamasına saygı gösterilir — izinsiz PDF indirilmez."
        )

    # --- Ağ öncesi kontrol: pdf_key ---
    if not pdf_key:
        raise ValueError(
            "pdf_key eksik. TezGoster?key=... URL'si oluşturmak için pdf_key gereklidir. "
            "Yalnızca açık (izinli) tezlerin pdf_key'i bulunur — kısıtlı tezlerde bu alan boştur."
        )

    # Tüm kontroller geçti → indir
    data = await http.get_bytes(pdf_url)
    if len(data) > MAX_PDF_BYTES:
        raise ValueError(
            f"PDF çok büyük ({len(data)} bayt > {MAX_PDF_BYTES}). İndirme iptal edildi."
        )
    # Temel PDF magic byte kontrolü
    if not data[:5].startswith(b"%PDF"):
        raise ValueError("İndirilen veri geçerli bir PDF değil (beklenen %PDF başlığı).")
    return extract(data, pdf_url, max_pages=max_pages, start_page=start_page)


def references_section(extracted: ExtractedPDF) -> str | None:
    """KAYNAKÇA veya KAYNAKLAR bölümünün metnini döndürür; bulunamazsa ``None``.

    Bölüm başlıkları Türkçe tez standartlarına göre eşleştirilir.
    """
    reference_keys = {"KAYNAKCA", "KAYNAKLAR", "REFERANSLAR", "REFERENCES", "BIBLIOGRAPHY"}
    for sec in extracted.sections:
        heading_folded = _fold_upper(sec.get("heading", ""))
        # Numaralandırma kalıntısını at ve saf başlıkla karşılaştır
        core = re.sub(r"^\s*([0-9]+([.\)][0-9]*)*|[IVXLC]+|[A-Da-d])[.\)]\s*", "", heading_folded).strip()
        if core in reference_keys:
            return sec.get("text") or None
    return None
