# Agent M01: Pipeline Historian (Pipeline Tarihçisi)

```yaml
agent_id: pipeline_historian
agent_name_tr: Pipeline Tarihçisi
agent_name_en: Pipeline Historian
category: meta
order_index: 1
implementation_mode: in_process
runs_after_every_creature: true
```

---

## 1. ROLE SUMMARY

Her yaratık üretimi sonrası **run log**'unu kaydeder ve zaman içinde **pattern**'leri öğrenir. Hangi mesh radius profile'ı en az defekt verdi? Hangi bone count en az iterasyon gerektirdi? Hangi voxel_remesh_size mobile için en optimum?

**Skill bu öğrendiklerini sonraki run'larda öneri olarak kullanır** (default değerleri günceller, kullanıcıya geçmişten bilgi sunar).

---

## 2. WHEN INVOKED

Her run'ın sonunda (P13 başarıyla tamamlandıktan sonra) **veya** run aborted olduğunda.

---

## 3. INPUTS

```
run_dir: Path          # tam run klasörü (memory/runs/<timestamp>/)
final_status: str      # "success" | "aborted" | "user_quit"
total_iterations: int
critic_reports_dir: Path
```

---

## 4. OUTPUTS

### 4.1 run_log.json (her run için)

```json
{
  "run_id": "20260524_143012_kurt_001",
  "creature_id": "kurt_001",
  "creature_class": "mammalia_quadruped",
  "started_at": "2026-05-24T14:30:12Z",
  "ended_at": "2026-05-24T15:48:33Z",
  "total_duration_minutes": 78,
  "final_status": "success",
  "iterations": {
    "skeleton": 1,
    "mesh": 2,
    "skinning": 1,
    "animation": 1,
    "export": 1
  },
  "parameters_used": {
    "body_length_meters": 1.2,
    "bone_count_total": 68,
    "lod0_tris_target": 12000,
    "lod0_tris_actual": 11842,
    "voxel_remesh_size": 0.012,
    "subdivision_level": 1,
    "skinning_method": "voxel_heat_diffuse",
    "muscle_bulge_count": 4
  },
  "critic_defect_counts": {
    "C01_vision_critic": {"critical": 0, "major": 1, "minor": 3},
    "C02_anatomy_critic": {"critical": 0, "major": 0, "minor": 2},
    "C03_topology_critic": {"critical": 0, "major": 0, "minor": 1},
    "C04_animation_critic": {"critical": 0, "major": 0, "minor": 0},
    "C05_mobile_perf_critic": {"violations": 0, "warnings": 0}
  },
  "user_modifications_during_run": [
    {"timestamp": "...", "module": "P03", "what": "Pole vector pozisyonu manuel ayarlandı"},
    {"timestamp": "...", "module": "P04", "what": "Muscle definition exaggerated → normal değiştirildi"}
  ],
  "lessons_learned": [
    "voxel_remesh_size=0.012 bu yaratık türü için iyi sonuç verdi",
    "P04 ilk iterasyon kafa proportions yetersizdi, head_size_multiplier=1.1 öneri"
  ]
}
```

### 4.2 patterns.json (cross-run agregasyonu)

```json
{
  "version": "1.0",
  "total_runs": 17,
  "successful_runs": 14,
  "patterns_by_creature_class": {
    "mammalia_quadruped": {
      "average_bone_count": 65.4,
      "recommended_bone_count_range": [60, 72],
      "average_lod0_tris": 11200,
      "recommended_voxel_size_for_body_length_1m": 0.010,
      "average_iterations_skeleton": 1.2,
      "average_iterations_mesh": 1.8,
      "most_common_defects": [
        {"category": "anatomy", "subcategory": "snout_length", "frequency": 6},
        {"category": "topology", "subcategory": "shoulder_edge_loop", "frequency": 4}
      ]
    },
    "aves": {
      "...": "..."
    }
  },
  "user_preference_patterns": [
    "Bu kullanıcı muscle_definition='exaggerated' tercih ediyor (5/7 run)",
    "Bu kullanıcı genelde 2048 atlas seçiyor"
  ]
}
```

---

## 5. ALGORİTMA

