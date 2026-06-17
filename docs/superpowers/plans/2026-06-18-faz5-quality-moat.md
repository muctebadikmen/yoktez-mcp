# YÖKTEZ MCP — Faz 5: Quality Pass + Moat Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the 3 non-functional tools and harden the 6 working ones to production quality, grounded in live-probe ground truth — then build the hybrid seed-index "moat" that the project was designed around.

**Architecture:** Live YÖKTEZ access stays funneled through the throttled `http.py`. We (1) fix multi-word search by using YÖKTEZ's real boolean slot recipe, (2) normalize advisor names to the format the server accepts, (3) re-rank/filter live hits through the same `tr_fold`+coverage logic the FTS index uses, (4) implement the now-confirmed-working `islem=2` advanced/filtered search and wire it into university listing + server-side filtering, (5) warm the FTS index from every live search and add a resumable, polite `build_index.py` harvester, and (6) correct every now-stale "unavailable / server error" note so the product's honesty contract holds.

**Tech Stack:** Python ≥3.10 · fastmcp · httpx · beautifulsoup4/lxml · sqlite FTS5 · pytest.

## Global Constraints

- **Politeness contract (never loosen):** concurrency=1, ≥1 req/s throttle, exponential backoff, self-identifying UA, session reuse — all already enforced in `http.py`. Every live call goes through `yoktez_mcp.http`. No PDF downloads in search/harvest paths.
- **Honesty:** never fabricate; report coverage (`source`, `coverage_complete`, `notes`); wrap external text in `[EXTERNAL CONTENT]`; keep `text_reliable` honest; restricted theses never yield PDF text.
- **Turkish folding symmetry:** `tr_fold` applied identically on index and query.
- **TDD:** failing test first; commit per green step.
- **Offline test suite must stay green:** `uv run pytest -m "not live" -q` (baseline: 310 passed).
- **Fixtures stay lean:** no multi-MB HTML committed; trim probe fixtures to small representative slices.
- **enum codes:** Tur 1=YL/2=Doktora/3=Tıpta Uzmanlık/4=Sanatta Yeterlik/5=Diş/6=Tıpta Yan Dal/7=Eczacılık; nevi 1=ad/2=yazar/3=danışman/4=konu/5=dizin/6=özet/7=tümü; tip 1=exact/2=contains; izin 0/1/2; Durum 0/1/3; Dil 1..14.

---

## File Structure

- `src/yoktez_mcp/search.py` — add term-splitting in `search_keyword`; add `search_advanced` (islem=2). Modified.
- `src/yoktez_mcp/relevance.py` — **new**: `relevance_filter_sort(hits, query, *, drop_uncovered)` shared by tools.
- `src/yoktez_mcp/server.py` — advisor normalization; route live hits through relevance; wire islem=2 into `list_university_theses` + `search_theses` filters; on-demand index warming; related_theses live fallback; honesty/`total_found` fixes. Modified.
- `src/yoktez_mcp/index.py` — fix stale docstring; keep `upsert` (now actually called). Modified.
- `scripts/build_index.py` — **new**: polite, resumable seed harvester via islem=2 slicing + auto-subdivision + checkpoint.
- `src/yoktez_mcp/data/seed_index.db.gz` — **replaced** by a real baked seed (Task 12).
- `tests/fixtures/probe/*` — trimmed to small representative fixtures (Task 1).
- `tests/test_search.py`, `tests/test_server.py`, `tests/test_relevance.py` (new), `tests/test_build_index.py` (new) — Modified/new.
- `src/yoktez_mcp/prompts.py`, `FINDINGS.md`, memory — note corrections. Modified.

---

### Task 1: Fixture hygiene + offline test fixtures

**Files:**
- Modify/trim: `tests/fixtures/probe/*.html` (delete the ~5 MB ones; keep small)
- Create: `tests/fixtures/probe/README.md`

**Interfaces:**
- Produces: small fixtures `t1d_advisor_contains_surnamefirst.html` (0 hits), `t2_all_yapayzeka_hukuk.html` (2 hits), `t2b_slot_yz_AND_hukuk.html` (16 hits), `t3_all_yapayzeka_tip.html` (drift), `t4f_islem2_istanbul_doktora_2023.html` (586, scoped) — each truncated to ≤ ~200 KB while keeping `div.result-count-text`, a handful of `div.result-card`, and a valid (possibly trimmed) `referenceData` block parseable by `search.parse_results`.

