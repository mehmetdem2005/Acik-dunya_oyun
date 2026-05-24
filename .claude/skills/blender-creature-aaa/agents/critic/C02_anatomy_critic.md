# Agent C02: Anatomy Critic (Anatomi Eleştirmen)

```yaml
agent_id: anatomy_critic
agent_name_tr: Anatomi Eleştirmen
agent_name_en: Anatomy Critic
category: critic
order_index: 2
implementation_mode: subprocess  # vision_call.py wrapper
parallel_with: [C01, C03, C04, C05]
estimated_duration_seconds: 30-90
```

---

## 1. ROLE SUMMARY

C01 Vision Critic'ten farklı olarak, bu ajan **referans fotoğraflarla** birebir karşılaştırma yapar. Yaratığın **anatomik orantı, kemik landmark pozisyonu, kas dağılımı, duruş tipi** gerçek hayvana ne kadar sadık?

**Diğer kritiklerden farkı:** referans foto gerektirir. Yoksa atlanır.

---

## 2. WHEN INVOKED

### Preconditions
- `renders_dir` mevcut (P03/P04/P08/P12 sonrası)
- `refs_dir` mevcut ve **en az 1 referans foto** içeriyor
- `CreatureSpec.json` mevcut

### Postconditions
- `critic_reports/anatomy_<phase>_<iter>.json` yazılmış

### Atlama Koşulu
Referans foto yoksa: skip + orchestrator'a "anatomy_critic_skipped: no_refs" sinyali.

---

## 3. INPUTS

```
renders_dir: Path        # 8 açı render'ları + (varsa) wireframe
refs_dir: Path           # GEREKLİ — referans fotolar
spec: CreatureSpec.json
phase: str               # hangi aşama
```

---

## 4. OUTPUTS

Aynı schema'da JSON (C01 ile uyumlu):

```json
{
  "critic_id": "C02_anatomy_critic",
  "phase": "mesh",
  "iteration": 2,
  "overall_assessment": "...",
  "anatomical_accuracy_score": 75,
  "defects": [
    {
      "id": "A001",
      "severity": "major",
      "category": "anatomy",
      "anatomical_landmark": "scapula",
      "location": "sol omuz",
      "description_tr": "Sol kürek kemiği gerçek kurttan ~%15 daha yukarda. Referans foto #2 ile kıyaslandığında omuz silueti farklı.",
      "evidence_image_names": ["rest_left.png", "ref_2_side_profile.jpg"],
      "expected_position_tr": "Omuz tepe noktası gövde yüksekliğinin yaklaşık %55'inde olmalı",
      "actual_position_tr": "Omuz tepe noktası gövde yüksekliğinin yaklaşık %63'ünde",
      "suggested_fix_tr": "Shoulder bone'unu Z ekseninde -0.05 indir, P03'e geri dön",
      "alternatives_tr": ["Mesh radius profile'da düzelt (cheap fix)", "Stilize kabul"]
    }
  ],
  "anatomical_landmarks_evaluated": [
    "scapula", "humerus", "pelvis", "femur", "spine_curve", "tail_attachment"
  ],
  "comparison_to_references": [
    {"ref": "ref_1_side.jpg", "match_score": 78},
    {"ref": "ref_2_3_4_front.jpg", "match_score": 82}
  ]
}
```

---

## 5. SYSTEM PROMPT (vision_call.py'a giden)

```
SEN ANATOMİ ELEŞTİRMENİSİN — uzman bir zoolojist + character TD.

Görevin: Mevcut 3D yaratık render'larını gerçek hayvan referans
fotoğraflarıyla anatomik olarak karşılaştırmak.

DİKKAT EDECEKLERIN:
1. İskelet landmark pozisyonları (omuz, kalça, diz, dirsek, kürek
   kemiği, pelvis kanat noktası)
2. Anatomik orantılar (kafa/gövde, bacak/gövde, kuyruk/gövde)
3. Duruş tipi (digitigrade için topuk yerden ne kadar yukarda?
   plantigrade için tüm taban yerde mi?)
4. Kas dağılımı (omuz omazı, gluteus, biceps femoris)
5. Kafa şekli (snout uzunluğu, kafatası genişlik/uzunluk oranı)
6. Pati/ayak detayları (parmak sayısı, pad varlığı)
7. Vücut silüeti yan profilde gerçeğe ne kadar yakın?

KESİN KURALLAR:
- Her defekt için anatomical_landmark alanını doldur
- expected_position_tr ve actual_position_tr ölçülebilir oran ver
- Referans foto adıyla evidence_image_names'e ekle
- description_tr ve suggested_fix_tr Türkçe + jargon-free
- "Production_ready" sadece tüm landmark'ler %95+ doğru ise

ÇIKIŞ: Strict JSON, C01 ile aynı schema + anatomical_accuracy_score (0-100).
```

---

## 6. CALL PROTOCOL

`vision_call.py` çağrısı, C01 ile aynı pattern:

```python
subprocess.run([
    "python", "scripts/vision_call.py",
    "--renders-dir", renders,
    "--refs-dir", refs,             # GEREKLİ
    "--spec", str(spec_path),
    "--phase", phase,
    "--output", str(report_path),
    "--system-prompt-override", "agents/critic/C02_anatomy_critic.md#system-prompt",
], timeout=300)
```

`vision_call.py`'a opsiyonel `--system-prompt-override` flag eklenir (v2'de). Bu critic için anatomi-focused prompt yüklenir.

---

## 7. CROSS-CRITIC INTERACTION

C02'nin "anatomy defekt" bulduğu bölgeyi C01 Vision Critic de "anatomy" kategorisinde rapor etmişse → **confirmed_by_multiple = True**, orchestrator severity bir basamak yükseltir.

C02 tek başına anatomy bulduysa ama C01 görmemişse → "single_critic_observation", confidence düşük.

---

## 8. FAILURE MODES

### F1: Referans foto yok
**Recovery:** Skip, manifest'e "no_references_provided".

### F2: Vision Claude referans ile current render'ı ayırt edemedi
**Recovery:** vision_call.py'a açıkça "reference" ve "current" etiketi geçir.

---

## 9. EXAMPLE OUTPUT (kurt için, P04 sonrası)

```json
{
  "critic_id": "C02_anatomy_critic",
  "phase": "mesh",
  "anatomical_accuracy_score": 78,
  "defects": [
    {
      "id": "A001",
      "severity": "major",
      "anatomical_landmark": "snout_length",
      "description_tr": "Burun yapısı gerçek kurttan kısa. Kurtlarda snout kafa uzunluğunun ~%55'i, mevcut model %40 civarı.",
      "suggested_fix_tr": "Head bone tail'ini Y ekseninde +0.05 uzat, mesh radius profile'da kafa ucunu inceltip uzat.",
    }
  ],
  "comparison_to_references": [
    {"ref": "ref_side_profile.jpg", "match_score": 78}
  ]
}
```
