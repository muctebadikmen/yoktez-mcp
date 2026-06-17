"""Akademik atıf biçimlendirme — YÖK Ulusal Tez Merkezi tezleri için.

Bu modül saf Python standart kütüphanesi ile yazılmıştır (bağımlılık yok).
Bir YÖK tezinden elde edilen meta verileri alıp; makine-okunur (BibTeX, RIS,
CSL-JSON) ve insan-okunur (APA, MLA, IEEE, Chicago, Harvard) atıf çıktıları
üretir.

Türkçe karakterler (İ ı ş ğ ü ö ç) insan-okunur çıktılarda, CSL-JSON ve RIS
çıktılarında KORUNUR — yalnızca BibTeX anahtarı ASCII'ye katlanır.

Tez türü eşlemesi:
  Yüksek Lisans  → @mastersthesis (BibTeX), "Yüksek lisans tezi" (APA)
  Doktora        → @phdthesis,     "Doktora tezi"
  Tıpta Uzmanlık → @phdthesis,     "Tıpta uzmanlık tezi"
  Sanatta Yeterlik → @phdthesis,   "Sanatta yeterlik tezi"
  Diş Hekimliği Uzmanlık → @phdthesis, "Diş hekimliği uzmanlık tezi"
  Tıpta Yan Dal Uzmanlık → @phdthesis, "Tıpta yan dal uzmanlık tezi"
  Eczacılıkta Uzmanlık   → @phdthesis, "Eczacılıkta uzmanlık tezi"

Deliberate deviations from YÖK server-rendered citations (tezBilgiDetay.json):
  1. Author casing: YÖK uses ALL-CAPS family names (KILIÇ); we use proper case.
  2. "YÖK Ulusal Tez Merkezi" vs YÖK's "Ulusal Tez Merkezi" — we use the full
     canonical name as specified in the task brief.
  3. APA includes (Tez No. XXXXX) in the bracket, matching YÖK's format.
  4. IEEE: we place university name, not just institute name, for clarity.
"""

from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from yoktez_mcp.models import Thesis

# Yayımcı sabiti — her atıf biçiminde tutarlı kullanım için.
_PUBLISHER = "YÖK Ulusal Tez Merkezi"

# APA için Türkçe tez türü etiketleri (küçük harf başlar, çünkü köşeli parantez
# içinde kullanılır: "[Doktora tezi, ...]").
_THESIS_TYPE_APA: dict[str, str] = {
    "Yüksek Lisans": "Yüksek lisans tezi",
    "Doktora": "Doktora tezi",
    "Tıpta Uzmanlık": "Tıpta uzmanlık tezi",
    "Sanatta Yeterlik": "Sanatta yeterlik tezi",
    "Diş Hekimliği Uzmanlık": "Diş hekimliği uzmanlık tezi",
    "Tıpta Yan Dal Uzmanlık": "Tıpta yan dal uzmanlık tezi",
    "Eczacılıkta Uzmanlık": "Eczacılıkta uzmanlık tezi",
}

# Doktora eşdeğeri tez türleri (@phdthesis).
_DOCTORAL_TYPES: frozenset[str] = frozenset({
    "Doktora",
    "Tıpta Uzmanlık",
    "Sanatta Yeterlik",
    "Diş Hekimliği Uzmanlık",
    "Tıpta Yan Dal Uzmanlık",
    "Eczacılıkta Uzmanlık",
})


# ---------------------------------------------------------------------------
# CitationData
# ---------------------------------------------------------------------------

@dataclass
class CitationData:
    """YÖK tezi atıf meta verisi.

    `author` tek bir tam isim (örn. "Zeynep Kılıç"). `thesis_type` THESIS_TYPE_BY_CODE
    etiketiyle eşleşmeli (örn. "Doktora", "Yüksek Lisans").
    """

    author: str | None = None
    year: str | None = None
    title: str | None = None
    thesis_type: str | None = None          # human label, e.g. "Doktora"
    university: str | None = None
    thesis_no: str | None = None            # human Tez No (e.g. "1009908")
    url: str | None = None
    language: str | None = None


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------

def _clean(value: str | None) -> str | None:
    """HTML entity'lerini çöz, boşlukları normalize et, boşsa None döndür."""
    if value is None:
        return None
    text = html.unescape(str(value))
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def split_name(full_name: str) -> tuple[str, str]:
    """Tam ismi (given, family) olarak böler.

    Sezgisel kural: family = son boşlukla ayrılmış parça, given = öncesi.
    Tek parça varsa family = o parça, given = "".
    Örnekler:
        "Zeynep Kılıç"  -> ("Zeynep", "Kılıç")
        "Ali Veli Han"  -> ("Ali Veli", "Han")
        "Madonna"       -> ("", "Madonna")
    """
    name = _clean(full_name) or ""
    parts = name.split()
    if not parts:
        return ("", "")
    if len(parts) == 1:
        return ("", parts[0])
    return (" ".join(parts[:-1]), parts[-1])


