# Agent P04: Mesh Sculptor (Mesh Heykeltıraşı)

```yaml
agent_id: mesh_sculptor
agent_name_tr: Mesh Heykeltıraşı
agent_name_en: Mesh Sculptor
category: production
order_index: 4
implementation_mode: subprocess
estimated_duration_minutes: 10-25
critical_path: true
```

---

## 1. ROLE SUMMARY

İskelet hazır olduktan sonra çağrılır. Skeleton bone'larından **eğriler** türetir, eğrilere **Geometry Nodes** ile kalınlık (kas/et) sarar, sonuçları boolean union + voxel remesh ile **tek dikişsiz mesh**'e çevirir. Çıktı: yaratığın iskelete sadık, anatomy-class proportional doğru ana mesh'i.

**"Inside-out modeling"** felsefesi: mesh'i tahmin etmek yerine **kemiklerin etrafına et giydirmek**. Bu, "düz boru" problemini kökten önler çünkü mesh skeleton'a matematiksel olarak bağımlıdır.

---

## 2. WHEN INVOKED

### Preconditions
- `SkeletonBlueprint.json` mevcut + valid
- `skeleton_v1.blend` mevcut (P03 üretti)
- C01-C02-C03 critic'ler P03 skeleton'ı onaylamış
- Kullanıcı "mesh oluştur" diyerek devam onayı vermiş

### Postconditions
- `MeshManifest.json` mevcut (mesh metadata)
- `mesh_v1.blend` mevcut (armature + base mesh)
- Mesh tris sayısı `BudgetSpec.polygon_budget.lod0_tris_target` ±%15 içinde
- Mesh manifold (watertight)
- Skeleton hala sahnede, mesh ile aynı origin

### Sıralama
- **Önceki:** P03 Skeleton Architect
- **Sonraki:** P05 Topology Surgeon (retopology, opsiyonel) veya P06 UV Cartographer
- **Critic:** C01 Vision + C03 Topology + C05 Mobile Perf

---

## 3. INPUTS

```python
# Required
SkeletonBlueprint.json         # P03 çıktısı
CreatureSpec.json
BudgetSpec.json
anatomy_class.md               # references/anatomy_classes/<class>.md
skeleton_v1.blend              # P03 üretti

# Optional
user_radius_overrides.json     # kullanıcı body/limb kalınlığını manuel set etmek isterse
reference_silhouette.png       # vision için referans silüet
```

---

## 4. OUTPUTS

### 4.1 MeshManifest.json

```json
{
  "manifest_version": "1.0",
  "creature_id": "kurt_001",
  "base_mesh_object_name": "creature_mesh",
  "tris_count_actual": 11842,
  "tris_count_target": 12000,
  "verts_count": 6234,
  "faces_count": 6021,
  "is_manifold": true,
  "is_watertight": true,
  "bbox_min": [-0.42, -0.65, 0.02],
  "bbox_max": [0.42, 0.55, 0.85],
  "body_parts_generated": {
    "spine_mesh": {"tris": 2840, "method": "curve_to_mesh"},
    "leg_front_L": {"tris": 980, "method": "curve_to_mesh"},
    "leg_front_R": {"tris": 980, "method": "curve_to_mesh"},
    "leg_rear_L": {"tris": 1120, "method": "curve_to_mesh"},
    "leg_rear_R": {"tris": 1120, "method": "curve_to_mesh"},
    "neck_head": {"tris": 1850, "method": "curve_to_mesh + sphere_blend"},
    "tail": {"tris": 1280, "method": "curve_to_mesh_tapered"},
    "ears": {"tris": 360, "method": "primitive_modified"},
    "jaw": {"tris": 320, "method": "primitive_modified"}
  },
  "radius_profiles_used": {
    "body_max_radius": 0.16,
    "neck_radius": 0.10,
    "head_radius": 0.13,
    "leg_upper_radius": 0.07,
    "leg_lower_radius": 0.045,
    "paw_radius": 0.05,
    "tail_base_radius": 0.06,
    "tail_tip_radius": 0.005
  },
  "subdivision_level_used": 1,
  "voxel_remesh_size": 0.012,
  "decimate_ratio_used": 1.0,
  "generated_by": "P04_mesh_sculptor",
  "generated_at": "2026-05-24T..."
}
```

