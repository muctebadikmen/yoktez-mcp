# Faz 0 — YÖKTEZ Live Discovery Findings (verified against tez.yok.gov.tr)

> Load-bearing facts about the live site, confirmed by polite live probing on 2026-06-17.
> Every parser in this repo is built against the fixtures in this directory. **These supersede
> the assumptions in `PLAN.md` §2 / §6 where they conflict** (see "Corrections" at the bottom).

Base URL: `https://tez.yok.gov.tr/UlusalTezMerkezi/`

## 1. Session flow
- `GET tarama.jsp` → 200 + `Set-Cookie: JSESSIONID=...; Path=/UlusalTezMerkezi; HttpOnly`. Bootstrap is mandatory before any POST.
- Reuse that one cookie jar for the search POST. **No CSRF token** in the form.

## 2. SearchTez — TWO forms

### `GForm2` — keyword search (`islem=4`) — WORKS, this is the live search path
- Fields: `keyword`, `keyword1`, `keyword2` (up to 3 terms), `ops_field`, `ops_field1` (`and`/`or`/`not`), `nevi` (search field), `tip` (match mode), `islem=4`.
- Minimal verified POST that returns results:
  `keyword=<query>&keyword1=&keyword2=&ops_field=and&ops_field1=and&nevi=1&tip=1&islem=4`
- **`nevi`** (which field to search): `1`=Tez Adı, `2`=Yazar, `3`=Danışman, `4`=Konu, `5`=Anahtar Kelime, `6`=Özet, `7`=Tümü.
- **`tip`** (match mode, NOT thesis type): `1`=exact ("sadece yazılan şekilde"), `2`=contains ("kelimenin içinde geçsin").
- ⚠️ Adding `izin`/`Tur`/`yil1`/`yil2` to the islem=4 POST **breaks it** → 302 → `tezSorguSonucHata.jsp` → "Geçersiz sorgulama. Lütfen tekrar deneyiniz." The keyword form is keyword-only.

### `GForm` — advanced search (`islem=2`) — NOT yet cracked (Faz 1 follow-up)
- Fields: `Universite`, `uni_yoksis_id`, `Enstitu`, `ABD`, `Bolum`, `Konu`, `Tur`, `yil1`, `yil2`, `izin`, `Durum`, `Dil`, `TezAd`, `Dizin`, `TezNo`, `Metin`, `islem=2`, submit `-find=  Bul`.
- All curl attempts returned `tezSorguSonucHata.jsp` "Hata Oluştu". The form's JS populates hidden `Universite`/`Enstitu`/`ABD`/`Konu` from **encrypted `kod` tokens** (from the facet endpoints). Cracking the exact POST shape needs a dedicated live probe — see `ISLEM2_TODO`.
- empty-as-"0": confirmed for the advanced form (blank `Enstitu`/`yil1`/`yil2`/... → "Geçersiz sorgulama"). All advanced dropdowns default to `value="0"`.

### 302 success pattern
`POST SearchTez` (islem=4) → **302 → `tezSorguSonucYeni.jsp`** (NOT a SearchTez re-render). Follow with GET on the same session.

## 3. Enum codes (from `tarama.html`)
| Param | Codes |
|---|---|
| **`Tur`** | **1=Yüksek Lisans, 2=Doktora, 3=Tıpta Uzmanlık, 4=Sanatta Yeterlik, 5=Diş Hekimliği Uzmanlık, 6=Tıpta Yan Dal Uzmanlık, 7=Eczacılıkta Uzmanlık** |
| `izin` | 0=Seçiniz, 1=İzinli (full-text permitted), 2=İzinsiz (restricted) |
| `Durum` | 3=Onaylandı (default), 1=Hazırlanıyor, 0=Tümü |
| `Dil` | 1=Türkçe, 2=İngilizce, 3=Arapça, … (non-contiguous: 1–21, 26–37, 39, 41–46) |
| `nevi` (islem=4) | 1=Tez Adı, 2=Yazar, 3=Danışman, 4=Konu, 5=Anahtar Kelime, 6=Özet, 7=Tümü |
| `tip` (islem=4) | 1=exact, 2=contains |

## 4. Result card (`tezSorguSonucYeni.jsp`)
- Each result: `<div class="result-card" data-index="N" data-kayitno="..." data-tezno="...">`.
- **Opaque keys** (both needed for detail/PDF AJAX): `data-kayitno` (e.g. `WenFEepJgOInK8Rs_AekDQ`), `data-tezno` (e.g. `LMwGw7OVrLZmxj8ZiPn0BQ`) — base64url-ish encrypted tokens.
- Visible human **Tez No** (e.g. `1009908`) in `.card-info` `<strong>Tez No:</strong>` — distinct from the keys.
- `.card-title` = TR title; italic `.card-info` = EN title.
- Card does NOT inline author/advisor/university/year. Those come from an embedded JS object on the page: `referenceData = { "<data-index>": { "meta": {author, year, subject, type, lang, yer, title} } }` (`yer` truncated, e.g. `"FIRAT ÜNİVERSİTESİ / "`). Full advisor/institute/ABD/abstract come from the detail AJAX.
- **2000-cap (CONFIRMED, parseable):** `<div class="result-count-text">Arama sonucunda 2.059 kayıt bulundu. 2.000 tanesi görüntülenmektedir.</div>`. Exactly 2000 cards render when total > cap. Parse both numbers → `total_found` vs `shown` → `coverage_complete = (shown >= total_found)`.

