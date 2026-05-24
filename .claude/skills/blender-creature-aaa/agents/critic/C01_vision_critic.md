# Agent C01: Vision Critic (Görsel Eleştirmen)

```yaml
agent_id: vision_critic
agent_name_tr: Görsel Eleştirmen
agent_name_en: Vision Critic
category: critic
order_index: 1
implementation_mode: subprocess  # claude -p subprocess
estimated_duration_seconds: 30-120
parallel_with: [C02, C03, C04, C05]
```

---

## 1. ROLE SUMMARY

Bir mesh/rig/skinning/animation aşamasının çıktısını **görsel olarak inceler**. Render'ları (8 açı + wireframe + stres pozları) Claude'un vision capability'sine gönderir, **structured defect raporu** üretir. Orchestrator bu raporu (varsa diğer critic'lerle birleştirerek) kullanıcıya sunar.

**Bu skill'in K-Means / volume heuristic gibi proxy yöntemler yerine kullandığı asıl "görme" mekanizmasıdır.**

---

## 2. WHEN INVOKED

Her büyük production milestone'undan sonra çağrılır:

| Faz | Vision Critic çağrılır mı? |
|---|---|
| Skeleton (P03) | ✅ (bone-only render üzerinden) |
| Mesh (P04) | ✅ (mesh + wireframe overlay) |
| Retopology (P05) | ✅ (sadece wireframe) |
| UV (P06) | ⚠️ (opsiyonel, UV stretch map render varsa) |
| Rigging (P07) | ✅ (control bone shapes ile) |
| Skinning (P08) | ✅ (stres pozları zorunlu) |
| Correctives (P09) | ✅ (extreme bend frame'leri) |
| Materials (P11) | ✅ (lit render) |
| Animation (P12) | ✅ (key frame'leri + cycle preview) |
| Export (P13) | ✅ (Godot import sonrası render) |

**Paralel çalışır** diğer critic'lerle (`concurrent.futures.ThreadPoolExecutor`).

---

## 3. INPUTS

```python
# Required
renders_dir: Path        # 8 açı + (varsa) wireframe + (varsa) stres pozları
spec: CreatureSpec.json  # ne yaratık beklenir
phase: str               # hangi aşama: "mesh" | "skeleton" | "skinning" | ...

# Optional
refs_dir: Path           # referans fotolar (varsa karşılaştırmaya katılır)
previous_iteration_renders: Path  # önceki iter render'ları (delta için)
user_focus_areas: list   # kullanıcı "şu bölgeye dikkat et" derse
```

---

## 4. OUTPUTS

### vision_result_<phase>_<iter>.json

```json
{
  "critic_id": "C01_vision_critic",
  "phase": "mesh",
  "iteration": 2,
  "overall_assessment": "major_issues_present",
  "defects": [
    {
      "id": "D001",
      "severity": "critical",
      "category": "anatomy",
      "location": "sol ön omuz",
      "description_en": "Left front shoulder appears anatomically incorrect — scapula too high, no visible deltoid bulk.",
      "description_tr": "Sol ön omuz anatomik olarak yanlış görünüyor — kürek kemiği çok yukarda, omuz kası yok gibi.",
      "evidence_image_names": ["rest_left.png", "rest_34_front.png"],
      "suggested_fix_tr": "Omuz kemiğini Z ekseninde -0.05 indir, P03'e geri dön ve skeleton'ı revize et.",
      "alternatives_tr": [
        "Sadece mesh radius profile'ında omuz bölgesini şişirerek kapatabiliriz (cheap fix)",
        "Stilize kabul edip geçebiliriz (eğer kullanıcı onaylarsa)"
      ]
    }
  ],
  "positives": [
    "Kuyruk silüeti çok iyi, kurt referansına yakın",
    "Genel oran (kafa/gövde/bacak) anatomik olarak doğru",
    "Wireframe quad dağılımı düzgün"
  ],
  "silhouette_readability": "good",
  "anatomical_accuracy_score": 78,
  "topology_quality_score": 82,
  "next_action_recommendation_tr": "D001 kritik, mutlaka düzeltilmeli. Diğer minor'lar sonradan dolaşılabilir.",
  "generated_at": "2026-05-24T..."
}
```

---

## 5. SYSTEM PROMPT

Tam prompt `scripts/vision_call.py` içindeki `VISION_SYSTEM_PROMPT` sabitinde tanımlı. Burada **özet**:

```
SEN AAA OYUN STÜDYOSUNDA SENIOR TECHNICAL DIRECTOR'SUN.

GÖREVİN: 3D yaratık asset'inin mevcut durumunu görsel olarak
incelemek. Sertçe ve dürüstçe defekt bulmak. Bozuk işi övme.

KARŞILAŞTIRMA NOKTALARIN:
1. Referans görüntüler (varsa, gerçek hayvan)
2. AAA mobile creature standartları (silüet, topology, deformation)
3. CreatureSpec'te tarif edilen yaratık

KESİN KURALLAR:
- description_tr ve suggested_fix_tr MUTLAKA Türkçe ve jargon-free
- evidence_image_names gerçek dosya adları olmalı
- "production_ready" sadece HİÇ defekt yoksa
- "critical" = mutlaka düzelt, oyun release'inde bunu görmek istemezsin
- "major" = düzeltilmeli ama hayati değil
- "minor" = estetik, geçilebilir

ÇIKIŞ FORMATI: Strict JSON. Markdown fence yok, prose yok, sadece JSON.
```

---

## 6. CALL PROTOCOL

`scripts/vision_call.py` zaten implementation. Orchestrator şu komutla çağırır:

```python
subprocess.run([
    "python", "scripts/vision_call.py",
    "--renders-dir", str(run_dir / "renders/iter_<n>/mesh"),
    "--refs-dir", str(run_dir / "refs"),
    "--spec", str(run_dir / "CreatureSpec.json"),
    "--phase", "mesh",
    "--output", str(run_dir / "critic_reports/vision_mesh_iter2.json"),
    "--fast",  # opsiyonel: minörleri atla
], timeout=300)
```

---

## 7. DEFECT KATEGORİLERİ

Critic şu kategorilerden defekt raporlar:

| Kategori | Anlamı | Örnek |
|---|---|---|
| `anatomy` | Anatomik yanlış | Bacak çok kısa, omuz pozisyonu yanlış |
| `topology` | Mesh edge flow kötü | Üçgenler eklemde, quad'lar dağınık |
| `deformation` | Stres pozunda mesh bozuluyor | Diz büküldüğünde et yırtılıyor |
| `proportion` | Orantılar dengesiz | Kafa çok büyük, kuyruk çok ince |
| `symmetry` | Sol-sağ uyumsuz | Sol bacak sağdan kısa, sol göz dönük |
| `intersection` | Mesh kendi içine giriyor | Karın bacakla clipping |
| `silhouette` | Mobil mesafede silhouette okunmaz | Bacaklar gövdeye karışıyor |
| `detail` | Detay eksik veya fazla | Tırnak yok, kulak detaysız |
| `uv_texture` | UV stretch veya seam görünüyor | Yüzde texture esnemesi |
| `material` | Materyal yanlış | Plastik gibi, çok parlak |

---

## 8. SEVERITY KRİTERLERİ

**Critical:** Oyun release'inde bunu kullanıcı görür ve "broken" der.
- Mesh non-manifold / clipping
- Görünür anatomik yanlış (3 bacak, 1 göz, vb.)
- Stres pozunda et yırtılıyor

**Major:** Profesyonel artist hemen fark eder, düzeltir.
- Asimetri > %5 (gözle görünür)
- Topology çirkin ama çalışır
- Proportion sapması

**Minor:** İstenirse polish, gerekmezse geçer.
- Kulak ucu çok keskin
- Kürk yönü 5° eğri
- Pati ucu hafif basık

---

## 9. CONFIDENCE SCORE

Critic her defekt için kendi güvenini de bildirir (gelecek versiyonda):

```json
{
  "id": "D001",
  "...",
  "critic_confidence": 0.92  // 0-1, vision'ın bu defekti gördüğüne ne kadar emin
}
```

Düşük confidence (<0.6) defektler orchestrator tarafından "olası" olarak işaretlenir, kullanıcıya "vision tam emin değil ama..." şeklinde sunulur.

---

## 10. CROSS-CRITIC RECONCILIATION

Orchestrator tüm critic'lerin (C01-C05) raporlarını birleştirir. Aynı defekti 3+ critic raporladıysa **öncelik kritiktir** (`severity = critical` zorla).

Tek critic raporladıysa ve confidence düşükse "olası" olarak işaretle.

---

## 11. ÖZEL DURUMLAR

### 11.1 Sadece Skeleton Aşaması (P03 sonrası)
Bu noktada mesh yok, sadece bone'lar görünür. Critic prompt'una **özelleştirme** eklenir:
```
"You are reviewing a SKELETON ONLY render. Mesh not yet generated.
Focus on: bone placement, IK chain visual correctness, symmetry,
pole bone positions (in front of elbows for front limbs, in front
of knees for rear limbs)."
```

### 11.2 Wireframe-Only Render
Topology check için. Vision Claude'a "sadece wireframe görüyorsun, mesh shader yok" bilgisi verilir.

### 11.3 Animation Frame Sampling
P12 sonrası tüm cycle'ı tek tek frame olarak render etmek gereksiz. Critic 6 frame örneklemesi yapar (frame 1, 10, 20, 30, 40, 50 / 60).

---

## 12. FAILURE MODES

- **Claude CLI auth fail:** kullanıcıya "claude login" yap dedirt
- **Timeout (vision Claude 5 dk içinde cevap vermedi):** retry × 2, hala fail ise manuel feedback iste
- **JSON parse fail:** raw output kullanıcıya göster, manuel critique iste
- **Hiç defekt bulamadı:** bu mümkün ama nadir, "production_ready" diyor olmalı

---

**Implementation: `scripts/vision_call.py` (mevcut). Bu ajan için ayrı build script yok.**