### 4.2 mesh_v1.blend

P03'ten gelen armature **silinmez**. Aynı dosyaya base_mesh objesi eklenir, ikisi birlikte saklanır. Armature parent ataması ve skinning P08'de yapılır, P04'te değil.

---

## 5. SYSTEM PROMPT

```
═══════════════════════════════════════════════════════════════
SEN MESH HEYKELTIRAŞISIN.
═══════════════════════════════════════════════════════════════

KİMLİĞİN:
Sen AAA oyun stüdyolarında çalışmış kıdemli bir character artist'sin.
Uzmanlık alanın: organik form modelleme, Geometry Nodes prosedürel
mesh üretimi, ve kemiklerin etrafına anatomik olarak doğru et
giydirme. Naughty Dog'un creature pipeline'ından, ZBrush'tan, ve
Houdini'den geçen "procedural-first then sculpt" felsefesini
benimsiyorsun.

GÖREVİN:
SkeletonBlueprint + CreatureSpec + BudgetSpec'i al, skeleton'a sadık
bir base mesh üret. Mesh poly bütçesinde kalsın, watertight (dikişsiz)
olsun, anatomic proportions doğru olsun.

KESİN KURALLAR:

  K1. Vertex'leri tek tek yazma. Asla `bmesh.verts.new(x, y, z)`
      döngülerine girme. Mesh'in OMURGASI = Geometry Nodes graph'ı
      olmalı. Curve-to-Mesh ve modifier zinciri kullan.

  K2. Skeleton bone'larından CURVE türet. Her IK chain ve spine
      zinciri kendi Bezier curve'ünü oluşturur. Bu curve'lerin
      kontrol noktaları bone head ve tail'lerine SADIK olmak zorunda.

  K3. Her body part'ın radius profili anatomy class'tan ve BudgetSpec'ten
      türemiş olsun. Kafa = küre-benzeri (spherical interp), gövde =
      ellipsoid (kalın orta, ince uç), bacaklar = tapered cylinder
      (üst kalın, alt ince), kuyruk = strongly tapered.

  K4. Final mesh MANIFOLD (her edge tam 2 face'e ait) ve WATERTIGHT
      (kapalı, delik yok) olmak zorunda. Boolean Union + Voxel Remesh
      garantili manifold üretir.

  K5. Tris sayısı BudgetSpec.polygon_budget.lod0_tris_target ±%15
      içinde kalmalı. Aşıyorsa Decimate ile düşür, az ise Subdivision
      ile artır.

  K6. Mesh origin = world origin (0,0,0) = skeleton origin. Asla
      mesh'i transform etme.

  K7. Mesh ile skeleton'ı parent ETMİYORSUN. Bu P08 Skinner'ın işi.
      Sadece base mesh üret ve sahnede armature ile yan yana bırak.

YAPMA:

  - Subsurf level 3+ kullanma (mobile zorlanır)
  - Bevel/Edge Loop manuel ekleme (Voxel Remesh sonrası anlamsız)
  - Vertex group atama (skinning değil burada)
  - Material atama (P11'in işi)

═══════════════════════════════════════════════════════════════
```

---

## 6. WORKFLOW

### 6.1 Skeleton'dan Curve Türetme

Her bone chain'ini bir Bezier curve'e çevir. Curve'ün noktaları bone'ların head ve tail koordinatları.

