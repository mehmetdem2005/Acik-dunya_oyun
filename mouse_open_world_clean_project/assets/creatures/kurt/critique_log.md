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

## Round 10 — 2026-06-01
**Önceki (round 09) en büyük 3 kusur:**
1. Ön bacak düz silindir — dirsek bükümü yok.
2. Patiler 3/4'te küre.
3. Kuyruk arka ucu sallanıp ayrık.
**Uygulanan parametre değişiklikleri:**
- front_leg: knee_y 0.150→0.175 (dirsek geriye), paw_y 0.150→0.135 (pati öne), y_top 0.130→0.110, r_top hafif arttı — hafif dirsek açısı (kusur 1).
**Sonuç render notu:** round_10_side.png — ön bacakta dirsek bükümü oluştu. Mesh sağlam (8 parça, ~19k tri).
**Sonraki tura öncelik:** Boyun açısını dikleştirme (kafa yukarı bakmalı); gövde uzunluğunu hafif kısaltma; pati yanal genişlik; kuyruk-bacak çakışması (3/4'te).

## Round 11 — 2026-06-01
**Önceki (round 10) en büyük 3 kusur:**
1. Snout aşağı eğik (kafa yukarı bakmalı).
2. Gövde fazla uzun.
3. Patiler küre.
**Uygulanan parametre değişiklikleri:**
- body_stations[0..2] z'leri +0.04..0.045 (snout yatay/yukarı, kafa kalktı) — kusur 1.
- back_mid/waist/hip y 0.360/0.520/0.680→0.355/0.500/0.650 (gövde ~%4 kısaldı); rear_leg y'leri 0.815→0.780 hizalandı — kusur 2.
**Sonuç render notu:** round_11_side.png — snout yatay/hafif yukarı, gövde kompakt, arka bacak hip altında. Mesh sağlam.
**Sonraki tura öncelik:** Pati yanal genişlik/yataylık; kuyruk arka ucu bacakla çakışması; chest-front bacak omuz kası bağlantısı; kafa tepesi (kulak arası) dolgunluğu.

## Round 12 — 2026-06-01
**Önceki (round 11) en büyük 3 kusur:**
1. Patiler küre (dairesel kesit, düz taban yok).
2. Kuyruk arka ucu bacakla çakışıyor (3/4).
3. Kafa tepesi düz.
**Uygulanan parametre değişiklikleri:**
- generator: _flatten_paw() eklendi — bacak mesh'inde z<0.085 vertexler yere bastırılıp pati düz tabanlı yapıldı (squash 0.45) — kusur 1.
**Sonuç render notu:** round_12_side/three_q.png — patiler artık yatık düz tabanlı, küre değil. Mesh sağlam.
**Sonraki tura öncelik:** Kafa tepesi/kafatası dolgunluğu (kulak arası); boyun kalınlığı (referansta kalın yeleli boyun); omuz-göğüs kası; kuyruk-arka bacak çakışması.

## Round 13 — 2026-06-01
**Önceki (round 12) en büyük 3 kusur:**
1. Boyun ince (referansta kalın yeleli boyun).
2. Kafatası kulak arası düz/dar.
3. Kuyruk-arka bacak çakışması.
**Uygulanan parametre değişiklikleri:**
- neck/neck_base hw 0.146/0.190→0.166/0.205, occiput hw 0.150→0.156 top_z +0.013 (boyun kalın, kafatası dolgun) — kusur 1,2.
- ear base z 0.805→0.818 (kafatası tepesine uyum).
**Sonuç render notu:** round_13_side/front.png — boyun-omuz dolgun, kafatası kubbe. Mesh sağlam.
**Sonraki tura öncelik:** Kuyruk-arka bacak çakışması (kuyruk droop/length ayar); gövde front'ta hafif armut (waist X daralt); göğüs ön (presternum) belirginliği; snout uç burun topuzu.

## Round 14 — 2026-06-01
**Önceki (round 13) en büyük 3 kusur:**
1. Kuyruk arka bacakla çakışıyor (aşağı sallanıyor).
2. Gövde front'ta armut.
3. Snout uç burun topuzu yok.
**Uygulanan parametre değişiklikleri:**
- tail: droop 0.07→0.045, length 0.50→0.56, segments 7→8, tip_lift 0.10→0.085 (daha yatay, arkaya uzanan kuyruk, bacaktan ayrıldı) — kusur 1.
**Sonuç render notu:** round_14_side.png — kuyruk yatay/arkaya, bacakla çakışma azaldı. Mesh sağlam.
**Sonraki tura öncelik:** Snout uç burun topuzu (nose); göğüs ön çıkıntı (presternum); gövde front armut (waist hw); kafa-snout oran (snout biraz kısa olabilir).

## Round 15 — 2026-06-01
**Önceki (round 14) en büyük 3 kusur:**
1. Burun ucu düz koni — nose topuzu yok.
2. Göğüs ön presternum çıkıntısı yok.
3. Gövde front armut.
**Uygulanan parametre değişiklikleri:**
- generator ön kapak: burun uç merkezi -0.022 aşağı (nose topuzu); body_stations[0] z hafif düşürüldü — kusur 1.
**Sonuç render notu:** round_15_side.png — burun ucu hafif aşağı topuz hissi. Mesh sağlam.
**Sonraki tura öncelik:** Göğüs ön presternum (chest istasyonu öne hafif çıkıntı); waist hw daralt (front armut); arka bacak uyluk kası (femur) dolgunluğu; topline withers belirginliği.

## Round 16 — 2026-06-01
**Önceki (round 15) en büyük 3 kusur:**
1. Arka uyluk ince — femur kası dolgun olmalı.
2. Bel (waist) front'ta geniş (armut).
3. Topline withers düz.
**Uygulanan parametre değişiklikleri:**
- rear_leg r_top 0.148→0.160, r_knee 0.096→0.100 (uyluk kası dolgun) — kusur 1.
- waist hw 0.186→0.174 (bel daraldı) — kusur 2.
**Sonuç render notu:** round_16_side.png — arka uyluk dolgun, bel daraldı. Mesh sağlam.
**Sonraki tura öncelik:** Topline withers tepe belirginliği; göğüs ön presternum; snout uzunluğu/incelik; arka bacak hock-pati açısı ince ayar.

## Round 17 — 2026-06-01
**Önceki (round 16) en büyük 3 kusur:**
1. Withers tepe düz (omuz tümseği zayıf).
2. Göğüs ön presternum çıkıntısı yok.
3. Snout oran.
**Uygulanan parametre değişiklikleri:**
- withers top_z 0.935→0.952 (omuz tümseği belirgin) — kusur 1.
- neck_base bot_z 0.435→0.405 (göğüs önü dolgun, presternum) — kusur 2.
**Sonuç render notu:** round_17_side.png — withers tümseği belirgin, göğüs önü dolu. Mesh sağlam.
**Sonraki tura öncelik:** Snout uzunluğu (referansta uzun); kafa-snout geçişi (stop) keskinliği; ön bacak alt incelik (pastern); kuyruk gürlüğü (bush) referans gibi.

## Round 18 — 2026-06-01
**Önceki (round 17) en büyük 3 kusur:**
1. Snout kısa.
2. Stop (kafa-burun geçişi) yumuşak.
3. Pastern (ön bacak alt) kalın.
**Uygulanan parametre değişiklikleri:**
- body_stations[0..3] y -0.520→-0.560 (snout uzadı), hw'ler hafif inceltildi, muzzle_base/stop top_z farkı 0.748→0.822 (stop keskinleşti) — kusur 1,2.
**Sonuç render notu:** round_18_side.png — snout uzun, stop girinti belirgin. Mesh sağlam.
**Sonraki tura öncelik:** Ön bacak pastern incelik (ankle r daralt); kuyruk gürlük (bush) artır; gövde alt karın hattı (waist bot_z tuck); kafa tepesi-kulak geçişi.

## Round 19 — 2026-06-01
**Önceki (round 18) en büyük 3 kusur:**
1. Karın tuck zayıf (bel altı sarkık).
2. Kuyruk ince (bush düşük).
3. Ön bacak pastern kalın.
**Uygulanan parametre değişiklikleri:**
- waist bot_z 0.430→0.458 (karın tuck) — kusur 1.
- tail bush 1.30→1.42 (kuyruk gür) — kusur 2.
- front_leg r_ankle 0.062→0.056, r_knee 0.086→0.082 (pastern ince) — kusur 3.
**Sonuç render notu:** round_19_side.png — karın tuck belirgin, kuyruk gür, pastern ince. Mesh sağlam.
**Sonraki tura öncelik:** Kafa-kulak geçişi yumuşatma; arka bacak alt (metatarsus) incelik; göğüs en derin nokta öne kaydırma; genel siluet referansla karşılaştırma.

## Round 20 — 2026-06-01
**Önceki (round 19) en büyük 3 kusur:**
1. Bacaklar front'ta A-duruşu (içe eğik).
2. Pati uçları front'tan sivri damla.
3. Boyun three_q'da ince.
**Uygulanan parametre değişiklikleri:**
- front_leg x 0.150→0.165, rear_leg x 0.168→0.180 (geniş, paralel duruş) — kusur 1.
- generator _flatten_paw: z_thresh 0.085→0.095, floor 0.018→0.016, squash 0.45→0.38 (pati daha düz) — kusur 2.
**Sonuç render notu:** round_20_front/side.png — bacaklar dik/paralel, patiler daha düz. Mesh sağlam.
**Sonraki tura öncelik:** Boyun three_q kalınlık; kafa front'ta dar (kafatası genişlik); göğüs front armut (chest hw front'ta genişlet); kulak kafaya tam oturtma.