## 5. Detail = AJAX (no `tezDetay.jsp?id=&no=`)
- **`tezBilgiDetay.jsp?kayitNo={data-kayitno}&tezNo={data-tezno}`** → **JSON** (served as text/html). Keys: `danisman`, `yer` (full `ÜNİVERSİTE / ENSTİTÜ / ANABİLİM DALI / Bilim Dalı`), `trOzet`, `enOzet`, `anahtarKelimeTr`, `anahtarKelimeEn`, plus pre-rendered citations `apa_ref`, `ieee_ref`, `mla_ref`, `chicago_ref`, `harvard_ref` (HTML). Author/year/title live inside the citation strings + page `referenceData.meta`.
- **`getTezPdf.jsp?kayitNo=...&tezNo=...`** → small HTML fragment carrying access state (§6).

## 6. Access model (izinli vs izinsiz) — from `getTezPdf.jsp` fragment
- **İzinli (open):** `<div class='pdf-container'><a href='TezGoster?key={ENCRYPTED}' target='_blank'><img src='image/pdfizinli.png'></a></div>`. The `TezGoster?key=` token is a THIRD distinct encrypted key. (Never fetched a PDF.)
- **İzinsiz (restricted):** `<div class='pdf-container'><span class='pdf-info-icon'>...<span class='pdf-info-msg'>Bu tezin, veri tabanı üzerinden yayınlanma izni bulunmamaktadır. Yayınlanma izni olmayan tezlerin basılı kopyalarına Üniversite kütüphaneniz aracılığıyla (TÜBESS üzerinden) erişebilirsiniz.</span></span></div>`. No `TezGoster`, no `pdfizinli.png`.
- Detection: izinli ⇔ `TezGoster?key=` / `pdfizinli.png` present; izinsiz ⇔ `pdf-info-msg` present.
- Restricted theses still expose full metadata + citations via `tezBilgiDetay.jsp` (only abstracts may be empty for old theses) → never fabricate; surface reason text + metadata.

## 7. Key stability — STABLE across sessions
`data-kayitno`/`data-tezno` resolve correctly from a fresh JSESSIONID → safe as cache keys and resource URIs. (`TezGoster?key=` stability untested — irrelevant, we never fetch PDFs.)

## 8. Facets
- **`tarama.jsp?ajax=getAllABD&ensGrubu=`** → 2.7MB HTML, **5,132** `<label class="option-item"><input ad="{ABD NAME}" kod="{NUMERIC}" ...></label>`. ABD `kod` = plain numeric (e.g. `ABAZA DİLİ VE EDEBİYATI ANABİLİM DALI` → `2821`).
- **`getUniversities.jsp?type=TR`** (and `type=INT`) → JSON array `{"kod","displayName","yoksisId"}`, **260** entries. University `kod` = ENCRYPTED token (e.g. `nt_f9P4THOQeT0AlevbLKw`) + separate `yoksisId` token. (List includes non-universities like `ADALET BAKANLIĞI`.)
- Other facet endpoints in form JS (unprobed): `?ajax=getAllEnstitu`, `?ajax=getEnstitu&uniKod=...`, `?ajax=getABD&uniKod=...&ensKod=...&ensGrubu=...`.

## Corrections to PLAN.md assumptions
1. Result page is `tezSorguSonucYeni.jsp`, not a SearchTez re-render.
2. `tezDetay.jsp?id=&no=` is obsolete → `tezBilgiDetay.jsp?kayitNo=&tezNo=` (JSON) + `getTezPdf.jsp?kayitNo=&tezNo=` (HTML).
3. Tıpta Uzmanlık = `Tur` 3; ladder has 7 types.
4. `nevi=5` = "Anahtar Kelime" (not "Dizin"); `tip` is a match-mode, not thesis type.
5. Filters (Tur/izin/Durum/Dil/year/ABD/Universite) only work on advanced form (islem=2), whose POST shape is **not yet cracked**.
6. Citations are pre-rendered server-side (apa/ieee/mla/chicago/harvard) — cross-check for our own builder.
7. Keys stable across sessions.
8. University `kod` encrypted; ABD `kod` numeric — heterogeneous facet key types.

## Fixtures in this directory
- `tarama.html` — bootstrap page: both forms, enum dropdowns, facet JS.
- `search_keyword_islem4.html` — working islem=4 "yapay zeka" search: cards, `referenceData`, 2000-cap msg, JS.
- `search_ataturk.html` — second working search (source of old/izinsiz examples).
- `tezBilgiDetay.json` — izinli thesis detail JSON (all keys + 5 citations).
- `tezBilgiDetay_izinsiz.json` — restricted thesis detail JSON (metadata + citations; abstracts empty).
- `getTezPdf_card0.html` — izinli access fragment (TezGoster + pdfizinli.png).
- `getTezPdf_izinsiz.html` — izinsiz access fragment (restriction-reason markup).
- `getAllABD.html` — 5,132 ABD entries (ad + numeric kod).
- `getUniversities_TR.html` — 260 universities JSON (encrypted kod + yoksisId).
- `error_gecersiz_sorgulama.html` — islem=4 + filters → "Geçersiz sorgulama".
- `error_hata_olustu.html` — islem=2 attempt → "Hata Oluştu".
