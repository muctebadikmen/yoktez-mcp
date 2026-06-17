# YÖKTEZ MCP

🇹🇷 Türkçe (bu dosya) · 🇬🇧 [English](README.en.md)

[YÖK Ulusal Tez Merkezi](https://tez.yok.gov.tr) (Türkiye'nin ulusal tez merkezi) için bir **Model Context Protocol (MCP)** sunucusu. Claude (Desktop / claude.ai / mobil) ve diğer MCP istemcilerinin yüksek lisans, doktora, tıpta uzmanlık ve sanatta yeterlik tezlerini **Türkçe-duyarlı** olarak aramasını, **danışman ve üniversite** ekseninde keşfetmesini, izinli tezlerin tam metnini okumasını ve **tez-doğru künye + 8 atıf formatı** üretmesini sağlar.

> ⚡ **En kolay kullanım: kurulum yok.** Aşağıdaki tek bir URL'yi Claude'a yapıştırın — uygulama, config, Python, hiçbiri gerekmez. [→ Hemen başla](#-en-hızlı-kurulum-urlyi-yapıştır-önerilen)

---

## 🚀 En hızlı kurulum: URL'yi yapıştır (önerilen)

Bu MCP **çevrimiçi bir sunucu** olarak yayında (Hugging Face Spaces, ücretsiz). Hiçbir şey indirmeden, **tek bir URL** ile birkaç tıkta eklenir — **Claude Desktop, claude.ai (tarayıcı) ve mobil** uygulamada çalışır.

**1) Şu URL'yi kopyala:**

```
https://muctebadikmen-yoktez-mcp.hf.space/mcp
```

**2) Claude'da bağla:** **Settings → Connectors → Add custom connector** → URL'yi yapıştır → **Add**.

> ⚠️ Bağlarken HF Space'in **sayfa adresini** (`huggingface.co/spaces/...`) değil, yukarıdaki **`...hf.space/mcp`** ile biten **endpoint** adresini yapıştırın. Space sayfasındaki "Connect" kartı kökü yokladığı için "connection issue" gösterebilir; bu kozmetiktir, gerçek endpoint `/mcp`'dir.

**3) Test et:** Claude'a şunu yaz:
> *"YÖKTEZ'de yapay zeka destekli eğitim üzerine tezleri ara."*

Bu kadar. Config dosyası yok, `uv`/Python kurulumu yok, sürükle-bırak yok.

> ℹ️ **Dürüst not:** Ücretsiz sunucu uzun süre hiç kullanılmazsa uykuya geçer; ilk istekte **~30–60 sn** uyanır, sonra hızlıdır. Açık ve anahtarsızdır — URL'yi bilen herkes kullanabilir (akademik açık araç).

<details>
<summary>🖥️ Kendi bilgisayarında <b>yerel</b> çalıştırmak istersen (gelişmiş / opsiyonel)</summary>

URL yöntemi çoğu kişi için yeterlidir. Ama sunucuyu **kendi makinende** çalıştırmak istersen (gizlilik, çevrimdışı önbellek, hosted sunucuya bağımlı olmamak) `uv` (Python yöneticisi) ile iki yol var.

### a) Tek-satır `uvx` (yerel, önerilen yerel yöntem)

**1) `uv`'yi kur:**
- macOS / Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Windows (PowerShell): `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"` (sonra terminali yeniden aç)

**2) Claude Desktop → Settings → Developer → Edit Config** (`claude_desktop_config.json`) açılır.

**3) Şu bloğu ekle:**
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

**4) Kaydet, Claude Desktop'ı tamamen kapat-aç** (Mac'te **Cmd+Q**).

- *"uvx bulunamadı":* tam yolu yaz — Mac/Linux `which uvx`, Windows `where uvx`.
- *Güncelleme:* `uvx --refresh --from git+https://github.com/muctebadikmen/yoktez-mcp yoktez-mcp`

