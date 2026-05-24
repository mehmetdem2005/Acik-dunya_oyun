# Agent P07: Rigger Polish (Animator UI)

```yaml
agent_id: rigger_polish
agent_name_tr: Rigger (Polish)
agent_name_en: Rigger Polish
category: production
order_index: 7
implementation_mode: subprocess
estimated_duration_minutes: 2-5
critical_path: false
```

---

## 1. ROLE SUMMARY

P03 Skeleton Architect IK constraint'leri + bone'ları kurar. Bu ajan **animatör UI**'sını polish eder:

- IK target bone'larına **custom display shapes** ekler (küre, daire, ok)
- Pole bone'larına **çubuk şekli** ekler
- Control bone'ların display color'ını set eder (sağ=mavi, sol=kırmızı, center=sarı)
- Bone group'ları oluşturur (animatör Outliner'da kolay göre/seç)

**Bu polish ajan animasyonu güzelleştirmez** — sadece animatörün hayatını kolaylaştırır.

---

## 2. WHEN INVOKED

### Preconditions
- `skeleton_v1.blend` veya sonrası mevcut
- Kullanıcı animasyon için manuel müdahale planlıyorsa veya
- Kullanıcı "rig polish yap" dedi

### Atlama Koşulu
Tamamen prosedürel animasyon istenirse (P12 otomatik) bu ajan **atlanabilir** — animatör UI gerekmez.

### Postconditions
- Armature'da custom display shape'ler set
- Bone group'ları kurulmuş
- `RigPolishManifest.json`

---

## 3. INPUTS

```
skeleton_v1.blend
SkeletonBlueprint.json
```

---

## 4. OUTPUTS

```json
{
  "manifest_version": "1.0",
  "custom_shapes_added": {
    "ik_targets": 4,
    "pole_targets": 4,
    "spine_controls": 5,
    "head_control": 1
  },
  "bone_groups": [
    {"name": "IK Controls", "color_set": "THEME01_BLUE", "bones": 8},
    {"name": "Spine Chain", "color_set": "THEME02_RED", "bones": 6},
    {"name": "Head + Jaw", "color_set": "THEME09_YELLOW", "bones": 3},
    {"name": "Tail", "color_set": "THEME03_GREEN", "bones": 5}
  ],
  "generated_by": "P07_rigger_polish"
}
```

---

## 5. WORKFLOW

### 5.1 Display Shape Mesh'ler Oluştur

```python
def create_widget_shapes():
    """Custom bone display için 4 mesh oluştur (Blender'ın widget objesi)."""
    shapes = {}
    
    # 1. Küre (IK foot/hand target)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=8, ring_count=4)
    sphere = bpy.context.active_object
    sphere.name = "WGT_sphere"
    sphere.hide_viewport = True
    shapes["sphere"] = sphere
    
    # 2. Daire (head control)
    bpy.ops.mesh.primitive_circle_add(radius=1.0, vertices=16)
    circle = bpy.context.active_object
    circle.name = "WGT_circle"
    circle.hide_viewport = True
    shapes["circle"] = circle
    
    # 3. Cube (root)
    bpy.ops.mesh.primitive_cube_add(size=1.0)
    cube = bpy.context.active_object
    cube.name = "WGT_cube"
    cube.hide_viewport = True
    shapes["cube"] = cube
    
    # 4. Arrow (pole)
    # Custom mesh: küçük çubuk
    mesh_data = bpy.data.meshes.new("WGT_arrow_data")
    verts = [(0, 0, 0), (0, 0, 1), (-0.2, 0, 0.8), (0.2, 0, 0.8)]
    edges = [(0, 1), (1, 2), (1, 3)]
    mesh_data.from_pydata(verts, edges, [])
    arrow = bpy.data.objects.new("WGT_arrow", mesh_data)
    bpy.context.collection.objects.link(arrow)
    arrow.hide_viewport = True
    shapes["arrow"] = arrow
    
    return shapes


def assign_custom_shape(armature_obj, bone_name, shape_obj, scale=0.15):
    """Pose bone'a custom display shape ata."""
    pb = armature_obj.pose.bones.get(bone_name)
    if pb is None:
        return False
    
    pb.custom_shape = shape_obj
    pb.custom_shape_scale_xyz = (scale, scale, scale)
    pb.use_custom_shape_bone_size = False
    
    return True
```

### 5.2 Bone Groups

```python
def create_bone_groups(armature_obj):
    """Animator için color-coded bone gruplar."""
    arm = armature_obj.data
    
    # Blender 4.x'te bone_groups → bone_collections
    if hasattr(arm, "collections"):
        # 4.0+
        col_api = arm.collections
        
        groups = [
            ("IK Controls", "ik_"),
            ("Spine Chain", "spine_"),
            ("Head + Jaw", ("head", "jaw", "neck_")),
            ("Tail", "tail_"),
            ("Pole Targets", "pole_"),
        ]
        
        for group_name, prefix in groups:
            col = col_api.new(group_name)
            for bone in armature_obj.data.bones:
                if isinstance(prefix, tuple):
                    if any(p in bone.name for p in prefix):
                        col.assign(bone)
                else:
                    if prefix in bone.name:
                        col.assign(bone)
    
    return True


def set_bone_colors(armature_obj):
    """Bone color (Blender 4.x bone_color API)."""
    for bone in armature_obj.data.bones:
        if bone.name.startswith("ik_") or bone.name.startswith("foot_ik"):
            bone.color.palette = 'THEME01'  # blue
        elif bone.name.endswith("_L"):
            bone.color.palette = 'THEME04'  # red ish
        elif bone.name.endswith("_R"):
            bone.color.palette = 'THEME06'  # purple ish
        elif bone.name.startswith("spine_"):
            bone.color.palette = 'THEME03'  # green
        elif bone.name in ("head", "jaw"):
            bone.color.palette = 'THEME09'  # yellow
        elif bone.name.startswith("tail_"):
            bone.color.palette = 'THEME02'  # red
```

### 5.3 Pipeline

```python
def polish_rig(armature_obj):
    shapes = create_widget_shapes()
    
    # IK targets → sphere
    for pb in armature_obj.pose.bones:
        if "ik" in pb.name.lower() and "foot" in pb.name.lower():
            assign_custom_shape(armature_obj, pb.name, shapes["sphere"], scale=0.08)
        elif "pole" in pb.name.lower():
            assign_custom_shape(armature_obj, pb.name, shapes["arrow"], scale=0.05)
        elif pb.name in ("head", "root_master"):
            assign_custom_shape(armature_obj, pb.name, shapes["circle"], scale=0.20)
    
    create_bone_groups(armature_obj)
    set_bone_colors(armature_obj)
```

---

## 6. FAILURE MODES

### F1: Custom shape assign exception (Blender API farklı)
**Recovery:** Try-except per bone, hatalı olanları skip, log.

### F2: Bone group API yok (eski Blender)
**Recovery:** Bone collections API kullan, yoksa skip (cosmetic kayıp).

---

## 7. IMPLEMENTATION

`scripts/production/build_rigging_polish.py`. P07 sadece P03 sonrası açıkça istenirse çağrılır.