## Round 21 — 2026-06-01
**Önceki (round 20) en büyük 3 kusur:**
1. Boyun front/three_q ince (kafa-gövde geçişi zayıf).
2. Kuyruk three_q'da burgu/spiral (twist) görünüyor.
3. Gövde front armut.
**Uygulanan parametre değişiklikleri:**
- neck_front hw 0.166→0.186, top_z 0.838→0.852, bot_z 0.500→0.470 (boyun dolgun) — kusur 1.
- neck_base hw 0.205→0.228, top_z 0.862→0.872, bot_z 0.405→0.395 (boyun-göğüs geçişi) — kusur 1.
**Sonuç render notu:** round_21_side/three_q.png — boyun belirgin dolgunlaştı, mesh sağlam. Kuyruk burgusu duruyor.
**Sonraki tura öncelik:** Kuyruk twist düzelt (tube_along_points up-vektör tutarlılığı / droop azalt); pati önden parmak ayrımı; kafa front genişlik.

## Round 22 — 2026-06-01
**Önceki (round 21) en büyük 3 kusur:**
1. Kuyruk three_q'da burgu/spiral (loft twist).
2. Patiler hafif twistli/sivri (aynı loft sorunu).
3. Kuyruk neredeyse yatay (droop düşük).
**Uygulanan parametre değişiklikleri:**
- generator tube_along_points: parallel-transport frame eklendi (prev_u'yu yeni eksene yansıt) → loft twist KÖKTEN gitti — kusur 1,2.
- tail droop 0.045→0.18, base_r 0.118→0.120, tip_r 0.030→0.045, bush 1.42→1.25, tip_lift 0.085→0.045, segments 8→10 (düzgün konik, doğal sarkma) — kusur 1,3.
**Sonuç render notu:** round_22_three_q/side.png — kuyruk burgusu TAMAMEN gitti, düzgün konik kuyruk; bacaklar da temizlendi. Mesh sağlam, tüm parçalar yerinde.
**Sonraki tura öncelik:** Pati önden parmak ayrımı/sivrilik; gövde front armut (chest bot_z genişlet); kafa front genişlik; kuyruk gürlük (bush biraz artırılabilir).

## Round 23 — 2026-06-01
**Önceki (round 22) en büyük 3 kusur:**
1. Gövde front armut (üst yuvarlak, alt sivri).
2. Pati önden sivri damla, parmak yok.
3. Kafa front küçük.
**Uygulanan parametre değişiklikleri:**
- generator ring_xz: alt-yarı (ventral) bastırma 0.82→0.90 (göğüs/karın altı dolgun, armut azalır) — kusur 1.
**Sonuç render notu:** round_23_front/side.png — gövde alt dolgunlaştı, armut hafifledi, mesh sağlam.
**Sonraki tura öncelik:** Pati parmak ayrımı (paw_points'e parmak çıkıntı/düzlük); kafa front genişlik (occiput/stop hw); gövde önden hâlâ yuvarlak (chest hw üst hafif daralt).

## Round 24 — 2026-06-01
**Önceki (round 23) en büyük 3 kusur:**
1. Pati önden sivri damla, parmak ayrımı yok.
2. Kafa front küçük.
3. Gövde önden yuvarlak.
**Uygulanan parametre değişiklikleri:**
- generator _paw_points: 3→4 nokta, parmak bölgesi r*0.50→0.95 + ön kenar r*0.70 (yuvarlak bloky pati, sivrilik gitti) — kusur 1.
**Sonuç render notu:** round_24_front/side.png — patiler bloky/yuvarlak, sivri damla gitti, mesh sağlam.
**Sonraki tura öncelik:** Kafa front genişlik (occiput/stop hw artır, kafatası geniş); gövde önden yuvarlak (chest top_z hafif düşür / hw üst hafif daralt); snout side'da çok uzun-ince.

## Round 25 — 2026-06-01
**Önceki (round 24) en büyük 3 kusur:**
1. Snout side'da çok uzun-ince (anteater).
2. Kafatası front küçük/dar.
3. Çene zayıf.
**Uygulanan parametre değişiklikleri:**
- body_stations[0..4]: nose y -0.560→-0.520 (snout kısaldı), hw'ler 0.064→0.078, 0.086→0.100, 0.104→0.120, 0.122→0.150, 0.156→0.178 (snout+kafatası kalınlaştı, güçlü çene) — kusur 1,2,3.
**Sonuç render notu:** round_25_side/front.png — snout kısaldı/kalınlaştı, kafa dolgunlaştı, mesh sağlam.
**Sonraki tura öncelik:** Kafa side'da hâlâ snout'a düz iniyor (stop/brow tümseği belirginleştir); gövde önden yuvarlak; kulak biraz büyük olabilir; arka bacak side'da öne eğik.

## Round 26 — 2026-06-01
**Önceki (round 25) en büyük 3 kusur:**
1. Kafa side'da snout'a düz iniyor (stop/kaş tümseği yok).
2. Gövde önden yuvarlak.
3. Arka bacak side'da öne eğik.
**Uygulanan parametre değişiklikleri:**
- body_stations[2..4] top_z: muzzle_base 0.752→0.746, stop 0.826→0.812, occiput 0.866→0.884; occiput hw 0.178→0.182 (stop girintisi + kaş tümseği belirgin) — kusur 1.
**Sonuç render notu:** round_26_side/three_q.png — kafa tepesi snout'tan yukarı çıkıyor, stop belirginleşti, mesh sağlam.
**Sonraki tura öncelik:** Gövde önden yuvarlak (chest top_z hafif düşür); arka bacak hock-pati side dik dur (hock_y öne); kulak boyutu; göğüs derinliği side.

## Round 27 — 2026-06-01
**Önceki (round 26) en büyük 3 kusur:**
1. Arka bacak side'da öne eğik (pati hock'tan öne kaçık).
2. Gövde önden yuvarlak.
3. Göğüs derinliği side.
**Uygulanan parametre değişiklikleri:**
- rear_leg: knee_y 0.690→0.700, hock_y 0.840→0.852, hock_z 0.190→0.195, paw_y 0.770→0.808 (bacak dikleşti, pati hock altına) — kusur 1.
**Sonuç render notu:** round_27_side/front.png — arka bacak daha dik, pati hock altına yaklaştı, mesh sağlam.
**Sonraki tura öncelik:** Gövde önden yuvarlak (chest top_z hafif düşür / hw üst daralt); göğüs side derinlik (chest bot_z aşağı); kulak boyutu büyük; sırt topline three_q.

## Round 28 — 2026-06-01
**Önceki (round 27) en büyük 3 kusur:**
1. Gövde önden yuvarlak (top-heavy yumurta).
2. Göğüs side derinliği yetersiz.
3. Kulak biraz büyük.
**Uygulanan parametre değişiklikleri:**
- withers hw 0.252→0.242, bot_z 0.330→0.320; chest hw 0.262→0.250, bot_z 0.235→0.205 (front genişlik azaldı, göğüs derinleşti) — kusur 1,2.
**Sonuç render notu:** round_28_front/side.png — göğüs side derin, front daha az şişman, mesh sağlam.
**Sonraki tura öncelik:** Kulak boyut/açı (referans dik üçgen, biraz küçült); gövde önden hâlâ hafif yuvarlak; sırt topline withers tepe three_q; snout side hafif aşağı eğim.

## Round 29 — 2026-06-01
**Önceki (round 28) en büyük 3 kusur:**
1. Kulaklar yuvarlak topak (referans dik sivri üçgen, ayrık).
2. Gövde önden hafif yuvarlak.
3. Snout side hafif düz.
**Uygulanan parametre değişiklikleri:**
- ear base x 0.078→0.092 (ayrık), height 0.190→0.196, width 0.115→0.098 (sivri), lean_out 12→16, lean_back 10→11 (dik+dışa) — kusur 1.
**Sonuç render notu:** round_29_front/three_q.png — kulaklar daha sivri, ayrık, dik; mesh sağlam.
**Sonraki tura öncelik:** Gövde önden yuvarlak (back_mid/waist front genişlik kontrol); snout side hafif aşağı eğim (nose top_z düşür); withers tepe three_q belirginlik; ön bacak side hafif dik.

## Round 30 — 2026-06-01
**Önceki (round 29) en büyük 3 kusur:**
1. Snout side düz/yatay (burun ucu hafif aşağı olmalı).
2. Gövde önden yuvarlak.
3. Withers tepe three_q.
**Uygulanan parametre değişiklikleri:**
- nose top_z 0.672→0.648, bot_z 0.588→0.580; muzzle top_z 0.710→0.698 (burun ucu hafif aşağı, doğal snout profili) — kusur 1.
**Sonuç render notu:** round_30_side.png — snout ucu hafif aşağı eğildi, doğal profil, mesh sağlam.
**Sonraki tura öncelik:** Gövde önden yuvarlak (waist/back_mid front genişlik); withers tepe three_q tümsek; ön bacak side dik; kalça (hip) side yuvarlaklık fazla.

## Round 31 — 2026-06-01
**Önceki (round 30) en büyük 3 kusur:**
1. Hip/kalça side çok yuvarlak şişkin, croup eğimi yok.
2. Gövde önden yuvarlak.
3. Ön bacak side dik değil.
**Uygulanan parametre değişiklikleri:**
- hip hw 0.240→0.228, top_z 0.795→0.782; rump hw 0.190→0.186, top_z 0.735→0.722 (croup eğimi, kalça şişkinliği azaldı) — kusur 1.
**Sonuç render notu:** round_31_side.png — croup doğal eğimle iniyor, kalça daha az şişkin, mesh sağlam.
**Sonraki tura öncelik:** Gövde önden yuvarlak; ön bacak side dik (knee_y/ankle_y hizala); withers tepe belirgin; kuyruk gürlük biraz artır.

## Round 32 — 2026-06-01
**Önceki (round 31) en büyük 3 kusur:**
1. Kafa/boyun side'da çok alçak ve yatay uzanıyor (karınca yiyen/sırtlan profili) — kurt başını withers seviyesinde taşır.
2. Snout side'da hâlâ uzun-ince.
3. Bacaklar gövdeye gömük, hayvan çömelmiş.
**Uygulanan parametre değişiklikleri:**
- body_stations[0..6]: tüm baş+boyun istasyonları top_z +0.04~0.05 yukarı (occiput 0.884→0.930, neck_front 0.852→0.905, neck_base 0.872→0.892); bot_z'ler de +0.02~0.03; nose y -0.520→-0.490 (snout kısaldı) — kusur 1,2.
**Sonuç render notu:** round_32_side/three_q.png — kafa/boyun belirgin yukarı kalktı, yatay uzanma gitti, withers tepesi güçlendi, snout kısaldı; mesh sağlam.
**Sonraki tura öncelik:** Bacakları uzat+dikleştir (hayvan çömelmiş duruyor); gövde front yuvarlak fıçı; snout hâlâ biraz ince; boyun side hâlâ ince/uzun.

## Round 33 — 2026-06-01
**Önceki (round 32) en büyük 3 kusur:**
1. Bacaklar kısa, hayvan çömelmiş (gövde yere yakın).
2. Gövde front yuvarlak fıçı.
3. Snout hâlâ ince.
**Uygulanan parametre değişiklikleri:**
- front_leg z_top 0.625→0.690, knee_z 0.355→0.400, ankle_z 0.160→0.175; rear_leg z_top 0.625→0.690, knee_z 0.400→0.450, hock_z 0.195→0.215 (bacaklar uzadı, gövde yerden kalktı); radyuslar hafif inceltildi (r_top 0.132→0.130 vb.) — kusur 1.
**Sonuç render notu:** round_33_side/three_q.png — bacaklar belirgin uzadı, dik duruş, çömelme gitti; mesh sağlam.
**Sonraki tura öncelik:** Gövde front yuvarlak fıçı (göğüs alt bacaklar arasından sarkıyor, chest bot_z yukarı al / hw daralt); snout ince; boyun side hâlâ uzun; ön bacak side hafif öne eğik.

## Round 34 — 2026-06-01
**Önceki (round 33) en büyük 3 kusur:**
1. Front'ta göğüs alt kısmı bacaklar arasından sarkıyor (chest bot_z çok aşağı).
2. Gövde front yuvarlak fıçı.
3. Boyun side hâlâ uzun.
**Uygulanan parametre değişiklikleri:**
- withers hw 0.242→0.228, bot_z 0.320→0.350; chest hw 0.250→0.232, bot_z 0.205→0.255; back_mid hw 0.224→0.210, bot_z 0.300→0.330 (göğüs alt yukarı çekildi, front genişlik daraldı) — kusur 1,2.
**Sonuç render notu:** round_34_front.png — göğüs sarkması azaldı, bacak arası temiz, gövde daha narrow; mesh sağlam.
**Sonraki tura öncelik:** Snout side ince/uzun (kalınlaştır); boyun side uzun; ön bacak side hafif öne eğik (knee_y hizala); kuyruk gürlük az.

## Round 35 — 2026-06-01
**Önceki (round 34) en büyük 3 kusur:**
1. Snout side ince/uzun (sivri burun, anteater hissi).
2. Boyun side uzun.
3. Ön bacak side hafif öne eğik.
**Uygulanan parametre değişiklikleri:**
- nose y -0.490→-0.470 (kısaldı), hw 0.082→0.096; muzzle hw 0.104→0.118; muzzle_base hw 0.124→0.138 (snout kalınlaştı, küt); bot_z'ler hafif aşağı (çene derin) — kusur 1.
**Sonuç render notu:** round_35_side/three_q.png — snout kısaldı+kalınlaştı, burun ucu küt/dolgun, anteater hissi azaldı; mesh sağlam.
**Sonraki tura öncelik:** Snout hâlâ biraz uzun (kademeli); boyun side uzun/ince; ön bacak side öne eğik (knee_y omuz altına hizala); kuyruk gürlük.

## Round 36 — 2026-06-01
**Önceki (round 35) en büyük 3 kusur:**
1. Ön bacak side'da öne eğik (pati omuz altında değil, ileride).
2. Boyun side uzun/ince.
3. Snout hâlâ biraz uzun.
**Uygulanan parametre değişiklikleri:**
- front_leg y_top 0.110→0.120, knee_y 0.175→0.155, ankle_y 0.150→0.140, paw_y 0.135→0.130 (bacak segment y-aralığı daraldı, dik kolon, pati omuz altına) — kusur 1.
**Sonuç render notu:** round_36_side.png — ön bacak dikleşti, öne eğim azaldı, pati omuz altına hizalandı; mesh sağlam.
**Sonraki tura öncelik:** Boyun side uzun/ince (kalınlaştır + kısalt); snout biraz uzun; kuyruk gürlük az/ince; arka pati side hafif arkaya kaçık.
