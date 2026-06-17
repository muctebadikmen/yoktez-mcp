# Probe fixtures — live YÖKTEZ evidence (Faz 5)

Saved from polite, read-only live probes of `tez.yok.gov.tr` during Faz 5 root-cause work.
Multi-MB responses were **not** committed (repo hygiene); these are small representative slices.
Every file parses with `yoktez_mcp.search.parse_results` and reproduces the documented count.

| Fixture | Query / POST | Demonstrates |
|---|---|---|
| `t1a_advisor_contains_TitleCase.html` | advisor (nevi=3) "Veysel Bozkurt" | advisor search works → **58** hits |
| `t1b_advisor_contains_UPPER.html` | advisor "VEYSEL BOZKURT" | case-insensitive (== t1a, 58) |
| `t1e_advisor_exact.html` | advisor exact (tip=1) "Veysel Bozkurt" | exact match also 58 |
| `t1d_advisor_contains_surnamefirst.html` | advisor "Bozkurt, Veysel" | surname-first form → **0** (the bug) |
| `t1f_all_contains.html` | nevi=7 "Veysel Bozkurt" | cross-field "Tümü" → 60 |
| `t2_all_yapayzeka_hukuk.html` | single `keyword` "yapay zeka hukuk" | phrase match → only **2** |
| `t2_all_yapayzeka_ceza.html` | single `keyword` "yapay zeka ceza" | phrase → 1 |
| `t2_all_yapayzeka_ceza_hukuku.html` | single `keyword`, 4 words | phrase → **0** (the bug) |
| `t2_all_split_and_slots.html` | 3-slot AND, 3 distinct terms | genuinely empty intersection → 0 |
| `t2b_slot_yz_AND_hukuk.html` | keyword="yapay zeka" + keyword1="hukuk", ops_field=and | **the fix**: real AND → **16** |
| `t2b_slot_yz_AND_cezahukuku.html` | keyword="yapay zeka" + keyword1="ceza hukuku" | 2 |
| `t2b_slot_yz_AND_ceza_AND_hukuk.html` | 3-term AND | 0 |
| `t2c_slot1empty_slot2hukuk.html` | keyword2-only AND (keyword1 empty) | empty slots skipped → 16 |
| `t3_all_yapayzeka_tip.html` | nevi=7 "yapay zeka tıp" | relevance drift: 3 hits, card 3 off-topic |
| `t4c_islem2_advisor_DanismanAdSoyad.html` | **islem=2** DanismanAdSoyad filter | islem=2 works + parses identically → 58 |
| `t4c_islem2_author_AdSoyad.html` | **islem=2** AdSoyad filter | islem=2 author filter → 1 |
