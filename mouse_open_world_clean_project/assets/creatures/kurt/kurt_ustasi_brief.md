# "Kurt Ustası" — iteratif eleştiri-iyileştirme ajan brifingi

Bu, her turda çalıştırılan uzman ajanın görev tanımıdır. Her ajan bir öncekinin
çıktısını **ağır biçimde eleştirir** ve referansa yaklaştırır.

## Çalışma dizini
`assets/creatures/kurt/`

## Her turun adımları (sıkı sırayla)

1. **Referansı oku:** `REFERENCE.png` (hedef — tam gövde fotoreal kurt).
2. **Önceki turu oku:** `renders/round_NN_{side,front,three_q,top,rear_q}.png`
   (NN = bir önceki tur numarası).
3. **AĞIR ELEŞTİRİ:** Render'ı referansla karşılaştır. Şu eksenlerde SOMUT,
   SAYISAL kusurları yaz (göz kararı "daha iyi olsun" değil):
   - Genel oran: gövde uzunluğu/yükseklik, bacak uzunluğu/gövde, kafa/gövde
   - Bacaklar: çok kısa/uzun mu? duruş (digitigrade açı), kalınlık, ayak
   - Topline (sırt hattı): withers (omuz) yükselişi, bel tuck, kalça/croup eğimi
   - Göğüs derinliği, boyun açısı/kalınlığı
   - Kafa: snout uzunluğu, stop, kulak boyutu/açısı
   - Kuyruk: uzunluk, droop, gürlük
   - Silüet kusurları (parçaların kopuk/iç içe görünmesi)
4. **PARAMETRE DÜZELT:** `wolf_params.json`'u düzenle. Sadece eleştirinde
   gerekçelendirdiğin alanları değiştir. Değişiklikleri ölçülü tut (tek turda
   %15-30 düzeltme — aşırı sıçrama yapma, döngü yakınsasın).
5. **YENİDEN RENDER:** `./run_round.sh round_MM` (MM = bu tur numarası).
6. **GÜNLÜK:** `critique_log.md`'ye bu turun girdisini ekle (aşağıdaki şablon).
7. **DOĞRULA:** `renders/round_MM_side.png`'i oku — değişiklik beklenen yönde mi?
   Mesh bozulduysa (parça kopması, normal hatası) parametreyi geri al.

## Kurallar
- Hiçbir mesh import etme — sadece `wolf_params.json` (ve gerekirse
  `kurt_generator.py` geometri mantığı) düzenlenir.
- Mevcut parça yapısını koru (gövde, 4 bacak, kuyruk, 2 kulak).
- Render Cycles CPU (denoise kapalı) — generator zaten ayarlı.
- Bir tur en fazla ~5 parametre grubu değiştirsin; kademeli yakınsama hedefi.

## critique_log.md girdi şablonu
```
## Round MM — <tarih>
**Önceki (round NN) en büyük 3 kusur:**
1. ...
2. ...
3. ...
**Uygulanan parametre değişiklikleri:**
- alan: eski → yeni  (gerekçe)
**Sonuç render notu:** (round_MM_side.png'e bakış — düzeldi mi?)
**Sonraki tura öncelik:** ...
```
