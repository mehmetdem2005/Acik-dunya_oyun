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

## Round 37 — 2026-06-01
**Önceki (round 36) en büyük 3 kusur:**
1. Boyun side uzun/ince (kurt boynu kalın-kaslı olmalı).
2. Snout biraz uzun.
3. Kuyruk gürlük az.
**Uygulanan parametre değişiklikleri:**
- neck_front hw 0.190→0.212, y -0.090→-0.085, bot_z 0.510→0.475 (boyun kalın, gerdan dolgun); neck_base hw 0.230→0.240 (omuza güçlü geçiş) — kusur 1.
**Sonuç render notu:** round_37_side/three_q.png — boyun kalınlaştı, omuza kaslı geçiş, gerdan dolgun; mesh sağlam.
**Sonraki tura öncelik:** Kuyruk gürlük/kalınlık (referans gür süpürge, mevcut ince muz); snout biraz uzun; arka pati side hafif arkaya kaçık; sırt topline withers-kalça arası.

## Round 38 — 2026-06-01
**Önceki (round 37) en büyük 3 kusur:**
1. Kuyruk ince/zayıf muz (referans gür süpürge).
2. Snout biraz uzun.
3. Arka pati side hafif arkaya kaçık.
**Uygulanan parametre değişiklikleri:**
- tail base_r 0.120→0.135, tip_r 0.045→0.060, bush 1.25→1.55 (kuyruk kalın+gür, uç da dolgun) — kusur 1.
**Sonuç render notu:** round_38_side/rear_q.png — kuyruk belirgin kalınlaştı/gürleşti, süpürge hissi; mesh sağlam.
**Sonraki tura öncelik:** Kuyruk droop az (yataya yakın, biraz daha aşağı sarksın); snout uzun; arka pati side arkaya kaçık (paw_y öne); sırt topline.