```python
def skeleton_to_curves(blueprint):
    """
    Skeleton'dan farklı body parts için curve'ler türet.
    
    Returns: {part_name: list_of_points}
    """
    curves = {}
    
    bones_by_name = {b["name"]: b for b in blueprint["bones"]}
    
    # 1. Spine curve: spine_00 head → spine_00 tail → spine_01 tail → ... → head tail
    spine_points = []
    spine_bones = sorted(
        [b for b in blueprint["bones"] if b["name"].startswith("spine_")],
        key=lambda b: int(b["name"].split("_")[1])
    )
    if spine_bones:
        spine_points.append(spine_bones[0]["head_local"])
        for sb in spine_bones:
            spine_points.append(sb["tail_local"])
    
    # Neck + head'i de spine curve'üne katmak (continuous body curve)
    neck_bones = sorted(
        [b for b in blueprint["bones"] if b["name"].startswith("neck_")],
        key=lambda b: int(b["name"].split("_")[1])
    )
    for nb in neck_bones:
        spine_points.append(nb["tail_local"])
    
    head_bone = bones_by_name.get("head")
    if head_bone:
        spine_points.append(head_bone["tail_local"])
    
    curves["spine"] = spine_points
    
    # 2. Kuyruk curve (spine'dan ayrı, çünkü daha keskin tapering)
    tail_bones = sorted(
        [b for b in blueprint["bones"] if b["name"].startswith("tail_")],
        key=lambda b: int(b["name"].split("_")[1])
    )
    if tail_bones:
        tail_points = [tail_bones[0]["head_local"]]
        for tb in tail_bones:
            tail_points.append(tb["tail_local"])
        curves["tail"] = tail_points
    
    # 3. Bacaklar (4 chain)
    for side in ["L", "R"]:
        # Ön bacak
        front_chain = ["shoulder", "upper_arm", "forearm", "wrist"]
        front_points = []
        for bname in front_chain:
            bone = bones_by_name.get(f"{bname}_{side}")
            if bone:
                if not front_points:
                    front_points.append(bone["head_local"])
                front_points.append(bone["tail_local"])
        if front_points:
            curves[f"leg_front_{side}"] = front_points
        
        # Arka bacak (5 bone chain digitigrade)
        rear_chain = ["hip", "thigh", "shin", "ankle", "foot"]
        rear_points = []
        for bname in rear_chain:
            bone = bones_by_name.get(f"{bname}_{side}")
            if bone:
                if not rear_points:
                    rear_points.append(bone["head_local"])
                rear_points.append(bone["tail_local"])
        if rear_points:
            curves[f"leg_rear_{side}"] = rear_points
    
    return curves
```

### 6.2 Radius Profili Hesaplama

Her body part için, anatomy class + body_length'e göre radius profili (curve_t → radius) hesapla.

```python
def compute_radius_profiles(creature_spec, anatomy_class_data, body_length):
    """
    Her part için (t_normalized, radius) tuple listesi döndürür.
    t = 0..1 curve boyunca, radius = metre.
    """
    profiles = {}
    
    # Anatomy class'tan oranlar
    chest_width = anatomy_class_data.get("chest_width_ratio", 0.22) * body_length
    chest_depth = anatomy_class_data.get("chest_depth_ratio", 0.28) * body_length
    # Body ana radius = ortalama (chest_width ve chest_depth ortalamalı yarısı)
    body_max_r = (chest_width + chest_depth) / 4
    
    neck_r_ratio = anatomy_class_data.get("neck_radius_ratio", 0.55)
    head_r_ratio = anatomy_class_data.get("head_radius_ratio", 0.75)
    
    # User mods (stilize için)
    mods = creature_spec.get("user_modifications", {})
    head_mult = mods.get("head_size_multiplier", 1.0)
    muscle_def = mods.get("muscle_definition", "normal")
    
    muscle_boost = {"subtle": 0.85, "normal": 1.0, "exaggerated": 1.2, "extreme": 1.4}.get(muscle_def, 1.0)
    
    # Spine profile: kuyruk başlangıcı (t=0) → kalça (t=0.1) → omuz (t=0.5) → boyun (t=0.8) → baş (t=1.0)
    # Spine + neck + head'i tek curve yaptığımız için:
    profiles["spine"] = [
        # (t, radius)
        (0.0, body_max_r * 0.85),                # kalça (en arka)
        (0.15, body_max_r * 1.0 * muscle_boost), # arka kas yumrusu (gluteus)
        (0.45, body_max_r * 0.95 * muscle_boost),# göğüs orta (rib cage)
        (0.55, body_max_r * 1.05 * muscle_boost),# göğüs ön (chest peak)
        (0.65, body_max_r * 0.85),               # omuz (göğüsten ince)
        (0.75, body_max_r * neck_r_ratio),       # boyun başlangıcı
        (0.85, body_max_r * neck_r_ratio * 0.9), # boyun ortası
        (0.92, body_max_r * head_r_ratio * head_mult),  # kafa başlangıcı
        (1.0, body_max_r * head_r_ratio * 0.85 * head_mult),  # burun
    ]
    
    # Kuyruk: kalın kalça yanında, ince uçta
    profiles["tail"] = [
        (0.0, body_max_r * 0.4),    # kuyruk başı
        (0.3, body_max_r * 0.3),
        (0.7, body_max_r * 0.12),
        (1.0, body_max_r * 0.03),   # neredeyse sıfır
    ]
    
    # Bacaklar (ön ve arka biraz farklı, ön bacak biraz daha ince)
    leg_upper_r = body_max_r * 0.4 * muscle_boost
    leg_lower_r = body_max_r * 0.22
    paw_r = body_max_r * 0.27
    
    for side in ["L", "R"]:
        profiles[f"leg_front_{side}"] = [
            (0.0, body_max_r * 0.5 * muscle_boost),  # omuz birleşim, kalın
            (0.15, leg_upper_r),                      # üst kol (humerus)
            (0.45, leg_upper_r * 0.8),                # dirsek
            (0.55, leg_lower_r * 1.05),               # önkol başlangıcı
            (0.85, leg_lower_r),                      # bilek üstü
            (0.92, paw_r),                            # pad
            (1.0, paw_r * 0.7),                       # parmak uçları
        ]
        profiles[f"leg_rear_{side}"] = [
            (0.0, body_max_r * 0.55 * muscle_boost), # kalça birleşim, geniş kas
            (0.20, leg_upper_r * 1.1),                # uyluk (quadriceps zone)
            (0.45, leg_upper_r * 0.7),                # diz
            (0.55, leg_lower_r * 1.0),                # baldır
            (0.75, leg_lower_r * 0.9),                # ankle ("görsel diz")
            (0.88, leg_lower_r * 0.95),               # metatarsus
            (0.95, paw_r),                            # paw pad
            (1.0, paw_r * 0.65),                      # parmak uçları
        ]
    
    return profiles
```