- [ ] **Step 1:** List probe fixtures with sizes: `ls -lS tests/fixtures/probe/`. Identify files > 500 KB.
- [ ] **Step 2:** For each fixture an offline test needs, produce a trimmed copy: keep `<head>`, the `result-count-text` div, the first ~5 `result-card` divs, and a `referenceData = {...};` block containing only those cards' indices (valid JSON object). Verify each trimmed file still parses: `uv run python -c "from yoktez_mcp.search import parse_results; print(parse_results(open('tests/fixtures/probe/<f>').read()).total_found)"`.
- [ ] **Step 3:** Delete the multi-MB fixtures not needed by any test (`t1c_*`, `t2_all_yapayzeka.html`, `t2b_phrase_cezahukuku.html`, `t2c_3slot_and_or.html`, `t4b_*`, `t4d_*`, `t4e_*`). Keep only the small ones listed in Interfaces + any < 200 KB.
- [ ] **Step 4:** Write `tests/fixtures/probe/README.md` documenting what each kept fixture demonstrates (query, expected count) so tests are self-explaining.
- [ ] **Step 5: Commit**
```bash
git add tests/fixtures/probe
git commit -m "test(fixtures): trim probe fixtures to small representative slices + README"
```

---

### Task 2: Multi-word AND search (search.py term-splitting)

**Root cause:** `search_keyword` crams the whole query into one `keyword` slot (phrase/substring match) → adding words collapses to 0. YÖKTEZ supports up to 3 boolean slots: `keyword`/`keyword1`/`keyword2` joined by `ops_field`/`ops_field1` (`and`/`or`/`not`).

**Files:**
- Modify: `src/yoktez_mcp/search.py` (`search_keyword` POST body construction)
- Test: `tests/test_search.py`

**Interfaces:**
- Produces: `search_keyword(query, *, field="title", match="contains", op="and")` — unchanged signature plus optional `op` (default `"and"`). New module-private `_build_keyword_slots(query) -> dict` returning `{"keyword","keyword1","keyword2","ops_field","ops_field1"}`.

- [ ] **Step 1: Write the failing test** (in `tests/test_search.py`)
```python
from yoktez_mcp.search import _build_keyword_slots

def test_build_keyword_slots_splits_three_terms_with_and():
    slots = _build_keyword_slots("yapay zeka hukuk")
    assert slots["keyword"] == "yapay"
    assert slots["keyword1"] == "zeka"
    assert slots["keyword2"] == "hukuk"
    assert slots["ops_field"] == "and"
    assert slots["ops_field1"] == "and"

def test_build_keyword_slots_single_term():
    slots = _build_keyword_slots("yapay")
    assert slots["keyword"] == "yapay"
    assert slots["keyword1"] == ""
    assert slots["keyword2"] == ""

def test_build_keyword_slots_more_than_three_terms_packs_remainder_into_third():
    # 4+ words: first two get their own slots; the rest collapse into slot 3
    # as a phrase so no term is silently dropped.
    slots = _build_keyword_slots("yapay zeka ceza hukuku")
    assert slots["keyword"] == "yapay"
    assert slots["keyword1"] == "zeka"
    assert slots["keyword2"] == "ceza hukuku"
    assert slots["ops_field"] == "and"
    assert slots["ops_field1"] == "and"
```
- [ ] **Step 2: Run to verify it fails**
Run: `uv run pytest tests/test_search.py -k build_keyword_slots -v`
Expected: FAIL (`_build_keyword_slots` not defined).
- [ ] **Step 3: Implement** — add to `search.py`:
```python
def _build_keyword_slots(query: str, op: str = "and") -> dict[str, str]:
    """Çok-kelimeli sorguyu YÖKTEZ'in 3 boolean slotuna dağıtır.

    YÖKTEZ tek `keyword`'ü phrase/substring olarak eşler; çok kelime tek slota
    konunca eşleşme 0'a düşer. Doğru yol: keyword/keyword1/keyword2 + ops_field.
    >3 kelime: ilk ikisi kendi slotunda, kalanı 3. slota phrase olarak konur
    (hiçbir terim sessizce düşmez).
    """
    words = query.split()
    if len(words) <= 1:
        return {"keyword": query.strip(), "keyword1": "", "keyword2": "",
                "ops_field": op, "ops_field1": op}
    if len(words) == 2:
        return {"keyword": words[0], "keyword1": words[1], "keyword2": "",
                "ops_field": op, "ops_field1": op}
    return {"keyword": words[0], "keyword1": words[1],
            "keyword2": " ".join(words[2:]),
            "ops_field": op, "ops_field1": op}
```
Then in `search_keyword`, replace the hardcoded `data` block's keyword fields with `**_build_keyword_slots(query)` (keep `nevi`, `tip`, `islem="4"`):
```python
    slots = _build_keyword_slots(query)
    data = {**slots, "nevi": nevi, "tip": tip, "islem": "4"}
```
- [ ] **Step 4: Run to verify pass**
Run: `uv run pytest tests/test_search.py -k build_keyword_slots -v`  → PASS
- [ ] **Step 5: Run full offline suite** `uv run pytest -m "not live" -q` → all green (update any existing test that asserted the old single-keyword body).
- [ ] **Step 6: Commit**
```bash
git add src/yoktez_mcp/search.py tests/test_search.py
git commit -m "fix(search): split multi-word query across YÖKTEZ boolean slots (real AND)"
```

