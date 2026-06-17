"""Prompt kayıt + içerik testleri — offline (ağsız).

Sahte (mock) bir ``mcp`` nesnesi kullanarak ``register(mcp)``'nin
tam olarak 4 prompt kaydettiğini ve her birinin beklenen araç
adlarını içeren boş-olmayan metin döndürdüğünü doğrular.
"""

from __future__ import annotations

from yoktez_mcp.prompts import register

# ---------------------------------------------------------------------------
# Mock MCP
# ---------------------------------------------------------------------------


class _MockMCP:
    """Minimal sahte FastMCP: yalnızca prompt kayıt mekanizmasını taklit eder."""

    def __init__(self) -> None:
        self._prompts: dict[str, object] = {}

    def prompt(self, *, name: str, description: str = ""):  # noqa: ARG002
        """Dekoratör fabrikası — DergiPark referansıyla aynı imza."""

        def decorator(fn):
            self._prompts[name] = fn
            return fn

        return decorator

    def call(self, name: str, **kwargs) -> str:
        fn = self._prompts[name]
        return fn(**kwargs)


# ---------------------------------------------------------------------------
# Testler
# ---------------------------------------------------------------------------


def test_register_adds_exactly_4_prompts():
    mcp = _MockMCP()
    register(mcp)
    assert len(mcp._prompts) == 4


def test_expected_prompt_names_registered():
    mcp = _MockMCP()
    register(mcp)
    assert set(mcp._prompts.keys()) == {
        "tez_literatur_taramasi",
        "tez_ozeti",
        "danisman_ekol_analizi",
        "universite_uretim_haritasi",
    }


def test_tez_literatur_taramasi_non_empty_and_mentions_tools():
    mcp = _MockMCP()
    register(mcp)
    text = mcp.call("tez_literatur_taramasi", topic="yapay zeka")
    assert text  # boş değil
    assert "search_theses" in text
    assert "yapay zeka" in text


def test_tez_literatur_taramasi_mentions_coverage_and_cap():
    mcp = _MockMCP()
    register(mcp)
    text = mcp.call("tez_literatur_taramasi", topic="eğitim")
    # Dürüstlük ilkesi: kapsam + 2000-cap
    assert "2000" in text or "kapsam" in text.lower() or "coverage" in text.lower()


def test_tez_literatur_taramasi_related_theses_mentioned():
    mcp = _MockMCP()
    register(mcp)
    text = mcp.call("tez_literatur_taramasi", topic="iletişim")
    assert "related_theses" in text


def test_tez_ozeti_non_empty_and_mentions_get_thesis():
    mcp = _MockMCP()
    register(mcp)
    text = mcp.call("tez_ozeti", kayit_no="123456", tez_no="abc")
    assert text
    assert "get_thesis" in text
    assert "123456" in text


def test_tez_ozeti_mentions_access_and_text_reliable():
    mcp = _MockMCP()
    register(mcp)
    text = mcp.call("tez_ozeti", kayit_no="999", tez_no="xyz")
    # Erişim durumu + text_reliable vurgusu
    assert "text_reliable" in text or "güvenilmez" in text.lower() or "izin" in text.lower()
    assert "access" in text.lower() or "erişim" in text.lower() or "izinsiz" in text.lower()


def test_tez_ozeti_fulltext_tool_mentioned():
    mcp = _MockMCP()
    register(mcp)
    text = mcp.call("tez_ozeti", kayit_no="111", tez_no="aaa")
    assert "get_thesis_fulltext" in text


def test_danisman_ekol_analizi_non_empty_and_mentions_tool():
    mcp = _MockMCP()
    register(mcp)
    text = mcp.call("danisman_ekol_analizi", advisor="Ahmet Yılmaz")
    assert text
    assert "find_advisor_theses" in text
    assert "Ahmet Yılmaz" in text


def test_danisman_ekol_analizi_mentions_genealogy_concepts():
    mcp = _MockMCP()
    register(mcp)
    text = mcp.call("danisman_ekol_analizi", advisor="Prof. Dr. Kaya")
    # Ekol / akademik soy kavramı
    assert (
        "ekol" in text.lower()
        or "soy" in text.lower()
        or "öğrenci" in text.lower()
        or "akademik" in text.lower()
    )


def test_universite_uretim_haritasi_non_empty_and_mentions_tool():
    mcp = _MockMCP()
    register(mcp)
    text = mcp.call("universite_uretim_haritasi", university="ODTÜ")
    assert text
    assert "list_university_theses" in text
    assert "ODTÜ" in text


def test_universite_uretim_haritasi_mentions_islem2_limitation():
    mcp = _MockMCP()
    register(mcp)
    text = mcp.call("universite_uretim_haritasi", university="Boğaziçi")
    # islem=2 kısıtlamasına dürüstçe atıf
    assert (
        "islem=2" in text
        or "indeks" in text.lower()
        or "index" in text.lower()
        or "sınırlı" in text.lower()
    )
