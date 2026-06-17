# YÖKTEZ MCP — Master Plan

> YÖK Ulusal Tez Merkezi (tez.yok.gov.tr) için üst düzey kaliteli bir Model Context Protocol sunucusu.
> Tasarım felsefesi: **DergiPark MCP'nin kanıtlanmış mimarisini devral, YÖKTEZ'in farklı gerçekliğine göre uyarla.**

---

## 0. Yönetici Özeti

DergiPark MCP'nin gücü üç şeyden gelir: (1) anahtarsız/ücretsiz resmî veri kaynağı (OAI-PMH), (2) Türkçe-duyarlı yerel FTS5 indeksi + bake'lenmiş seed index ile anında çapraz arama, (3) dürüstlük (reliability/permission bayrakları, kapsam bildirimi, prompt-injection sarmalama).

YÖKTEZ'in gerçekliği farklı:
- **Resmî API / OAI-PMH YOK.** Tek erişim, JSP/servlet HTML arayüzünü scrape etmek.
- **2000 sonuç/sorgu sunucu kapaması** — canlı arama doğası gereği eksik ve yavaş.
- **Session (JSESSIONID) zorunlu**, `POST SearchTez` formu, `izin=1/2` permission modeli.
- **CAPTCHA yok, ViewState yok, robots.txt yok** — ama site kırılgan, nazik davranılmalı.
- **Tezlerin önemli kısmı erişime kapalı** (yazar izni yok) — PDF indirilemez.

**Stratejik sonuç:** DergiPark'ın *seed index* fikri YÖKTEZ'de **lüks değil, zorunluluk** olur. Önceden hasat edilmiş Türkçe-duyarlı FTS5 indeksi, YÖKTEZ'in en büyük üç zayıflığını (2000 limiti, yavaşlık, kırılganlık) tek hamlede çözer. Bu bizim **kalemiz (moat)**: rakipler (saidsurucu/yoktez-mcp) her sorguda canlı scrape ederken, biz sıcak bir indeksten anında çapraz-tez araması veririz; havuzda olmayanı canlı tamamlarız.

**Karar (kullanıcı onaylı):** Hibrit (seed index + canlı fallback). Sıfırdan, DergiPark modüllerini yeniden kullanarak. saidsurucu yoluna bağlı değiliz.

---

## 1. DergiPark MCP'den Devralınan Mimari (ne, neden)

| Modül | DergiPark'taki rolü | YÖKTEZ'de durumu |
|---|---|---|
| `http.py` | Paylaşılan async httpx client, 1 req/s throttle, semaphore=1, 429/5xx üstel backoff, kendini tanıtan User-Agent | **Neredeyse aynen devralınır.** + cookie jar / session yönetimi eklenir (JSESSIONID). |
| `cache.py` | Bellek (LRU+TTL) + opsiyonel disk (SQLite, platformdirs) | **Aynen devralınır.** Tez detayları 24h, arama sonuçları kısa TTL. |
| `index.py` | SQLite FTS5, `tr_fold()` Türkçe katlama, BM25 + phrase/recency bonusları, seed index yükleme | **Devralınır, şema tez alanlarına genişletilir** (danışman, üniversite, tez türü, ABD eklenir). |
| `citations.py` | 8 atıf formatı, yapısal yazar | **Devralınır, TEZ atıf kurallarına uyarlanır** (tez atıfı makaleden farklı — bkz. §6). |
| `pdf.py` | pypdf, bölüm haritası, `text_reliable` bayrağı (OCR yok, dürüst) | **Aynen devralınır.** Tez bölüm sözlüğü (ÖZET/ABSTRACT/GİRİŞ/YÖNTEM/BULGULAR/TARTIŞMA/SONUÇ/KAYNAKÇA/EKLER). |
| `prompts.py` | 4 araştırma iş akışı | **Devralınır, tez iş akışlarına uyarlanır** (literatür taraması, danışman/üniversite keşfi). |
| `server.py` | FastMCP, `@mcp.tool(annotations=READONLY)`, EXTERNAL CONTENT sarmalama, source_notice | **Devralınır, yeni tool seti.** |
| `directory.py` | ~2550 dergi dizini + konu | **Karşılığı:** üniversite + enstitü + anabilim dalı (ABD) dizini (`tarama.jsp?ajax=getAllABD` ~2500 ABD). |

