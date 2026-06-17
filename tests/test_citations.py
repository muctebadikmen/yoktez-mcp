"""Tez atıf biçimlendirme — offline (ağ gerektirmez)."""

import pytest

from yoktez_mcp import citations
from yoktez_mcp.citations import CitationData, from_thesis
from yoktez_mcp.models import Thesis

# ---------------------------------------------------------------------------
# Ortak fixture'lar
# ---------------------------------------------------------------------------

def doktora_data() -> CitationData:
    """Doktora tezi örneği — fixture tezBilgiDetay.json'dan adapte."""
    return CitationData(
        author="Zeynep Kılıç",
        year="2026",
        title="Makine öğrenmesi algoritmaları ile Bitcoin fiyat tahmini",
        thesis_type="Doktora",
        university="Fırat Üniversitesi",
        thesis_no="1009908",
        url="https://tez.yok.gov.tr/UlusalTezMerkezi/TezGoster?key=abc123",
        language="Türkçe",
    )


def yuksek_lisans_data() -> CitationData:
    """Yüksek Lisans tezi örneği."""
    return CitationData(
        author="Zeynep Kılıç",
        year="2026",
        title="Makine öğrenmesi algoritmaları ile Bitcoin fiyat tahmini",
        thesis_type="Yüksek Lisans",
        university="Fırat Üniversitesi",
        thesis_no="1009908",
        url="https://tez.yok.gov.tr/UlusalTezMerkezi/TezGoster?key=abc123",
        language="Türkçe",
    )


def tipta_uzmanlik_data() -> CitationData:
    return CitationData(
        author="Ahmet Yılmaz",
        year="2023",
        title="Hipertansiyon Tedavisinde Yeni Yaklaşımlar",
        thesis_type="Tıpta Uzmanlık",
        university="Hacettepe Üniversitesi",
        thesis_no="888888",
    )


def sanatta_yeterlik_data() -> CitationData:
    return CitationData(
        author="Ayşe Demir",
        year="2022",
        title="Çağdaş Türk Resim Sanatında Soyutlama",
        thesis_type="Sanatta Yeterlik",
        university="Mimar Sinan Güzel Sanatlar Üniversitesi",
        thesis_no="777777",
    )


# ---------------------------------------------------------------------------
# from_thesis helper
# ---------------------------------------------------------------------------

def test_from_thesis_uses_human_thesis_no_not_opaque_key():
    """Regression: from_thesis must map thesis_no (human Tez No), not tez_no (opaque key)."""
    t = Thesis(
        kayit_no="k",
        tez_no="OPAQUE_KEY_XYZ",
        thesis_no="1009908",
        author="Zeynep Kılıç",
        year=2026,
        title_tr="Test",
        thesis_type="Yüksek Lisans",
        university="Fırat Üniversitesi",
    )
    d = from_thesis(t)
    apa = citations.format_apa(d)
    assert "1009908" in apa, "APA must contain the human Tez No"
    assert "OPAQUE_KEY_XYZ" not in apa, "APA must never expose the opaque key"
    assert d.thesis_no == "1009908"


def test_from_thesis_maps_correctly():
    t = Thesis(
        kayit_no="12345",
        tez_no="OPAQUE_ENCRYPTED_KEY",
        thesis_no="1009908",
        author="Zeynep Kılıç",
        year=2026,
        title_tr="Makine öğrenmesi algoritmaları ile Bitcoin fiyat tahmini",
        thesis_type="Yüksek Lisans",
        university="Fırat Üniversitesi",
        language="Türkçe",
    )
    d = from_thesis(t)
    assert d.author == "Zeynep Kılıç"
    assert d.year == "2026"
    assert d.title == "Makine öğrenmesi algoritmaları ile Bitcoin fiyat tahmini"
    assert d.thesis_type == "Yüksek Lisans"
    assert d.university == "Fırat Üniversitesi"
    assert d.thesis_no == "1009908"  # human Tez No, not the opaque key
    assert d.language == "Türkçe"