### b) Claude Code (CLI)
```bash
claude mcp add --transport http yoktez https://muctebadikmen-yoktez-mcp.hf.space/mcp   # hosted URL
# veya yerel:
claude mcp add yoktez -- uvx --from git+https://github.com/muctebadikmen/yoktez-mcp yoktez-mcp
```
</details>

---

## ⭐ Neden bu MCP?

YÖKTEZ'in **resmî API'si, OAI-PMH'si veya açık arama servisi yoktur** — tek erişim yolu JSP/servlet arayüzünü nazikçe kazımaktır. Mevcut alternatifler ya her sorguda canlı kazır (yavaş, YÖK'ün **2000 sonuç/sorgu** sınırına takılır), ya bir web uygulamasıdır (MCP değil), ya da manuel tarayıcı eklentisidir.

Bu proje farkını **mühendislik kalitesi ve dürüstlükten** alır:

| | **Bu proje** | Canlı-kazıma rakipler | tezara.org | Bookmarklet |
|---|---|---|---|---|
| **MCP standardı** | ✅ FastMCP (stdio + HTTP + hosted) | ✅ | ❌ (web) | ❌ |
| **Türkçe-duyarlı arama** | ✅ `İ/ı/ş/ğ/ü/ö/ç` katlama + BM25 | ⚠️ sunucuya bağlı | — | ❌ |
| **Danışman ekseni** (akademik soyağacı) | ✅ Birinci sınıf keşif | kısmî | kısmî | ❌ |
| **Tez-doğru atıf** | ✅ 8 format (`@phdthesis`/`@mastersthesis`) | birkaç | ❌ | ❌ |
| **Dürüstlük** (kapsam / erişim / güvenilirlik) | ✅ Açık bayraklar | kısmî | — | ❌ |
| **Prompt-injection koruması** | ✅ `[EXTERNAL CONTENT]` | belirsiz | — | ❌ |
| **Anahtarsız / ücretsiz** | ✅ | değişir | ✅ | ✅ |
| **Sıcak çapraz-tez indeksi** | 🛠️ Mimari hazır — *hasat yol haritasında* | ❌ | ✅ (web) | ❌ |

> **Tasarım ilkesi:** Site kırılgan ve resmî API yok — bu yüzden **iyi vatandaş** olunur (tek oturum, ≥1 istek/sn, 429 backoff, kendini tanıtan `User-Agent`) ve **dürüstlük** her yanıta işlenir: neyin canlı, neyin eksik, neyin erişime kapalı, neyin güvenilmez olduğu açıkça söylenir.

---

## Ne yapar?

### 🔧 Araçlar (9)

