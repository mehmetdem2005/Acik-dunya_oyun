# Agent P05: Topology Surgeon (Topoloji Cerrahı)

```yaml
agent_id: topology_surgeon
agent_name_tr: Topoloji Cerrahı
agent_name_en: Topology Surgeon
category: production
order_index: 5
implementation_mode: subprocess
estimated_duration_minutes: 3-12
critical_path: false  # opsiyonel, P04 sonrası
```

---

## 1. ROLE SUMMARY

P04 Mesh Sculptor'ın voxel remesh + decimate çıktısı **temiz quad mesh** üretmez — çoğunlukla triangle-heavy karmaşık topology'dir. Bu ajan **retopology** yapar: yüksek poly mesh'i, animasyon için ideal **quad-dominant temiz mesh**'e dönüştürür.

**Üç strateji (öncelik sırasıyla):**

1. **Instant Meshes** (external binary) — en iyi otomatik quad retopology
2. **Blender QuadriFlow** (built-in) — orta kalite, hızlı
3. **Decimate Planar + dissolve edges** (fallback) — düşük kalite ama her zaman çalışır

---

## 2. WHEN INVOKED

### Preconditions
- `mesh_v1.blend` mevcut (P04'ten)
- C03 Topology Critic "quad_ratio < %70" raporladı **veya**
- Kullanıcı açıkça "retopology yap" dedi

### Atlama Koşulu
Quad ratio zaten %75+ ise (P04 sonrası yeterince temiz) → skip.

### Postconditions
- `retopo_v1.blend` mevcut (yeni temiz mesh)
- Tris/quad ratio iyileşmiş
- Bone vertex groups **kaybolur** — P08 Skinner yeniden çalıştırılmalı
- `TopologyManifest.json` yazılmış

---

## 3. INPUTS

```
mesh_v1.blend
MeshManifest.json
BudgetSpec.json
```

---

## 4. OUTPUTS

### 4.1 TopologyManifest.json

```json
{
  "manifest_version": "1.0",
  "method_used": "quadriflow" | "instant_meshes" | "decimate_planar",
  "before": {
    "tris": 11842, "quads": 0, "ngons": 4, "quad_ratio": 0.0
  },
  "after": {
    "tris": 2456, "quads": 4180, "ngons": 0, "quad_ratio": 0.77
  },
  "vertex_count_before": 6234,
  "vertex_count_after": 5118,
  "edge_flow_quality": "good",
  "warning_vertex_groups_lost": true,
  "generated_by": "P05_topology_surgeon"
}
```

---

## 5. SYSTEM PROMPT

```
═══════════════════════════════════════════════════════════════
SEN TOPOLOJİ CERRAHISIN.
═══════════════════════════════════════════════════════════════

KİMLİĞİN:
Sen modeling pipeline'da retopology uzmanı bir character TD'sin.
Karmaşık tri-heavy mesh'leri animasyon için uygun quad-dominant
clean mesh'e dönüştürmek senin uzmanlık alanın.

GÖREVİN:
P04'ün ham çıktısını al, anatomik edge flow'a sadık şekilde
retopo et. Eklem yerlerinde edge loop yarat. Quad ratio %75+
hedefle.

KESİN KURALLAR:

  K1. Quad-dominant topology hedefi: hexagonal/triangular yerine
      4-köşeli yüzeyler. Animasyonda düzgün deforme olur.

  K2. Eklem yerlerinde (omuz, dirsek, diz, kalça, çene) edge loop
      yarat. Bunlar bükülmede mesh'in catastrophic fail olmasını
      önler.

  K3. Vertex count'u %50-70 oranında azalt (eğer kullanıcı budget
      tris hedefiyle uyumluysa).

  K4. Asla kullanıcıya "manuel retopo yap" demek YOK — otomatik
      tool zincirini kullan, başarısızsa fallback'a düş.

  K5. Yeni mesh'in armature'la origin'i aynı kalmalı.

═══════════════════════════════════════════════════════════════
```

---

## 6. WORKFLOW

### 6.1 Method Tespiti

```python
def detect_retopo_method():
    # Önce Instant Meshes binary'yi PATH'te ara
    import shutil
    if shutil.which("instant-meshes") or shutil.which("Instant Meshes"):
        return "instant_meshes"
    
    # QuadriFlow Blender built-in (4.0+)
    return "quadriflow"
    # Hiç çalışmazsa: "decimate_planar"
```

### 6.2 QuadriFlow (Blender Built-in)

```python
def retopo_quadriflow(mesh_obj, target_faces=4000):
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.mode_set(mode='OBJECT')
    
    # QuadriFlow remesh
    bpy.ops.object.quadriflow_remesh(
        target_faces=target_faces,
        use_paint_symmetry=True,  # X mirror
        smooth_normals=True,
    )
```

### 6.3 Instant Meshes (External Binary)

```python
def retopo_instant_meshes(mesh_obj, target_verts=5000):
    """
    1. Mesh'i .obj export
    2. instant-meshes CLI ile retopo
    3. Sonucu import + replace
    """
    import subprocess
    import tempfile
    
    tmp_dir = Path(tempfile.mkdtemp())
    in_path = tmp_dir / "in.obj"
    out_path = tmp_dir / "out.obj"
    
    # Export
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.select_all(action='DESELECT')
    mesh_obj.select_set(True)
    bpy.ops.wm.obj_export(filepath=str(in_path),
                            export_selected_objects=True)
    
    # Instant Meshes CLI
    result = subprocess.run(
        ["instant-meshes", str(in_path), "-o", str(out_path),
         "-v", str(target_verts), "-D", "-r", "0", "-p", "4"],
        capture_output=True, text=True, timeout=300,
    )
    
    if result.returncode != 0:
        return False
    
    # Import sonucu
    old_name = mesh_obj.name
    bpy.data.objects.remove(mesh_obj, do_unlink=True)
    
    bpy.ops.wm.obj_import(filepath=str(out_path))
    new_obj = bpy.context.selected_objects[0]
    new_obj.name = old_name
    
    return True
```

### 6.4 Decimate Planar Fallback

```python
def retopo_decimate_planar(mesh_obj, angle_limit_deg=10):
    """Düşük kalite ama her zaman çalışır."""
    # Planar decimate: koplanar yüzeyleri birleştir
    dec = mesh_obj.modifiers.new("DecimatePlanar", 'DECIMATE')
    dec.decimate_type = 'DISSOLVE'
    dec.angle_limit = math.radians(angle_limit_deg)
    
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.modifier_apply(modifier=dec.name)
```

---

## 7. VALIDATION

| # | Kriter | Hata |
|---|---|---|
| V1 | Quad ratio iyileşti (yeni > eski) | warning: değişmedi → retopo başarısız |
| V2 | Mesh hala manifold | error: retopo bozdu → undo |
| V3 | Origin (0,0,0)'da | error: transform apply |
| V4 | Vertex count budget'a uygun | warning |

---

## 8. FAILURE MODES

### F1: QuadriFlow timeout (>5 dk)
**Recovery:** target_faces'i düşür (4000 → 2000), tekrar dene.

### F2: Instant Meshes binary yok
**Recovery:** QuadriFlow'a düş.

### F3: Retopo sonucu mesh corrupted (non-manifold)
**Recovery:** Original mesh'i restore et, fallback method'a düş.

---

## 9. KULLANICI UYARISI

Bu ajan **mesh'i yeniler**, yani **bone vertex group'ları kaybolur**. Orchestrator kullanıcıya:

> ⚠️ Retopology sonrası mesh yenilendi. Vertex groups silindi. P08 Skinner yeniden çalıştırılmalı (~5 dk). Devam edeyim mi?

`scripts/production/build_topology.py` executable.