**Yeni / DergiPark'tan farklı modüller:**
- `search.py` (oai.py'nin yerine) — `GET tarama.jsp` → session → `POST SearchTez` (form-urlencoded) → 302 takip → sonuç kartı parse. İki mod: anahtar-kelime (`islem=4`) ve gelişmiş (`islem=2`).
- `detail.py` (site.py'nin yerine) — `tezDetay.jsp?id=&no=` parse; `tezBilgiDetay.jsp` (PDF'siz hafif künye) parse.
- `facets.py` — ABD/üniversite/enstitü kod sözlükleri + enum kodları (Tür/İzin/Dil/Durum).

---

## 2. YÖKTEZ Teknik Gerçekliği (doğrulanmış)

- **Stack:** Java/JSP, Apache Tomcat 9.0.118. Base: `https://tez.yok.gov.tr/UlusalTezMerkezi/`
- **Akış:** `GET tarama.jsp` (JSESSIONID cookie) → `POST SearchTez` (`application/x-www-form-urlencoded`, `Referer: tarama.jsp`, `Origin` header) → genelde 302 → sonuç sayfası GET.
- **Sonuç kartı:** `data-kayitno` / `data-tezno` / `data-index` attribute'ları → `id` (opak/şifreli key) + `no` (şifreli tez no).
- **Detay:** `GET tezDetay.jsp?id={key}&no={enc_no}`.
- **Hafif künye:** `tezBilgiDetay.jsp` (PDF indirmeden künye + hazır atıflar).
- **PDF:** `TezGoster?key=...` linki varsa erişilebilir (`is_pdf_permissible=True`); yoksa gerekçe metni parse edilir.
- **Enum kodları:** `Tur` (1=YL, 2=Doktora, 4=Sanatta Yeterlik; Tıpta Uzmanlık kodu **canlı formdan doğrulanacak**), `izin` (1=İzinli, 2=İzinsiz), `Durum` (3=Onaylandı, 1=Hazırlanıyor, 0=Tümü), `Dil` (1=TR, 2=EN…), `nevi` (aranacak alan: 1=Tez adı, 2=Yazar, 3=Danışman, 4=Konu, 5=Dizin, 6=Özet, 7=Tümü).
- **Kritik kural:** Boş `Enstitu`/`yil1`/`yil2` → `"0"` gönderilmeli, yoksa "Geçersiz sorgulama".
- **2000 sonuç/sorgu sunucu kapaması** — toplu hasat için yıl/ABD bazında bölerek sorgulama gerekir.
- **robots.txt yok** (404) — ama "yok" ≠ "serbest"; nazik davranış (throttle, session reuse) şart.

---

## 3. Rakip Ekosistem ve Bizim Farkımız (Moat)

| | **Bizim YÖKTEZ MCP** | saidsurucu/yoktez-mcp | tezara.org | mytunca/theses |
|---|---|---|---|---|
| Yaklaşım | **Hibrit: seed index + canlı** | Her sorguda canlı scrape | Önceden kazınmış DB (web app) | Tarayıcı bookmarklet (manuel) |
| Çapraz-tez anlık arama | ✅ Sıcak FTS5 indeks | ⚠️ Canlı, 2000 limitli, yavaş | ✅ (ama MCP değil) | ❌ |
| Türkçe-duyarlı arama | ✅ `tr_fold` + BM25 bonuslar | ⚠️ Sunucu aramasına bağlı | — | ❌ |
| 2000 limiti aşımı | ✅ Indekste yok | ❌ | ✅ | ✅ |
| Danışman/üniversite genealojisi | ✅ Birinci-sınıf keşif ekseni | Kısmî | Kısmî | ❌ |
| Atıf formatları (tez-doğru) | ✅ 8 format, tez kuralları | 5 format | ❌ | ❌ |
| Dürüstlük (reliability/permission/kapsam) | ✅ Açık bayraklar | Kısmî | — | ❌ |
| Prompt-injection koruması | ✅ EXTERNAL CONTENT | Belirsiz | — | ❌ |
| MCP standardı | ✅ FastMCP, stdio+HTTP | ✅ | ❌ (web) | ❌ |

**Tek cümlelik kale:** *"Herkes canlı scrape ederken biz sıcak, Türkçe-duyarlı bir tez indeksinden anında çapraz arama veriyoruz; danışman/üniversite eksenli akademik keşif sunuyoruz; ve neyin eksik/kapalı/güvenilmez olduğunu dürüstçe söylüyoruz."*

---

## 4. Mimari Diyagram

```
İstemci (Claude)  ──MCP──>  server.py (araçlar + prompt'lar + kaynaklar)
   • Hosted: HF Spaces (HTTP, /mcp)
   • Yerel:  uvx / .mcpb (stdio)
                               │
   ┌───────────┬──────────────┼───────────────┬──────────────┬────────────┐
   ▼           ▼              ▼               ▼              ▼            ▼
search.py    detail.py      pdf.py          index.py      facets.py   citations.py
(SearchTez   (tezDetay/     (PDF→md +       (FTS5 +       (ABD/üni/    (8 atıf,
 POST akışı, tezBilgiDetay  bölüm +         Türkçe fold + enstitü +    TEZ kuralları)
 session,    parse,         text_reliable)  BM25 + seed)  enum kodları)
 2000 cap,   permission                       │
 kart parse) tespiti)                          ▼
   │             │              cache.py (bellek+disk) · http.py (throttle, session, 429 backoff)
   └─────────────┴──────────────────────────────────────────────────────────
                               │
                     data/seed_index.db.gz  (önceden hasat: çok-üniversiteli/çok-alanlı tez havuzu)
```

---

## 5. Tool Seti (taslak)

DergiPark'ın 10 tool'unu tez dünyasına uyarlıyoruz; danışman/üniversite eksenini birinci sınıf yapıyoruz.

| Araç | Açıklama | Veri yolu |
|---|---|---|
| `search_theses` | Türkçe-duyarlı anahtar kelime araması. Filtre: tür (YL/Doktora/…), yıl, üniversite, ABD, dil, izin durumu. Sıralama: ilgi/yeni/eski. | Önce **seed index (FTS5)**; havuzda yetersizse **canlı `SearchTez`** ile tamamla + indekse ekle. Kapsam dürüstçe bildirilir. |
| `get_thesis` | Zengin künye: başlık (TR/EN), yazar, **danışman**, üniversite/enstitü/ABD, tür, yıl, sayfa, dil, konu, dizin terimleri, özet (TR/EN), izin durumu + **8 atıf formatı**. | `tezBilgiDetay.jsp` (PDF'siz, ucuz) + `tezDetay.jsp` zenginleştirme. |
| `get_thesis_fulltext` | İzinliyse PDF→Markdown; bölüm haritası (ÖZET/GİRİŞ/YÖNTEM/…/KAYNAKÇA), sayfa-sayfa. Taranmış/bozuk → `text_reliable=false`. İzinsizse net `permission` mesajı. | `TezGoster?key=` → `pdf.py`. |
| `find_advisor_theses` | **Danışman bazlı keşif** — bir danışmanın yönettiği tüm tezler (akademik soyağacı / ekol). Ad-sırası toleranslı. | Seed index (`advisor` alanı) + canlı `nevi=3`. |
| `find_author_theses` | Bir yazarın tezleri (genelde 1-2 tez ama tarama için). | Index + canlı `nevi=2`. |
| `list_university_theses` | Bir üniversite/enstitü/ABD'nin tezleri (fakülte üretim haritası), tür/yıl filtreli. | Gelişmiş arama `islem=2` + index. |
| `related_theses` | Verilen teze benzer tezler (konu/dizin/başlık örtüşmesi). | Index benzerlik. |
| `list_facets` | Üniversite / enstitü / anabilim dalı sözlüğü + arama enum'ları (geçerli filtre değerlerini keşfetmek için). | `facets.py` (+ `getAllABD`). |
| `get_thesis_references` | Tezin kaynakçası (PDF'ten/KAYNAKÇA bölümünden çıkarım). | `pdf.py` bölüm haritası. |
| `search_advanced` *(ops.)* | Gelişmiş çok-alanlı sorgu (üni + ABD + konu + danışman + yıl) — güç kullanıcılar için ham `islem=2` erişimi. | Canlı `SearchTez`. |

**Prompt'lar (4):** `tez_literatur_taramasi` · `tez_ozeti` · `danisman_ekol_analizi` (bir danışmanın öğrenci/konu ağı) · `universite_uretim_haritasi`.

**Kaynaklar (Resources):** `yoktez://thesis/{id}` · `yoktez://advisor/{name}` · `yoktez://university/{slug}`.

---

## 6. YÖKTEZ'e Özgü Tasarım Kararları (DergiPark'tan ayrışan yerler)

1. **Tez atıf formatları ≠ makale atıfları.** APA 7: `Yazar, A. (Yıl). *Tez başlığı* [Yüksek lisans tezi/Doktora tezi, Üniversite Adı]. YÖK Ulusal Tez Merkezi.` Her formatın (MLA, IEEE, Chicago, Harvard, BibTeX `@phdthesis`/`@mastersthesis`, RIS `TY - THES`, CSL-JSON `"type":"thesis"`) tez varyantı uygulanmalı. `citations.py` genişletilir.

2. **Danışman birinci sınıf vatandaş.** Makalelerde olmayan, tezlerde kritik bir keşif ekseni: akademik soyağacı, ekol takibi, "X hocanın doktora öğrencileri". Indeks şemasına `advisor` kolonu + ona özel tool/prompt.

3. **İzin/erişim modeli dürüstçe yüzeye çıkar.** Her tezde `access_status` ∈ {açık, izinsiz, süreli-kısıt, yalnız-basılı}. `get_thesis_fulltext` izinsizde uydurma yapmaz; YÖK'ün gerekçe metnini olduğu gibi döndürür (DergiPark'ın `text_reliable` dürüstlüğünün tez karşılığı).

4. **2000-cap'i seed index ile aş, canlıda dürüstçe bildir.** Canlı sorgu cap'e takılırsa `coverage_complete=false` + "YÖK 2000 sonuç sınırı; daraltın (yıl/ABD)" notu.

5. **Seed index hasat stratejisi.** `scripts/build_index.py`: tür × yıl × üniversite/ABD bazında bölerek 2000-cap altında kalan dilimlerle geniş, çok-alanlı bir metadata havuzu topla (başlık TR/EN + özet + danışman + üni + ABD + dizin terimleri). Sadece **metadata** (PDF değil) → küçük, hızlı, yasal olarak en güvenli (künye/özet açık erişim). gzip'le paketle.

6. **Session dayanıklılığı.** `http.py`'ye JSESSIONID yaşam döngüsü: ilk istekte `GET tarama.jsp`, cookie eskirse otomatik yenile, 302 takibi, `Referer/Origin` header'ları.

---

## 7. Dürüstlük, Etik, Güvenlik (DergiPark ilkeleri devam)

- **Prompt-injection:** Tez özeti/tam metni/kaynakçası dış içerik → `[EXTERNAL CONTENT]…[/EXTERNAL CONTENT]` sarmalama + `source_notice`.
- **Nazik kullanım:** throttle (≥1 req/s), concurrency=1, 429/5xx backoff, kendini tanıtan UA, session reuse. Site kırılgan; toplu hasat saygılı dilimlerle.
- **Yasal:** Metadata (künye/başlık/özet) açık erişim. Tam metin yalnızca yazarın izinli işaretlediği tezler için ve son-kullanıcı anlık getirimi; izinsiz tezlerin PDF'i hiç indirilmez. İzin durumu her yanıtta açık.
- **Kapsam dürüstlüğü:** `search_theses`/`find_advisor_theses` her zaman "kaç tez / hangi üniversiteler indekste, ne kadarı canlı" bildirir.

---

## 8. Test Stratejisi (DergiPark deseni)

- **Offline (ağsız, hızlı):** FTS5 normalizasyon/Türkçe fold, BM25 sıralama, tez atıf formatları, PDF bölüm/reliability, fixture HTML parse (kaydedilmiş `tezDetay.jsp`/`SearchTez` örnekleri), facet parse.
- **Live (`@pytest.mark.live`):** Gerçek YÖKTEZ akışı — session kurma, SearchTez POST, detay parse, izinli/izinsiz PDF ayrımı. Nazik, yavaş.
- **conftest:** paylaşılan async state reset (httpx/cache/lock), arka-plan yenileme kapalı.
- Fixture'lar: izinli tez, izinsiz tez, çok-yazarlı, taranmış-PDF, 2000-cap'e takılan sorgu.

---

## 9. Paketleme & Dağıtım (DergiPark deseni)

- `pyproject.toml`: `fastmcp`, `httpx`, `beautifulsoup4`/`lxml`, `pypdf`, `platformdirs`. İki entrypoint: `yoktez-mcp` (stdio), `yoktez-mcp-serve` (HTTP).
- Gömülü veri: `data/seed_index.db.gz` + `data/facets.json` (force-include).
- Dağıtım: (1) **Hosted URL** (HF Spaces, HTTP `/mcp`) — kurulum yok, önerilen; (2) `uvx --from git+…`; (3) `.mcpb` sürükle-bırak.
- İki dilli README (TR + EN), DergiPark formatında: moat tablosu, slug/ID kavramı, örnek doğal-dil kullanımları, dürüst sınırlamalar.

---

## 10. Fazlı Yol Haritası

**Faz 0 — Keşif/doğrulama (canlı problar):** SearchTez form alanlarını, enum kodlarını (özellikle Tıpta Uzmanlık), 302 akışını, `tezDetay`/`tezBilgiDetay` HTML yapısını, izinli/izinsiz PDF farkını gerçek isteklerle doğrula. Fixture'ları kaydet.

**Faz 1 — Çekirdek scraping + parse:** `http.py` (session'lı), `search.py`, `detail.py`, `facets.py`. `search_theses` (canlı) + `get_thesis` çalışır.

**Faz 2 — İndeks + Türkçe arama:** `index.py` tez şemasıyla, `tr_fold`, BM25 bonusları. Canlı sonuçları indekse yaz, indeksten oku.

**Faz 3 — PDF + atıflar:** `pdf.py` (bölüm/reliability), `citations.py` tez kuralları (8 format). `get_thesis_fulltext`, `get_thesis_references`.

**Faz 4 — Keşif eksenleri:** `find_advisor_theses`, `find_author_theses`, `list_university_theses`, `related_theses`, prompt'lar, resources.

**Faz 5 — Seed index hasadı:** `scripts/build_index.py` (tür×yıl×ABD dilimleme, 2000-cap altı), gzip paket. Çapraz-tez araması sıcak başlar.

**Faz 6 — Sertleştirme + dağıtım:** prompt-injection sarmalama, kapsam bildirimi, test suite (offline+live), README (TR/EN), HF Spaces + uvx + .mcpb, CI.

---

## 11. Açık Riskler / Doğrulanacaklar

- **Tıpta Uzmanlık `Tur` kodu** — referans implementasyonda eksik; canlı formdan doğrula.
- **Site kırılganlığı** — JSP arayüzü değişirse parse bozulur; seed index bu riski azaltır (en azından indeksli kapsam çalışmaya devam eder).
- **Rate limit/engelleme** — YÖK'ün toleransı ölçülmeli; hasat dilimlemesi nazik olmalı.
- **`id`/`no` şifreli anahtarlar** — kalıcı mı yoksa session'a mı bağlı? (Resource URI ve cache key tasarımını etkiler.) Faz 0'da doğrula.
- **Yasal sınır** — metadata serbest; tam metin yalnız izinli + anlık getirim ilkesine sıkı uy.

---

*Sonraki adım: Faz 0 canlı doğrulama probları — onay verirsen gerçek YÖKTEZ isteklerini atıp form alanlarını ve HTML yapısını netleştirir, fixture'ları kaydederim. Ardından Faz 1 iskeletini kurarız.*