---

### Task 3: Advisor name normalization (server.py)

**Root cause:** Advisor `nevi=3` works, but a "Soyad, Ad" (surname-first, comma) input returns 0; titles ("PROF. DR.") and commas also hurt. Combined with Task 2's slot-splitting, name words become independent AND terms (order-robust).

**Files:**
- Create helper in: `src/yoktez_mcp/search.py` → `normalize_person_name(name) -> str`
- Modify: `src/yoktez_mcp/server.py` (`find_advisor_theses`, `_resolve_advisor`, `find_author_theses`) to normalize before the live call.
- Test: `tests/test_search.py`

**Interfaces:**
- Produces: `normalize_person_name(name: str) -> str` — strips academic titles, converts "Soyad, Ad" → "Ad Soyad", collapses whitespace.

- [ ] **Step 1: Failing test**
```python
from yoktez_mcp.search import normalize_person_name

def test_normalize_surname_first_to_given_first():
    assert normalize_person_name("Bozkurt, Veysel") == "Veysel Bozkurt"

def test_normalize_strips_titles():
    assert normalize_person_name("PROF. DR. Veysel Bozkurt") == "Veysel Bozkurt"
    assert normalize_person_name("Doç. Dr. Aslı Deniz Helvacıoğlu") == "Aslı Deniz Helvacıoğlu"

def test_normalize_plain_name_unchanged():
    assert normalize_person_name("Veysel Bozkurt") == "Veysel Bozkurt"
```
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** in `search.py`:
```python
import re as _re

_TITLE_RE = _re.compile(
    r"^(prof|doç|doc|dr|öğr|ogr|üye|uye|yrd|arş|ars|gör|gor)\.?\s*",
    _re.IGNORECASE,
)

def normalize_person_name(name: str) -> str:
    """Kişi adını YÖKTEZ'in beklediği 'Ad Soyad' biçimine getirir.

    - Akademik ünvanları ('Prof. Dr.', 'Doç. Dr.', 'Dr. Öğr. Üyesi') ayıklar.
    - 'Soyad, Ad' (virgüllü) → 'Ad Soyad'.
    - Fazla boşlukları sadeleştirir.
    """
    s = " ".join((name or "").split())
    # ünvan ön eklerini tekrar tekrar ayıkla
    prev = None
    while prev != s:
        prev = s
        s = _TITLE_RE.sub("", s).strip()
    if "," in s:
        surname, _, given = s.partition(",")
        s = f"{given.strip()} {surname.strip()}".strip()
    return " ".join(s.split())
```
- [ ] **Step 4:** In `server.py`, in `find_advisor_theses` and `_resolve_advisor`, change the live call to `search.search_keyword(search.normalize_person_name(advisor), field="advisor", match="contains")`. In `find_author_theses`, likewise normalize the author. (Keep passing the *original* string to the index `by_advisor`/`by_author` since the index stores raw scraped names.)
- [ ] **Step 5: Run** `uv run pytest tests/test_search.py -k normalize -v` → PASS; then full offline suite → green.
- [ ] **Step 6: Commit**
```bash
git add src/yoktez_mcp/search.py src/yoktez_mcp/server.py tests/test_search.py
git commit -m "fix(advisor): normalize names to 'Ad Soyad' so nevi=3 advisor search returns hits"
```

---

### Task 4: Live-hit relevance filter/re-rank (relevance.py)

**Root cause:** Only index hits get BM25 + bonuses; live hits return in server order with no relevance check → off-topic abstract matches leak (e.g. "yapay zeka tıp" → din eğitimi tezi). Cards only carry title/author/advisor/university, so we filter/re-rank on those.

**Files:**
- Create: `src/yoktez_mcp/relevance.py`
- Create: `tests/test_relevance.py`

**Interfaces:**
- Produces: `relevance_filter_sort(hits, query, *, require_all_terms=True) -> list` — returns hits where (when `require_all_terms`) every folded content-term of `query` appears across `title_tr+title_en+author+advisor`, sorted by term coverage (desc) then title-match then year (desc). Reuses `text.tr_fold` and the stopword logic from `index._query_terms`.

