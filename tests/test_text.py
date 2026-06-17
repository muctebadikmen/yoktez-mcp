"""tests/test_text.py — yoktez_mcp.text modülü için birim testleri.

Türkçe-duyarlı katlama fonksiyonu simetri ve doğruluk testleri.
"""

from yoktez_mcp.text import fold_contains, tr_fold


class TestTrFold:
    def test_istanbul_fold(self) -> None:
        """İSTANBUL ÜNİVERSİTESİ → 'istanbul universitesi' ile eşleşmeli."""
        assert tr_fold("İSTANBUL ÜNİVERSİTESİ") == tr_fold("istanbul universitesi")

    def test_symmetric_dotless_i(self) -> None:
        """ı (dotless i) ve I (uppercase dotless) ikisi de 'i' olmalı."""
        assert tr_fold("ıI") == "ii"

    def test_symmetric_dotted_i(self) -> None:
        """İ (uppercase dotted i) 'i' olmalı."""
        assert tr_fold("İ") == "i"

    def test_all_turkish_chars(self) -> None:
        """ş ğ ü ö ç ve büyük halleri doğru katlanmalı."""
        assert tr_fold("şŞğĞüÜöÖçÇ") == "ssgguuoocc"

    def test_none_returns_empty(self) -> None:
        assert tr_fold(None) == ""

    def test_empty_returns_empty(self) -> None:
        assert tr_fold("") == ""

    def test_already_ascii(self) -> None:
        assert tr_fold("hello world") == "hello world"

    def test_mixed_case_symmetry(self) -> None:
        """Büyük/küçük harf ve Türkçe karakter karışımı simetrik olmalı."""
        assert tr_fold("EĞİTİM") == tr_fold("eğitim")

    def test_hacettepe(self) -> None:
        """Sık geçen üniversite ismi doğru katlanmalı."""
        assert tr_fold("HACETTEPe ÜNİVERSİTESİ") == tr_fold("hacettepe universitesi")


class TestFoldContains:
    def test_basic_contains(self) -> None:
        assert fold_contains("İstanbul Üniversitesi", "istanbul") is True

    def test_case_insensitive(self) -> None:
        assert fold_contains("ANKARA ÜNİVERSİTESİ", "ankara") is True

    def test_not_contains(self) -> None:
        assert fold_contains("Boğaziçi Üniversitesi", "hacettepe") is False

    def test_empty_needle(self) -> None:
        assert fold_contains("herhangi bir metin", "") is True

    def test_none_haystack(self) -> None:
        assert fold_contains(None, "test") is False

    def test_turkish_chars_in_needle(self) -> None:
        assert fold_contains("ORTADOĞU TEKNİK ÜNİVERSİTESİ", "orta dogu") is False
        # exact substring match after folding
        assert fold_contains("ORTADOĞU TEKNİK ÜNİVERSİTESİ", "ortadogu teknik") is True
