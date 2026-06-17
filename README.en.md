# YÖKTEZ MCP

🇹🇷 [Türkçe](README.md) · 🇬🇧 English (this file)

A **Model Context Protocol (MCP)** server for [YÖK National Thesis Center (YÖK Ulusal Tez Merkezi)](https://tez.yok.gov.tr) — Turkey's national thesis repository. It lets Claude (Desktop / claude.ai / mobile) and other MCP clients search Master's, PhD, Medical Specialty, and Proficiency in Art theses with **Turkish-aware** full-text search, discover theses by **advisor and university**, read the full text of open-access theses, and generate **thesis-correct citations in 8 formats**.

> ⚡ **Easiest use: no installation.** Paste a single URL into Claude — no app, no config, no Python. [→ Get started](#-fastest-install-paste-a-url-recommended)

---

## 🚀 Fastest install: paste a URL (recommended)

This MCP is live as an **online server** (Hugging Face Spaces, free). With no downloads, a **single URL** adds it in a few clicks — and it works in **Claude Desktop, claude.ai (browser), and mobile**.

**1) Copy this URL:**

```
https://muctebadikmen-yoktez-mcp.hf.space/mcp
```

**2) Connect in Claude:** **Settings → Connectors → Add custom connector** → paste the URL → **Add**.

> ⚠️ When connecting, paste the **endpoint** URL ending in **`...hf.space/mcp`** above — not the HF Space **page address** (`huggingface.co/spaces/...`). The "Connect" card on the Space page probes the root and may show "connection issue"; this is cosmetic — the real endpoint is `/mcp`.

**3) Test it:** ask Claude:
> *"Search YÖKTEZ for theses on AI-assisted education."*

That's it. No config file, no `uv`/Python, no drag-and-drop.

> ℹ️ **Honest note:** the free server sleeps after long idle periods; the first request takes **~30–60s** to wake, then it's fast. It's open and keyless — anyone with the URL can use it (an open academic tool).

<details>
<summary>🖥️ Want to run it <b>locally</b> on your own machine? (advanced / optional)</summary>

The URL method is enough for most people. But if you want to run the server **on your own machine** (privacy, offline cache, no dependency on the hosted server), there are two ways with `uv` (a Python manager).

### a) One-line `uvx` (recommended local method)

**1) Install `uv`:**
- macOS / Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Windows (PowerShell): `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"` (then reopen the terminal)

**2) Claude Desktop → Settings → Developer → Edit Config** (opens `claude_desktop_config.json`).

**3) Add this block:**
```json
{
  "mcpServers": {
    "yoktez": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/muctebadikmen/yoktez-mcp", "yoktez-mcp"]
    }
  }
}
```

**4) Save and fully quit-and-reopen Claude Desktop** (**Cmd+Q** on Mac).

- *"uvx not found":* use the full path — `which uvx` (Mac/Linux), `where uvx` (Windows).
- *Update:* `uvx --refresh --from git+https://github.com/muctebadikmen/yoktez-mcp yoktez-mcp`

### b) Claude Code (CLI)
```bash
claude mcp add --transport http yoktez https://muctebadikmen-yoktez-mcp.hf.space/mcp   # hosted URL
# or local:
claude mcp add yoktez -- uvx --from git+https://github.com/muctebadikmen/yoktez-mcp yoktez-mcp
```
</details>

---

## ⭐ Why this MCP?