### 6.3 Geometry Nodes Graph Kurma

Her body part için bir curve obj + GN modifier setup'ı.

```python
def create_curve_object(name, points, smooth=True):
    """Bezier curve obj oluştur."""
    curve_data = bpy.data.curves.new(name=f"{name}_curve", type='CURVE')
    curve_data.dimensions = '3D'
    curve_data.resolution_u = 12  # spline interpolation kalitesi
    
    spline = curve_data.splines.new('BEZIER')
    spline.bezier_points.add(len(points) - 1)  # 1 default
    
    for i, p in enumerate(points):
        bp = spline.bezier_points[i]
        bp.co = Vector(p)
        if smooth:
            bp.handle_left_type = 'AUTO'
            bp.handle_right_type = 'AUTO'
    
    obj = bpy.data.objects.new(name, curve_data)
    bpy.context.collection.objects.link(obj)
    return obj


def build_geometry_nodes_flesh(curve_obj, radius_profile, profile_resolution=12,
                                 segment_resolution=24):
    """
    Curve obj'ye Geometry Nodes modifier ekle.
    Graph:
        Curve → Set Spline Resolution → Set Curve Radius (Float Curve) →
        Curve to Mesh (Circle Profile, resolution=profile_resolution) →
        Output
    """
    mod = curve_obj.modifiers.new(name="FleshGen", type='NODES')
    
    # Yeni node group
    ng = bpy.data.node_groups.new("FleshNodeGroup", 'GeometryNodeTree')
    mod.node_group = ng
    
    # Interface
    ng.interface.new_socket(name="Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket(name="Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    
    # Input/Output nodes
    n_input = ng.nodes.new('NodeGroupInput')
    n_output = ng.nodes.new('NodeGroupOutput')
    n_input.location = (-800, 0)
    n_output.location = (800, 0)
    
    # Set Spline Resolution (curve segment density)
    n_resolution = ng.nodes.new('GeometryNodeSetSplineResolution')
    n_resolution.location = (-600, 0)
    n_resolution.inputs['Resolution'].default_value = segment_resolution
    
    # Spline Parameter (t değeri)
    n_spline_param = ng.nodes.new('GeometryNodeSplineParameter')
    n_spline_param.location = (-600, -200)
    
    # Float Curve (radius profile)
    n_float_curve = ng.nodes.new('ShaderNodeFloatCurve')
    n_float_curve.location = (-400, -200)
    n_float_curve.mapping.use_clip = False
    
    # Radius profile point'lerini Float Curve'e basacağız
    curve_mapping = n_float_curve.mapping
    fc = curve_mapping.curves[0]
    
    # Mevcut default 2 noktayı sil, profile'ı uygula
    while len(fc.points) > 2:
        fc.points.remove(fc.points[1])  # 2 noktayı koru, ortasını silmek için
    
    for i, (t, r) in enumerate(radius_profile):
        if i < 2:
            # Mevcut noktaları update
            fc.points[i].location = (t, r)
        else:
            # Yeni nokta ekle
            fc.points.new(t, r)
    
    curve_mapping.update()
    
    # Set Curve Radius
    n_set_radius = ng.nodes.new('GeometryNodeSetCurveRadius')
    n_set_radius.location = (-200, 0)
    
    # Curve to Mesh
    n_curve_to_mesh = ng.nodes.new('GeometryNodeCurveToMesh')
    n_curve_to_mesh.location = (200, 0)
    
    # Profile circle
    n_circle = ng.nodes.new('GeometryNodeCurvePrimitiveCircle')
    n_circle.location = (0, -300)
    n_circle.inputs['Resolution'].default_value = profile_resolution
    n_circle.inputs['Radius'].default_value = 1.0  # radius modülasyonu Set Curve Radius'tan gelecek
    
    # Set Shade Smooth (Blender 4.x'te face shade smooth)
    n_shade = ng.nodes.new('GeometryNodeSetShadeSmooth')
    n_shade.location = (500, 0)
    
    # Bağlantılar
    links = ng.links
    links.new(n_input.outputs[0], n_resolution.inputs['Curve'])
    links.new(n_resolution.outputs['Curve'], n_set_radius.inputs['Curve'])
    links.new(n_spline_param.outputs['Factor'], n_float_curve.inputs['Value'])
    links.new(n_float_curve.outputs['Value'], n_set_radius.inputs['Radius'])
    links.new(n_set_radius.outputs['Curve'], n_curve_to_mesh.inputs['Curve'])
    links.new(n_circle.outputs['Curve'], n_curve_to_mesh.inputs['Profile Curve'])
    links.new(n_curve_to_mesh.outputs['Mesh'], n_shade.inputs['Geometry'])
    links.new(n_shade.outputs['Geometry'], n_output.inputs[0])
    
    return mod
```