- [ ] **Step 1: Failing test**
```python
from yoktez_mcp.models import SearchHit
from yoktez_mcp.relevance import relevance_filter_sort

def _hit(title, year=2020, kayit="k"):
    return SearchHit(kayit_no=kayit, tez_no="t", thesis_no=None, title_tr=title,
                     title_en=None, author=None, year=year, university=None, thesis_type=None)

def test_drops_hit_missing_a_query_term():
    hits = [
        _hit("Yapay zeka ve tıpta tanı", kayit="a"),
        _hit("Din eğitimi açısından anlatı", kayit="b"),
    ]
    out = relevance_filter_sort(hits, "yapay zeka tıp")
    kayits = [h.kayit_no for h in out]
    assert "a" in kayits
    assert "b" not in kayits  # 'yapay/zeka/tıp' hepsi başlıkta yok → elendi

def test_orders_full_coverage_before_partial():
    hits = [
        _hit("Yapay zeka", kayit="partial"),
        _hit("Yapay zeka ile hukuk", kayit="full"),
    ]
    out = relevance_filter_sort(hits, "yapay zeka hukuk", require_all_terms=False)
    assert out[0].kayit_no == "full"
```
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** `relevance.py`:
```python
"""Canlı YÖKTEZ sonuçlarını sorgu-alaka düzeyine göre filtreler/sıralar.

YÖKTEZ canlı sonuçları sıralamasız döner ve özet alanındaki rastgele eşleşmeler
sızabilir. Kart düzeyinde yalnızca title/author/advisor/university var; bu yüzden
kapsam (coverage) bu alanlar üzerinden tr_fold-simetrik hesaplanır.
"""
from __future__ import annotations

from .index import _query_terms  # tr_fold + stopword'lü terim bölme (tek kaynak)
from .text import tr_fold


def _hit_text(h) -> str:
    parts = [h.title_tr, h.title_en, h.author, getattr(h, "advisor", None)]
    return tr_fold(" ".join(p for p in parts if p))


def relevance_filter_sort(hits: list, query: str, *, require_all_terms: bool = True) -> list:
    terms = _query_terms(query)
    if not terms:
        return list(hits)

    def coverage(h) -> int:
        text = _hit_text(h)
        return sum(1 for t in terms if t in text)

    scored = [(h, coverage(h)) for h in hits]
    if require_all_terms:
        scored = [(h, c) for (h, c) in scored if c == len(terms)]

    def sort_key(item):
        h, c = item
        title = tr_fold((h.title_tr or "") + " " + (h.title_en or ""))
        title_cov = sum(1 for t in terms if t in title)
        return (-c, -title_cov, -(h.year or 0))

    scored.sort(key=sort_key)
    return [h for (h, _c) in scored]
```
- [ ] **Step 4: Run** `uv run pytest tests/test_relevance.py -v` → PASS.
- [ ] **Step 5: Commit**
```bash
git add src/yoktez_mcp/relevance.py tests/test_relevance.py
git commit -m "feat(relevance): tr_fold coverage filter/re-rank for live hits"
```

---

### Task 5: islem=2 advanced/filtered search (search.py `search_advanced`)

**Confirmed working POST shape (probe Task 4).** Empty facet codes must be `"0"`; text facets `""`; `Durum="3"`, `source="TR"`, submit `"-find":"  Bul"`, `islem="2"`. Result page parses identically via `parse_results`.

**Files:**
- Modify: `src/yoktez_mcp/search.py` (+`search_advanced`)
- Test: `tests/test_search.py` (POST-builder unit test; live test marked)

**Interfaces:**
- Produces:
```python
async def search_advanced(
    *, university_kod: str = "", university_yoksis: str = "", university_name: str = "",
    tur: str = "0", year_from: str = "0", year_to: str = "0",
    dil: str = "0", izin: str = "0", durum: str = "3",
    title: str = "", author: str = "", advisor: str = "", subject: str = "",
) -> SearchResult
```
plus module-private `_build_advanced_body(**kwargs) -> dict`.

