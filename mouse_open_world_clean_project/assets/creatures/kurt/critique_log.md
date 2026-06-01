# Kurt Ustası — Eleştiri Günlüğü

Hedef: `REFERENCE.png` (tam gövde fotoreal kurt). Her tur bir öncekini ağır
eleştirir, `wolf_params.json`'u düzeltir, yeniden render alır.

## Round 00 — taban (baseline)
Prosedürel tam-gövde kurt tabanı. Kasıtlı kaba; eleştiri döngüsünün hammaddesi.
- 8 parça, ~16k tri (subsurf 2).
- Bilinen sorunlar (gözle): bacaklar kısa ve sadece yakın taraf görünüyor;
  kulaklar minik; gövde fazla uzun/silindirik; kuyruk kopuk görünüyor;
  withers/topline düz; kafa formu belirsiz.
- Render: `renders/round_00_*.png`

## Round 01 — 2026-06-01
**Önceki (round 00) en büyük 3 kusur:**
1. Bacaklar çok kısa ve dar duruşlu — gövde havada yüzüyor, ön görünüşte sadece yakın bacaklar ayırt ediliyor; ayaklar yere sağlam basmıyor.
2. Gövde fazla uzun/silindirik (y=-0.58→1.01, ~1.6 boy) ve topline düz — withers (omuz) tepesi neredeyse belli değil, karın tuck zayıf.
3. Kuyruk kopuk/kırık sosis gibi görünüyor — fazla droop (0.20) + agresif bush profili rumptan ayrık ve bükük bir kütle yaratıyor.
**Uygulanan parametre değişiklikleri:**
- body_stations: y aralığı sıkıştırıldı (son istasyon 1.090→0.905, kuyruk dibi 1.010→0.905; ~%15 kısalma), gövde tubularlığı azaldı (gerekçe: kusur 2).
- body_stations withers top_z: 0.880→0.918, neck_base 0.812→0.835, chest top_z 0.815→0.850 (omuz tepesi yükseltildi, topline kavisi belirginleşti — kusur 2).
- front_leg: x 0.130→0.158, z_top 0.560→0.600, knee_z 0.330→0.350, ankle_z 0.140→0.155, yarıçaplar hafif artırıldı (daha geniş duruş + uzun, dolgun bacak — kusur 1).
- rear_leg: x 0.150→0.178, z_top 0.560→0.600, knee_z 0.360→0.385, hock_z 0.170→0.180 (kusur 1).
- tail: droop 0.20→0.14, bush 1.7→1.45, tip_r 0.022→0.028, length 0.55→0.52 (kopuk/bükük görünüm azaltıldı — kusur 3).
- ear: height 0.165→0.200, width 0.095→0.110, z 0.792→0.812 (minik kulaklar büyütüldü — ikincil kusur).
**Sonuç render notu:** `round_01_side.png` — withers hump'ı artık görünür, gövde daha kompakt, 4 bacak three_q'da ayrı ayrı seçiliyor, kuyruk rumpa daha yakın ve daha az bükük. Mesh sağlam (8 parça, ~16k tri, kopma/çıkıntı yok). Round 00'a göre belirgin iyileşme.
**Sonraki tura öncelik:** Kuyruk hâlâ hafif ayrık duruyor — base_r ve droop ince ayarı; snout/stop tanımı (kafa formu belirsiz); bacakların digitigrade açısı ve pati formu; göğüs derinliğinin yana taşması (top görünüşte gövde genişliği).