### 6.4 Boolean Union (Tüm Parçaları Birleştir)

```python
def union_all_parts(part_objects, target_object_name="creature_mesh"):
    """
    Tüm part'ları boolean union ile tek mesh'e topla.
    
    Strateji: en büyük (spine) base alır, üstüne diğerleri union edilir.
    """
    # Önce her part'ın GN modifier'larını apply et (mesh haline gel)
    for obj in part_objects:
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        # Curve'ü mesh'e convert
        bpy.ops.object.convert(target='MESH')
        obj.select_set(False)
    
    # Base = spine
    base = next((o for o in part_objects if "spine" in o.name), part_objects[0])
    base.name = target_object_name
    
    # Diğerlerini union et
    for obj in part_objects:
        if obj == base:
            continue
        
        bool_mod = base.modifiers.new(name=f"Union_{obj.name}", type='BOOLEAN')
        bool_mod.operation = 'UNION'
        bool_mod.object = obj
        bool_mod.solver = 'EXACT'  # FAST'tan daha sağlam
        
        bpy.context.view_layer.objects.active = base
        bpy.ops.object.modifier_apply(modifier=bool_mod.name)
        
        # Diğerini sil
        bpy.data.objects.remove(obj, do_unlink=True)
    
    return base
```

### 6.5 Voxel Remesh (Manifold Garantisi)

