"""yoktez_mcp.index — SQLite FTS5 tez indeksi + Türkçe-duyarlı arama.

Hibrit strateji: önceden derlenmiş seed index (``data/seed_index.db.gz``)
anında yüklenerek sıcak başlar; ``on-demand`` scraping ile ek tezler eklenir.

Türkçe normalizasyon (``tr_fold``) hem İNDEKSE hem SORGUYA **simetrik** uygulanır —
text.py'deki tr_fold import edilir, burada yeniden tanımlanmaz.

NOT: Şu an gönderilen seed_index.db.gz bir yer tutucudur (sadece _meta tablosu,
tez satırı yok). ``get_default_index()`` bunu algılar ve boş ama işlevsel bir
in-memory indeks döndürür. Faz 5'te gerçek seed derlendiğinde bu loader onu doğrudan
servis edecektir.
"""

from __future__ import annotations

import gzip
import os
import re
import shutil
import sqlite3
from pathlib import Path

from .cache import cache_dir
from .models import AccessStatus, SearchHit, SearchResult, Thesis
from .text import tr_fold

# ---------------------------------------------------------------------------
# Stopwords ve sorgu yardımcıları
# ---------------------------------------------------------------------------

# Küçük Türkçe/İngilizce stopword listesi. Fold edilmiş uzayda tutulur.
_STOPWORDS = {
    tr_fold(w) for w in {
        "ve", "ile", "bir", "bu", "da", "de", "için", "olarak", "the", "of",
        "and", "in", "on", "a", "an", "to", "ya", "veya", "mi", "mu",
    }
}


def _query_terms(query: str) -> list[str]:
    """Sorguyu katlanmış, stopword'süz, FTS5-güvenli terimlere böler."""
    folded = tr_fold(query)
    terms = re.findall(r"\w+", folded, flags=re.UNICODE)
    return [t for t in terms if t not in _STOPWORDS]


# ---------------------------------------------------------------------------
# SearchIndex
# ---------------------------------------------------------------------------