## Round 02 — 2026-06-01
**Önceki (round 01) en büyük 3 kusur:**
1. Kuyruk rumptan kopuk muz gibi sarkıyor (base gövde son istasyonundan başlıyor, ayrık küre).
2. Snout belirsiz — burun ucu gövdeyle aynı yükseklikte (top_z 0.620), stop yok.
3. Bacaklar ince ve front'ta dışa eğik; pati uçları sivri.
**Uygulanan parametre değişiklikleri:**
- tail: droop 0.14→0.10, base_r 0.098→0.115, bush 1.45→1.35; generator'da kuyruk başlangıcı rumpa gömüldü (by-0.06, bz+0.04) — kopukluk azaltıldı.
- body_stations[0..2]: burun ucu/muzzle top_z düşürüldü (0.620→0.575 vb), hw inceltildi — snout tanımı (kusur 2).
- front/rear_leg: yarıçaplar +%10 kalınlaştırıldı, x hafif daraltıldı, z_top 0.600→0.620 (kusur 3).
**Sonuç render notu:** round_02_side.png — kuyruk rumpa daha yakın, snout incelmiş, bacaklar dolgun. Mesh sağlam (8 parça, ~16k tri). Gövde hâlâ şişkin/yatay tüp, topline düz.
**Sonraki tura öncelik:** Gövde tubularlığı (withers hump zayıf, karın derin sarkık), topline kavisi; kuyruk dibi hâlâ hafif ayrık; kulakların kafaya konumu.

## Round 03 — 2026-06-01
**Önceki (round 02) en büyük 3 kusur:**
1. Boyun/kafa çok aşağı (snout yere bakıyor), topline düz.
2. Karın derin sarkık, gövde yatay balon tüp.
3. Kulaklar kafadan kopuk uçuyor (base y=-0.205 çok önde, z=0.812 düşük).
**Uygulanan parametre değişiklikleri:**
- body_stations: snout/stop/occiput/neck top_z +0.04..0.06 yükseltildi (boyun-kafa kalktı, topline kavisi); waist bot_z 0.395→0.430, hip bot_z yukarı (karın tuck) — kusur 1,2.
- ear base: [0.108,-0.205,0.812]→[0.100,-0.180,0.850] (kafa üstüne çekildi) — kusur 3.
**Sonuç render notu:** round_03_side.png — boyun yükseldi, snout düz uzanıyor, topline daha kavisli. Mesh sağlam. Gövde hâlâ yatay, kuyruk dibi hafif ayrık.
**Sonraki tura öncelik:** Kuyruk dibinin rumpa tam kaynaşması; göğüs derinliği (chest bot_z aşağı, dirsek hizası); croup eğimi; bacak digitigrade açısı.