- [ ] **Step 1: Failing test**
```python
from yoktez_mcp.search import _build_advanced_body

def test_advanced_body_defaults_are_zero_and_durum_3():
    body = _build_advanced_body(tur="2", year_from="2023", year_to="2023")
    assert body["islem"] == "2"
    assert body["Durum"] == "3"
    assert body["source"] == "TR"
    assert body["Enstitu"] == "0" and body["ABD"] == "0" and body["Dil"] == "0"
    assert body["Tur"] == "2" and body["yil1"] == "2023" and body["yil2"] == "2023"
    assert body["-find"].strip() == "Bul"

def test_advanced_body_university_scope_sets_kod_and_yoksis():
    body = _build_advanced_body(university_kod="ENC", university_yoksis="YID",
                                university_name="İSTANBUL ÜNİVERSİTESİ")
    assert body["Universite"] == "ENC"
    assert body["uni_yoksis_id"] == "YID"
    assert body["uniad"] == "İSTANBUL ÜNİVERSİTESİ"
```
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** in `search.py`:
```python
def _build_advanced_body(
    *, university_kod: str = "", university_yoksis: str = "", university_name: str = "",
    tur: str = "0", year_from: str = "0", year_to: str = "0",
    dil: str = "0", izin: str = "0", durum: str = "3",
    title: str = "", author: str = "", advisor: str = "", subject: str = "",
) -> dict:
    """islem=2 (gelişmiş/filtreli arama) POST gövdesi.

    Boş facet kodları '0', boş metin alanları '' gönderilmeli (aksi halde
    'Geçersiz sorgulama' / 'Hata Oluştu'). Üniversite kapsamı için şifreli
    Universite kod + uni_yoksis_id birlikte gider.
    """
    return {
        "uniad": university_name, "Universite": university_kod,
        "uni_yoksis_id": university_yoksis, "source": "TR",
        "ensad": "", "Enstitu": "0", "abdad": "", "ABD": "0", "Konu": subject,
        "Tur": tur, "yil1": year_from, "yil2": year_to,
        "izin": izin, "Durum": durum, "Dil": dil,
        "TezAd": title, "AdSoyad": author, "DanismanAdSoyad": advisor,
        "Dizin": "", "TezNo": "", "Metin": "", "Bolum": "0",
        "islem": "2", "-find": "  Bul",
    }

async def search_advanced(**kwargs) -> "SearchResult":
    body = _build_advanced_body(**kwargs)
    resp = await post_form("SearchTez", body)
    return parse_results(resp.text)
```
- [ ] **Step 4: Run** `uv run pytest tests/test_search.py -k advanced_body -v` → PASS.
- [ ] **Step 5: Add a live test** (marked, not in default run):
```python
@pytest.mark.live
async def test_advanced_university_scope_live():
    from yoktez_mcp import facets, search
    uni = facets.find_university("İstanbul Üniversitesi")[0]
    res = await search.search_advanced(
        university_kod=uni["kod"], university_yoksis=uni["yoksis_id"],
        university_name=uni["name"], tur="2", year_from="2023", year_to="2023")
    assert res.hits
    assert all("İSTANBUL ÜNİVERSİTESİ" in (h.university or "").upper() for h in res.hits[:10])
```
- [ ] **Step 6: Commit**
```bash
git add src/yoktez_mcp/search.py tests/test_search.py
git commit -m "feat(search): implement islem=2 advanced/filtered search (search_advanced)"
```

---

### Task 6: Wire live university listing (server.py `list_university_theses`)

**Files:**
- Modify: `src/yoktez_mcp/server.py` (`list_university_theses`, `_resolve_university`)
- Test: `tests/test_server.py` (with monkeypatched `search.search_advanced` + `facets.find_university`)

**Interfaces:**
- Consumes: `search.search_advanced`, `facets.find_university`, `index.by_university`, `relevance` (n/a here), `_dedupe_hits`.

- [ ] **Step 1: Failing test** — monkeypatch `facets.find_university` to return one fake uni and `search.search_advanced` to return 2 fake hits; assert `list_university_theses` returns `source` in {"live","hybrid"}, `count==2`, and the stale "islem=2 kullanılamıyor" note is GONE.
```python
async def test_list_university_uses_live_islem2(monkeypatch):
    from yoktez_mcp import server, search, facets
    from yoktez_mcp.models import SearchHit, SearchResult
    monkeypatch.setattr(facets, "find_university",
        lambda q: [{"kod": "ENC", "name": "X ÜNİVERSİTESİ", "yoksis_id": "YID"}])
    async def fake_adv(**kw):
        return SearchResult(hits=[SearchHit(kayit_no="a", tez_no="t", thesis_no=None,
            title_tr="T", title_en=None, author=None, year=2023,
            university="X ÜNİVERSİTESİ", thesis_type="Doktora")],
            total_found=1, shown=1, coverage_complete=True, source="live", notes=[])
    monkeypatch.setattr(search, "search_advanced", fake_adv)
    out = await server.list_university_theses("X Üniversitesi")
    assert out["count"] == 1
    assert out["source"] in ("live", "hybrid")
    assert not any("kullanılamıyor" in n for n in out["notes"])
```
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** — rewrite `list_university_theses` body:
  - Resolve uni via `facets.find_university(university)`; if none → keep index-only path + honest note "üniversite facet'te bulunamadı".
  - If found, take the first match; call `await search.search_advanced(university_kod=u["kod"], university_yoksis=u["yoksis_id"], university_name=u["name"], tur=_tur_code(thesis_type), year_from=str(year_from or "0"), year_to=str(year_to or "0"))` inside try/except (catch SearchError/Exception → note + index fallback).
  - Merge live + `idx.by_university(...)`, dedupe, apply `thesis_type`/year client filter only if not already server-filtered, `source` = hybrid/live/index, honest `coverage_complete`, drop the stale notes.
  - Add helper `_tur_code(label) -> str` mapping "Doktora"→"2", "Yüksek Lisans"→"1", etc. via `facets.ENUMS["Tur"]` reverse lookup (default "0").
  - Mirror the same in `_resolve_university`.