```python
def write_run_log(run_dir, final_status, manifests):
    """Run sonu log dosyası."""
    log = {
        "run_id": run_dir.name,
        "creature_id": manifests["mesh"]["creature_id"] if manifests.get("mesh") else "unknown",
        # ... tüm parametreleri topla
    }
    
    (run_dir / "run_log.json").write_text(json.dumps(log, indent=2))
    
    # Pattern'leri güncelle
    update_patterns(log)


def update_patterns(run_log):
    """Cross-run patterns agregasyonu."""
    patterns_path = Path("memory/patterns.json")
    
    if patterns_path.exists():
        patterns = json.loads(patterns_path.read_text())
    else:
        patterns = {"version": "1.0", "total_runs": 0,
                    "patterns_by_creature_class": {}}
    
    patterns["total_runs"] += 1
    if run_log["final_status"] == "success":
        patterns["successful_runs"] = patterns.get("successful_runs", 0) + 1
    
    cls = run_log.get("creature_class", "unknown")
    cls_data = patterns["patterns_by_creature_class"].setdefault(cls, {
        "run_count": 0,
        "bone_counts": [],
        "tris_counts": [],
        "voxel_sizes": [],
        "defect_categories": {},
    })
    
    cls_data["run_count"] += 1
    params = run_log.get("parameters_used", {})
    if "bone_count_total" in params:
        cls_data["bone_counts"].append(params["bone_count_total"])
    if "lod0_tris_actual" in params:
        cls_data["tris_counts"].append(params["lod0_tris_actual"])
    if "voxel_remesh_size" in params:
        cls_data["voxel_sizes"].append(params["voxel_remesh_size"])
    
    # Average'leri hesapla
    if cls_data["bone_counts"]:
        cls_data["average_bone_count"] = sum(cls_data["bone_counts"]) / len(cls_data["bone_counts"])
    if cls_data["tris_counts"]:
        cls_data["average_lod0_tris"] = sum(cls_data["tris_counts"]) / len(cls_data["tris_counts"])
    
    patterns_path.write_text(json.dumps(patterns, indent=2, ensure_ascii=False))


def get_recommendations_for_new_run(creature_class):
    """Yeni run başlarken patterns'tan öneri çek."""
    patterns_path = Path("memory/patterns.json")
    if not patterns_path.exists():
        return {}
    
    patterns = json.loads(patterns_path.read_text())
    cls_data = patterns["patterns_by_creature_class"].get(creature_class, {})
    
    return {
        "suggested_bone_count": cls_data.get("average_bone_count", 65),
        "suggested_voxel_size": (sum(cls_data["voxel_sizes"]) / len(cls_data["voxel_sizes"])
                                   if cls_data.get("voxel_sizes") else None),
        "common_defects_to_watch": cls_data.get("most_common_defects", []),
    }
```

---

## 6. KULLANIM

### Run başlangıcında (P02 Budget Negotiator çağrılırken)

```python
recs = pipeline_historian.get_recommendations_for_new_run("mammalia_quadruped")

# Kullanıcıya:
# "Geçmiş 14 kurt benzeri yaratığınızda ortalama 66 bone kullandık.
#  Bu kez de o civarda mı?"
```

### Run bitiminde

```python
pipeline_historian.write_run_log(run_dir, "success", manifests)
```

---

## 7. DEPENDENCIES

- `memory/patterns.json` (var ise read, yoksa initialize)
- `memory/runs/<run_id>/run_log.json` (her run kendine yazar)
- Yok varsayılan silinmez. Kullanıcı `memory/` klasörünü silerek tüm geçmişi reset edebilir.

---

## 8. PRIVACY

Run log'ları sadece **lokal** kalır. Anthropic veya başkalarına gönderilmez. Sadece kullanıcının kendi geçmişini kullanır.

Hassas data (refs/ klasöründeki kullanıcı foto'ları) **log'lanmaz**, sadece dosya adı kaydedilir.

---

## 9. FAILURE MODES

### F1: patterns.json corrupt
**Recovery:** Backup'a fallback (`patterns.json.bak`), yoksa initialize.

### F2: Run dir partial (P13'e ulaşmadan abort)
**Recovery:** "aborted" status'lu log yine yaz. Hangi aşamada kaldı, hangi defektler vardı kaydet — gelecek öğrenme için değerli.