## Round 04 — 2026-06-01
**Önceki (round 03) en büyük 3 kusur:**
1. Kulaklar kafadan kopuk havada uçuyor (front'ta iki damla).
2. Kuyruk dibi hâlâ rumptan ayrık.
3. Front'ta bacaklar A-duruşu (dışa açık).
**Uygulanan parametre değişiklikleri:**
- ear base [0.100,-0.180,0.850]→[0.072,-0.190,0.805] (kafa içine gömüldü), width 0.110→0.115; kafa istasyonları (stop/occiput) hw 0.118/0.132→0.128/0.150 genişletildi — kusur 1.
- generator: kuyruk başlangıcı daha agresif gömüldü (by-0.11, bz+0.05) — kusur 2.
**Sonuç render notu:** round_04_side/front.png — kulaklar artık kafaya bağlı görünüyor, kuyruk dibi rumpla kaynaştı. Mesh sağlam. Kuyruk arka kısmı hâlâ sarkık/ayrık, snout hafif aşağı.
**Sonraki tura öncelik:** Göğüs derinliği (chest bot_z aşağı, dirsek seviyesi); snout'u düzleştir/yatay; kuyruk droop azalt; front bacak paralelliği.

## Round 05 — 2026-06-01
**Önceki (round 04) en büyük 3 kusur:**
1. Göğüs sığ — referansta dirsek seviyesine kadar derin sarkmalı.
2. Snout hafif aşağı eğik.
3. Kuyruk arka kısmı sarkık.
**Uygulanan parametre değişiklikleri:**
- chest/withers bot_z 0.290/0.355→0.235/0.330, back_mid 0.350→0.300 (derin göğüs) — kusur 1.
- snout istasyonları top_z +0.015..0.02 (burun düzleşti) — kusur 2.
- tail droop 0.10→0.07, bush 1.35→1.32 — kusur 3.
**Sonuç render notu:** round_05_side.png — göğüs ön bacaklar arasında derinleşti, kuyruk daha yatay. Mesh sağlam.
**Sonraki tura öncelik:** Croup/kalça eğimi (rump çok yüksek/yuvarlak); boyun-omuz geçişi yumuşatma; pati tanımı (sivri uçlar); snout uç inceltme.

## Round 06 — 2026-06-01
**Önceki (round 05) en büyük 3 kusur:**
1. Pati yok — bacaklar tek koni, sivri bitiyor.
2. Rump yuvarlak/yüksek.
3. Snout uç hafif kalın.
**Uygulanan parametre değişiklikleri:**
- generator: _paw_points() eklendi — ayak ucunda öne (-Y) uzanan 3 noktalı yatay pati (bilek altı/gövde/parmak ucu); front paw_len 0.10, rear 0.11. Tri 16k→19k. (kusur 1)
**Sonuç render notu:** round_06_side/three_q.png — ayaklarda öne uzanan pati formu oluştu, bacaklar artık sivri bitmiyor. Mesh sağlam (8 parça). Pati hâlâ topça/yuvarlak.
**Sonraki tura öncelik:** Pati yataylaştırma (parmak ucu daha düz, daha az yumru); rump croup eğimi; ön bacak dirsek bükümü.

## Round 07 — 2026-06-01
**Önceki (round 06) en büyük 3 kusur:**
1. Pati topça/yumru.
2. Rump yüksek/yuvarlak (croup eğimi yok).
3. (sürüyor) gövde yatay.
**Uygulanan parametre değişiklikleri:**
- generator _paw_points: parmak ucu r_paw*0.80→0.62 inceltildi, z düşürüldü, gövde noktası geriye (0.45) — daha düz pati (kusur 1).
- body_stations rump/hip top_z 0.748/0.705→0.735/0.680 (croup arkaya eğim) — kusur 2.
**Sonuç render notu:** round_07_side.png — patiler öne uzanan düz forma yaklaştı, croup hafif eğimli. Mesh sağlam.
**Sonraki tura öncelik:** Boyun-omuz geçişi (withers'tan boyna keskin geçiş yumuşatma); snout uç inceltme; gövde genişliği (top view'da fazla şişkin olabilir).

## Round 08 — 2026-06-01
**Önceki (round 07) en büyük 3 kusur:**
1. Snout top'tan çok ince/sivri (muzzle dolgun olmalı).
2. Pati 3/4'te hâlâ topça.
3. (sürüyor) gövde yatay duruş.
**Uygulanan parametre değişiklikleri:**
- body_stations[0..2] hw 0.050/0.070/0.094→0.062/0.086/0.108 (muzzle dolgunlaştı) — kusur 1.
- generator _paw_points: parmak ucu r*0.62→0.50, z'ler düşürüldü (daha düz pati) — kusur 2.
**Sonuç render notu:** round_08_side.png — snout dolgun, patiler düzleşti. Mesh sağlam.
**Sonraki tura öncelik:** Genel duruş — gövde hâlâ yatay tüp; topline withers→croup eğimi güçlendir; arka bacak hock açısı (digitigrade); kuyruk arka ucu hafif yukarı kaldırma.

## Round 09 — 2026-06-01
**Önceki (round 08) en büyük 3 kusur:**
1. Arka bacak düz — digitigrade hock açısı (Z formu) yok.
2. Kuyruk ucu düz aşağı, hafif yukarı kıvrım yok.
3. (sürüyor) gövde yatay.
**Uygulanan parametre değişiklikleri:**
- rear_leg: knee_y 0.730→0.715 (öne), hock_y 0.850→0.870 (geri), paw_y 0.820→0.800 (öne) — Z açısı belirginleşti (kusur 1).
- generator tail: tip_lift parametresi eklendi (son %30 uç yukarı kıvrılır), tail.tip_lift=0.10 — kusur 2.
**Sonuç render notu:** round_09_side.png — arka bacak hock açısı belirgin, kuyruk ucu yataylaştı. Mesh sağlam.
**Sonraki tura öncelik:** Ön bacak dirsek bükümü (knee öne offset); gövdeyi kısaltıp dikleştirme; boyun açısını dikleştirme; pati X-genişliği.