- [ ] **Step 4: Run** `uv run pytest tests/test_server.py -k university -v` → PASS; full offline → green.
- [ ] **Step 5: Commit**
```bash
git add src/yoktez_mcp/server.py tests/test_server.py
git commit -m "feat(university): live islem=2 path for list_university_theses (+facets uni resolve)"
```

---

### Task 7: Server-side filters for search_theses via islem=2

**Files:**
- Modify: `src/yoktez_mcp/server.py` (`search_theses`)
- Test: `tests/test_server.py`

**Interfaces:** Consumes `search.search_advanced`, `relevance.relevance_filter_sort`, `_build_keyword_slots` (indirect).

- [ ] **Step 1: Failing test** — when `university`/`thesis_type`/`year_from` provided, `search_theses` should call `search.search_advanced` (server-side filter) rather than only client-side filtering; relevance filter applied to merged set; stale "client-side / islem=2 kullanılamıyor" note removed. Monkeypatch both `search.search_keyword` and `search.search_advanced`; assert advanced was called when a filter is present and that an off-topic live hit is dropped by relevance.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement:**
  - Keep `search_keyword(query, field=...)` for the keyword leg.
  - If any of `university`/`thesis_type`/`year_from`/`year_to`/`language`/`access` is set AND a `query` exists, ALSO call `search_advanced` with the resolved facets (`TezAd`=query when `field=="title"`, else `Konu`/`Metin` as appropriate; map `language`→Dil code, `access`→izin code). Merge with the keyword leg.
  - Run merged live hits (relevance sort) through `relevance.relevance_filter_sort(hits, query, require_all_terms=(sort=="relevance"))` before applying remaining client filters + limit.
  - Replace the "client-side / islem=2 unavailable" notes with accurate ones (server-side filters applied; note residual client filters only where truly client-side).
- [ ] **Step 4: Run** offline suite → green.
- [ ] **Step 5: Commit**
```bash
git add src/yoktez_mcp/server.py tests/test_server.py
git commit -m "feat(search): server-side filters via islem=2 + relevance re-rank in search_theses"
```

---

### Task 8: On-demand index warming (server.py)

**Root cause:** `index.upsert` is never called → index never warms. Cheap fix: after a live search returns hits, upsert them (best-effort, never blocks/raises into the response).

**Files:**
- Modify: `src/yoktez_mcp/server.py` (add `_warm_index(hits)` helper; call from search/advisor/author/university paths)
- Modify: `src/yoktez_mcp/index.py` (add `upsert_hits(hits)` accepting `SearchHit` — lighter than full `Thesis`)
- Test: `tests/test_index.py`

**Interfaces:**
- Produces: `SearchIndex.upsert_hits(self, hits: list[SearchHit]) -> int` — upserts minimal rows (title/author/year/university/thesis_type; abstract/keywords empty), returns count; `server._warm_index(hits)` wraps it in try/except and dedupes.

- [ ] **Step 1: Failing test** (`tests/test_index.py`): build `:memory:` index, `upsert_hits([hit])`, then `search("<title token>")` finds it; second `upsert_hits` of same kayit_no does not duplicate (total stays 1).
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** `upsert_hits` by adapting `upsert` to accept SearchHit-shaped rows (map to a transient `Thesis`-like upsert; reuse existing upsert path by constructing minimal `Thesis` objects, or factor a private `_upsert_row(...)`). Add `server._warm_index(hits)` and call it (fire-and-forget, wrapped) in `search_theses`, `find_advisor_theses`, `find_author_theses`, `list_university_theses` after computing live hits. Must never raise into the tool response.
- [ ] **Step 4: Run** `uv run pytest tests/test_index.py -k warm -v` and full offline → green.
- [ ] **Step 5: Commit**
```bash
git add src/yoktez_mcp/index.py src/yoktez_mcp/server.py tests/test_index.py
git commit -m "feat(index): warm FTS index from live hits (on-demand), dedup-safe"
```

---

### Task 9: related_theses live fallback (server.py)

**Files:**
- Modify: `src/yoktez_mcp/server.py` (`related_theses`)
- Test: `tests/test_server.py`

**Interfaces:** Consumes `index.related`, `search.search_keyword`, `relevance.relevance_filter_sort`.

