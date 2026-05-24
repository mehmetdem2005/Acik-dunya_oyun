# Agent C05: Mobile Performance Critic

```yaml
agent_id: mobile_perf_critic
agent_name_tr: Mobil Performans Eleştirmen
agent_name_en: Mobile Performance Critic
category: critic
order_index: 5
implementation_mode: in_process  # vision yok, sadece manifest okuma
parallel_with: [C01, C02, C03, C04]
estimated_duration_seconds: 2-5
no_vision_required: true
```

---

## 1. ROLE SUMMARY

**Vision kullanmayan** kritik. Sadece manifest dosyalarını okur, **BudgetSpec'e uyumluluk** kontrol eder. Render render etmez, claude -p çağırmaz, hızlı çalışır.

**Bu, mobile-shipped asset'ın oyun release'e hazır olduğunu garanti eden son güvenlik ağıdır.**

---

## 2. WHEN INVOKED

Her aşamada (bütçe kontrolü olarak):
- Mesh sonrası (P04) → tris check
- Skinning sonrası (P08) → bone count + vertex weight check
- Animation sonrası (P12) → keyframe count check
- Export sonrası (P13) → final glb size check

---

## 3. INPUTS

```
BudgetSpec.json
MeshManifest.json
SkinningManifest.json
AnimationManifest.json
ExportManifest.json
```

Hangi manifest'lerin mevcut olduğuna göre kontrol scope'u belirlenir.

---

## 4. OUTPUTS

```json
{
  "critic_id": "C05_mobile_perf_critic",
  "phase": "final",
  "overall_assessment": "compliant",
  "budget_compliance": {
    "polygon_budget": {
      "lod0_target": 12000,
      "lod0_actual": 11842,
      "status": "compliant",
      "delta_percent": -1.3
    },
    "rig_budget": {
      "bone_count_max": 100,
      "bone_count_actual": 68,
      "status": "compliant"
    },
    "vertex_weights": {
      "max_per_vertex_target": 4,
      "max_per_vertex_actual": 4,
      "status": "compliant"
    },
    "texture_budget": {
      "atlas_resolution_target": 2048,
      "atlas_resolution_actual": 2048,
      "status": "compliant"
    },
    "animation_budget": {
      "total_clips_target": 7,
      "total_clips_actual": 7,
      "status": "compliant"
    },
    "shape_key_budget": {
      "muscle_bulge_count_max": 4,
      "muscle_bulge_count_actual": 4,
      "status": "compliant"
    },
    "file_size": {
      "lod0_max_kb": 2000,
      "lod0_actual_kb": 1842,
      "status": "compliant"
    }
  },
  "violations": [],
  "warnings": [
    {
      "category": "draw_call_estimation",
      "description_tr": "Yaratık tek material'da, draw call tahmini düşük. İyi.",
      "estimated_draw_calls": 1
    }
  ]
}
```

---

## 5. ALGORİTMA

```python
def check_budget_compliance(manifests, budget_spec):
    violations = []
    
    # 1. Polygon budget
    mesh_m = manifests.get("mesh")
    if mesh_m:
        actual = mesh_m["tris_count_actual"]
        target = budget_spec["polygon_budget"]["lod0_tris_target"]
        hard_max = budget_spec["polygon_budget"]["lod0_tris_hard_max"]
        
        if actual > hard_max:
            violations.append({
                "category": "polygon_budget",
                "severity": "critical",
                "description_tr": f"LOD0 tris {actual} > hard_max {hard_max}. P04'e geri dön, decimate ratio düşür.",
                "actual": actual,
                "limit": hard_max,
            })
    
    # 2. Bone budget
    skel_m = manifests.get("skeleton")
    if skel_m:
        bone_count = skel_m["bone_count_total"]
        max_b = budget_spec["rig_budget"]["bone_count_max"]
        if bone_count > max_b:
            violations.append({
                "category": "rig_budget",
                "severity": "critical",
                "description_tr": f"Bone sayısı {bone_count} > max {max_b}.",
            })
    
    # 3. Vertex weights
    skinning_m = manifests.get("skinning")
    if skinning_m:
        max_inf = skinning_m["max_influences_per_vertex_target"]
        target = budget_spec["rig_budget"]["vertex_weights_per_vertex_max"]
        if max_inf > target:
            violations.append({
                "category": "vertex_weights",
                "severity": "major",
                "description_tr": f"Vertex weight {max_inf} > {target}. Mobile shader uyumsuz.",
            })
    
    # 4. Animation clips
    anim_m = manifests.get("animation")
    if anim_m:
        actual = anim_m["total_actions"]
        target = len(budget_spec["animation_clips"])
        if actual < target:
            violations.append({
                "category": "animation_budget",
                "severity": "major",
                "description_tr": f"Eksik animasyon klip: {actual}/{target}",
            })
    
    # 5. Export file size
    export_m = manifests.get("export")
    if export_m:
        for exp in export_m["exports"]:
            if exp["level"] == "LOD0":
                size_kb = exp["file_size_bytes"] / 1024
                if size_kb > 5000:  # 5 MB üst sınır
                    violations.append({
                        "category": "file_size",
                        "severity": "major",
                        "description_tr": f"LOD0 dosya boyutu {size_kb:.0f} KB > 5000 KB (mobile için ağır)",
                    })
    
    return violations


def estimate_draw_calls(manifests):
    """
    Materyal sayısı + UV island sayısı + LOD config'e göre draw call tahmini.
    """
    mat_m = manifests.get("material")
    if mat_m is None:
        return 1
    
    # Tek material = 1 draw call
    # Multi material varsa = N draw call
    if mat_m.get("texture_strategy") == "single_atlas":
        return 1
    else:
        return len(mat_m.get("texture_slots", [1]))
```

---

## 6. SEVERITY KURALLAR

| Bulgu | Severity |
|---|---|
| LOD0 tris > hard_max | critical |
| Bone count > max | critical |
| Vertex weight > target | major |
| File size > 5 MB | major |
| Missing animation clip | major |
| Texture resolution > target | major |
| Texel density inconsistent (>%30) | minor |

---

## 7. FAILURE MODES

### F1: Manifest dosyası eksik
**Recovery:** İlgili pipeline aşamasını "incomplete" olarak işaretle, kontrolü skip et, log'a yaz.

### F2: Manifest JSON corrupt
**Recovery:** "manifest_unreadable" violation ekle, ilgili aşamayı re-run öner.

---

## 8. CROSS-CRITIC

C05 + C01 + C03'ün hepsi pozitifse → **green light to ship**.

C05 critical violation bulduysa **STOP**, asla export ETME. Diğer kritiklerin onayına rağmen.
