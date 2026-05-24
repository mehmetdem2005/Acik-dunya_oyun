# Agent P06: UV Cartographer (UV Kartografı)

```yaml
agent_id: uv_cartographer
agent_name_tr: UV Kartografı
agent_name_en: UV Cartographer
category: production
order_index: 6
implementation_mode: subprocess
estimated_duration_minutes: 2-5
critical_path: false  # opsiyonel ama texture'lı yaratık için zorunlu
```

---

## 1. ROLE SUMMARY

Mesh'in **UV unwrap**'ini yapar. Yani 3D mesh'i 2D düzleme açar — texture pixel'lerinin mesh yüzeyine nasıl haritalanacağını belirler.

**Strateji:**
1. Seam'leri akıllı yerleştir (simetri ekseni, üye-gövde birleşimi, eklem yerleri)
2. Smart UV Project veya marked-seam unwrap
3. Pack islands (UV space'i optimal kullan)
4. UV overlap kontrolü
5. UV stretch map render et (critic için)

**Bu adım atlanırsa** texture mesh'e doğru oturmaz, "texture kayması" olur.

---

## 2. WHEN INVOKED

### Preconditions
- `mesh_v1.blend` mevcut (P04'ten) veya `retopo_v1.blend` (P05'ten)
- Mesh manifold + watertight
- `BudgetSpec.texture_budget.atlas_strategy` tanımlı

### Postconditions
- Mesh'te `UVMap` adlı UV layer mevcut
- UV islands pack edilmiş (texture space'in %85+ kullanılmış)
- UV overlap yok (her face unique UV koordinatlı)
- `UVManifest.json` yazılmış
- (Opsiyonel) UV stretch map render

---

## 3. INPUTS

```
mesh_v1.blend (or retopo_v1.blend)
MeshManifest.json
BudgetSpec.json
```

---

## 4. OUTPUTS

### 4.1 UVManifest.json

```json
{
  "manifest_version": "1.0",
  "uv_layer_name": "UVMap",
  "method_used": "smart_project_marked_seams",
  "seam_count": 412,
  "island_count": 18,
  "uv_space_utilization": 0.87,
  "has_overlap": false,
  "stretch_metric_max": 0.05,
  "stretch_metric_mean": 0.018,
  "texel_density_uniform": true,
  "generated_by": "P06_uv_cartographer"
}
```

---

## 5. SYSTEM PROMPT

```
═══════════════════════════════════════════════════════════════
SEN UV KARTOGRAFISIN.
═══════════════════════════════════════════════════════════════

KİMLİĞİN:
UV unwrap uzmanı character TD'sin. Seam yerleştirme, island
packing, texel density consistency, ve atlas verim konularında
uzmansın. Mobile texture budget'ları dikkate alarak işin %85+
texture space verim olmalı.

KESİN KURALLAR:

  K1. Seam'leri **görünmez** yerlere koy:
      - Simetri ekseni (X=0 sırt çizgisi)
      - Üye-gövde birleşim ringi (kol/bacak başlangıcı)
      - Kuyruk alt çizgisi
      - Karın orta hattı
      - Kulak iç kenarı
      Asla yüzde, dişlerde, görünür bölgelerde seam OLAMAZ.

  K2. UV island'lar non-overlapping. İki face aynı UV alanını
      paylaşamaz (texture overlap = visible artifact).

  K3. Texel density tüm yüzeyde uniform (±%15 tolerans).
      Yüz/gözde aynı density, popoda da aynı density olmalı.

  K4. UV space utilization > %85. İslands tightly packed, dead
      space minimum.

  K5. Stretch metric ortalama < 0.05. Yüksek stretch = texture
      görünür şekilde çekilir.

═══════════════════════════════════════════════════════════════
```

---

## 6. WORKFLOW

### 6.1 Seam Marking

```python
def mark_seams_quadruped(mesh_obj):
    """
    Quadruped için anatomik seam yerleri.
    Vertex coordinate'lere göre tespit eder ve seam mark eder.
    """
    import bmesh
    
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(mesh_obj.data)
    
    # Symmetry seam: X=0 edge'leri
    for edge in bm.edges:
        v1, v2 = edge.verts
        if abs(v1.co.x) < 0.01 and abs(v2.co.x) < 0.01:
            edge.seam = True
    
    # Belly seam: karın alt çizgisi (Z minimum'a yakın)
    bbox_z_min = min(v.co.z for v in bm.verts)
    for edge in bm.edges:
        v1, v2 = edge.verts
        if v1.co.z < bbox_z_min + 0.05 and v2.co.z < bbox_z_min + 0.05:
            # Sadece center band (X yakın 0)
            if abs(v1.co.x) < 0.05 and abs(v2.co.x) < 0.05:
                edge.seam = True
    
    bmesh.update_edit_mesh(mesh_obj.data)
    bpy.ops.object.mode_set(mode='OBJECT')


def mark_seams_at_joints(mesh_obj, armature_obj):
    """
    Üye-gövde birleşim yerlerinde ring seam mark et.
    Bone vertex group boundary'lerini bul.
    """
    # Her ana bone için (örn: shoulder, hip), vertex group boundary'sinde
    # seam mark et. Bu, mesh büyük topoloji düzgünse otomatik bulunur.
    # Şimdilik basit fallback: Smart UV Project angle limit ile.
    pass  # Smart UV Project bunu hallediyor angle_limit ile
```

### 6.2 Unwrap

```python
def unwrap_marked_seams(mesh_obj):
    """Marked seam'leri kullanarak unwrap."""
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    
    bpy.ops.uv.unwrap(method='ANGLE_BASED', margin=0.005)
    
    bpy.ops.object.mode_set(mode='OBJECT')


def smart_uv_project(mesh_obj, angle_limit=66, island_margin=0.02):
    """Otomatik Smart UV Project (fallback)."""
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    
    bpy.ops.uv.smart_project(
        angle_limit=angle_limit,
        island_margin=island_margin,
        area_weight=0.0,
        correct_aspect=True,
        scale_to_bounds=False,
    )
    
    bpy.ops.object.mode_set(mode='OBJECT')


def pack_islands(mesh_obj, margin=0.005):
    """UV islands'ı atlas'a sıkıca pack."""
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.select_all(action='SELECT')
    
    bpy.ops.uv.pack_islands(
        rotate=True,
        margin=margin,
    )
    
    bpy.ops.object.mode_set(mode='OBJECT')
```

### 6.3 Validation: Overlap + Stretch

```python
def check_uv_overlap(mesh_obj):
    """UV overlap kontrol (face pair'leri için)."""
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.select_all(action='SELECT')
    
    # Built-in select_overlap
    bpy.ops.uv.select_overlap()
    
    # Kaç face overlap'te seçildi
    import bmesh
    bm = bmesh.from_edit_mesh(mesh_obj.data)
    uv_layer = bm.loops.layers.uv.active
    
    overlap_faces = 0
    for face in bm.faces:
        if all(loop[uv_layer].select for loop in face.loops):
            overlap_faces += 1
    
    bpy.ops.object.mode_set(mode='OBJECT')
    
    return overlap_faces


def measure_uv_utilization(mesh_obj):
    """UV space içinde kaç % alan kapsanmış."""
    import bmesh
    
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.mode_set(mode='EDIT')
    
    bm = bmesh.from_edit_mesh(mesh_obj.data)
    uv_layer = bm.loops.layers.uv.active
    
    # Tüm UV vertex'lerinin bbox'ı
    all_u = []
    all_v = []
    for face in bm.faces:
        for loop in face.loops:
            u, v = loop[uv_layer].uv
            all_u.append(u)
            all_v.append(v)
    
    if not all_u:
        bpy.ops.object.mode_set(mode='OBJECT')
        return 0.0
    
    u_min, u_max = min(all_u), max(all_u)
    v_min, v_max = min(all_v), max(all_v)
    
    used_area = (u_max - u_min) * (v_max - v_min)
    
    # Toplam face UV area / total UV space (1×1)
    total_face_area = 0.0
    for face in bm.faces:
        # 3 nokta için cross product alan
        if len(face.loops) >= 3:
            loops = list(face.loops)
            uv1 = Vector(loops[0][uv_layer].uv)
            for i in range(1, len(loops) - 1):
                uv2 = Vector(loops[i][uv_layer].uv)
                uv3 = Vector(loops[i + 1][uv_layer].uv)
                # Triangle alan = 0.5 × |cross|
                edge1 = uv2 - uv1
                edge2 = uv3 - uv1
                cross = abs(edge1.x * edge2.y - edge1.y * edge2.x)
                total_face_area += 0.5 * cross
    
    bpy.ops.object.mode_set(mode='OBJECT')
    
    # Utilization = face area / (1×1 UV space) = total area kullanım
    return min(1.0, total_face_area)


def render_uv_stretch_map(mesh_obj, output_path, resolution=1024):
    """
    UV stretch map render et — kırmızı bölgeler stretching var demek.
    Critic için kanıt görüntü.
    """
    # Bu için viewport overlay veya custom shader gerekir.
    # Basit fallback: UV layout image render.
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.select_all(action='SELECT')
    
    bpy.ops.uv.export_layout(
        filepath=str(output_path),
        size=(resolution, resolution),
        opacity=0.5,
        check_existing=False,
    )
    
    bpy.ops.object.mode_set(mode='OBJECT')
```

---

## 7. VALIDATION CRITERIA

| # | Kriter | Hata |
|---|---|---|
| V1 | UV layer mevcut | error: unwrap yeniden |
| V2 | UV overlap = 0 face | error: pack_islands tekrar, veya manuel seam ekle |
| V3 | UV space utilization > 0.7 (warning < 0.85 ideal) | warning: pack_islands rotate=True |
| V4 | Stretch max < 0.1 | warning: seam yerleştirme yetersiz, manuel review |
| V5 | UV layer name = "UVMap" (Godot convention) | error: rename |

---

## 8. FAILURE MODES

### F1: Marked seam unwrap "no faces selected" hatası
**Recovery:** Edit mode'a mutlaka select all uygula, sonra unwrap.

### F2: Pack islands sonrası utilization < %70
**Recovery:** angle_limit'i değiştir (66 → 45 daha çok island = sıkı pack ama daha çok seam).

### F3: Overlap detected (genelde marked seam yetersiz)
**Recovery:** Seam'leri daha agresif mark et (üye-gövde ring'leri, kuyruk dibi), unwrap tekrar.

---

## 9. IMPLEMENTATION NOTES

`scripts/production/build_uv.py`:

```python
subprocess.run([
    "blender", "--background", str(run_dir / "blender_scenes/mesh_v1.blend"),
    "--python", "scripts/production/build_uv.py",
    "--",
    "--budget", str(run_dir / "BudgetSpec.json"),
    "--output-blend", str(run_dir / "blender_scenes/uv_v1.blend"),
], timeout=180)
```
