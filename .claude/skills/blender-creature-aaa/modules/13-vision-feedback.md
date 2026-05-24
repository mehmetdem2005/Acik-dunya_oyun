# Modül 13 — Vision Feedback Loop

**Amaç:** Skill'in "kör" olmamasını sağlamak. Her büyük modül çıktısı (mesh, rig, skin, anim) render edilir, vision-capable bir Claude çağrısıyla analiz edilir, defektler kullanıcıya sunulur ve düzeltme döngüsüne girilir.

**Bu, skill'in beynidir.** K-Means clustering veya volume metric gibi proxy'ler yerine **gerçek görsel değerlendirme** yapar.

---

## 1. NEDEN BU YAKLAŞIM

Önceki kuşak Blender pipeline'larında yapay zeka **kör** kabul edilir. Bütün hata tespiti matematiksel proxy'ye dayanır (volume change, vertex distance, bounding box). Bu proxy'ler:

- Bacağın **görsel** olarak yanlış yöne büküldüğünü göremez (volume korunduğu sürece "OK" der)
- Mesh'in başka mesh'in **içine girdiğini** tespit edemez (BVH overlap mantığı sıklıkla yanlış)
- Anatomik orantı bozukluğunu (kafa çok küçük, kuyruk çok uzun) göremez
- Kürk yönünün ters döndüğünü göremez

**Çözüm:** Blender headless modda viewport'u PNG'ye render eder. Bu PNG'ler vision-capable Claude'a gönderilir. Vision Claude görsel kritik döner. Skill kritike göre fix uygular.

---

## 2. RENDER ALMA PROTOKOLÜ

`scripts/render_eval.py` çağrılır. Render set'i şu açılardan oluşur:

### 2.1 Statik (Rest Pose) Render Set'i

| # | Açı | Lens | Amaç |
|---|-----|------|------|
| 1 | Front (Y+) | 50mm | Sol-sağ simetri kontrolü |
| 2 | Back (Y-) | 50mm | Arka simetri + kuyruk |
| 3 | Left (X-) | 50mm | Yan profil + orantılar |
| 4 | Right (X+) | 50mm | Diğer yan profil simetri |
| 5 | Top (Z+) | 50mm | Üstten bakış + spine alignment |
| 6 | Bottom (Z-) | 50mm | Karın + ayak dağılımı |
| 7 | 3/4 Front-Left | 50mm | Genel form |
| 8 | 3/4 Back-Right | 50mm | Genel form (diğer açı) |

### 2.2 Wireframe Overlay Render

Aynı 8 açıdan ama Blender `solid + wireframe` shading. Topology kontrolü için.

### 2.3 Stres Pozu Render Set'i (rig hazırsa)

Skill 4 ekstrem poz çalar ve her birinden 4 açıdan render alır:

- **Squat:** kalça maksimum çömelmiş, dizler bükülmüş (deformation check)
- **Twist:** omurga 45° yana bükülmüş (spine deformation)
- **Run-stride:** ön ve arka bacaklar ekstrem ileri-geri (IK chain check)
- **Yawn / mouth open:** çene maksimum açık (eğer kafa rigi varsa)

Toplam: 16 stres pozu render'ı.

### 2.4 In-Game Camera Distance Render

Mobil oyun bağlamı için kritik. Kullanıcının belirlediği "in-game camera distance"tan render (default mesafeyi sorar). Bu render düşük çözünürlüklü (1080×1920 mobil 9:16 portrait veya 1920×1080 landscape) — silüet ve detay yeterliliği kontrolü için.

---

## 3. RENDER AYARLARI

`scripts/render_eval.py` şu Blender ayarlarını set eder:

```python
import bpy

# Engine
bpy.context.scene.render.engine = 'BLENDER_EEVEE_NEXT'  # hızlı, gerçekçi yeterli

# Resolution
bpy.context.scene.render.resolution_x = 1024  # eval için yeterli, sorulduğunda override
bpy.context.scene.render.resolution_y = 1024
bpy.context.scene.render.resolution_percentage = 100

# Output
bpy.context.scene.render.image_settings.file_format = 'PNG'
bpy.context.scene.render.image_settings.color_mode = 'RGB'  # alpha sorun yaratabiliyor vision'da

# Lighting (kontrollü, neutral)
# 3-point setup: key, fill, rim
# Renkler nötr beyaz, intensity standart, gölgeler soft

# Material override (eval rendering)
# Tüm mesh'lere geçici neutral matcap material (gri, hafif metalik) bind edilir
# Texture varlığı kontrolü ayrı bir render pass'inde yapılır

# Camera
# Orbital kamera setup, 8 açıya programatik yerleştirme
```

Bu **eval render**'dır, final render değil. Hız önceliklidir.

---

## 4. VISION CALL PROTOKOLÜ

Render'lar alındıktan sonra `scripts/vision_call.py` subprocess olarak `claude -p` çağırır.