```python
def voxel_remesh_for_manifold(mesh_obj, voxel_size=0.012):
    """
    Voxel Remesh: mesh'i voxel grid'ine convert eder, manifold çıkartır.
    voxel_size küçük olur → detay artar, poly artar.
    
    voxel_size default = body_length / 100. Mobil için 0.012-0.020 arası iyi.
    """
    bpy.context.view_layer.objects.active = mesh_obj
    
    mesh_data = mesh_obj.data
    mesh_data.remesh_mode = 'VOXEL'
    mesh_data.remesh_voxel_size = voxel_size
    mesh_data.use_remesh_smooth_normals = True
    mesh_data.use_remesh_preserve_volume = True
    
    bpy.ops.object.voxel_remesh()


def subdivide_smooth(mesh_obj, level=1):
    """Subdivision Surface modifier."""
    sub = mesh_obj.modifiers.new(name="Subsurf", type='SUBSURF')
    sub.levels = level
    sub.render_levels = level
    
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.modifier_apply(modifier=sub.name)


def decimate_to_target_tris(mesh_obj, target_tris):
    """
    Mevcut tris sayısını target'a indirir Decimate modifier ile.
    """
    current_tris = sum(1 for f in mesh_obj.data.polygons for _ in f.loop_indices) // 3  # approx
    # Daha doğru: triangulate edip say
    # ...
    
    if current_tris <= target_tris:
        return  # zaten içerde
    
    ratio = target_tris / current_tris
    
    dec = mesh_obj.modifiers.new(name="Decimate", type='DECIMATE')
    dec.ratio = ratio
    dec.decimate_type = 'COLLAPSE'
    
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.modifier_apply(modifier=dec.name)
```

### 6.6 Validation

```python
def validate_mesh(mesh_obj, budget_spec):
    """Mesh'in production-hazır olup olmadığını kontrol et."""
    import bmesh
    
    results = {"errors": [], "warnings": []}
    
    bm = bmesh.new()
    bm.from_mesh(mesh_obj.data)
    bm.faces.ensure_lookup_table()
    
    # Manifold check
    non_manifold_edges = [e for e in bm.edges if not e.is_manifold]
    if non_manifold_edges:
        results["errors"].append(f"Non-manifold edges: {len(non_manifold_edges)}")
    
    # Watertight check
    boundary_edges = [e for e in bm.edges if len(e.link_faces) < 2]
    if boundary_edges:
        results["errors"].append(f"Watertight değil, boundary edges: {len(boundary_edges)}")
    
    # NaN/Inf vertex check
    nan_verts = [v for v in bm.verts
                  if any(c != c or abs(c) == float('inf') for c in v.co)]
    if nan_verts:
        results["errors"].append(f"NaN/Inf vertex: {len(nan_verts)}")
    
    # Tris count
    tris_count = sum(len(f.verts) - 2 for f in bm.faces)
    target = budget_spec["polygon_budget"]["lod0_tris_target"]
    hard_max = budget_spec["polygon_budget"]["lod0_tris_hard_max"]
    
    if tris_count > hard_max:
        results["errors"].append(f"Tris bütçe aşıldı: {tris_count} > {hard_max}")
    elif tris_count > target * 1.15:
        results["warnings"].append(f"Tris hedeften fazla: {tris_count} vs {target}")
    elif tris_count < target * 0.85:
        results["warnings"].append(f"Tris hedeften az: {tris_count} vs {target}")
    
    # Bounding box sanity
    bbox_min = Vector((min(v.co.x for v in bm.verts),
                       min(v.co.y for v in bm.verts),
                       min(v.co.z for v in bm.verts)))
    bbox_max = Vector((max(v.co.x for v in bm.verts),
                       max(v.co.y for v in bm.verts),
                       max(v.co.z for v in bm.verts)))
    
    bm.free()
    
    return results, tris_count, list(bbox_min), list(bbox_max)
```

---

## 7. VALIDATION CRITERIA

| # | Kriter | Hata |
|---|---|---|
| V1 | Mesh manifold | error: voxel remesh ile yeniden çalıştır, voxel_size düşür |
| V2 | Mesh watertight (boundary edge yok) | error: boolean union FAST yerine EXACT yap, voxel remesh |
| V3 | NaN/Inf vertex yok | error: corrupted, scene'i temizle, yeniden başla |
| V4 | Tris ∈ [target×0.85, target×1.15] | warning + Decimate ratio ayarla |
| V5 | Bounding box anatomik proportions ile uyumlu | warning: radius profile'larını tekrar gözden geçir |
| V6 | Mesh origin = (0,0,0) | error: transform apply, origin reset |
| V7 | Tek mesh objesi (parçalar union edilmiş) | error: union eksik kalmış, tekrar çalıştır |
| V8 | Subdivision sonrası shade smooth | warning: shade smooth uygula |

---

## 8. FAILURE MODES & RECOVERY

### F1: Boolean Union hata fırlattı (overlapping faces)
**Recovery:** FAST solver dene, başarısızsa voxel remesh ile baştan başla, part'ları intermediate manifold yap (her partın kendi voxel remesh'ini al, sonra union).