class SearchIndex:
    """Tez FTS5 indeksi. Tek event-loop'ta kullanılmak üzere tasarlanmıştır.

    db_path=":memory:" → tamamen geçici; test ortamları için uygun.
    db_path=None → cache_dir() altında ``thesis_index.db`` olarak kalıcı.
    """

    # FTS5 sütun ağırlıkları: title_tr/en 5×, keywords 3×, advisor/author 3×, abstract 1×
    _BM25_WEIGHTS = "5.0, 5.0, 3.0, 3.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 3.0, 1.0, 1.0"
    # Sıra: title_tr, title_en, author, advisor, university, institute, department,
    #       thesis_type, year_str, keywords, subjects, abstract_tr, abstract_en

    def __init__(self, db_path: str | Path | None = None) -> None:
        if db_path is None:
            d = cache_dir()
            d.mkdir(parents=True, exist_ok=True)
            db_path = d / "thesis_index.db"
        self.db_path = str(db_path)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    # ---------------------------------------------------------------- schema --

    def _init_schema(self) -> None:
        c = self._conn
        # Ana tablo: kayit_no → rowid eşlemesi + depolanmış alanlar.
        # FTS'ye JOIN ile ulaşılır (rowid üzerinden).
        c.execute(
            """CREATE TABLE IF NOT EXISTS theses(
                rowid    INTEGER PRIMARY KEY,
                kayit_no TEXT NOT NULL UNIQUE,
                tez_no   TEXT NOT NULL,
                thesis_no     TEXT,
                title_tr      TEXT,
                title_en      TEXT,
                author        TEXT,
                advisor       TEXT,
                university    TEXT,
                institute     TEXT,
                department    TEXT,
                thesis_type   TEXT,
                year          INTEGER,
                access_status TEXT
            )"""
        )
        # FTS5 sanal tablo — tr_fold edilmiş metin.
        # content='' (contentless): FTS kendi içeriğini saklar, ana tablodan JOIN yok.
        # Güncelleme: DELETE + INSERT (content='' tablosunda desteklenen yöntem).
        # Sütun sırası _BM25_WEIGHTS ile eşleşmeli.
        c.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS theses_fts USING fts5("
            "title_tr, title_en, author, advisor, university, institute, department, "
            "thesis_type, year_str, keywords, subjects, abstract_tr, abstract_en, "
            "content='', tokenize='unicode61 remove_diacritics 1', prefix='2 3 4')"
        )
        # kayit_no → FTS rowid haritası (content='' FTS güncelleme için gerekli)
        c.execute(
            "CREATE TABLE IF NOT EXISTS theses_fts_map("
            "kayit_no TEXT PRIMARY KEY, fts_rowid INTEGER NOT NULL)"
        )
        c.commit()

    # --------------------------------------------------------------- upsert --

    def upsert(self, theses: list[Thesis]) -> None:
        """Tezleri upsert ile indeksler. Birincil anahtar: kayit_no.

        INSERT OR IGNORE + UPDATE kullanılır (INSERT OR REPLACE rowid'i değiştirir →
        FTS ghost satırlarına yol açar). Bu yöntemle rowid kararlı kalır.
        Metin alanları tr_fold ile normalleştirilerek FTS5'e yazılır (simetri sağlanır).
        """
        c = self._conn
        for t in theses:
            access_val = (
                t.access_status.value if t.access_status else AccessStatus.UNKNOWN.value
            )
            keywords = "; ".join((t.keywords_tr or []) + (t.keywords_en or []))
            subjects = "; ".join(t.subjects or [])

            # 1. Yeni kayıt ise ekle (rowid sabit tutulur)
            c.execute(
                "INSERT OR IGNORE INTO theses"
                "(kayit_no,tez_no,thesis_no,title_tr,title_en,author,advisor,"
                "university,institute,department,thesis_type,year,access_status)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    t.kayit_no, t.tez_no, t.thesis_no,
                    t.title_tr, t.title_en,
                    t.author, t.advisor,
                    t.university, t.institute, t.department,
                    t.thesis_type, t.year, access_val,
                ),
            )
            is_new = c.execute(
                "SELECT changes()"
            ).fetchone()[0] > 0

            if not is_new:
                # Güncelle (rowid değişmez)
                c.execute(
                    "UPDATE theses SET tez_no=?,thesis_no=?,title_tr=?,title_en=?,"
                    "author=?,advisor=?,university=?,institute=?,department=?,"
                    "thesis_type=?,year=?,access_status=? WHERE kayit_no=?",
                    (
                        t.tez_no, t.thesis_no,
                        t.title_tr, t.title_en,
                        t.author, t.advisor,
                        t.university, t.institute, t.department,
                        t.thesis_type, t.year, access_val,
                        t.kayit_no,
                    ),
                )

            # Mevcut rowid'i al
            row = c.execute(
                "SELECT rowid FROM theses WHERE kayit_no=?", (t.kayit_no,)
            ).fetchone()
            thesis_rowid = row[0]

            fts_values = (
                thesis_rowid,
                tr_fold(t.title_tr or ""),
                tr_fold(t.title_en or ""),
                tr_fold(t.author or ""),
                tr_fold(t.advisor or ""),
                tr_fold(t.university or ""),
                tr_fold(t.institute or ""),
                tr_fold(t.department or ""),
                tr_fold(t.thesis_type or ""),
                str(t.year) if t.year else "",
                tr_fold(keywords),
                tr_fold(subjects),
                tr_fold(t.abstract_tr or ""),
                tr_fold(t.abstract_en or ""),
            )
            _fts_insert_sql = (
                "INSERT INTO theses_fts("
                "rowid, title_tr, title_en, author, advisor, university, institute, "
                "department, thesis_type, year_str, keywords, subjects, abstract_tr, abstract_en"
                ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
            )

            if is_new:
                # Yeni kayıt: FTS'e ekle
                c.execute(_fts_insert_sql, fts_values)
            else:
                # Güncelleme: eski FTS satırını sil, yeni ekle
                c.execute(
                    "INSERT INTO theses_fts(theses_fts, rowid, title_tr, title_en, author, "
                    "advisor, university, institute, department, thesis_type, year_str, "
                    "keywords, subjects, abstract_tr, abstract_en) "
                    "VALUES('delete',?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (thesis_rowid, "", "", "", "", "", "", "", "", "", "", "", "", ""),
                )
                c.execute(_fts_insert_sql, fts_values)

            # Haritayı güncelle
            c.execute(
                "INSERT OR REPLACE INTO theses_fts_map(kayit_no, fts_rowid) VALUES(?,?)",
                (t.kayit_no, thesis_rowid),
            )
        c.commit()

    # ----------------------------------------------------------- upsert_hits --

    def upsert_hits(self, hits: list[SearchHit]) -> int:
        """SearchHit (hafif arama kartı) satırlarını indekse upsert eder.

        On-demand warming için: canlı aramadan dönen kartlar indekse yazılır,
        böylece indeks kullanımla ısınır. Yalnızca kartta bulunan alanlar
        (title/author/year/university/thesis_type) yazılır; abstract/keywords/
        advisor boş kalır. ``kayit_no``'ya göre dedup-güvenli (upsert).
        ``kayit_no``'su olan satır sayısını döndürür.
        """
        theses = [
            Thesis(
                kayit_no=h.kayit_no,
                tez_no=h.tez_no or "",
                thesis_no=h.thesis_no,
                title_tr=h.title_tr,
                title_en=h.title_en,
                author=h.author,
                year=h.year,
                university=h.university,
                thesis_type=h.thesis_type,
            )
            for h in hits
            if h.kayit_no
        ]
        if theses:
            self.upsert(theses)
        return len(theses)

    # ---------------------------------------------------------------- search --

    def search(
        self,
        query: str,
        *,
        thesis_type: str | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
        university: str | None = None,
        advisor: str | None = None,
        department: str | None = None,
        limit: int = 20,
    ) -> SearchResult:
        """FTS5 BM25 arama + Python taraflı filtreler + sıralama sinyalleri.

        Döndürülen SearchResult.source her zaman "index"'tir.
        coverage_complete=True: indeks kapsamında tam sonuç (canlı sorgu yok).
        """
        terms = _query_terms(query)
        if not terms:
            return SearchResult(
                hits=[], total_found=0, shown=0,
                coverage_complete=True, source="index",
                notes=["Sorgu terimleri stopword listesinde; arama yapılmadı."],
            )

        match_expr = " ".join(f"{t}*" for t in terms)

        sql = (
            f"SELECT t.rowid, t.kayit_no, t.tez_no, t.thesis_no, t.title_tr, t.title_en, "
            f"t.author, t.advisor, t.university, t.institute, t.department, t.thesis_type, "
            f"t.year, t.access_status, "
            f"bm25(theses_fts, {self._BM25_WEIGHTS}) AS score "
            f"FROM theses_fts JOIN theses t ON t.rowid=theses_fts.rowid "
            f"WHERE theses_fts MATCH ?"
        )
        params: list = [match_expr]
        sql += " ORDER BY score LIMIT 5000"

        rows = [dict(r) for r in self._conn.execute(sql, params).fetchall()]

        # Python taraflı filtreler (tr_fold ile; SQL tarafı index-only eşleme)
        if thesis_type:
            ttf = tr_fold(thesis_type)
            rows = [r for r in rows if ttf in tr_fold(r.get("thesis_type") or "")]
        if year_from is not None:
            rows = [r for r in rows if r.get("year") is not None and int(r["year"]) >= int(year_from)]
        if year_to is not None:
            rows = [r for r in rows if r.get("year") is not None and int(r["year"]) <= int(year_to)]
        if university:
            uf = tr_fold(university)
            rows = [r for r in rows if uf in tr_fold(r.get("university") or "")]
        if advisor:
            aterms = _query_terms(advisor)
            if aterms:
                rows = [
                    r for r in rows
                    if all(at in tr_fold(r.get("advisor") or "") for at in aterms)
                ]
        if department:
            df = tr_fold(department)
            rows = [r for r in rows if df in tr_fold(r.get("department") or "")]

        # Sıralama sinyalleri (BM25 + başlık phrase bonus + recency)
        phrase = " ".join(terms)
        multi = len(terms) >= 2

        def adjusted(r: dict) -> float:
            score = r["score"]  # bm25: küçük (negatif) = daha iyi
            title_f = tr_fold((r.get("title_tr") or "") + " " + (r.get("title_en") or ""))
            bonus = 0.0
            if phrase and phrase in title_f:
                bonus -= 4.0 if multi else 2.0
            elif multi and phrase in tr_fold(r.get("abstract_tr") or ""):
                bonus -= 1.5
            if multi:
                bonus -= 0.7 * sum(1 for t in terms if t in title_f)
            yr = r.get("year")
            if yr:
                bonus -= min(max(int(yr) - 2000, 0), 30) * 0.03
            return score + bonus

        rows.sort(key=adjusted)

        total = len(rows)
        page = rows[:limit]
        hits = [_row_to_hit(r) for r in page]

        return SearchResult(
            hits=hits,
            total_found=total,
            shown=len(hits),
            coverage_complete=True,
            source="index",
            notes=["Sonuçlar indeks kapsamındadır (canlı YÖKTEZ sorgusu yapılmadı)."],
        )

    # --------------------------------------------------------- by_advisor --

    def by_advisor(self, name: str, *, limit: int = 50) -> SearchResult:
        """Danışman adına göre tez listesi (ad sırası bağımsız, fold destekli)."""
        aterms = _query_terms(name)
        if not aterms:
            return SearchResult(hits=[], total_found=0, shown=0,
                                coverage_complete=True, source="index", notes=[])
        match_expr = " ".join(f"{t}*" for t in aterms)
        sql = (
            "SELECT t.rowid, t.kayit_no, t.tez_no, t.thesis_no, t.title_tr, t.title_en, "
            "t.author, t.advisor, t.university, t.institute, t.department, t.thesis_type, "
            "t.year, t.access_status "
            "FROM theses_fts JOIN theses t ON t.rowid=theses_fts.rowid "
            "WHERE theses_fts MATCH ? LIMIT 5000"
        )
        rows = [dict(r) for r in self._conn.execute(sql, [match_expr]).fetchall()]
        # Terimlerin GERÇEKTEN danışman alanında geçmesini doğrula (gürültü ele)
        rows = [
            r for r in rows
            if all(at in tr_fold(r.get("advisor") or "") for at in aterms)
        ]
        rows.sort(key=lambda r: (-(r.get("year") or 0)))
        hits = [_row_to_hit(r) for r in rows[:limit]]
        return SearchResult(
            hits=hits, total_found=len(rows), shown=len(hits),
            coverage_complete=True, source="index", notes=[],
        )

    # --------------------------------------------------------- by_author --

    def by_author(self, name: str, *, limit: int = 50) -> SearchResult:
        """Yazar adına göre tez listesi (ad sırası bağımsız, fold destekli)."""
        aterms = _query_terms(name)
        if not aterms:
            return SearchResult(hits=[], total_found=0, shown=0,
                                coverage_complete=True, source="index", notes=[])
        match_expr = " ".join(f"{t}*" for t in aterms)
        sql = (
            "SELECT t.rowid, t.kayit_no, t.tez_no, t.thesis_no, t.title_tr, t.title_en, "
            "t.author, t.advisor, t.university, t.institute, t.department, t.thesis_type, "
            "t.year, t.access_status "
            "FROM theses_fts JOIN theses t ON t.rowid=theses_fts.rowid "
            "WHERE theses_fts MATCH ? LIMIT 5000"
        )
        rows = [dict(r) for r in self._conn.execute(sql, [match_expr]).fetchall()]
        # Terimlerin GERÇEKTEN yazar alanında geçmesini doğrula
        rows = [
            r for r in rows
            if all(at in tr_fold(r.get("author") or "") for at in aterms)
        ]
        rows.sort(key=lambda r: (-(r.get("year") or 0)))
        hits = [_row_to_hit(r) for r in rows[:limit]]
        return SearchResult(
            hits=hits, total_found=len(rows), shown=len(hits),
            coverage_complete=True, source="index", notes=[],
        )

    # ------------------------------------------------------ by_university --

    def by_university(
        self,
        name: str,
        *,
        thesis_type: str | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
        limit: int = 50,
    ) -> SearchResult:
        """Üniversiteye göre tez listesi (fold destekli, filtre opsiyonel)."""
        uf = tr_fold(name)
        if not uf:
            return SearchResult(hits=[], total_found=0, shown=0,
                                coverage_complete=True, source="index", notes=[])
        # Üniversite alanında geçen tüm tezleri FTS ile bul
        # (university sütunu indekste; prefix match ile fold edilmiş değerle arama)
        terms = re.findall(r"\w+", uf, flags=re.UNICODE)
        if not terms:
            return SearchResult(hits=[], total_found=0, shown=0,
                                coverage_complete=True, source="index", notes=[])
        match_expr = " ".join(f"{t}*" for t in terms)
        sql = (
            "SELECT t.rowid, t.kayit_no, t.tez_no, t.thesis_no, t.title_tr, t.title_en, "
            "t.author, t.advisor, t.university, t.institute, t.department, t.thesis_type, "
            "t.year, t.access_status "
            "FROM theses_fts JOIN theses t ON t.rowid=theses_fts.rowid "
            "WHERE theses_fts MATCH ? LIMIT 10000"
        )
        rows = [dict(r) for r in self._conn.execute(sql, [match_expr]).fetchall()]
        # Üniversite alanında filtrele
        rows = [r for r in rows if uf in tr_fold(r.get("university") or "")]
        if thesis_type:
            ttf = tr_fold(thesis_type)
            rows = [r for r in rows if ttf in tr_fold(r.get("thesis_type") or "")]
        if year_from is not None:
            rows = [r for r in rows if r.get("year") is not None and int(r["year"]) >= int(year_from)]
        if year_to is not None:
            rows = [r for r in rows if r.get("year") is not None and int(r["year"]) <= int(year_to)]
        rows.sort(key=lambda r: (-(r.get("year") or 0)))
        hits = [_row_to_hit(r) for r in rows[:limit]]
        return SearchResult(
            hits=hits, total_found=len(rows), shown=len(hits),
            coverage_complete=True, source="index", notes=[],
        )

    # ---------------------------------------------------------------- related --

    def related(self, thesis: Thesis, *, limit: int = 10) -> SearchResult:
        """Verilen tezle konu/anahtar kelime örtüşmesi olan ilgili tezler (OR eşleşme)."""
        # Kaynak tezin keyword ve subject terimlerini topla
        raw_terms = (
            list(thesis.keywords_tr or [])
            + list(thesis.keywords_en or [])
            + list(thesis.subjects or [])
        )
        # Başlık tokenlarını da ekle (zenginleştirme)
        if thesis.title_tr:
            raw_terms.append(thesis.title_tr)

        all_terms: list[str] = []
        for rt in raw_terms:
            all_terms.extend(_query_terms(rt))
        terms = list(dict.fromkeys(all_terms))[:12]  # dedup + sınırla

        if not terms:
            return SearchResult(hits=[], total_found=0, shown=0,
                                coverage_complete=True, source="index", notes=[])

        match_expr = " OR ".join(f"{t}*" for t in terms)
        sql = (
            f"SELECT t.rowid, t.kayit_no, t.tez_no, t.thesis_no, t.title_tr, t.title_en, "
            f"t.author, t.advisor, t.university, t.institute, t.department, t.thesis_type, "
            f"t.year, t.access_status, "
            f"bm25(theses_fts, {self._BM25_WEIGHTS}) AS score "
            f"FROM theses_fts JOIN theses t ON t.rowid=theses_fts.rowid "
            f"WHERE theses_fts MATCH ? ORDER BY score LIMIT 5000"
        )
        rows = [dict(r) for r in self._conn.execute(sql, [match_expr]).fetchall()]
        # Kaynak tezin kendisini çıkar
        rows = [r for r in rows if r["kayit_no"] != thesis.kayit_no]
        total = len(rows)
        hits = [_row_to_hit(r) for r in rows[:limit]]
        return SearchResult(
            hits=hits, total_found=total, shown=len(hits),
            coverage_complete=True, source="index", notes=[],
        )

    # ----------------------------------------------------------------- close --

    def close(self) -> None:
        self._conn.close()