- [ ] **Step 1: Failing test** — monkeypatch `index.related` to return empty and `search.search_keyword` to return 3 hits; assert `related_theses` falls back to live (derives terms from the source thesis subjects/keywords/title), returns `source` "live" (or "hybrid"), excludes the source `kayit_no`, and `count>0`.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** — after computing `idx.related(thesis)`, if `total_found == 0` (or thin), build a query from `thesis.keywords_tr/subjects/title_tr` (top terms via `index._query_terms`), call `search.search_keyword(query, field="all")`, run through `relevance.relevance_filter_sort`, drop the source `kayit_no`, set source/coverage honestly, update notes (live-derived, not index).
- [ ] **Step 4: Run** offline → green.
- [ ] **Step 5: Commit**
```bash
git add src/yoktez_mcp/server.py tests/test_server.py
git commit -m "feat(related): live fallback when index has no/low overlap"
```

---

### Task 10: Polite resumable seed harvester (scripts/build_index.py)

**Files:**
- Create: `scripts/build_index.py`
- Create: `tests/test_build_index.py`

**Interfaces:**
- Produces (importable, testable):
  - `iter_slices(universities, turler, years) -> Iterator[Slice]` — cartesian product as `Slice(uni, tur, year)`.
  - `async def harvest_slice(slice, *, subdivide=True) -> tuple[list[SearchHit], bool]` — runs `search_advanced`; if `coverage_complete` is False (>2000), subdivides by `Dil` then `izin`; returns (hits, complete_flag).
  - `Checkpoint(path)` — `.done(key)`, `.mark(key)`, persisted as JSON; makes re-runs resume.
  - `async def build(*, out_path, universities, turler, years, checkpoint_path)` — orchestrates, upserts into a `SearchIndex(out_path)`, then gzips to `data/seed_index.db.gz`.

- [ ] **Step 1: Failing test** (mock the network):
```python
import asyncio
from yoktez_mcp.models import SearchHit, SearchResult

def test_iter_slices_cartesian():
    from scripts.build_index import iter_slices, Slice
    sl = list(iter_slices([{"kod":"k","name":"U","yoksis_id":"y"}], ["2"], [2023]))
    assert sl == [Slice(uni={"kod":"k","name":"U","yoksis_id":"y"}, tur="2", year=2023)]

def test_harvest_slice_subdivides_when_capped(monkeypatch):
    from scripts import build_index
    calls = {"n": 0}
    async def fake_adv(**kw):
        calls["n"] += 1
        # first call (no Dil) → capped; Dil-split calls → complete
        capped = kw.get("dil", "0") == "0"
        hit = SearchHit(kayit_no=f"k{calls['n']}", tez_no="t", thesis_no=None,
            title_tr="T", title_en=None, author=None, year=2023,
            university="U", thesis_type="Doktora")
        return SearchResult(hits=[hit], total_found=(3000 if capped else 1),
            shown=(2000 if capped else 1), coverage_complete=not capped,
            source="live", notes=[])
    monkeypatch.setattr(build_index.search, "search_advanced", fake_adv)
    sl = build_index.Slice(uni={"kod":"k","name":"U","yoksis_id":"y"}, tur="2", year=2023)
    hits, complete = asyncio.run(build_index.harvest_slice(sl))
    assert calls["n"] > 1          # subdivided
    assert complete is True

def test_checkpoint_roundtrip(tmp_path):
    from scripts.build_index import Checkpoint
    cp = Checkpoint(tmp_path / "cp.json")
    assert not cp.done("a")
    cp.mark("a")
    cp2 = Checkpoint(tmp_path / "cp.json")
    assert cp2.done("a")
```
- [ ] **Step 2: Run** `uv run pytest tests/test_build_index.py -v` → FAIL.
- [ ] **Step 3: Implement** `scripts/build_index.py` with: argparse CLI (`--universities all|<file>`, `--turler 1,2,4`, `--years 2015-2025`, `--out`, `--checkpoint`, `--limit-universities N`); `Slice` dataclass; `iter_slices`; `harvest_slice` (subdivide by Dil 1..14 then izin 1,2 when capped, logging a `coverage_incomplete` warning if still capped — honest); `Checkpoint`; `build()` that upserts via `SearchIndex.upsert_hits`, commits per slice, and gzips the final db. All live calls via `search.search_advanced` (→ `http` politeness). Print progress + a politeness ledger (request count).
- [ ] **Step 4: Run** `uv run pytest tests/test_build_index.py -v` → PASS.
- [ ] **Step 5: Commit**
```bash
git add scripts/build_index.py tests/test_build_index.py
git commit -m "feat(harvest): polite resumable seed-index harvester (islem=2 slicing + auto-subdivide)"
```

---

### Task 11: Honesty + quality polish (offline)