### F2: Voxel Remesh çok yavaş (>5 dk)
**Recovery:** voxel_size'ı 2× büyüt (detay azalt), tekrar dene. 3 deneme sonrası hala yavaşsa user'a "Mesh çok karmaşık, basitleştirmek için stilize seviyesini düşürelim mi?" sor.

### F3: Tris hedef altında çıktı (yetersiz detay)
**Recovery:** Subdivision level'ı artır (1→2). Hala düşükse profile circle resolution'ı artır (12→16→24).

### F4: Tris hedef çok üstünde
**Recovery:** Decimate ratio set et. Sonra QEM (quadric edge collapse) ile cleanup.

### F5: Mesh skeleton'la kötü hizalı (offset)
**Recovery:** Mesh ve armature'in world space koordinatlarını karşılaştır. Mesh'e Apply All Transforms uygula, origin (0,0,0)'a set et.

### F6: Anatomy class'tan radius oranı eksik
**Recovery:** Default değerler kullan, log'a yaz, anatomy class'a "missing field" patch öner.

---

## 9. EXAMPLE I/O

### Input — kurt için

CreatureSpec (body_length=1.2m, anatomy_class=mammalia_quadruped, stylization=stylized_realistic) + BudgetSpec (lod0_tris_target=12000, atlas_strategy=single_atlas).

### Beklenen Output

```
[mesh_sculptor] Skeleton'dan curve türetiliyor...
  ✓ spine curve: 9 control point (spine + neck + head)
  ✓ tail curve: 8 control point
  ✓ leg_front_L curve: 5 control point
  ✓ leg_front_R curve: 5 control point
  ✓ leg_rear_L curve: 6 control point (digitigrade)
  ✓ leg_rear_R curve: 6 control point

[mesh_sculptor] Radius profilleri hesaplanıyor...
  ✓ body_max_radius: 0.150 m
  ✓ tail_base: 0.060 m, tail_tip: 0.005 m
  ✓ leg_upper: 0.060 m, paw: 0.040 m

[mesh_sculptor] Geometry Nodes graph kurularak et giydiriliyor...
  ✓ 7 curve obj + GN modifier

[mesh_sculptor] Mesh convert ve boolean union...
  ✓ Tek mesh: creature_mesh

[mesh_sculptor] Voxel Remesh (size=0.012)...
  ✓ Manifold OK

[mesh_sculptor] Subdivision Surface level 1...
[mesh_sculptor] Decimate to target tris (~12000)...
  ✓ Final tris: 11842

[mesh_sculptor] Validation...
  ✓ Manifold: pass
  ✓ Watertight: pass
  ✓ Tris budget: pass (11842 ∈ [10200, 13800])
  ✓ Bounding box: pass

[mesh_sculptor] mesh_v1.blend kaydedildi
```

---

## 10. IMPLEMENTATION NOTES

Bu ajan **subprocess** mode'da çalışır. Orchestrator akışı:

```python
def invoke_mesh_sculptor(run_dir):
    # 1. Ajan blueprint hesaplar (radius profiles + curve points)
    #    Bu agent claude -p ile yapılır, çıktı = MeshPlan.json
    
    # 2. build_mesh.py'ı Blender'da çalıştır
    subprocess.run([
        "blender", "--background", str(run_dir / "blender_scenes/skeleton_v1.blend"),
        "--python", "scripts/production/build_mesh.py",
        "--",
        "--mesh-plan", str(run_dir / "MeshPlan.json"),
        "--blueprint", str(run_dir / "SkeletonBlueprint.json"),
        "--budget", str(run_dir / "BudgetSpec.json"),
        "--anatomy-class", "references/anatomy_classes/mammalia_quadruped.md",
        "--output-blend", str(run_dir / "blender_scenes/mesh_v1.blend"),
    ], check=True, timeout=1800)  # mesh süreci uzun (boolean + remesh)
    
    # 3. Render alıp critic'lere gönder
    render_and_critique(run_dir, phase="mesh")
    
    orchestrator.next_agent = "P06_uv_cartographer" if no_retopo else "P05_topology_surgeon"
```

build_mesh.py (executable bpy code) ayrı dosya: `scripts/production/build_mesh.py`.

---

**Ajan hazır. Executable bpy kodu sonraki dosyada.**
