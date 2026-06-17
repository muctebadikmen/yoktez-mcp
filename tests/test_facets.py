"""tests/test_facets.py — yoktez_mcp.facets modülü için birim testleri.

Offline testler: parse_abd, parse_universities, load_facets, find_university, find_abd.
Türkçe-duyarlı eşleştirme testleri dahildir.
"""

from __future__ import annotations

from pathlib import Path

from yoktez_mcp.facets import (
    ENUMS,
    find_abd,
    find_university,
    load_facets,
    parse_abd,
    parse_universities,
)

FIXTURES = Path(__file__).parent / "fixtures"
DERIVED = FIXTURES / "derived"
FAZ0 = FIXTURES / "faz0"


# ---------------------------------------------------------------------------
# parse_abd
# ---------------------------------------------------------------------------


class TestParseAbd:
    def test_known_first_entry(self) -> None:
        """İlk giriş: ABAZA DİLİ VE EDEBİYATI ANABİLİM DALI, kod=2821."""
        html = (DERIVED / "abd_sample.html").read_text(encoding="utf-8")
        result = parse_abd(html)
        assert len(result) >= 10
        first = result[0]
        assert first["kod"] == "2821"
        assert first["name"] == "ABAZA DİLİ VE EDEBİYATI ANABİLİM DALI"

    def test_count_sample(self) -> None:
        """Örnek fixture 10 giriş içermeli."""
        html = (DERIVED / "abd_sample.html").read_text(encoding="utf-8")
        result = parse_abd(html)
        assert len(result) == 10

    def test_dict_keys(self) -> None:
        """Her kayıt 'kod' ve 'name' anahtarı içermeli."""
        html = (DERIVED / "abd_sample.html").read_text(encoding="utf-8")
        result = parse_abd(html)
        for item in result:
            assert "kod" in item
            assert "name" in item

    def test_empty_html(self) -> None:
        """Boş HTML → boş liste."""
        assert parse_abd("") == []

    def test_full_fixture_count(self) -> None:
        """Gerçek getAllABD.html fixture'dan tam 5132 giriş çıkmalı."""
        full_html_path = FAZ0 / "getAllABD.html"
        html = full_html_path.read_text(encoding="utf-8")
        result = parse_abd(html)
        assert len(result) == 5132


# ---------------------------------------------------------------------------
# parse_universities
# ---------------------------------------------------------------------------


class TestParseUniversities:
    def test_count(self) -> None:
        """getUniversities_TR.html tam 260 kayıt içermeli."""
        json_text = (FAZ0 / "getUniversities_TR.html").read_text(encoding="utf-8")
        result = parse_universities(json_text)
        assert len(result) == 260

    def test_field_mapping(self) -> None:
        """displayName → name, yoksisId → yoksis_id."""
        json_text = (FAZ0 / "getUniversities_TR.html").read_text(encoding="utf-8")
        result = parse_universities(json_text)
        first = result[0]
        assert "kod" in first
        assert "name" in first
        assert "yoksis_id" in first
        # Eski alan isimleri olmamalı
        assert "displayName" not in first
        assert "yoksisId" not in first

    def test_encrypted_kod(self) -> None:
        """Üniversite kod'u şifreli token olmalı (kısa alfanümerik değil)."""
        json_text = (FAZ0 / "getUniversities_TR.html").read_text(encoding="utf-8")
        result = parse_universities(json_text)
        # İlk kayıt ABANT İZZET BAYSAL — encrypted kod must be non-numeric
        first = result[0]
        assert first["kod"] == "nt_f9P4THOQeT0AlevbLKw"
        assert first["name"] == "ABANT İZZET BAYSAL ÜNİVERSİTESİ"

    def test_empty_json(self) -> None:
        assert parse_universities("[]") == []


# ---------------------------------------------------------------------------
# ENUMS
# ---------------------------------------------------------------------------


class TestEnums:
    def test_tur_has_seven_entries(self) -> None:
        assert len(ENUMS["Tur"]) == 7
        assert ENUMS["Tur"][1] == "Yüksek Lisans"
        assert ENUMS["Tur"][2] == "Doktora"
        assert ENUMS["Tur"][3] == "Tıpta Uzmanlık"
        assert ENUMS["Tur"][7] == "Eczacılıkta Uzmanlık"

    def test_izin_codes(self) -> None:
        assert ENUMS["izin"][1] == "İzinli"
        assert ENUMS["izin"][2] == "İzinsiz"

    def test_durum_codes(self) -> None:
        assert ENUMS["Durum"][3] == "Onaylandı"
        assert ENUMS["Durum"][0] == "Tümü"

    def test_nevi_codes(self) -> None:
        assert ENUMS["nevi"][1] == "Tez Adı"
        assert ENUMS["nevi"][7] == "Tümü"

    def test_tip_codes(self) -> None:
        assert ENUMS["tip"][1] == "exact"
        assert ENUMS["tip"][2] == "contains"

    def test_dil_has_turkish_english(self) -> None:
        assert ENUMS["Dil"][1] == "Türkçe"
        assert ENUMS["Dil"][2] == "İngilizce"


# ---------------------------------------------------------------------------
# load_facets
# ---------------------------------------------------------------------------


class TestLoadFacets:
    def test_returns_dict_with_required_keys(self) -> None:
        facets = load_facets()
        assert "enums" in facets
        assert "universities" in facets
        assert "abd" in facets
        assert "built_at" in facets

    def test_universities_count(self) -> None:
        facets = load_facets()
        assert len(facets["universities"]) == 260

    def test_abd_count(self) -> None:
        facets = load_facets()
        assert len(facets["abd"]) == 5132

    def test_enums_tur_present(self) -> None:
        facets = load_facets()
        # JSON'da int key string olur; her iki formatı kabul et
        tur = facets["enums"]["Tur"]
        # key 1 ya int ya str olabilir
        keys = {int(k) for k in tur.keys()}
        assert 1 in keys
        assert 7 in keys


# ---------------------------------------------------------------------------
# find_university
# ---------------------------------------------------------------------------


class TestFindUniversity:
    def test_exact_name(self) -> None:
        results = find_university("HACETTEPE")
        assert len(results) >= 1
        names = [r["name"] for r in results]
        assert any("HACETTEPe".upper() in n.upper() or "HACETTEPE" in n for n in names)

    def test_turkish_fold(self) -> None:
        """Büyük/küçük ve Türkçe karakter farkı gözetmeden eşleşmeli."""
        r1 = find_university("istanbul")
        r2 = find_university("İSTANBUL")
        assert len(r1) >= 1
        assert len(r1) == len(r2)

    def test_not_found(self) -> None:
        results = find_university("XXXXXXNONEXISTENTXXXXXX")
        assert results == []

    def test_partial_match(self) -> None:
        """Kısmi isimle de sonuç gelmeli."""
        results = find_university("teknik")
        assert len(results) >= 1


# ---------------------------------------------------------------------------
# find_abd
# ---------------------------------------------------------------------------


class TestFindAbd:
    def test_exact(self) -> None:
        results = find_abd("ABAZA")
        assert len(results) >= 1
        assert any("ABAZA" in r["name"] for r in results)

    def test_turkish_fold(self) -> None:
        r1 = find_abd("matematik")
        r2 = find_abd("MATEMATİK")
        assert len(r1) >= 1
        assert len(r1) == len(r2)

    def test_not_found(self) -> None:
        assert find_abd("XXXXXXNONEXISTENTXXXXXX") == []