**Files:**
- Modify: `src/yoktez_mcp/server.py` (`total_found` None vs 0 in advisor/author/university; remove now-false "islem=2 sunucu hatası" notes left anywhere), `src/yoktez_mcp/index.py` (docstring lines 4-5/9-12 → describe real behavior), `src/yoktez_mcp/prompts.py` (lines ~108/117 islem=2 wording), `FINDINGS.md`, memory files.
- Test: `tests/test_server.py`

- [ ] **Step 1: Failing test** — `find_advisor_theses`/`find_author_theses`/`list_university_theses` return `total_found is None` (not `0`) when only the index contributes / live returned nothing, matching `search_theses`.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** — change `live_total = 0` defaults to `None`; only set an int when live actually contributed; update `total_found` in the returned dicts. Fix the stale docstrings/notes (index.py "on-demand scraping" is now TRUE → reword to present tense; remove "islem=2 server error/unavailable" claims; prompts.py wording). Update `FINDINGS.md` §2/addendum to record islem=2 is usable + advisor name-format finding.
- [ ] **Step 4: Run** offline → green; `uvx ruff check src/ tests/ scripts/` clean.
- [ ] **Step 5: Commit**
```bash
git add src/ tests/ FINDINGS.md
git commit -m "chore(honesty): fix total_found semantics + remove stale islem=2/warming claims"
```

---

### Task 12: Run the seed harvest + bake seed_index.db.gz (operational)

**Files:** `src/yoktez_mcp/data/seed_index.db.gz` (replaced).

- [ ] **Step 1:** Choose initial polite scope: a curated set of ~15 major universities × Tur {1,2} × years 2015–2025 (sliced per Universite×Tur×year; auto-subdivide handles the few > 2000). Pre-estimate request count and print it before starting.
- [ ] **Step 2:** Run `uv run python scripts/build_index.py --turler 1,2 --years 2015-2025 --limit-universities 15 --out src/yoktez_mcp/data/seed_index.db --checkpoint .harvest_checkpoint.json` (resumable). Monitor the politeness ledger; throttle is enforced by `http.py`.
- [ ] **Step 3:** Gzip → `src/yoktez_mcp/data/seed_index.db.gz`; confirm `_seed_has_theses` is True and `index.get_default_index().search("yapay zeka")` returns rows.
- [ ] **Step 4:** Sanity-run `related_theses` on a known thesis → now returns index neighbors; `list_university_theses` on a harvested uni → returns index rows even offline.
- [ ] **Step 5: Commit**
```bash
git add src/yoktez_mcp/data/seed_index.db.gz
git commit -m "data: bake real seed index (curated 15 unis × YL+Doktora × 2015-2025)"
```

---

### Task 13: Full verification + finishing the branch

- [ ] **Step 1:** `uv run pytest -m "not live" -q` → all green (≥310 + new tests).
- [ ] **Step 2:** Polite live smoke: `uv run pytest -m live -q` (advisor diacritic, multi-word AND>0, islem=2 uni scope, relevance drop) — run once, sequential.
- [ ] **Step 3:** `uvx ruff check src/ tests/ scripts/` clean.
- [ ] **Step 4:** Manual MCP smoke via stdio: start server, call `find_advisor_theses("Aslı Deniz Helvacıoğlu")` → returns the known thesis; `search_theses("yapay zeka ceza hukuku")` → returns hits; `list_university_theses("Boğaziçi Üniversitesi")` → live results; `related_theses(known)` → neighbors.
- [ ] **Step 5:** Invoke `superpowers:verification-before-completion`; then `superpowers:finishing-a-development-branch` to merge `build/faz5-quality-moat` → master.

---

### Task 14: Update GitHub + MCP server (deploy)

**Authorized explicitly by the user.**

- [ ] **Step 1:** Push: `git push origin master` (and the branch if kept). Confirm remote updated.
- [ ] **Step 2:** Update README/docs to reflect now-working advisor/university/related + islem=2 + seed index.
- [ ] **Step 3:** Update the HF Spaces deployment (Dockerfile/space) so the live MCP server serves the new build (rebuild/redeploy). Confirm the deployed `/mcp` endpoint reports the new behavior.
- [ ] **Step 4: Commit + push** any deploy-artifact changes.

---

## Self-Review

- **Spec coverage:** WS1→Task2; WS2→Task3; WS3→Task4+7+9; WS4→Task5+6+7; WS5→Task8+10+12; WS6→Task11; deploy→Task14; verification→Task13; fixtures→Task1. All covered.
- **Placeholders:** none — each task has concrete code/tests/commands.
- **Type consistency:** `_build_keyword_slots`, `normalize_person_name`, `relevance_filter_sort`, `_build_advanced_body`/`search_advanced`, `upsert_hits`, `Slice`/`iter_slices`/`harvest_slice`/`Checkpoint` referenced consistently across tasks.
