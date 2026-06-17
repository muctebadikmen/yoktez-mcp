---
title: YÖKTEZ MCP
emoji: 🎓
colorFrom: indigo
colorTo: red
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: YÖK Ulusal Tez Merkezi için MCP sunucusu (tez arama + atıf)
---

# YÖKTEZ MCP — uzak (remote) sunucu

**YÖK Ulusal Tez Merkezi** (`tez.yok.gov.tr`) için **Model Context Protocol (MCP)** sunucusu —
Türkiye'nin ulusal tez merkezini Claude ve diğer MCP istemcilerine açar: Türkçe-duyarlı
tez araması, **danışman / üniversite** ekseninde keşif, izinli tam metin okuma ve
tez-doğru atıflar (8 format).

## Bağlanma (Claude)

**MCP endpoint:**

```
https://muctebadikmen-yoktez-mcp.hf.space/mcp
```

Claude (Desktop veya claude.ai) → **Settings → Connectors → Add custom connector** →
yukarıdaki URL'yi yapıştır → **Add**. Yapılandırma dosyası gerekmez; tarayıcıda da çalışır.

## Araçlar

`search_theses` · `get_thesis` · `get_thesis_fulltext` · `find_advisor_theses` ·
`find_author_theses` · `list_university_theses` · `related_theses` · `list_facets` ·
`get_thesis_references` — ve 4 araştırma prompt'u + 3 resource.

## Dürüstlük ilkeleri

- **Kapsam dürüst bildirilir:** YÖK'ün 2000 sonuç/sorgu sınırına takılan aramalar
  `coverage_complete=false` ile işaretlenir.
- **Erişim modeli gerçektir:** izinsiz (erişime kapalı) tezler için içerik uydurulmaz;
  YÖK'ün gerçek izin/gerekçe metni döndürülür. İzinsiz PDF asla indirilmez.
- **Güvenilirlik:** taranmış/bozuk-font PDF'ler `text_reliable=false` ile işaretlenir
  (OCR yok). Tüm dış metin prompt-injection'a karşı `[EXTERNAL CONTENT]` ile sarılır.

## Notlar

- İlk istek, sunucu uykudaysa ~30–60 sn (HF ücretsiz katman) gerektirebilir.
- YÖKTEZ'e nazik davranılır: tek oturum, ≥1 istek/sn, 429 backoff.
- Kaynak kod (MIT): <https://github.com/muctebadikmen/yoktez-mcp>