# ---------------------------------------------------------------------------
# Yardımcı: satır → SearchHit
# ---------------------------------------------------------------------------

def _row_to_hit(r: dict) -> SearchHit:
    return SearchHit(
        kayit_no=r["kayit_no"],
        tez_no=r.get("tez_no"),
        thesis_no=r.get("thesis_no"),
        title_tr=r.get("title_tr"),
        title_en=r.get("title_en"),
        author=r.get("author"),
        year=r.get("year"),
        university=r.get("university"),
        thesis_type=r.get("thesis_type"),
    )


# ---------------------------------------------------------------------------
# Varsayılan indeks — lazy singleton
# ---------------------------------------------------------------------------

_default_index: SearchIndex | None = None


def _seed_index_path() -> Path | None:
    """Bake'lenmiş seed indeksinin yolu (varsa).

    Önce ``YOKTEZ_SEED_INDEX`` env (deterministik override), aksi halde
    pakete gömülü ``data/seed_index.db`` veya ``data/seed_index.db.gz``.
    Dosya yoksa/boşsa None.
    """
    override = os.environ.get("YOKTEZ_SEED_INDEX")
    if override:
        candidates = [Path(override)]
    else:
        data = Path(__file__).parent / "data"
        candidates = [data / "seed_index.db", data / "seed_index.db.gz"]
    for p in candidates:
        try:
            if p.exists() and p.stat().st_size > 0:
                return p
        except OSError:
            continue
    return None