def test_from_thesis_with_english_title_fallback():
    t = Thesis(
        kayit_no="99",
        tez_no="99",
        author="Ali Veli",
        year=2021,
        title_tr=None,
        title_en="An English Title",
        thesis_type="Doktora",
        university="İstanbul Üniversitesi",
    )
    d = from_thesis(t)
    assert d.title == "An English Title"


def test_from_thesis_builds_url_when_pdf_key_present():
    t = Thesis(
        kayit_no="99",
        tez_no="99",
        author="Ali Veli",
        year=2021,
        title_tr="Başlık",
        thesis_type="Doktora",
        university="İstanbul Üniversitesi",
        pdf_key="abc123",
    )
    d = from_thesis(t)
    assert d.url is not None
    assert "TezGoster" in d.url
    assert "abc123" in d.url


# ---------------------------------------------------------------------------
# is_doctoral_equivalent helper
# ---------------------------------------------------------------------------

def test_doctoral_equivalent_doktora():
    from yoktez_mcp.citations import is_doctoral_equivalent
    assert is_doctoral_equivalent("Doktora") is True


def test_doctoral_equivalent_tipta_uzmanlik():
    from yoktez_mcp.citations import is_doctoral_equivalent
    assert is_doctoral_equivalent("Tıpta Uzmanlık") is True


def test_doctoral_equivalent_sanatta_yeterlik():
    from yoktez_mcp.citations import is_doctoral_equivalent
    assert is_doctoral_equivalent("Sanatta Yeterlik") is True


def test_doctoral_equivalent_dis_hekimligi():
    from yoktez_mcp.citations import is_doctoral_equivalent
    assert is_doctoral_equivalent("Diş Hekimliği Uzmanlık") is True


def test_doctoral_equivalent_tipta_yan_dal():
    from yoktez_mcp.citations import is_doctoral_equivalent
    assert is_doctoral_equivalent("Tıpta Yan Dal Uzmanlık") is True


def test_doctoral_equivalent_eczacilikta():
    from yoktez_mcp.citations import is_doctoral_equivalent
    assert is_doctoral_equivalent("Eczacılıkta Uzmanlık") is True


def test_doctoral_equivalent_yuksek_lisans_is_false():
    from yoktez_mcp.citations import is_doctoral_equivalent
    assert is_doctoral_equivalent("Yüksek Lisans") is False


# ---------------------------------------------------------------------------
# APA
# ---------------------------------------------------------------------------

def test_apa_doktora_bracket_and_suffix():
    out = citations.format_apa(doktora_data())
    assert "[Doktora tezi, " in out
    assert out.rstrip().endswith("YÖK Ulusal Tez Merkezi.")


def test_apa_yuksek_lisans_bracket():
    out = citations.format_apa(yuksek_lisans_data())
    assert "[Yüksek lisans tezi, " in out
    assert out.rstrip().endswith("YÖK Ulusal Tez Merkezi.")


def test_apa_tipta_uzmanlik_bracket():
    out = citations.format_apa(tipta_uzmanlik_data())
    assert "[Tıpta uzmanlık tezi, " in out


def test_apa_sanatta_yeterlik_bracket():
    out = citations.format_apa(sanatta_yeterlik_data())
    assert "[Sanatta yeterlik tezi, " in out


def test_apa_contains_year_author_title():
    out = citations.format_apa(doktora_data())
    assert "Kılıç, Z." in out
    assert "(2026)" in out
    assert "Bitcoin fiyat tahmini" in out
    assert "Fırat Üniversitesi" in out


def test_apa_includes_thesis_no():
    out = citations.format_apa(doktora_data())
    assert "1009908" in out


def test_apa_missing_year_is_nd():
    d = doktora_data()
    d.year = None
    out = citations.format_apa(d)
    assert "(n.d.)" in out


# ---------------------------------------------------------------------------
# MLA
# ---------------------------------------------------------------------------

def test_mla_doktora_structure():
    out = citations.format_mla(doktora_data())
    assert "Kılıç, Zeynep" in out
    assert "Fırat Üniversitesi" in out
    assert "2026" in out
    assert "Doktora tezi" in out
    assert "YÖK Ulusal Tez Merkezi" in out