def _initials(given: str) -> str:
    """Verilen adı baş harflere indirger: "Zeynep" -> "Z.", "Ali Veli" -> "A. V."."""
    given = _clean(given) or ""
    if not given:
        return ""
    pieces: list[str] = []
    for word in given.split():
        sub = [p for p in re.split(r"-", word) if p]
        if not sub:
            continue
        joined = "-".join(f"{p[0]}." for p in sub)
        pieces.append(joined)
    return " ".join(pieces)


def _lastfirst(given: str, family: str, *, initials: bool = False) -> str:
    """"Soyad, Ad" biçimi — alanlardan biri boşsa baştaki/sondaki virgülü ÜRETMEZ."""
    g = _initials(given) if initials else (_clean(given) or "")
    f = _clean(family) or ""
    if f and g:
        return f"{f}, {g}"
    return f or g


def _ascii_fold(text: str) -> str:
    """Türkçe/Unicode karakterleri ASCII'ye katlar (yalnızca BibTeX anahtarı için)."""
    mapping = {
        "İ": "I", "ı": "i", "Ş": "S", "ş": "s", "Ğ": "G", "ğ": "g",
        "Ü": "U", "ü": "u", "Ö": "O", "ö": "o", "Ç": "C", "ç": "c",
    }
    text = "".join(mapping.get(ch, ch) for ch in text)
    normalized = unicodedata.normalize("NFKD", text)
    return normalized.encode("ascii", "ignore").decode("ascii")


def _bibtex_escape(value: str) -> str:
    """BibTeX değer kaçışı — alanlar {} ile sarıldığı için minimal."""
    return value.replace("\\", "\\textbackslash{}").replace("{", "\\{").replace("}", "\\}")


def _title_no_period(d: CitationData) -> str | None:
    title = _clean(d.title)
    if not title:
        return None
    return title.rstrip(".")


def _apa_thesis_label(thesis_type: str | None) -> str:
    """Tez türünü APA köşeli parantez etiketi olarak döndürür."""
    if not thesis_type:
        return "Tez"
    return _THESIS_TYPE_APA.get(thesis_type, f"{thesis_type} tezi")


# ---------------------------------------------------------------------------
# is_doctoral_equivalent
# ---------------------------------------------------------------------------

def is_doctoral_equivalent(thesis_type: str | None) -> bool:
    """Tez türü doktora eşdeğeri mi? Evet ise @phdthesis, hayır ise @mastersthesis."""
    if not thesis_type:
        return False
    return thesis_type in _DOCTORAL_TYPES


# ---------------------------------------------------------------------------
# BibTeX anahtar üretimi
# ---------------------------------------------------------------------------

def _bibtex_key(d: CitationData) -> str:
    """BibTeX anahtarı: <soyad><yıl>, ASCII'ye katlanmış."""
    year = _clean(d.year) or ""
    author = _clean(d.author)
    if author:
        _, family = split_name(author)
        if family:
            base = _ascii_fold(family).lower()
            base = re.sub(r"[^a-z0-9]", "", base)
            return f"{base}{year}" if base else (year or "thesis")
    return f"yoktez{year}" if year else "thesis"


# ---------------------------------------------------------------------------
# Makine-okunur biçimler
# ---------------------------------------------------------------------------

def to_bibtex(d: CitationData) -> str:
    """BibTeX girdisi döndürür. Tür: @phdthesis veya @mastersthesis."""
    entry_type = "phdthesis" if is_doctoral_equivalent(d.thesis_type) else "mastersthesis"
    key = _bibtex_key(d)

    fields: list[tuple[str, str]] = []

    author = _clean(d.author)
    if author:
        given, family = split_name(author)
        fields.append(("author", _lastfirst(given, family)))

    title = _clean(d.title)
    if title:
        fields.append(("title", title))

    uni = _clean(d.university)
    if uni:
        fields.append(("school", uni))

    year = _clean(d.year)
    if year:
        fields.append(("year", year))

    thesis_type = _clean(d.thesis_type)
    if thesis_type:
        fields.append(("type", thesis_type))

    fields.append(("note", _PUBLISHER))

    url = _clean(d.url)
    if url:
        fields.append(("url", url))

    lines = [f"@{entry_type}{{{key},"]
    body = [f"  {name} = {{{_bibtex_escape(value)}}}" for name, value in fields]
    lines.append(",\n".join(body))
    lines.append("}")
    return "\n".join(lines)