def _seed_has_theses(db_path: str) -> bool:
    """Seed SQLite dosyasının içinde tez satırı olup olmadığını denetler.

    Placeholder seed (sadece _meta tablosu, theses tablosu yok veya boş) için
    False döndürür → boş in-memory indeks oluşturulur.
    """
    try:
        conn = sqlite3.connect(db_path)
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        if "theses" not in tables:
            conn.close()
            return False
        count = conn.execute("SELECT COUNT(*) FROM theses").fetchone()[0]
        conn.close()
        return count > 0
    except Exception:  # noqa: BLE001
        return False


def get_default_index() -> SearchIndex:
    """Uygulama genelinde paylaşılan indeks (lazy singleton).

    Davranış:
    - cache_dir/thesis_index.db varsa → onu yükle (yerel veriyi koru).
    - Yoksa ve seed varsa → seed'i cache'e kopyala (gzip ise açarak), yükle.
    - Seed placeholder ise (theses tablosu yok/boş) → boş in-memory indeks döner.
    - Seed bozuksa/açılamazsa → sessizce boş indeksle devam et.

    Dönen indeks her zaman ``source="index"`` bildirir (SearchResult aracılığıyla).
    """
    global _default_index
    if _default_index is None:
        d = cache_dir()
        d.mkdir(parents=True, exist_ok=True)
        target = d / "thesis_index.db"

        if not target.exists():
            seed = _seed_index_path()
            if seed is not None:
                try:
                    if seed.suffix == ".gz":
                        with gzip.open(seed, "rb") as src, open(target, "wb") as dst:
                            shutil.copyfileobj(src, dst)
                    else:
                        shutil.copy2(seed, target)
                except Exception:  # noqa: BLE001
                    target.unlink(missing_ok=True)  # yarım kalan dosyayı temizle

        # Hedef dosya var ama placeholder ise → in-memory boş indeks
        if target.exists() and not _seed_has_theses(str(target)):
            _default_index = SearchIndex(":memory:")
        elif target.exists():
            _default_index = SearchIndex(str(target))
        else:
            # Ne seed ne çalışma dosyası var → boş in-memory
            _default_index = SearchIndex(":memory:")

    return _default_index