def test_mla_ends_with_period():
    out = citations.format_mla(doktora_data())
    assert out.rstrip().endswith(".")


# ---------------------------------------------------------------------------
# IEEE
# ---------------------------------------------------------------------------

def test_ieee_doktora_structure():
    out = citations.format_ieee(doktora_data())
    assert "Z. Kılıç" in out
    assert "Doktora tezi" in out
    assert "Fırat Üniversitesi" in out
    assert "2026" in out


def test_ieee_ends_with_period():
    out = citations.format_ieee(doktora_data())
    assert out.rstrip().endswith(".")


# ---------------------------------------------------------------------------
# Chicago
# ---------------------------------------------------------------------------

def test_chicago_doktora_structure():
    out = citations.format_chicago(doktora_data())
    assert "Kılıç, Zeynep" in out
    assert "Doktora tezi" in out
    assert "Fırat Üniversitesi" in out
    assert "2026" in out


def test_chicago_ends_with_period():
    out = citations.format_chicago(doktora_data())
    assert out.rstrip().endswith(".")


# ---------------------------------------------------------------------------
# Harvard
# ---------------------------------------------------------------------------

def test_harvard_doktora_structure():
    out = citations.format_harvard(doktora_data())
    assert "Kılıç, Z." in out
    assert "(2026)" in out
    assert "Doktora tezi" in out
    assert "Fırat Üniversitesi" in out
    assert "YÖK Ulusal Tez Merkezi" in out


def test_harvard_missing_year_is_nd():
    d = doktora_data()
    d.year = None
    out = citations.format_harvard(d)
    assert "(n.d.)" in out


# ---------------------------------------------------------------------------
# BibTeX
# ---------------------------------------------------------------------------

def test_bibtex_doktora_is_phdthesis():
    out = citations.to_bibtex(doktora_data())
    assert out.startswith("@phdthesis{")


def test_bibtex_yuksek_lisans_is_mastersthesis():
    out = citations.to_bibtex(yuksek_lisans_data())
    assert out.startswith("@mastersthesis{")


def test_bibtex_tipta_uzmanlik_is_phdthesis():
    out = citations.to_bibtex(tipta_uzmanlik_data())
    assert out.startswith("@phdthesis{")


def test_bibtex_sanatta_yeterlik_is_phdthesis():
    out = citations.to_bibtex(sanatta_yeterlik_data())
    assert out.startswith("@phdthesis{")


def test_bibtex_contains_required_fields():
    out = citations.to_bibtex(doktora_data())
    assert "author = {Kılıç, Zeynep}" in out
    assert "title = {Makine öğrenmesi algoritmaları ile Bitcoin fiyat tahmini}" in out
    assert "school = {Fırat Üniversitesi}" in out
    assert "year = {2026}" in out
    assert "note = {YÖK Ulusal Tez Merkezi}" in out


def test_bibtex_key_ascii_folded():
    out = citations.to_bibtex(doktora_data())
    first_line = out.splitlines()[0]
    # key = <ascii_fold(family)><year>  (no article_id for theses)
    assert first_line == "@phdthesis{kilic2026,"


def test_bibtex_ends_with_brace():
    out = citations.to_bibtex(doktora_data())
    assert out.rstrip().endswith("}")


# ---------------------------------------------------------------------------
# RIS
# ---------------------------------------------------------------------------

def test_ris_ty_is_thes():
    out = citations.to_ris(doktora_data())
    assert "TY  - THES" in out


def test_ris_structure():
    out = citations.to_ris(doktora_data())
    assert "AU  - Kılıç, Zeynep" in out
    assert "T1  - Makine öğrenmesi algoritmaları ile Bitcoin fiyat tahmini" in out
    assert "PY  - 2026" in out
    assert out.endswith("ER  - \n")


def test_ris_contains_thesis_no():
    out = citations.to_ris(doktora_data())
    assert "1009908" in out


def test_ris_contains_publisher():
    out = citations.to_ris(doktora_data())
    assert "YÖK Ulusal Tez Merkezi" in out