### 4.1 Prompt Şablonu (vision Claude'a giden)

```
SYSTEM: You are a 3D character art technical director (TD) reviewing
a creature asset for a mobile game (Godot 4 engine). The user is
Turkish-speaking but you should respond in structured JSON.

The creature is described as:
{CREATURE_SPEC_SUMMARY}

Reference images (real anatomy) are attached for comparison:
{REFERENCE_IMAGES}

Current state renders are attached:
{CURRENT_RENDERS}

Stress pose renders (if rig is ready):
{STRESS_POSE_RENDERS}

YOUR TASK: Identify defects in the current state. Compare to:
1. The reference anatomy
2. AAA mobile creature standards (poly distribution, silhouette
   clarity, deformation quality)
3. Topology and edge flow visible in wireframe renders

OUTPUT FORMAT (strict JSON):
{
  "overall_assessment": "critical_issues_present" | "major_issues_present" | "minor_polish_needed" | "production_ready",
  "defects": [
    {
      "id": "D001",
      "severity": "critical" | "major" | "minor",
      "category": "anatomy" | "topology" | "deformation" | "proportion" | "symmetry" | "intersection" | "silhouette" | "detail",
      "location": "where on the creature (e.g., 'left front shoulder', 'tail tip', 'right paw pad')",
      "description_en": "what is wrong, technical",
      "description_tr": "Turkish summary for end user, plain language no jargon",
      "evidence_image_ids": ["render_3.png", "render_7.png"],
      "suggested_fix": "what should be done",
      "alternatives": ["alt1", "alt2"]
    }
  ],
  "positives": ["what looks good (Turkish)"],
  "next_action_recommendation": "what to do next"
}

CRITICAL RULES:
- Don't be vague. Specify exact location and what's wrong.
- Compare to references. If no references, use real-world knowledge of the species.
- Mobile context: distant silhouette must be readable.
- Be honest. Don't praise broken work.
- Turkish descriptions must be jargon-free for non-technical reader.
```

### 4.2 Çağrı Komutu

```python
# vision_call.py'nin core'u
import subprocess
import json
from pathlib import Path

def call_vision(renders_dir: Path, refs_dir: Path, spec: dict, output: Path):
    images = sorted(renders_dir.glob("*.png"))
    refs = sorted(refs_dir.glob("*.jpg")) + sorted(refs_dir.glob("*.png"))
    
    # claude -p çağrısı
    cmd = ["claude", "-p", "--output-format", "json"]
    
    # Görüntü ekleme: claude CLI flag pattern (versiyona göre değişir)
    for img in images + refs:
        cmd.extend(["--image", str(img)])
    
    prompt = build_prompt(spec, [i.name for i in images], [r.name for r in refs])
    
    result = subprocess.run(
        cmd,
        input=prompt,
        capture_output=True,
        text=True,
        timeout=300  # 5 dk timeout
    )
    
    if result.returncode != 0:
        # fail handling
        raise RuntimeError(f"Vision call failed: {result.stderr}")
    
    # Parse JSON
    try:
        vision_output = json.loads(result.stdout)
    except json.JSONDecodeError:
        # Bazen output'ta wrapping text olur, extract et
        vision_output = extract_json_from_text(result.stdout)
    
    output.write_text(json.dumps(vision_output, indent=2, ensure_ascii=False))
    return vision_output
```

> **NOT:** `claude -p` CLI'nin tam flag yapısı (özellikle `--image` veya `--attach`) Claude Code sürümüne göre değişebilir. Skill ilk run'da `claude --help` çıktısını parse edip doğru flag'i tespit eder, `memory/cli_signature.json`'a kaydeder.

---

## 5. KULLANICIYA SUNUM

Vision Claude döndükten sonra skill kullanıcıya **konsolide rapor** sunar:

```
══════════════════════════════════════════════════
VISION CHECK SONUCU — Faz 3 (Mesh) sonrası

📊 GENEL DEĞERLENDİRME: ⚠️ MAJÖR SORUNLAR VAR
   (3 kritik, 5 majör, 2 minör defekt)

═══ KRİTİK DEFEKTLER (mutlaka düzeltilmeli) ═══

🔴 D001 — Sol ön omuz, anatomi
   Kurt'un sol ön omuz yapısı gerçek anatomiden farklı görünüyor:
   kürek kemiği (scapula) çok yukarıda, omuz kası eksik. Referans
   foto #2 ile karşılaştırıldığında yaklaşık 0.15 birim aşağıda
   olmalı.
   
   Önerilen düzeltme: shoulder bone'u Z ekseninde -0.15 indir,
   skinning'i yeniden hesapla.
   
   Alternatifler:
     • Sadece mesh'i yeniden modify et, bone'a dokunma
     • Stilize kabul et, geç
   
   Kanıt: render_3.png (sol profil)
   
   [düzelt önerilen şekilde / alternatif1 / alternatif2 / yoksay / sen karar ver]

🔴 D002 — Mesh kesişimi, sağ arka bacak
   Sağ arka bacak ile karın bölgesi arasında geometri kesişimi
   var (clipping). Squat pozisyonunda %30 mesh içeride.
   
   Önerilen düzeltme: karın bölgesinin alt vertex'lerini Z+0.05 kaldır
   Alternatifler: bacak bone'un X eksenini 0.1 dışa al
   
   [...]

═══ MAJÖR DEFEKTLER ═══

🟠 D004 — Topology, kuyruk başlangıcı
   Kuyruk gövdeye birleştiği yerde edge flow kötü, üçgen yüzeyler
   yoğunlaşmış. Animasyonda kuyruk büküldüğünde et yırtılma efekti
   verecek.
   
   [...]

═══ MİNÖR (estetik) ═══

🟡 D009 — Kulak ucu çok keskin
   [...]

══════════════════════════════════════════════════

✅ İYİ NOKTALAR:
   • Genel silüet kurt formuna iyi oturmuş
   • Bacak orantıları gerçeğe yakın
   • Kürk yönü doğru

📋 ÖNERİLEN SONRAKİ AKSİYON:
   D001 ve D002'yi öncelikle düzelt, sonra D004'ü gözden geçir.
   D009 estetik, sen karar ver.

══════════════════════════════════════════════════

KARARIN:
  [a] Tümünü öner şekilde düzelt (otomatik)
  [b] Tek tek karar vereceğim (her defekti ayrıca sor)
  [c] Sadece kritikleri düzelt, gerisini yoksay
  [d] Bu defektleri yoksay, devam et (riskli)
  [e] Renderları tekrar gönder, başka açıdan vision check yap
  [f] Vision Claude haksız, ben farklı görüyorum (manuel feedback)

══════════════════════════════════════════════════
```

---

## 6. FIX UYGULAMA

Kullanıcı kararı verdikten sonra `modules/14-self-correct.md` (henüz yazılmadı) çağrılır. Her defekt için fix protokolü orada tanımlı.

Düzeltme sonrası **tekrar render + tekrar vision check**. Bu loop:

```
while max_iterations < user_limit:
    render_eval()
    vision_result = call_vision()
    
    if vision_result["overall_assessment"] == "production_ready":
        break
    
    if vision_result["overall_assessment"] == "minor_polish_needed":
        if user_setting["auto_fix_minors"]:
            apply_fixes(minors)
            continue
        else:
            ask_user()
    
    # critical or major
    show_user_report()
    user_decision = await_user()
    apply_decision()
```

`user_limit` runtime'da sorulur, default `MAX_RUNTIME=2 hours`.

---

## 7. ELLE OVERRIDE

Kullanıcı vision Claude'a katılmıyorsa (f seçeneği) skill kullanıcıdan **manuel feedback** alır:

```
══════════════════════════════════════════════════
MANUEL VISION FEEDBACK

Vision Claude'un dediklerine katılmıyorsan kendi feedback'ini ver.

Format (her satır bir gözlem):
  CRIT: [kısa açıklama]
  MAJOR: [...]
  MINOR: [...]

Veya: "vision Claude şunu görmüş ama ben bunu görüyorum: ..."

══════════════════════════════════════════════════
```

Bu feedback aynı pipeline'a girer, fix protokolü uygulanır.

---

## 8. RENDER ARŞİVLEME

Her vision check'in render'ları `memory/runs/<timestamp>/renders/iter_<n>/` altına kaydedilir. Bu arşiv:
- Self-critique için dataset
- Kullanıcı sonradan "önceki versiyona dönelim" derse referans
- Patent bulma: aynı defektin tekrar tekrar çıkması = modül talimatında eksiklik

---

## 9. HIZLI MOD

Kullanıcı zaman dar ise "hızlı vision check" isteyebilir:
- Sadece 4 açı (front, side, top, 3/4)
- Wireframe atla
- Stres poz atla
- Sadece critical/major bul, minör atla

---

## 10. BU MODÜLÜN KENDİ KENDİNİ ELEŞTİRMESİ

Vision Claude bazen yanlış pozitif verebilir (sahte defekt). Her kullanıcı override "vision haksızdı" log'lanır. Eğer aynı tür defekt 3+ kez yanlış pozitif veriyorsa, skill bu modülün prompt'unu güncellemeyi önerir (örn: "kürk yönü defekti çok yanlış pozitif çıkıyor, bu kategoriyi prompt'ta zayıflatalım mı?").

---

## 11. SONRAKİ MODÜLE GEÇİŞ

Vision check temiz çıkana veya kullanıcı "kabul" diyene kadar bu modülden çıkış yok. Sonraki modüle geçiş kullanıcının açık onayıyla.
