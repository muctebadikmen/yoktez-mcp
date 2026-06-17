# YÖKTEZ MCP — Implementation Plan (Foundation → Faz 4)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Each task is sized for one fresh-context subagent running a full TDD cycle (failing test → minimal impl → green → commit) against the saved Faz 0 fixtures and the DergiPark reference. Steps use checkbox (`- [ ]`) syntax.

**Goal:** A high-quality MCP server for YÖK Ulusal Tez Merkezi (`tez.yok.gov.tr`): Turkish-aware thesis search, advisor/university discovery, permission-aware full-text, thesis-correct citations — hybrid (live scrape now, seed index later).

**Architecture:** Adapt DergiPark MCP's proven modules (`../dergipark-mcp/src/dergipark_mcp/`) — devral, uyarla, kopyalama. Replace the OAI/journal layer with YÖKTEZ scraping (session + `SearchTez` POST + AJAX JSON detail). All facts are verified in `tests/fixtures/faz0/FINDINGS.md`; **build every parser against those fixtures.**

**Tech Stack:** Python ≥3.10 · `fastmcp>=3.4` · `httpx>=0.27` · `beautifulsoup4>=4.12` · `pypdf>=4.2` · `platformdirs>=4.0`. Dev: `pytest`, `pytest-asyncio`. Lint: `ruff`. Build: `hatchling`. Package manager: `uv`.

## Global Constraints