| Araç | Açıklama |
|---|---|
| `search_theses` | **Türkçe-duyarlı tez araması.** Alan (tez adı / yazar / danışman / konu / anahtar kelime / özet / tümü), tür, yıl, üniversite, bölüm, dil ve erişim filtreleri. Sonuçlarda **kapsam dürüstçe** bildirilir (YÖK'ün 2000-sonuç sınırı → `coverage_complete=false`). |
| `get_thesis` | **Zengin künye:** başlık (TR/EN), yazar, **danışman**, üniversite / enstitü / anabilim dalı / bilim dalı, tür, yıl, dil, özet (TR/EN), anahtar kelimeler, **erişim durumu** + **8 atıf formatı**. |
| `get_thesis_fulltext` | İzinliyse PDF'i indirip Markdown'a çevirir; **bölüm haritası** (ÖZET/GİRİŞ/YÖNTEM/BULGULAR/…/KAYNAKÇA). Taranmış/bozuk-font → dürüstçe `text_reliable=false`. **İzinsizse** YÖK'ün gerçek izin/gerekçe metnini döndürür — asla uydurma yapmaz. |
| `find_advisor_theses` | **Danışman bazlı keşif** — bir danışmanın yönettiği tezler (akademik soyağacı / ekol analizi). Ad-sırasından bağımsız. |
| `find_author_theses` | Bir yazarın tez(ler)i. |
| `list_university_theses` | Bir üniversitenin tez üretim haritası (tür/yıl filtreli). |
| `related_theses` | Verilen bir teze **benzer** tezler (konu/anahtar kelime/başlık örtüşmesi). |
| `list_facets` | **Geçerli filtre değerleri:** ~5.100 anabilim dalı + 260 üniversite sözlüğü ve enum kodları (tür, izin, durum, dil, arama alanı). |
| `get_thesis_references` | İzinli tezin kaynakçası (PDF'in KAYNAKÇA bölümünden). |

### 💬 Prompt'lar (4) — hazır araştırma iş akışları

`tez_literatur_taramasi` · `tez_ozeti` · `danisman_ekol_analizi` · `universite_uretim_haritasi`. Claude Desktop'ta "/" menüsünde görünür.

### 📦 Kaynaklar (Resources, 3)

`yoktez://thesis/{kayit_no}/{tez_no}` · `yoktez://advisor/{name}` · `yoktez://university/{name}`

### ✨ Öne çıkan özellikler

- **Danışman birinci sınıf vatandaş:** Makalelerde olmayan, tezlerde kritik olan **akademik soyağacı** — "X hocanın doktora öğrencileri", ekol takibi — kendi aracı + prompt'u ile.
- **Türkçe-duyarlı arama:** `İ/ı/ş/ğ/ü/ö/ç` simetrik katlanır → "eğitim" ≈ "Eğitim" ≈ "egitim"; indeks ve sorgu aynı katlamayı kullanır.
- **Tez-doğru atıflar (8 format):** APA, MLA, IEEE, Chicago, Harvard, BibTeX, RIS, CSL-JSON — **tez kurallarıyla**: `[Doktora tezi, Üniversite]. YÖK Ulusal Tez Merkezi.`, BibTeX `@phdthesis`/`@mastersthesis`, RIS `TY - THES`, CSL `"type":"thesis"`.
- **Erişim modeli gerçektir:** her tezin durumu (açık / izinsiz) yüzeye çıkar; izinsiz tezin PDF'i **asla** indirilmez, içeriği **asla** uydurulmaz.
- **Dürüst kapsam:** YÖK'ün 2000-sonuç sınırına takılan aramalar `coverage_complete=false` ile işaretlenir ve daraltma önerilir.

---

## 🔑 Önemli kavramlar

### `kayit_no` + `tez_no` (tez kimliği)
Bir teze bu **iki anahtarla** erişilir. Bunlar arama sonucu kartlarından gelen **opak/şifreli** anahtarlardır (YÖK'ün dahili AJAX anahtarları) ve **oturumlar arası kalıcıdır** — bu yüzden cache anahtarı ve resource URI olarak güvenle kullanılır. Kullanıcıya görünen **"Tez No"** (ör. `1009908`) bunlardan ayrıdır; atıflarda o insan-okur numara kullanılır.

### Tez türü kodları (`Tur`)
`1` Yüksek Lisans · `2` Doktora · `3` Tıpta Uzmanlık · `4` Sanatta Yeterlik · `5` Diş Hekimliği Uzmanlık · `6` Tıpta Yan Dal Uzmanlık · `7` Eczacılıkta Uzmanlık.

### Erişim durumu
`open` (izinli — tam metin PDF mevcut) · `restricted` (izinsiz — yazar yayın izni vermemiş; YÖK'ün gerekçe metni döndürülür, PDF indirilmez).

---

## 🗣️ Örnek kullanım (Claude'a doğal dille)

- *"YÖKTEZ'de **yapay zeka destekli eğitim** üzerine tezleri bul."* → `search_theses`
- *"**Duygu Mutlu Bayraktar** danışmanlığında yapılan tezleri listele."* → `find_advisor_theses` (akademik soyağacı)
- *"**Ahmet Yılmaz**'ın YÖKTEZ'deki tezlerini getir."* → `find_author_theses`
- *"Şu tezin künyesini ve **APA + BibTeX** atfını ver."* → `get_thesis`
- *"Bu tezin **izinli tam metnini** oku, yöntem bölümünü özetle."* → `get_thesis_fulltext`
- *"Şu doktora teziyle **benzer** tezler öner."* → `related_theses`
- *"Hacettepe Üniversitesi'nin son 5 yıldaki doktora tezlerini göster."* → `list_university_theses`
- *"/danisman_ekol_analizi advisor=Prof. Dr. ..."* (prompt)

---

## ⚙️ Çevre değişkenleri (opsiyonel — yerel çalıştırma)

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `YOKTEZ_MIN_INTERVAL` | `1.0` | İstekler arası min saniye (nezaket). |
| `YOKTEZ_MAX_CONCURRENCY` | `1` | Eşzamanlı istek sayısı. |
| `YOKTEZ_MAX_RETRIES` | `4` | 429/5xx için yeniden deneme sayısı. |
| `YOKTEZ_BACKOFF_BASE` | `2.0` | Üstel backoff tabanı (saniye). |
| `YOKTEZ_TIMEOUT` | `60.0` | İstek zaman aşımı (saniye). |
| `YOKTEZ_ENABLE_DISK_CACHE` | kapalı | `1` → disk önbelleğini açar (süreçler arası kalıcı). |
| `YOKTEZ_CACHE_DIR` | platforma özgü | Önbellek + arama indeksi dizini. |

---

## ⚠️ Dürüst sınırlamalar

Bu projenin omurgası dürüstlüktür; mevcut sürümün gerçek sınırları:

- **YÖK'ün tek-sorgu sınırı 2000 sonuçtur** — tüm site taranır ama bir sorgu 2000'den fazla tezle eşleşirse yalnızca 2000'i döner ve `coverage_complete=false` dürüstçe bildirilir. **Aşmanın iki yolu:** (1) `list_university_theses(..., exhaustive=True)` — yıl-dilimleme ile bir üniversitenin TÜM tezlerini eksiksiz toplar (canlı, nazik, daha çok istek); (2) seed indeksi (önceden dilimlenmiş). **İstisna:** konu/keyword "all" araması (`islem=4`) yıl-dilimlenemez (YÖK reddediyor), bu yüzden geniş konu sorguları 2000-cap'e tabidir — alanı daraltın (başlık/üniversite) veya `exhaustive` üniversite listesini kullanın.
- **Seed indeksi seçili kapsamda hasat edilmiştir (tüm YÖKTEZ değil).** Pakete gömülü `data/seed_index.db.gz` şu an **6 büyük üniversite × Doktora × 2018–2025** dilimini içerir (~19 bin tez); bu kapsam dışındaki tezler **canlı** sorgulanır (ve indeks kullanımla ısınır). Kapsam genişletmek için `scripts/build_index.py --turler 1,2 --years 2010-2025` çalıştırılabilir (nazik, resume-edilebilir).
- **Danışman indeksi yoktur — danışman keşfi canlıdır.** Arama sonuç kartları danışman bilgisi taşımadığından seed indeksinde `advisor` alanı boştur; `find_advisor_theses` bu yüzden **canlı `nevi=3`** üzerinden çalışır (ekol/soy-ağacı analizi için birincil yol).
- **OCR yoktur.** Taranmış/bozuk-font PDF'lerde metin fiziksel olarak çıkarılamaz; ücretsiz, anahtarsız, sürtünmesiz bir OCR yolu olmadığından kapsam dışıdır. Bu belgeler **`text_reliable=false`** ile işaretlenir.
- **İzinsiz tezlerin tam metni yoktur.** Yazar yayın izni vermemişse PDF erişilemez; içerik uydurulmaz, YÖK'ün gerekçe metni döndürülür. (Basılı kopyalar üniversite kütüphaneleri üzerinden TÜBESS ile temin edilebilir.)

---

## 🔒 Güvenlik (prompt-injection)

YÖKTEZ'den gelen özet / tam metin / kaynakça **dış içeriktir**. Sunucu bu metni `[EXTERNAL CONTENT] … [/EXTERNAL CONTENT]` ile sarar ve yanıtlara bir `source_notice` ekler: bu içerik **veri** olarak değerlendirilmeli, **talimat** olarak değil.

## 🙏 Nazik kullanım (good citizen)

Site kırılgandır ve resmî API sunmaz. İstemci varsayılan olarak **eşzamanlılığı 1**, **istek aralığını ≥1 sn** tutar, 429/geçici 5xx'te **üstel backoff** uygular, **tek oturumu (JSESSIONID) yeniden kullanır** ve `User-Agent`'ta kendini tanıtır. Toplu hasat (seed indeksi) yapılırsa nazik dilimlerle yapılır; site asla hızlı/agresif kazınmaz.

## ⚖️ Yasal / etik

- **Künye/metadata** (başlık, yazar, danışman, özet) açık erişimdir ve serbestçe taranır.
- **Tam metin** yalnızca yazarın **izinli** işaretlediği tezler için ve son kullanıcı için **anlık** getirilir; izinsiz tezlerin PDF'i **hiç indirilmez.** Erişim durumu her yanıtta açıktır.
- İstemci hız-sınırlar, tek oturumu yeniden kullanır ve kendini tanıtır.

Bu yazılım "olduğu gibi" sağlanır; içeriğin kullanım sorumluluğu kullanıcıya aittir.

---

## 🧱 Mimari

```
İstemci (Claude)  ──MCP──>  server.py (9 araç + 4 prompt + 3 kaynak, EXTERNAL CONTENT sarmalama)
   • Hosted: https://muctebadikmen-yoktez-mcp.hf.space/mcp  (HTTP)
   • Yerel:  uvx  (stdio)
                               │
   ┌────────────┬──────────────┼───────────────┬──────────────┬────────────┐
   ▼            ▼             ▼               ▼              ▼            ▼
search.py     detail.py      pdf.py          index.py      facets.py   citations.py
(SearchTez    (tezBilgiDetay (PDF→md +       (FTS5 +       (~5.100 ABD  (8 atıf,
 islem=4 +     JSON +         bölüm +         Türkçe fold + + 260 üni +  TEZ kuralları)
 sonuç kartı   getTezPdf      text_reliable,  BM25 +        enum kodları)
 + 2000-cap    erişim parse)  izinsiz-PDF     seed yükleme)
 parse)            │           guard)            │
   │               │                              ▼
   └───────────────┴────────  cache.py (bellek+disk) · http.py (oturum, throttle, 429 backoff) · text.py (tr_fold)
```

Hibrit mimari: **canlı `SearchTez`** kazıma (keyword `islem=4` + filtreli `islem=2`) + **yerel FTS5 indeksi**. Pakete gömülü, gzip'li seed indeksi (`data/seed_index.db.gz`, ~19 bin tez) açılışta yüklenerek çapraz-tez aramasını **sıcak** başlatır; ayrıca her canlı aramadan dönen sonuçlar indekse yazılarak (on-demand warming) kapsam kullanımla genişler.

---

## 🧪 Geliştirme & test

```bash
uv sync
uv run pytest -m "not live" -q     # offline (hızlı): parser/index/citations/pdf/cache/facets
uv run pytest -m live -q           # canlı (gerçek YÖKTEZ trafiği — nazik, yavaş)
uvx ruff check src/ tests/         # lint
```

**Facet sözlüğünü (üniversite/ABD/enum) yenileme:**
```bash
uv run python scripts/build_facets.py     # data/facets.json'u canlı YÖKTEZ'den yeniden üretir
```

---

## 📄 Lisans

MIT — bkz. [LICENSE](LICENSE).

---

*Bu sunucu, [DergiPark MCP](https://github.com/muctebadikmen/dergipark-mcp)'nin kanıtlanmış mimarisini tez dünyasına uyarlar — ikisi tutarlı bir Türk akademik MCP ailesi oluşturur.*