def to_ris(d: CitationData) -> str:
    """RIS biçimi döndürür. `ER  - ` ile ve sondaki yeni satır ile biter."""
    lines: list[str] = ["TY  - THES"]

    author = _clean(d.author)
    if author:
        given, family = split_name(author)
        lines.append(f"AU  - {_lastfirst(given, family)}")

    title = _clean(d.title)
    if title:
        lines.append(f"T1  - {title}")

    year = _clean(d.year)
    if year:
        lines.append(f"PY  - {year}")

    uni = _clean(d.university)
    if uni:
        lines.append(f"PB  - {uni}")

    thesis_no = _clean(d.thesis_no)
    if thesis_no:
        lines.append(f"U1  - Tez No: {thesis_no}")

    thesis_type = _clean(d.thesis_type)
    if thesis_type:
        lines.append(f"M3  - {thesis_type}")

    lines.append(f"DB  - {_PUBLISHER}")

    url = _clean(d.url)
    if url:
        lines.append(f"UR  - {url}")

    lines.append("ER  - ")
    return "\n".join(lines) + "\n"


def to_csl_json(d: CitationData) -> dict:
    """CSL-JSON öğe sözlüğü döndürür. Eksik alanlar atlanır."""
    item: dict = {"type": "thesis"}

    title = _clean(d.title)
    if title:
        item["title"] = title

    author = _clean(d.author)
    if author:
        given, family = split_name(author)
        if given:
            item["author"] = [{"given": given, "family": family}]
        else:
            item["author"] = [{"family": family}]

    year = _clean(d.year)
    if year:
        try:
            item["issued"] = {"date-parts": [[int(year)]]}
        except ValueError:
            item["issued"] = {"date-parts": [[year]]}

    thesis_type = _clean(d.thesis_type)
    if thesis_type:
        item["genre"] = thesis_type

    uni = _clean(d.university)
    if uni:
        item["publisher"] = _PUBLISHER
        item["publisher-place"] = uni

    item["publisher"] = _PUBLISHER
    item["archive"] = _PUBLISHER

    url = _clean(d.url)
    if url:
        item["URL"] = url

    return item


# ---------------------------------------------------------------------------
# İnsan-okunur biçimler
# ---------------------------------------------------------------------------

def format_apa(d: CitationData) -> str:
    """APA 7. baskı tez atıfı.

    Biçim: Soyad, A. (Yıl). *Başlık* (Tez No. XXXXX) [Tez türü, Üniversite]. YÖK Ulusal Tez Merkezi.
    """
    author = _clean(d.author)
    author_segment = ""
    if author:
        given, family = split_name(author)
        author_segment = _lastfirst(given, family, initials=True)

    year = _clean(d.year) or "n.d."

    parts: list[str] = []
    if author_segment:
        parts.append(f"{author_segment.rstrip('.')}.")
    parts.append(f"({year}).")

    title = _title_no_period(d)
    if title:
        parts.append(f"*{title}*")

    # Tez No parantezi
    thesis_no = _clean(d.thesis_no)
    tez_no_seg = f"(Tez No. {thesis_no})" if thesis_no else ""

    # Köşeli parantez: [Tür tezi, Üniversite]
    label = _apa_thesis_label(_clean(d.thesis_type))
    uni = _clean(d.university)
    bracket_inner = f"{label}, {uni}" if uni else label
    bracket = f"[{bracket_inner}]"

    title_line_parts = []
    if title:
        title_line_parts.append(f"*{title}*")
    if tez_no_seg:
        title_line_parts.append(tez_no_seg)
    title_line_parts.append(bracket + ".")

    # Rebuild parts without the title we already added
    parts_final: list[str] = []
    if author_segment:
        parts_final.append(f"{author_segment.rstrip('.')}.")
    parts_final.append(f"({year}).")
    parts_final.append(" ".join(title_line_parts))
    parts_final.append(f"{_PUBLISHER}.")

    return " ".join(parts_final)


def format_mla(d: CitationData) -> str:
    """MLA 9. baskı tez atıfı.

    Biçim: Soyad, Ad. *Başlık*. Üniversite, Yıl. Tür tezi. YÖK Ulusal Tez Merkezi.
    """
    author = _clean(d.author)
    author_segment = ""
    if author:
        given, family = split_name(author)
        author_segment = _lastfirst(given, family) + "."

    parts: list[str] = []
    if author_segment:
        parts.append(author_segment)

    title = _title_no_period(d)
    if title:
        parts.append(f"*{title}*.")

    uni = _clean(d.university)
    year = _clean(d.year)
    loc_segs: list[str] = []
    if uni:
        loc_segs.append(uni)
    if year:
        loc_segs.append(year)
    if loc_segs:
        parts.append(", ".join(loc_segs) + ".")

    label = _apa_thesis_label(_clean(d.thesis_type))
    parts.append(f"{label}.")

    parts.append(f"{_PUBLISHER}.")

    return " ".join(parts)