# ---------------------------------------------------------------------------
# CSL-JSON
# ---------------------------------------------------------------------------

def test_csl_json_type_is_thesis():
    item = citations.to_csl_json(doktora_data())
    assert item["type"] == "thesis"


def test_csl_json_genre_is_thesis_type():
    item = citations.to_csl_json(doktora_data())
    assert item["genre"] == "Doktora"


def test_csl_json_publisher_is_yok():
    item = citations.to_csl_json(doktora_data())
    assert item["publisher"] == "YÖK Ulusal Tez Merkezi"


def test_csl_json_structure():
    item = citations.to_csl_json(doktora_data())
    assert item["title"] == "Makine öğrenmesi algoritmaları ile Bitcoin fiyat tahmini"
    assert item["author"] == [{"given": "Zeynep", "family": "Kılıç"}]
    assert item["issued"] == {"date-parts": [[2026]]}
    assert item["archive"] == "YÖK Ulusal Tez Merkezi"


# ---------------------------------------------------------------------------
# all_citations
# ---------------------------------------------------------------------------

def test_all_citations_returns_8_keys():
    out = citations.all_citations(doktora_data())
    assert set(out.keys()) == {
        "bibtex", "ris", "csl_json", "apa", "mla", "ieee", "chicago", "harvard"
    }


def test_all_citations_correct_types():
    out = citations.all_citations(doktora_data())
    assert isinstance(out["csl_json"], dict)
    assert isinstance(out["bibtex"], str)
    assert isinstance(out["ris"], str)
    assert isinstance(out["apa"], str)


def test_all_citations_consistency():
    out = citations.all_citations(doktora_data())
    assert out["bibtex"].startswith("@phdthesis{")
    assert "TY  - THES" in out["ris"]
    assert out["csl_json"]["type"] == "thesis"
    assert out["ris"].endswith("ER  - \n")


# ---------------------------------------------------------------------------
# format_citation dispatch
# ---------------------------------------------------------------------------

def test_format_citation_case_insensitive():
    d = doktora_data()
    assert citations.format_citation(d, "APA") == citations.format_apa(d)
    assert citations.format_citation(d, "Apa") == citations.format_apa(d)
    assert citations.format_citation(d, "ieee") == citations.format_ieee(d)


def test_format_citation_unknown_raises():
    with pytest.raises(ValueError):
        citations.format_citation(doktora_data(), "vancouver")


# ---------------------------------------------------------------------------
# Edge cases: zero author, missing fields
# ---------------------------------------------------------------------------

def test_zero_author_does_not_crash():
    d = CitationData(
        title="Yazarsız Tez",
        year="2023",
        thesis_type="Doktora",
        university="Test Üniversitesi",
        thesis_no="000000",
    )
    apa = citations.format_apa(d)
    mla = citations.format_mla(d)
    ieee = citations.format_ieee(d)
    chicago = citations.format_chicago(d)
    harvard = citations.format_harvard(d)
    for out in (apa, mla, ieee, chicago, harvard):
        assert "Yazarsız Tez" in out or "2023" in out
    ris = citations.to_ris(d)
    assert "TY  - THES" in ris
    assert "AU  - " not in ris


def test_missing_thesis_type_does_not_crash():
    d = CitationData(
        author="Ali Veli",
        year="2020",
        title="Başlık",
        university="Üniversite",
    )
    out = citations.format_apa(d)
    assert "Ali" in out or "Veli" in out


def test_html_entities_unescaped():
    d = CitationData(
        author="Ali Veli",
        year="2021",
        title="Sa&#287;l&#305;k &amp; Eğitim",
        thesis_type="Doktora",
        university="Bilim &amp; Teknoloji Üniversitesi",
    )
    apa = citations.format_apa(d)
    assert "&amp;" not in apa
    assert "&#" not in apa
    # &amp; → & (correct HTML unescaping)
    assert "Bilim & Teknoloji Üniversitesi" in apa
    # Numeric entities decoded
    assert "Sağlık" in apa