- **Politeness (contract, not a setting):** concurrency=1, ≥1 req/s throttle, exponential backoff on 429/5xx, self-identifying User-Agent, **single shared session (JSESSIONID) reused**. Never raise concurrency / drop throttle / bulk-pull PDFs without explicit approval.
- **Honesty (product spine):** never present scanned/broken-font PDF text as reliable (`text_reliable=false`, no OCR); never fabricate restricted content (return YÖK's real permission reason); always report coverage (warm-index vs live, 2000-cap → `coverage_complete=false`); wrap ALL external text (abstracts, full text, references) in `[EXTERNAL CONTENT] … [/EXTERNAL CONTENT]` + a `source_notice`.
- **Naming:** tool names and JSON field names in **English** (`search_theses`, `advisor`, `access_status`); YÖKTEZ content (titles/abstracts) returned **as-is in Turkish**. Turkish code comments welcome where they aid clarity.
- **Turkish folding MUST be symmetric:** same `tr_fold` applied on index and on query.
- **Never** download an `izinsiz` PDF, hardcode secrets, touch `../dergipark-mcp/`, or assume HTML shape not present in a fixture.
- **Verified site facts** (full detail in `tests/fixtures/faz0/FINDINGS.md`): base `https://tez.yok.gov.tr/UlusalTezMerkezi/`; bootstrap `GET tarama.jsp` → JSESSIONID; keyword search `POST SearchTez` (`islem=4`, fields `keyword/keyword1/keyword2/ops_field/ops_field1/nevi/tip`) → 302 → `tezSorguSonucYeni.jsp`; result cards `.result-card[data-kayitno][data-tezno][data-index]` + page-embedded `referenceData` JS object + `.result-count-text` (2000-cap); detail `tezBilgiDetay.jsp?kayitNo=&tezNo=` → JSON; access `getTezPdf.jsp?kayitNo=&tezNo=` → HTML fragment (izinli ⇔ `TezGoster?key=`/`pdfizinli.png`; izinsiz ⇔ `pdf-info-msg`); keys stable across sessions; `Tur` 1–7 (Tıpta Uzmanlık=3); facets `getAllABD` (numeric kod) + `getUniversities.jsp?type=TR` (encrypted kod). **`islem=2` advanced POST recipe is being cracked by a background probe — fold its result into Task 6 when it lands.**

---

## File Structure

```
src/yoktez_mcp/
  __init__.py        # version
  __main__.py        # python -m yoktez_mcp -> stdio
  http.py            # T2: async client + JSESSIONID session + throttle + 429 backoff + POST/302
  cache.py           # T3: memory LRU+TTL + optional disk (near-verbatim from dergipark)
  models.py          # T1: shared dataclasses (Thesis, SearchResult, AccessStatus enum)
  facets.py          # T4: enum tables + parse getAllABD/getUniversities; load data/facets.json
  search.py          # T5/T6: SearchTez islem=4 (kw) + islem=2 (advanced) + result-card parse
  detail.py          # T7: tezBilgiDetay JSON parse + getTezPdf access parse
  index.py           # T8: FTS5 + tr_fold + BM25 bonuses (thesis schema) + seed load
  citations.py       # T9: CitationData + 8 formats, THESIS rules
  pdf.py             # T10: PDF->md + thesis section map + text_reliable
  prompts.py         # T12: 4 thesis prompts (register(mcp))
  server.py          # T11/T13: FastMCP tools + resources + EXTERNAL CONTENT wrapping
  data/facets.json   # built by scripts/build_facets.py (T4)
scripts/
  build_facets.py    # T4: getAllABD + getUniversities -> data/facets.json
tests/
  conftest.py        # T2: async state reset (http/cache/lock), background refresh off
  fixtures/faz0/...  # committed (Faz 0)
  fixtures/derived/  # trimmed fixtures created per-task from the gitignored raws
```

---

## Task 0: Project scaffold

**Files:** Create `pyproject.toml`, `src/yoktez_mcp/__init__.py`, `src/yoktez_mcp/__main__.py`, `tests/conftest.py`, `README.md` (stub).

**Interfaces — Produces:** installable package `yoktez_mcp`; entrypoints `yoktez-mcp` (stdio `server:main`) and `yoktez-mcp-serve` (HTTP `server:serve_http`) — defined now, server filled in T11/T13; `uv run pytest -m "not live"` runs.

- [ ] Mirror DergiPark `pyproject.toml` (deps, ruff, pytest markers incl. `live`, hatch wheel + `force-include` for `data/facets.json` and `data/seed_index.db.gz`). Rename to `yoktez-mcp`, version `0.1.0`.
- [ ] `__init__.py`: `__version__ = "0.1.0"`. `__main__.py`: `from .server import main; main()`.
- [ ] `tests/conftest.py`: adapt DergiPark conftest — autouse fixture resetting http client/semaphore/lock + cache between tests; disable background refresh.
- [ ] `uv sync`; `uv run pytest -m "not live" -q` (collects 0 tests, exits clean). Commit.

---

## Task 1: Shared models

**Files:** Create `src/yoktez_mcp/models.py`, `tests/test_models.py`.

**Interfaces — Produces:**
- `class AccessStatus(str, Enum)`: `OPEN="open"`, `RESTRICTED="restricted"`, `UNKNOWN="unknown"`.
- `@dataclass Thesis`: `kayit_no, tez_no, thesis_no(human), title_tr, title_en, author, advisor, university, institute, department(ABD), science_branch, thesis_type(str), year(int|None), pages(int|None), language, subjects(list), keywords_tr(list), keywords_en(list), abstract_tr, abstract_en, access_status(AccessStatus), access_reason(str|None), pdf_key(str|None)`.
- `@dataclass SearchHit`: lightweight card row — `kayit_no, tez_no, thesis_no, title_tr, title_en, author, year, university, thesis_type`.
- `@dataclass SearchResult`: `hits(list[SearchHit]), total_found(int), shown(int), coverage_complete(bool), source(str: "live"|"index"|"hybrid"), notes(list[str])`.
- `THESIS_TYPE_BY_CODE: dict[str,str]` and `THESIS_TYPE_TO_CODE` for `Tur` 1–7 (1 Yüksek Lisans, 2 Doktora, 3 Tıpta Uzmanlık, 4 Sanatta Yeterlik, 5 Diş Hekimliği Uzmanlık, 6 Tıpta Yan Dal Uzmanlık, 7 Eczacılıkta Uzmanlık).

- [ ] TDD: test that `THESIS_TYPE_BY_CODE["3"] == "Tıpta Uzmanlık"` and round-trips; dataclasses instantiate with defaults (all optional except keys). Commit.

---

## Task 2: http.py — session-aware polite client

**Files:** Create `src/yoktez_mcp/http.py`, `tests/test_http.py`.

**Interfaces — Consumes:** nothing. **Produces:**
- `async def get(url, params=None) -> httpx.Response`
- `async def get_text(url, params=None) -> str`, `async def get_bytes(url, params=None) -> bytes`
- `async def post_form(path, data: dict) -> httpx.Response` — form-urlencoded POST with `Referer: <base>/tarama.jsp`, `Origin: https://tez.yok.gov.tr`, **follows 302**; returns the final response after redirect.
- `async def ensure_session() -> None` — idempotent `GET tarama.jsp` to seed JSESSIONID if the cookie jar lacks it; auto-called by `post_form`.
- `async def aclose()`; module constants `BASE_URL`, `USER_AGENT`, env-tunable `MIN_INTERVAL/MAX_CONCURRENCY/MAX_RETRIES/BACKOFF_BASE/TIMEOUT` (prefix `YOKTEZ_`).

**Notes:** Adapt DergiPark `http.py`. Use ONE persistent `httpx.AsyncClient(cookies=<jar>, follow_redirects=False)` so JSESSIONID persists; do redirect-follow manually in `post_form` (need to see the 302 Location). Throttle + semaphore=1 + 429/5xx backoff identical to DergiPark. UA `yoktez-mcp/<ver> (academic research MCP; +mdikment@gmail.com)`.

- [ ] Test (offline, monkeypatch transport): two sequential `get()` calls are ≥`MIN_INTERVAL` apart (throttle); `post_form` sets Referer/Origin headers and follows a 302 to its Location; `ensure_session` only fetches tarama.jsp once when cookie already present. Commit.
- [ ] Live test (`@pytest.mark.live`): `ensure_session` yields a JSESSIONID cookie. Commit.

---

## Task 3: cache.py

**Files:** Create `src/yoktez_mcp/cache.py`, `tests/test_cache.py`. **Interfaces — Produces:** `class Cache` (memory LRU+TTL + optional disk SQLite via platformdirs), `cache_dir()`. Near-verbatim adapt from DergiPark; rename env prefix to `YOKTEZ_`, app name `yoktez-mcp`.

- [ ] Adapt DergiPark `test_cache.py`. TTL expiry, LRU eviction, disk round-trip, schema-version invalidation. Commit.

---

## Task 4: facets.py + build_facets.py

**Files:** Create `src/yoktez_mcp/facets.py`, `scripts/build_facets.py`, `tests/test_facets.py`, `src/yoktez_mcp/data/facets.json`. Derive trimmed fixtures from `tests/fixtures/faz0/getAllABD.html` (gitignored raw) + committed `getUniversities_TR.html`.

**Interfaces — Produces:**
- `ENUMS: dict` — code tables for `Tur, izin, Durum, Dil, nevi, tip` (verbatim from FINDINGS §3) with human labels.
- `def parse_abd(html: str) -> list[dict]` → `[{"kod": "2821", "name": "ABAZA DİLİ VE EDEBİYATI ANABİLİM DALI"}, ...]` from `<input ad= kod=>`.
- `def parse_universities(json_text: str) -> list[dict]` → `[{"kod","name","yoksis_id"}]` (note: `kod` encrypted, `displayName`→`name`).
- `def load_facets() -> dict` (embedded `data/facets.json`); `def find_university(query: str) -> list[dict]` and `find_abd(query)` (tr_fold substring match — import `tr_fold` from index OR a local copy; resolve in T8).
- `scripts/build_facets.py`: politely fetch getAllABD + getUniversities (TR+INT), write `data/facets.json` `{enums, universities, abd, built_at}`.

- [ ] TDD `parse_abd` vs derived ABD fixture (assert count & a known `kod`/`name`); `parse_universities` vs `getUniversities_TR.html` (260 entries; encrypted kod present). Build `facets.json`, assert `load_facets()` returns enums+universities+abd. Commit.

---

## Task 5: search.py — keyword (islem=4) flow + result-card parse

**Files:** Create `src/yoktez_mcp/search.py`, `tests/test_search.py`. Derive a trimmed fixture `tests/fixtures/derived/results_islem4.html` from the gitignored `search_keyword_islem4.html` containing: the `.result-count-text`, ~5 `.result-card`s, and the matching `referenceData` JS slice for those indices, plus (separately) a no-results page snippet.

**Interfaces — Consumes:** `http.post_form`, `models.SearchHit/SearchResult`. **Produces:**
- `def parse_results(html: str) -> SearchResult` — extract cards (`data-kayitno/-tezno/-index`, `.card-title` TR, italic `.card-info` EN, `Tez No`), merge per-card meta from embedded `referenceData` (author, year, type, university via `yer`), parse `.result-count-text` → `total_found/shown/coverage_complete`. Robust to missing fields and the no-results case (`hits=[]`).
- `async def search_keyword(query, *, field="title", match="contains") -> SearchResult` — map `field`→`nevi` (title=1, author=2, advisor=3, subject=4, keyword=5, abstract=6, all=7), `match`→`tip` (exact=1, contains=2), build the verified minimal islem=4 POST (`keyword,keyword1=,keyword2=,ops_field=and,ops_field1=and,nevi,tip,islem=4`), `post_form` → parse final 302 page. `source="live"`.

**Critical:** Do NOT add `izin/Tur/yil` to the islem=4 POST (breaks → "Geçersiz sorgulama"). Detect the error page (`error_gecersiz_sorgulama.html`) and raise a clear `SearchError`.

- [ ] TDD `parse_results` vs derived fixture: ≥5 hits, a known `data-kayitno`, `total_found`/`shown` parsed, `coverage_complete` correct; no-results → empty. Error-page detection vs `error_gecersiz_sorgulama.html`. Commit.
- [ ] Live test (`@pytest.mark.live`): `search_keyword("yapay zeka")` returns hits with non-empty `kayit_no`. Commit.

---

## Task 6: search.py — advanced (islem=2) filtered flow

**Depends on:** the background `islem=2` probe result (fold in its verified POST recipe + any new fixture `search_advanced_islem2.html`). If the probe reports "not cracked," implement the function to raise `NotImplementedError("advanced live filter pending islem=2")` and rely on index-side filtering (T8) for type/year/university — record the gap in a `notes` entry and in FINDINGS.

**Interfaces — Produces:** `async def search_advanced(*, query=None, field="title", thesis_type=None, year_from=None, year_to=None, university_kod=None, university_yoksis_id=None, abd_kod=None, izin=None, language=None, durum="approved") -> SearchResult` — build the islem=2 POST per the probe recipe (empty→"0" rule, `-find` submit, encrypted university `kod`+`yoksis_id` pair, numeric `abd_kod`), `post_form` → `parse_results`.

- [ ] TDD vs the advanced fixture (if cracked): type+year filter yields hits; reuse `parse_results`. Live test type-filtered query. Commit. (If not cracked: test the NotImplementedError path + note.)

---

## Task 7: detail.py — JSON detail + access parse

**Files:** Create `src/yoktez_mcp/detail.py`, `tests/test_detail.py`. Fixtures: `tezBilgiDetay.json`, `tezBilgiDetay_izinsiz.json`, `getTezPdf_card0.html`, `getTezPdf_izinsiz.html` (all committed).

**Interfaces — Consumes:** `http.get_text`, `models.Thesis/AccessStatus`. **Produces:**
- `def parse_detail(json_text: str) -> dict` — from `tezBilgiDetay.jsp` JSON: `danisman`→advisor; split `yer` (`ÜNİV / ENSTİTÜ / ABD / Bilim Dalı`) → university/institute/department/science_branch; `trOzet/enOzet`→abstracts; `anahtarKelimeTr/En`→keyword lists; keep server citations (`apa_ref…harvard_ref`) for cross-check.
- `def parse_access(fragment_html: str) -> tuple[AccessStatus, str|None, str|None]` → `(status, reason, pdf_key)`: izinli ⇔ `TezGoster?key=([^'"]+)` present → `(OPEN, None, key)`; izinsiz ⇔ `pdf-info-msg` text → `(RESTRICTED, <that text>, None)`; neither → `(UNKNOWN, None, None)`.
- `async def get_thesis(kayit_no, tez_no, *, base_meta: SearchHit|None=None) -> Thesis` — fetch `tezBilgiDetay.jsp?kayitNo=&tezNo=` + `getTezPdf.jsp?kayitNo=&tezNo=`, merge with any `base_meta` (author/year/title/type from the search card), populate `access_status/access_reason/pdf_key`.

- [ ] TDD: `parse_detail` vs both JSON fixtures (advisor, `yer` split, keyword lists; izinsiz has empty abstracts but present advisor/citations). `parse_access` → OPEN+key for `getTezPdf_card0.html`, RESTRICTED+exact reason text for `getTezPdf_izinsiz.html`. Commit.
- [ ] Live test: a real izinli thesis → `access_status==OPEN`, `pdf_key` set. Commit.

---

## Task 8: index.py — FTS5 + Turkish fold + thesis schema

**Files:** Create `src/yoktez_mcp/index.py`, `tests/test_index.py`. Adapt DergiPark `index.py`.

**Interfaces — Produces:** `def tr_fold(s) -> str` (Turkish-aware: İ/ı/I/i, ş/ç/ğ/ö/ü → folded, symmetric on index+query); `class SearchIndex` with `upsert(theses: list[Thesis])`, `search(query, *, thesis_type=None, year_from=None, year_to=None, university=None, advisor=None, department=None, limit=20) -> SearchResult` (BM25 + phrase/recency bonuses), `by_advisor(name)`, `by_author(name)`, `by_university(name, ...)`, `related(thesis, limit)`; `get_default_index()` (loads `data/seed_index.db.gz` if present — absent for now → empty warm index). Schema columns: title_tr/en, author, **advisor**, university, institute, department, thesis_type, year, keywords, subjects, abstract_tr/en, kayit_no, tez_no, access_status.

- [ ] TDD: `tr_fold("İŞÇİ")==tr_fold("isci"...)` symmetric; upsert 3 theses then `search` ranks exact-title higher; `by_advisor` folds name order; filters narrow results. `get_default_index()` with no seed → empty, `source="index"`. Commit.

---

## Task 9: citations.py — thesis rules, 8 formats

**Files:** Create `src/yoktez_mcp/citations.py`, `tests/test_citations.py`. Adapt DergiPark `citations.py`; replace article rules with thesis rules.

**Interfaces — Produces:** `@dataclass CitationData` (author, year, title, thesis_type, university, thesis_no, url, language…); `format_apa/mla/ieee/chicago/harvard`, `to_bibtex` (`@phdthesis` for Doktora/Tıpta/Sanatta, `@mastersthesis` for Yüksek Lisans), `to_ris` (`TY  - THES`), `to_csl_json` (`"type":"thesis"`), `all_citations(d) -> dict`, `format_citation(d, style)`.

- APA 7: `Yazar, A. (Yıl). *Başlık* [Yüksek lisans tezi / Doktora tezi, Üniversite Adı]. YÖK Ulusal Tez Merkezi.`
- Cross-check our APA/IEEE/MLA/Chicago/Harvard against the server-rendered `*_ref` strings in `tezBilgiDetay.json` (close, not necessarily byte-identical — document any deliberate deviation).

- [ ] TDD: build `CitationData` from the fixture thesis; assert APA has `[Doktora tezi, …]. YÖK Ulusal Tez Merkezi.`; BibTeX entry type matches thesis_type; RIS `TY  - THES`; CSL `type: thesis`; `all_citations` returns 8 keys. Commit.

---

## Task 10: pdf.py — full text, thesis sections, reliability

**Files:** Create `src/yoktez_mcp/pdf.py`, `tests/test_pdf.py`. Adapt DergiPark `pdf.py`; swap section keywords to thesis sections (ÖZET, ABSTRACT, GİRİŞ, YÖNTEM/GEREÇ VE YÖNTEM, BULGULAR, TARTIŞMA, SONUÇ, KAYNAKÇA/KAYNAKLAR, EKLER).

**Interfaces — Produces:** `@dataclass ExtractedPDF`; `def split_sections(text)`, `def readable_ratio(text)`, `def extract(data: bytes, ...) -> ExtractedPDF` (sets `text_reliable` via readable-ratio; **no OCR**); `async def download_and_extract(pdf_url) -> ExtractedPDF` — only ever called for an OPEN thesis with a `TezGoster?key=` url. `def references_section(extracted) -> str|None` (KAYNAKÇA slice).

**Honesty:** scanned/broken-font → `text_reliable=false`; never invent text. **Guard:** `download_and_extract` must refuse if called without a pdf_key/OPEN status.

- [ ] TDD: `split_sections` finds thesis headings in a synthetic thesis text; `readable_ratio` low for garbled → `text_reliable=false`; `references_section` extracts KAYNAKÇA. (Live PDF test optional, `@pytest.mark.live`, single small open thesis.) Commit.

---

## Task 11: server.py — tools + EXTERNAL CONTENT wrapping

**Files:** Create `src/yoktez_mcp/server.py`, `tests/test_server.py`. Adapt DergiPark `server.py` (FastMCP, READONLY annotations, `main()` stdio + `serve_http()`).

**Interfaces — Produces tools** (all READONLY; external text wrapped in `[EXTERNAL CONTENT]…[/EXTERNAL CONTENT]` + `source_notice`):
- `search_theses(query, field?, thesis_type?, year_from?, year_to?, university?, department?, language?, access?, sort?, limit?)` — index-first then live `search_keyword`/`search_advanced` to fill; merge + dedupe by `kayit_no`; honest `source`/`coverage_complete`/`notes`.
- `get_thesis(kayit_no, tez_no)` — rich record + all 8 citations.
- `get_thesis_fulltext(kayit_no, tez_no)` — OPEN → PDF→md + section map + `text_reliable`; RESTRICTED → `access_status` + reason, no fabrication.
- `find_advisor_theses(advisor)`, `find_author_theses(author)`, `list_university_theses(university, thesis_type?, year_from?, year_to?)`, `related_theses(kayit_no, tez_no)`, `list_facets(kind?, query?)`, `get_thesis_references(kayit_no, tez_no)`.

- [ ] TDD (offline, monkeypatch search/detail to fixture data): `search_theses` returns wrapped result with coverage fields; `get_thesis_fulltext` on a restricted thesis returns the reason and never PDF text; external text is wrapped. Commit.

---

## Task 12: prompts.py — 4 thesis workflows

**Files:** Create `src/yoktez_mcp/prompts.py`, `tests/test_prompts.py`. `def register(mcp)`: `tez_literatur_taramasi`, `tez_ozeti`, `danisman_ekol_analizi`, `universite_uretim_haritasi`.

- [ ] TDD: `register` adds 4 prompts; each returns non-empty guidance text. Commit.

---

## Task 13: Resources + wire-up + end-to-end live smoke

**Files:** Modify `server.py`; create `tests/test_live_e2e.py`.

**Interfaces — Produces:** resources `yoktez://thesis/{kayit_no}/{tez_no}`, `yoktez://advisor/{name}`, `yoktez://university/{slug}`; `prompts.register(mcp)` wired; `main()`/`serve_http()` runnable.
- [ ] `uv run yoktez-mcp` starts (stdio handshake). Live e2e (`@pytest.mark.live`): search → get_thesis → (open) fulltext OR (restricted) reason. Commit.

---

## Deferred (separate plans, after Faz 4 is green)
- **Faz 5 — seed index harvest** (`scripts/build_index.py`, Tur×yıl×ABD slicing under 2000-cap, gzip → `data/seed_index.db.gz`). Heavy polite scraping → its own plan + explicit go.
- **Faz 6 — hardening + distribution** (bilingual README TR/EN, `.mcpb`, HF Spaces, CI). HF deploy = stop-and-ask.

## Self-Review notes
- Every PLAN.md §5 tool maps to a task (T11). Citations (§6.1) → T9; advisor axis (§6.2) → T1/T7/T8/T11/T12; access honesty (§6.3) → T7/T10/T11; 2000-cap (§6.4) → T5; session (§6.6) → T2.
- Known gap: `islem=2` advanced live filter depends on the background probe (T6 has both branches). Index-side filtering (T8) is the fallback for type/year/university until cracked.
- No OCR anywhere (honesty). No PDF fetch for restricted (T10 guard).