def format_ieee(d: CitationData) -> str:
    """IEEE tez atıfı.

    Biçim: A. Soyad, "Başlık," Tür tezi, Üniversite, Yıl.
    """
    author = _clean(d.author)
    author_segment = ""
    if author:
        given, family = split_name(author)
        ini = _initials(given)
        author_segment = f"{ini} {family}".strip() if ini else family

    title = _title_no_period(d)
    label = _apa_thesis_label(_clean(d.thesis_type))
    uni = _clean(d.university)
    year = _clean(d.year)

    parts: list[str] = []
    if author_segment and title:
        parts.append(f'{author_segment}, "{title},"')
    elif author_segment:
        parts.append(f"{author_segment},")
    elif title:
        parts.append(f'"{title},"')

    tail_segs: list[str] = [label]
    if uni:
        tail_segs.append(uni)
    if year:
        tail_segs.append(year)
    parts.append(", ".join(tail_segs) + ".")

    return " ".join(parts)


def format_chicago(d: CitationData) -> str:
    """Chicago (kaynakça) tez atıfı.

    Biçim: Soyad, Ad. "Başlık." Tür tezi, Üniversite, Yıl.
    """
    author = _clean(d.author)
    author_segment = ""
    if author:
        given, family = split_name(author)
        author_segment = _lastfirst(given, family) + "."

    parts: list[str] = []
    if author_segment:
        parts.append(author_segment)

    title = _title_no_period(d)
    if title:
        parts.append(f'"{title}."')

    label = _apa_thesis_label(_clean(d.thesis_type))
    uni = _clean(d.university)
    year = _clean(d.year)

    tail_segs: list[str] = [label]
    if uni:
        tail_segs.append(uni)
    if year:
        tail_segs.append(year)
    parts.append(", ".join(tail_segs) + ".")

    return " ".join(parts)


def format_harvard(d: CitationData) -> str:
    """Harvard tez atıfı.

    Biçim: Soyad, A. (Yıl) *Başlık*. Tür tezi. Üniversite. YÖK Ulusal Tez Merkezi.
    """
    author = _clean(d.author)
    author_segment = ""
    if author:
        given, family = split_name(author)
        author_segment = _lastfirst(given, family, initials=True)

    year = _clean(d.year) or "n.d."

    parts: list[str] = []
    if author_segment:
        parts.append(author_segment)
    parts.append(f"({year})")

    head = " ".join(parts)

    title = _title_no_period(d)
    label = _apa_thesis_label(_clean(d.thesis_type))
    uni = _clean(d.university)

    segs: list[str] = []
    if title:
        segs.append(f"*{title}*.")
    segs.append(f"{label}.")
    if uni:
        segs.append(f"{uni}.")
    segs.append(f"{_PUBLISHER}.")

    return f"{head} " + " ".join(segs)


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_DISPATCH = {
    "apa": format_apa,
    "mla": format_mla,
    "ieee": format_ieee,
    "chicago": format_chicago,
    "harvard": format_harvard,
}


def format_citation(d: CitationData, style: str) -> str:
    """Stil adına göre uygun biçimlendiriciyi çağırır (büyük/küçük harf duyarsız)."""
    key = (style or "").strip().lower()
    if key not in _DISPATCH:
        valid = ", ".join(sorted(_DISPATCH))
        raise ValueError(f"Bilinmeyen atıf stili: {style!r}. Geçerli: {valid}")
    return _DISPATCH[key](d)


def all_citations(d: CitationData) -> dict:
    """Tüm biçimleri tek sözlükte döndürür (8 anahtar)."""
    return {
        "bibtex": to_bibtex(d),
        "ris": to_ris(d),
        "csl_json": to_csl_json(d),
        "apa": format_apa(d),
        "mla": format_mla(d),
        "ieee": format_ieee(d),
        "chicago": format_chicago(d),
        "harvard": format_harvard(d),
    }


# ---------------------------------------------------------------------------
# from_thesis convenience helper
# ---------------------------------------------------------------------------

def from_thesis(thesis: Thesis) -> CitationData:
    """Maps a Thesis dataclass to a CitationData for citation generation.

    Uses title_tr preferentially, falls back to title_en.
    Builds a TezGoster URL if pdf_key is available.
    """
    title = thesis.title_tr or thesis.title_en

    url: str | None = None
    if hasattr(thesis, "pdf_key") and thesis.pdf_key:
        url = (
            f"https://tez.yok.gov.tr/UlusalTezMerkezi/TezGoster?key={thesis.pdf_key}"
        )

    return CitationData(
        author=thesis.author,
        year=str(thesis.year) if thesis.year is not None else None,
        title=title,
        thesis_type=thesis.thesis_type,
        university=thesis.university,
        thesis_no=thesis.thesis_no,
        url=url,
        language=thesis.language,
    )