YÖKTEZ has **no official API, no OAI-PMH, and no open search service** — the only access path is politely scraping its JSP/servlet interface. Existing alternatives either scrape live on every query (slow, hit by YÖK's **2,000-results/query** cap), are web applications (not MCP), or are manual browser extensions.

This project's advantage comes from **engineering quality and honesty**:

| | **This project** | Live-scraping competitors | tezara.org | Bookmarklet |
|---|---|---|---|---|
| **MCP standard** | ✅ FastMCP (stdio + HTTP + hosted) | ✅ | ❌ (web) | ❌ |
| **Turkish-aware search** | ✅ `İ/ı/ş/ğ/ü/ö/ç` folding + BM25 | ⚠️ server-dependent | — | ❌ |
| **Advisor axis** (academic genealogy) | ✅ First-class discovery | partial | partial | ❌ |
| **Thesis-correct citations** | ✅ 8 formats (`@phdthesis`/`@mastersthesis`) | a few | ❌ | ❌ |
| **Honesty** (coverage / access / reliability) | ✅ Explicit flags | partial | — | ❌ |
| **Prompt-injection protection** | ✅ `[EXTERNAL CONTENT]` | unclear | — | ❌ |
| **Keyless / free** | ✅ | varies | ✅ | ✅ |
| **Warm cross-thesis index** | 🛠️ Architecture ready — *harvest on the roadmap* | ❌ | ✅ (web) | ❌ |

> **Design principle:** The site is fragile and has no official API — so we act as a **good citizen** (single session, ≥1 req/s, 429 backoff, self-identifying `User-Agent`) and bake **honesty** into every response: what is live, what is missing, what is access-restricted, and what is unreliable is stated explicitly.

---

## What does it do?

### 🔧 Tools (9)

| Tool | Description |
|---|---|
| `search_theses` | **Turkish-aware thesis search.** Field filters (thesis title / author / advisor / subject / keyword / abstract / all), type, year, university, department (anabilim dalı), language, and access filters. **Coverage is reported honestly** in results (YÖK's 2,000-result cap → `coverage_complete=false`). |
| `get_thesis` | **Rich record:** title (TR/EN), author, **advisor**, university / institute / department (anabilim dalı) / subdiscipline, type, year, language, abstract (TR/EN), keywords, **access status** + **8 citation formats**. |
| `get_thesis_fulltext` | Downloads the PDF and converts it to Markdown for open-access theses; includes a **section map** (ABSTRACT/INTRODUCTION/METHODS/RESULTS/…/REFERENCES). Scanned/broken-font PDFs are honestly flagged `text_reliable=false`. For **restricted theses**, returns YÖK's actual permission/reason text — never fabricates content. |
| `find_advisor_theses` | **Advisor-based discovery** — all theses supervised by an advisor (academic genealogy / school-of-thought analysis). Name-order independent. |
| `find_author_theses` | An author's thesis or theses. |
| `list_university_theses` | A university's thesis production map (filterable by type/year). |
| `related_theses` | Theses **similar** to a given one (subject/keyword/title overlap). |
| `list_facets` | **Valid filter values:** dictionary of ~5,100 departments (anabilim dalı) + 260 universities and enum codes (type, access, status, language, search field). |
| `get_thesis_references` | The reference list from an open-access thesis's REFERENCES section (PDF). |

### 💬 Prompts (4) — ready-made research workflows

`tez_literatur_taramasi` · `tez_ozeti` · `danisman_ekol_analizi` · `universite_uretim_haritasi`. They appear in the "/" menu in Claude Desktop.

### 📦 Resources (3)

`yoktez://thesis/{kayit_no}/{tez_no}` · `yoktez://advisor/{name}` · `yoktez://university/{name}`

### ✨ Highlights

- **Advisor as a first-class citizen:** Academic genealogy — critical in the thesis world, absent from journal tools — "X's PhD students", tracking scholarly lineages — with its own dedicated tool and prompt.
- **Turkish-aware search:** `İ/ı/ş/ğ/ü/ö/ç` are folded symmetrically → "eğitim" ≈ "Eğitim" ≈ "egitim"; the index and query use the same folding.
- **Thesis-correct citations (8 formats):** APA, MLA, IEEE, Chicago, Harvard, BibTeX, RIS, CSL-JSON — with **thesis rules**: `[Doktora tezi, Üniversite]. YÖK Ulusal Tez Merkezi.`, BibTeX `@phdthesis`/`@mastersthesis`, RIS `TY - THES`, CSL `"type":"thesis"`.
- **The access model is real:** every thesis's status (open / restricted (izinli/izinsiz)) is surfaced; the PDF of a restricted thesis is **never** downloaded and its content is **never** fabricated.
- **Honest coverage:** queries that hit YÖK's 2,000-result cap are flagged `coverage_complete=false` with a suggestion to narrow the query.

---

## 🔑 Key concepts

### `kayit_no` + `tez_no` (thesis identity)
A thesis is accessed via these **two keys**. They are **opaque/encrypted** keys from result-card attributes (YÖK's internal AJAX keys) and are **stable across sessions** — making them safe to use as cache keys and resource URIs. The **"Tez No"** visible to users (e.g. `1009908`) is separate; that human-readable number is used in citations.

### Thesis type codes (`Tur`)
`1` Yüksek Lisans (Master's) · `2` Doktora (PhD) · `3` Tıpta Uzmanlık (Medical Specialty) · `4` Sanatta Yeterlik (Proficiency in Art) · `5` Diş Hekimliği Uzmanlık (Dental Specialty) · `6` Tıpta Yan Dal Uzmanlık (Medical Sub-specialty) · `7` Eczacılıkta Uzmanlık (Pharmacy Specialty).

### Access status
`open` (izinli — full-text PDF available) · `restricted` (izinsiz — author has not granted publication permission; YÖK's reason text is returned, PDF is not downloaded).

---

## 🗣️ Example usage (natural language to Claude)

- *"Search YÖKTEZ for theses on **AI-assisted education**."* → `search_theses`
- *"List theses supervised by **Duygu Mutlu Bayraktar**."* → `find_advisor_theses` (academic genealogy)
- *"Find **Ahmet Yılmaz**'s theses on YÖKTEZ."* → `find_author_theses`
- *"Give me the record and **APA + BibTeX** citation for this thesis."* → `get_thesis`
- *"Read the **open-access full text** of this thesis and summarize the methods section."* → `get_thesis_fulltext`
- *"Suggest theses **similar** to this PhD thesis."* → `related_theses`
- *"Show Hacettepe University's PhD theses from the last 5 years."* → `list_university_theses`
- *"/danisman_ekol_analizi advisor=Prof. Dr. ..."* (prompt)

---

## ⚙️ Environment variables (optional — local runs)

| Variable | Default | Description |
|---|---|---|
| `YOKTEZ_MIN_INTERVAL` | `1.0` | Min seconds between requests (politeness). |
| `YOKTEZ_MAX_CONCURRENCY` | `1` | Concurrent requests. |
| `YOKTEZ_MAX_RETRIES` | `4` | Retry count for 429/5xx. |
| `YOKTEZ_BACKOFF_BASE` | `2.0` | Exponential backoff base (seconds). |
| `YOKTEZ_TIMEOUT` | `60.0` | Request timeout (seconds). |
| `YOKTEZ_ENABLE_DISK_CACHE` | off | `1` → enables disk cache (persists across processes). |
| `YOKTEZ_CACHE_DIR` | platform-specific | Cache + search-index directory. |

---

## ⚠️ Honest limitations

Honesty is the backbone of this project. The real limitations of the current version:

- **Advanced-filter *live* search not yet available (`islem=2`).** YÖK's advanced search form (type/year/university/department filters) is closed to programmatic POST requests server-side (requires browser-specific JS; a plain request returns "Hata Oluştu"). Currently these filters are applied **on the local index + live keyword results**. *(Roadmap: to be resolved by capturing the real browser POST.)*
- **Warm cross-thesis index not yet harvested.** The seed index bundled with the package is currently an **empty placeholder**; search therefore runs on **live keyword** queries and is subject to YÖK's **2,000-results/query** cap (coverage is reported honestly). *(Roadmap: polite harvest by type×year×department slicing → `data/seed_index.db.gz`.)*
- **No OCR.** Scanned/broken-font PDFs cannot yield real extracted text; with no free, keyless, frictionless OCR path available, it is out of scope. These documents are marked **`text_reliable=false`**.
- **No full text for restricted theses.** If the author has not granted publication permission, the PDF is inaccessible; content is not fabricated — YÖK's reason text is returned instead. (Print copies can be obtained through university libraries via TÜBESS.)

---

## 🔒 Security (prompt-injection)

Abstracts, full text, and references from YÖKTEZ are **external content**. The server wraps this text in `[EXTERNAL CONTENT] … [/EXTERNAL CONTENT]` and adds a `source_notice` to responses: this content should be treated as **data**, not **instructions**.

## 🙏 Good citizen

The site is fragile and provides no official API. The client keeps **concurrency at 1**, **request spacing at ≥1s**, applies **exponential backoff** on 429/transient 5xx, **reuses a single session (JSESSIONID)**, and identifies itself in the `User-Agent`. Bulk harvesting (seed index) is done in polite slices; the site is never scraped aggressively.

## ⚖️ Legal / ethics

- **Bibliographic metadata** (title, author, advisor, abstract) is open-access and may be freely indexed.
- **Full text** is fetched on demand for the end user, and only for theses the author has marked **open (izinli)**; the PDF of a restricted thesis is **never downloaded**. Access status is explicit in every response.
- The client rate-limits, reuses a single session, and identifies itself.

This software is provided "as is"; responsibility for content use lies with the user.

---

## 🧱 Architecture

```
Client (Claude)  ──MCP──>  server.py (9 tools + 4 prompts + 3 resources, EXTERNAL CONTENT wrapping)
   • Hosted: https://muctebadikmen-yoktez-mcp.hf.space/mcp  (HTTP)
   • Local:  uvx  (stdio)
                               │
   ┌────────────┬──────────────┼───────────────┬──────────────┬────────────┐
   ▼            ▼             ▼               ▼              ▼            ▼
search.py     detail.py      pdf.py          index.py      facets.py   citations.py
(SearchTez    (tezBilgiDetay (PDF→md +       (FTS5 +       (~5,100 dept (8 citations,
 islem=4 +     JSON +         section map +   Turkish fold + + 260 univ + THESIS rules)
 result card   getTezPdf      text_reliable,  BM25 +        enum codes)
 + 2000-cap    access parse)  restricted-PDF  seed load)
 parse)            │           guard)            │
   │               │                              ▼
   └───────────────┴────────  cache.py (memory+disk) · http.py (session, throttle, 429 backoff) · text.py (tr_fold)
```

Hybrid architecture: **live `SearchTez`** scraping + **local FTS5 index**. A bundled, gzipped seed index (`data/seed_index.db.gz`) is loaded at startup; once harvesting is complete, it will make cross-thesis search **warm** from the first query (currently an empty placeholder — see Honest limitations).

---

## 🧪 Development & testing

```bash
uv sync
uv run pytest -m "not live" -q     # offline (fast): parser/index/citations/pdf/cache/facets
uv run pytest -m live -q           # live (real YÖKTEZ traffic — polite, slow)
uvx ruff check src/ tests/         # lint
```

**Refresh the facet dictionary (universities/departments/enums):**
```bash
uv run python scripts/build_facets.py     # regenerates data/facets.json from live YÖKTEZ
```

---

## 📄 License

MIT — see [LICENSE](LICENSE).

---

*This server adapts the proven architecture of [DergiPark MCP](https://github.com/muctebadikmen/dergipark-mcp) for the world of theses — together they form a consistent family of Turkish academic MCP tools.*