## Round 39 — 2026-06-01
**Önceki (round 38) en büyük 3 kusur:**
1. Kuyruk droop az (yataya yakın çıkıyor, kurt kuyruğu aşağı sarkmalı).
2. Snout uzun.
3. Arka pati side arkaya kaçık.
**Uygulanan parametre değişiklikleri:**
- tail droop 0.18→0.52, length 0.56→0.58, tip_lift 0.045→0.020 (kuyruk belirgin aşağı sarkar); generator droop eğrisi t^1.6→t^1.25 + tip_lift eşiği 0.7→0.75 (sarkma kuyruk başından itibaren etki eder) — kusur 1. (İç deneme: ilk droop 0.34 yetersizdi, 0.52'ye çıkarıldı + eğri düzeltildi.)
**Sonuç render notu:** round_39_three_q/rear_q.png — kuyruk artık belirgin aşağı sarkıyor, doğal rahat duruş; gür+sarkık; mesh sağlam.
**Sonraki tura öncelik:** Snout uzun (kademeli kısalt); arka pati side arkaya kaçık (paw_y öne); sırt topline withers-kalça; gövde top view fıçı genişlik.

## Round 40 — 2026-06-01
**Önceki (round 39) en büyük 3 kusur:**
1. Snout uzun (kafanın ~%79'u, fazla çıkık burun).
2. Arka pati side arkaya kaçık.
3. Sırt topline.
**Uygulanan parametre değişiklikleri:**
- nose y -0.470→-0.435, muzzle -0.385→-0.360, muzzle_base -0.295→-0.280 (snout %14 kısaldı, kafatası korundu); hw'ler hafif +0.002-0.004 — kusur 1.
**Sonuç render notu:** round_40_side/three_q.png — snout kısaldı, kafa kompakt/oranlı, hortum hissi azaldı; mesh sağlam.
**Sonraki tura öncelik:** Arka pati side arkaya kaçık (paw_y öne, hock altına); sırt topline withers-kalça hafif kavis; gövde top fıçı; ön bacak side hafif öne.

## Round 41 — 2026-06-01
**Önceki (round 40) en büyük 3 kusur:**
1. Arka pati side hock'tan öne kaçık (hock-pati dikey hizalı değil).
2. Sırt topline withers-kalça.
3. Gövde top fıçı.
**Uygulanan parametre değişiklikleri:**
- rear_leg hock_y 0.852→0.860, paw_y 0.808→0.840 (pati hock altına yaklaştı, dik hock-pati hizası) — kusur 1.
**Sonuç render notu:** round_41_three_q/rear_q.png — arka bacak dikleşti, pati hock altına hizalandı, dikey kolon; mesh sağlam.
**Sonraki tura öncelik:** Gövde top view fıçı (waist daralt, karın tuck belirgin); sırt topline withers-kalça hafif kavis; ön bacak side hafif öne; kafa top genişlik.

## Round 42 — 2026-06-01
**Önceki (round 41) en büyük 3 kusur:**
1. Gövde top view fıçı/tüpsel (bel daralması yok).
2. Sırt topline withers-kalça.
3. Ön bacak side hafif öne.
**Uygulanan parametre değişiklikleri:**
- back_mid hw 0.210→0.196; waist hw 0.174→0.156, bot_z 0.458→0.470; hip hw 0.228→0.226 (bel belirgin daralma, top'tan kum saati silüeti) — kusur 1.
**Sonuç render notu:** round_42_top/three_q.png — bel daralması belirgin, omuz-bel-kalça kum saati, karın atletik; mesh sağlam.
**Sonraki tura öncelik:** Sırt topline withers tepe-kalça hafif düz/kavis; ön bacak side hafif öne; kafa top dar (kafatası genişlik); göğüs side derinlik.

## Round 43 — 2026-06-01
**Önceki (round 42) en büyük 3 kusur:**
1. Sırt topline withers tek keskin tümsek, kalçaya dik iniş.
2. Front kafa-gövde geçişi (kafa küçük tümsek).
3. Ön bacak side hafif öne.
**Uygulanan parametre değişiklikleri:**
- withers top_z 0.952→0.930 (keskinlik azaldı); back_mid 0.800→0.814, waist 0.778→0.792 (sırt daha yumuşak/yatay iner) — kusur 1.
**Sonuç render notu:** round_43_side/three_q.png — topline withers-kalça yumuşak akıcı iniş, keskin tepe gitti; mesh sağlam.
**Sonraki tura öncelik:** Front kafa-gövde geçişi (boyun front dar, kafa gövdeden ayrık görünsün); ön bacak side öne; göğüs side derinlik; gövde top omuz genişlik.

## Round 44 — 2026-06-01
**Önceki (round 43) en büyük 3 kusur:**
1. Kulaklar küçük ve yana açık (referans büyük dik öne bakan üçgen).
2. Front kafa-gövde geçişi (boyun front görünmüyor).
3. Ön bacak side hafif öne.
**Uygulanan parametre değişiklikleri:**
- ear height 0.196→0.224 (büyük dik üçgen), base z 0.818→0.860 (kafatası tepesine oturdu), lean_out 16→12, lean_back 11→9 (daha dik+öne) — kusur 1.
**Sonuç render notu:** round_44_front/three_q.png — kulaklar büyüdü, dik üçgen, öne bakar; mesh sağlam.
**Kalıcı kusur notu:** Front-on görünümde kafa gövde arkasında perspektifle küçük kalıyor (kamera açısı doğal sonucu); takılmadan diğer eksenlerde ilerlenecek.
**Sonraki tura öncelik:** Ön bacak side öne (knee hizala); göğüs side derinlik; gövde top omuz genişlik; snout front aşağı bakıyor (burun ucu hafif kaldır).

## Round 45 — 2026-06-01
**Önceki (round 44) en büyük 3 kusur:**
1. Göğüs side derinliği yetersiz (kurt göğsü dirsek seviyesine iner).
2. Ön bacak side hafif öne.
3. Snout front aşağı bakıyor.
**Uygulanan parametre değişiklikleri:**
- chest bot_z 0.255→0.232 (göğüs derinleşti, dirsek hizasına yakın), hw 0.232→0.236 (dolgun göğüs); withers bot_z 0.350→0.335, back_mid 0.330→0.318 — kusur 1.
**Sonuç render notu:** round_45_three_q/side.png — göğüs derinleşti, kürek/göğüs hacmi arttı, bacak arası temiz (sarkma yok); mesh sağlam.
**Sonraki tura öncelik:** Ön bacak side hafif öne (knee_y); snout front aşağı (burun ucu kaldır); gövde top omuz genişlik; kalça/but kası side dolgunluk.

## Round 46 — 2026-06-01
**Önceki (round 45) en büyük 3 kusur:**
1. Snout/burun ucu aşağı sarkık (front+side, gömük burun).
2. Ön bacak side hafif öne.
3. Gövde top omuz genişlik.
**Uygulanan parametre değişiklikleri:**
- nose top_z 0.688→0.706, bot_z 0.588→0.602; muzzle 0.736→0.750/0.592; muzzle_base 0.792→0.800 (burun ucu kalktı, snout profili yatay/güçlü) — kusur 1.
**Sonuç render notu:** round_46_side/three_q.png — burun ucu kalktı, snout profili güçlü/yatay, sarkma azaldı; mesh sağlam.
**Sonraki tura öncelik:** Ön bacak side hafif öne (knee_y geri); kalça/but kası side dolgunluk; gövde top omuz genişlik; arka bacak üst (uyluk) kas hacmi.

## Round 47 — 2026-06-01
**Önceki (round 46) en büyük 3 kusur:**
1. Arka bacak üst (uyluk/but) kas hacmi zayıf (kurt arka bacağı üstte güçlü).
2. Ön bacak side hafif öne.
3. Gövde top omuz genişlik.
**Uygulanan parametre değişiklikleri:**
- rear_leg r_top 0.158→0.176, r_knee 0.096→0.104 (uyluk/but kas hacmi arttı, kalçayla kaynaştı) — kusur 1.
**Sonuç render notu:** round_47_side/rear_q.png — uyluk dolgun/kaslı, aşağı incelen güçlü arka bacak; mesh sağlam.
**Sonraki tura öncelik:** Ön bacak side hafif öne (knee_y geri); ön bacak üst (omuz/humerus) kas hacmi (r_top); gövde top omuz genişlik; arka bacak side hock açısı (digitigrade belirgin).

## Round 48 — 2026-06-01
**Önceki (round 47) en büyük 3 kusur:**
1. Ön bacak üst (omuz/humerus) kas hacmi zayıf (arka bacağa göre ince).
2. Ön bacak side hafif öne.
3. Arka bacak hock açısı (digitigrade belirgin değil).
**Uygulanan parametre değişiklikleri:**
- front_leg r_top 0.130→0.146, r_knee 0.078→0.084 (omuz/humerus kası dolgun, göğüse kaynaştı, ön-arka denge) — kusur 1.
**Sonuç render notu:** round_48_side/three_q.png — ön bacak üstü dolgun kaslı omuz, göğüsle kaynaşma; mesh sağlam.
**Sonraki tura öncelik:** Arka bacak hock açısı digitigrade belirginleştir (hock_z aşağı, paw öne); ön bacak side hafif öne; gövde top omuz genişlik; baş side kafatası tepesi (occiput tümseği).

## Round 49 — 2026-06-01
**Önceki (round 48) en büyük 3 kusur:**
1. Arka bacak hock açısı digitigrade belirgin değil (düz kolon gibi).
2. Ön bacak side hafif öne.
3. Gövde top omuz genişlik.
**Uygulanan parametre değişiklikleri:**
- rear_leg knee_y 0.700→0.690 (diz öne), knee_z 0.450→0.455, hock_y 0.852→0.868 (hock geri), hock_z 0.215→0.198 (aşağı), paw_y 0.840→0.822 (pati öne) — belirgin Z digitigrade açısı — kusur 1.
**Sonuç render notu:** round_49_side/three_q.png — arka bacak Z digitigrade kıvrımı belirgin, doğal kurt duruşu; mesh sağlam.
**Sonraki tura öncelik:** Ön bacak side hafif öne (knee geri hizala); gövde top omuz genişlik; baş side occiput/kafatası tepesi tümseği; göğüs front V/keel daralma.

## Round 50 — 2026-06-01
**Önceki (round 49) en büyük 3 kusur:**
1. Ön bacak side hafif öne eğik (dikey kolon değil).
2. Gövde top omuz genişlik.
3. Baş side kafatası tepesi tümseği.
**Uygulanan parametre değişiklikleri:**
- front_leg y_top 0.120→0.125, knee_y 0.155→0.135, ankle_y 0.140→0.128, paw_y 0.130→0.122 (bacak segment y daraldı, dikey kolon, pati omuz altına) — kusur 1.
**Sonuç render notu:** round_50_side/three_q.png — ön bacak dikey, öne eğim gitti, pati omuz altında; mesh sağlam. Genel silüet net kurt.
**Sonraki tura öncelik:** Baş side kafatası tepesi (occiput) hafif tümsek; gövde top omuz genişlik; göğüs front V/keel; boyun-kafa side geçiş (ense yelesi hacmi).

## Round 51 — 2026-06-01
**Önceki (round 50) en büyük 3 kusur:**
1. Boyun üstü (ense) side'da çukur (occiput-withers arası iniyor, yele yok).
2. Gövde top omuz genişlik.
3. Göğüs front V/keel.
**Uygulanan parametre değişiklikleri:**
- neck_front top_z 0.905→0.922, hw 0.212→0.216; neck_base top_z 0.892→0.916, hw 0.240→0.244 (boyun üstü çukur doldu, ense yelesi dolgun, occiput-withers düz akış) — kusur 1.
**Sonuç render notu:** round_51_side/three_q.png — ense yelesi dolgun, boyun üstü kaslı, occiput-withers hattı güçlü; mesh sağlam.
**Sonraki tura öncelik:** Gövde top omuz genişlik (omuz top'tan dar); göğüs front V/keel daralma; baş side çene/gıdı (alt çene hattı); pati parmak ayrımı (kalıcı, generator).

## Round 52 — 2026-06-01
**Önceki (round 51) en büyük 3 kusur:**
1. Pati parmak ayrımı YOK (düz bloky uç) — brief kalıcı kusur.
2. Gövde top omuz genişlik.
3. Göğüs front V/keel.
**Uygulanan parametre/generator değişiklikleri:**
- generator: yeni _toe_grooves() fonksiyonu — pati ön bölgesini X yönünde 3 parmak lobuna böler (oluk derinliği depth=0.030, parmak uçları öne 0.045, oluklar geri 0.018, parmak ucuna doğru artan t profili). build_front/rear_leg toe_grooves çağırır + pati tüpü seg 12→20 (parmak çözünürlüğü) — kusur 1.
- (İç deneme: ilk depth=0.012/seg=12 etkisiz kaldı; depth 0.030 + seg 20 + toe forward 0.045 ile belirgin parmak ayrımı.)
**Sonuç render notu:** round_52_front/three_q.png — ön ve arka patilerde belirgin 3 parmak ayrımı, gerçek ayak hissi; mesh sağlam, kopma yok. tri 21696→28352.
**Sonraki tura öncelik:** Gövde top omuz genişlik; göğüs front V/keel daralma; baş side çene/gıdı; parmak ayrımı ince ayar (gerekirse derinlik).

## Round 53 — 2026-06-01
**Önceki (round 52) en büyük 3 kusur:**
1. Göğüs/karın front'ta alttan yuvarlak şişman (keel/V yok).
2. Gövde top omuz genişlik.
3. Baş side çene/gıdı.
**Uygulanan parametre/generator değişiklikleri:**
- generator ring_xz: ventral (zu<0) bölgede x *= 1+0.18*zu (alt gövde %16'ya kadar daralır) — göğüs/karın keel (V) hissi, alttan dar — kusur 1.
**Sonuç render notu:** round_53_front/three_q.png — göğüs alt kısmı daraldı, keel hissi, daha az şişman fıçı; mesh sağlam.
**Sonraki tura öncelik:** Baş side çene/gıdı (alt çene hattı belirgin); gövde top omuz hafif dar; kafa side stop (alın-burun açısı) belirgin; göz çukuru/kaş hafif.

## Round 54 — 2026-06-01
**Önceki (round 53) en büyük 3 kusur:**
1. Kafa side stop (alın-burun açısı) belirgin değil (snout'tan alına düz geçiş).
2. Baş side çene/gıdı.
3. Gövde top omuz genişlik.
**Uygulanan parametre değişiklikleri:**
- muzzle top_z 0.750→0.744, muzzle_base 0.800→0.784 (snout sırtı düzleşti); stop top_z 0.858→0.868 (alın yükseldi) — snout-alın arası stop girintisi belirginleşti — kusur 1.
**Sonuç render notu:** round_54_side/three_q.png — stop belirgin, düz snout + yükselen alın, kurt profili; mesh sağlam.
**Sonraki tura öncelik:** Baş side alt çene/gıdı hattı (alt çene belirgin, gıdı dolgun); gövde top omuz dar; göz/kaş çıkıntısı; arka but side dolgunluk.

## Round 55 — 2026-06-01
**Önceki (round 54) en büyük 3 kusur:**
1. Kafa side alt çene/gıdı hattı zayıf (çene altı yüzeysel).
2. Gövde top omuz dar.
3. Göz/kaş çıkıntısı.
**Uygulanan parametre değişiklikleri:**
- muzzle bot_z 0.592→0.580, muzzle_base 0.592→0.572, stop bot_z 0.625→0.598 (çene alt hattı snout boyunca düz+derin, gıdı dolgun) — kusur 1.
**Sonuç render notu:** round_55_three_q/side.png — alt çene belirgin, çene altı dolgun, güçlü kafa profili; mesh sağlam.
**Sonraki tura öncelik:** Gövde top omuz hafif dar; göz/kaş çıkıntısı (kafatası yan tümsek); arka but side dolgunluk; kuyruk dibi rumpla kaynaşma (kopuk muz hissi).

## Round 56 — 2026-06-01
**Önceki (round 55) en büyük 3 kusur:**
1. Arka but/kalça side dolgunluğu zayıf (but kası arka bacakla kaynaşmıyor).
2. Gövde top omuz dar.
3. Göz/kaş çıkıntısı.
**Uygulanan parametre değişiklikleri:**
- hip hw 0.226→0.242, bot_z 0.360→0.328 (but aşağı dolgunlaştı); rump hw 0.186→0.198, bot_z 0.425→0.410 (but arkası dolgun) — kusur 1.
**Sonuç render notu:** round_56_side/three_q.png — but/kalça dolgun, but kası arka bacakla kaynaştı, güçlü uyluk; mesh sağlam.
**Sonraki tura öncelik:** Gövde top omuz hafif dar; göz/kaş çıkıntısı (kafatası yan); göğüs/sternum side önde çıkıntı (ön bacak önü); pati parmak ayrımı ince ayar.

## Round 57 — 2026-06-01
**Önceki (round 56) en büyük 3 kusur:**
1. Göğüs/sternum side önde çıkıntı yok (göğüs ön bacakların önünde dolgun olmalı).
2. Gövde top omuz dar.
3. Göz/kaş çıkıntısı.
**Uygulanan parametre değişiklikleri:**
- neck_base bot_z 0.400→0.358, withers bot_z 0.335→0.300 (göğüs önü-altı dolgunlaştı, sternum/prosternum hissi) — kusur 1.
**Sonuç render notu:** round_57_side/front.png — göğüs önü dolgun, sternum çıkıntısı, derin göğüs; bacak arası temiz (sarkma yok); mesh sağlam.
**Sonraki tura öncelik:** Gövde top omuz hafif dar; göz/kaş çıkıntısı; ön bacak alt (bilek/metacarpus) hafif açı; pati biraz büyük olabilir (orantı).
