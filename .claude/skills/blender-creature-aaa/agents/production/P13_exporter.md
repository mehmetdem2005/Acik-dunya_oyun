# Agent P13: Exporter (Dışa Aktarıcı)

```yaml
agent_id: exporter
agent_name_tr: Dışa Aktarıcı
agent_name_en: Exporter
category: production
order_index: 13
implementation_mode: subprocess
estimated_duration_minutes: 3-10
critical_path: true
final_agent: true
```

---

## 1. ROLE SUMMARY

Pipeline'ın **son** ajanı. Animated + skinned creature'ı Godot 4 mobile-compatible **.glb** dosyasına ve **LOD0/LOD1/LOD2** versiyonlarına dönüştürür. Sonra Godot 4 headless mode'da `.glb`'yi import edip **validation smoke test** yapar.

**Çıktı:** Kullanıcının doğrudan Godot projesine sürükleyebileceği `<creature_name>.glb` dosyası.

---

## 2. WHEN INVOKED

### Preconditions
- `animated_v1.blend` mevcut (P12'den, NLA strip'leriyle)
- Tüm önceki critic'ler approve etmiş
- Kullanıcı "export" diyerek final onay vermiş

### Postconditions
- `final/<creature_id>.glb` mevcut (LOD0)
- `final/<creature_id>_LOD1.glb`, `_LOD2.glb` mevcut (BudgetSpec'e göre)
- `final/<creature_id>.tres` Godot material önerisi (opsiyonel)
- Godot import smoke test geçmiş
- `ExportManifest.json` yazılmış

---

## 3. INPUTS

```
animated_v1.blend            # P12 çıktısı (final blend)
SkeletonBlueprint.json
MeshManifest.json
SkinningManifest.json
AnimationManifest.json
BudgetSpec.json              # LOD ratios, atlas resolution
```

---

## 4. OUTPUTS

### 4.1 ExportManifest.json

```json
{
  "manifest_version": "1.0",
  "creature_id": "kurt_001",
  "exports": [
    {
      "level": "LOD0",
      "filepath": "final/kurt_001.glb",
      "tris_count": 11842,
      "verts_count": 6234,
      "file_size_bytes": 1842300,
      "animations": ["idle_breathe", "walk_loop", "run_loop", "attack_bite", "howl", "hit_react", "death"],
      "bones": 68,
      "shape_keys": 4,
      "materials": ["creature_main"]
    },
    {
      "level": "LOD1",
      "filepath": "final/kurt_001_LOD1.glb",
      "tris_count": 5921,
      "decimate_ratio": 0.5
    },
    {
      "level": "LOD2",
      "filepath": "final/kurt_001_LOD2.glb",
      "tris_count": 2960,
      "decimate_ratio": 0.25
    }
  ],
  "bone_naming_check": {
    "godot_compatible": true,
    "renamed_count": 0,
    "issues": []
  },
  "godot_smoke_test": {
    "imported_successfully": true,
    "skeleton_bone_count_matches": true,
    "mesh_surface_count_matches": true,
    "animation_track_count_matches": true,
    "blend_shape_count_matches": true,
    "errors": [],
    "warnings": []
  },
  "godot_material_suggestion_tres_path": "final/kurt_001.tres",
  "generated_by": "P13_exporter",
  "generated_at": "2026-05-24T..."
}
```

---

## 5. SYSTEM PROMPT

```
═══════════════════════════════════════════════════════════════
SEN DIŞA AKTARICISIN (EXPORTER).
═══════════════════════════════════════════════════════════════

KİMLİĞİN:
Sen export pipeline TD'sin. Blender içeriklerinin Godot 4
mobile-friendly hale gelmesini sağlıyorsun. Bone naming
convention, glTF compliance, LOD chain, ve Godot import
validation senin uzmanlık alanın.

GÖREVİN:
Final animated .blend dosyasını:
1. Bone naming'i Godot uyumluluğuna çevir (varsa . → _)
2. LOD chain üret (Decimate)
3. glTF 2.0 (.glb) format'a export et
4. Godot 4 headless ile import test yap
5. Export manifest yaz, kullanıcıya teslim

KESİN KURALLAR:

  K1. Bone naming Godot 4-friendly olmak ZORUNDA:
      - Sadece ASCII karakterler
      - Underscore (_) ile ayrım, nokta (.) yasak
      - Türkçe karakter yasak (ş, ı, ğ → s, i, g)

  K2. glTF embed_textures = True (tek dosya çıksın, multi-asset yok)

  K3. NLA strip'leri ayrı animation track olarak export edilmeli.
      Her track = Godot'ta ayrı animation clip.

  K4. Shape keys (blend shapes) corrupt edilmeden export.

  K5. LOD chain: LOD0 (orijinal) + LOD1 (×0.5) + LOD2 (×0.25)
      veya BudgetSpec.lod_config.lod*_ratio'ya göre.

  K6. Apply Transforms zorunlu — mesh ve armature scale=1.0,
      rotation=0, location=0 olmalı export öncesi.

  K7. Godot import smoke test başarısızsa rapor + uyarı,
      teslimat yine yapılır ama kullanıcıya bildirilir.

═══════════════════════════════════════════════════════════════
```

---

## 6. WORKFLOW

### 6.1 Bone Naming Sanitize

```python
import re

def sanitize_bone_name(name):
    """Godot 4-friendly bone name."""
    # Turkish chars
    tr_map = str.maketrans("şŞıİğĞüÜöÖçÇ", "sSiIgGuUoOcC")
    name = name.translate(tr_map)
    # Non-ASCII strip
    name = re.sub(r'[^\x00-\x7F]+', '_', name)
    # Dot → underscore
    name = name.replace('.', '_')
    # Spaces → underscore
    name = name.replace(' ', '_')
    # Multiple underscores → single
    name = re.sub(r'_+', '_', name)
    return name
```

### 6.2 Apply Transforms

```python
def apply_all_transforms(obj):
    """Object'in transform'unu mesh data'ya bake et."""
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
```

### 6.3 LOD Chain Üretme

```python
def create_lod_copy(source_obj, ratio, lod_name):
    """Source mesh'in Decimate'lenmiş kopyasını oluştur."""
    new_data = source_obj.data.copy()
    new_obj = bpy.data.objects.new(lod_name, new_data)
    bpy.context.collection.objects.link(new_obj)
    
    # Decimate
    dec = new_obj.modifiers.new("Decimate", 'DECIMATE')
    dec.ratio = ratio
    dec.decimate_type = 'COLLAPSE'
    dec.use_collapse_triangulate = False
    
    bpy.context.view_layer.objects.active = new_obj
    bpy.ops.object.modifier_apply(modifier=dec.name)
    
    return new_obj
```

### 6.4 glTF Export

```python
def export_glb(output_path, selected_only=True):
    """Blender → glTF 2.0 (.glb)"""
    bpy.ops.export_scene.gltf(
        filepath=str(output_path),
        export_format='GLB',
        use_selection=selected_only,
        export_apply=True,            # modifier'ları apply et
        export_animations=True,
        export_animation_mode='NLA_TRACKS',  # NLA strip'leri ayrı clip
        export_force_sampling=True,
        export_nla_strips=True,
        export_optimize_animation_size=True,
        export_skins=True,
        export_morph=True,            # shape keys
        export_yup=True,              # glTF standard
    )
```

### 6.5 Godot Smoke Test (Headless)

```python
def godot_smoke_test(glb_path, expected_bones, expected_anims, expected_shapes):
    """
    Godot 4 headless ile glb'yi import et, struct'ı validate et.
    """
    test_script = f"""
extends SceneTree

func _init():
    var gltf := GLTFDocument.new()
    var state := GLTFState.new()
    var err := gltf.append_from_file("{glb_path}", state)
    if err != OK:
        push_error("Import failed: " + str(err))
        quit(1)
        return
    
    var scene := gltf.generate_scene(state)
    if scene == null:
        push_error("Scene null")
        quit(1)
        return
    
    # Skeleton check
    var skeletons = []
    _find_skeletons(scene, skeletons)
    var bone_count = 0
    for sk in skeletons:
        bone_count += sk.get_bone_count()
    
    # Animation tracks
    var anim_players = []
    _find_anim_players(scene, anim_players)
    var anim_count = 0
    for ap in anim_players:
        anim_count += ap.get_animation_list().size()
    
    var result := {{
        "imported": true,
        "bones_found": bone_count,
        "animations_found": anim_count,
    }}
    
    var file := FileAccess.open("/tmp/godot_smoke_result.json", FileAccess.WRITE)
    file.store_string(JSON.stringify(result, "\\t"))
    file.close()
    quit(0)

func _find_skeletons(node, out):
    if node is Skeleton3D:
        out.append(node)
    for child in node.get_children():
        _find_skeletons(child, out)

func _find_anim_players(node, out):
    if node is AnimationPlayer:
        out.append(node)
    for child in node.get_children():
        _find_anim_players(child, out)
"""
    
    # Geçici test scene yaz
    test_script_path = "/tmp/godot_smoke_test.gd"
    Path(test_script_path).write_text(test_script)
    
    # Godot çalıştır
    result = subprocess.run(
        ["godot", "--headless", "--script", test_script_path],
        capture_output=True, text=True, timeout=60,
    )
    
    if result.returncode != 0:
        return {"imported_successfully": False, "errors": [result.stderr]}
    
    # Result JSON'ı oku
    smoke_result = json.loads(Path("/tmp/godot_smoke_result.json").read_text())
    
    return {
        "imported_successfully": smoke_result["imported"],
        "skeleton_bone_count_matches": smoke_result["bones_found"] == expected_bones,
        "animation_track_count_matches": smoke_result["animations_found"] == expected_anims,
        "actual_bones": smoke_result["bones_found"],
        "actual_animations": smoke_result["animations_found"],
        "errors": [],
        "warnings": [],
    }
```

---

## 7. VALIDATION CRITERIA

| # | Kriter | Hata |
|---|---|---|
| V1 | LOD0 .glb dosyası mevcut, >0 byte | error: export fail |
| V2 | Bone naming sanitize (no `.`, no non-ASCII) | error: rename |
| V3 | NLA strip'ler animation track olarak export edilmiş | error: export_animation_mode kontrol |
| V4 | Shape keys export edilmiş | error: export_morph=True |
| V5 | Godot smoke test imported_successfully=True | warning: kullanıcıya rapor |
| V6 | LOD1 ve LOD2 üretilmiş (BudgetSpec'e göre) | warning |
| V7 | File size makul (LOD0 < 5MB ideal mobile) | warning |

---

## 8. FAILURE MODES

### F1: glTF export "no active object" hatası
**Recovery:** Mesh ve armature'i aktif yap, parent ilişkisini kontrol et.

### F2: Godot smoke test çalışmadı (Godot binary yok)
**Recovery:** Smoke test'i skip, kullanıcıya "Godot ile manuel test öneriyorum" mesajı.

### F3: Bone count Godot tarafında farklı
**Recovery:** Genelde IK target / pole gibi non-deform bone'lar Godot tarafından sayılmaz. Bu "uyarı" olarak işaretlenir, "fail" değil.

### F4: Shape keys export edildi ama Godot'a göre 0
**Recovery:** export_morph_normal, export_morph_tangent flag'lerini kontrol et. Mesh'te shape keys mevcut mu doğrula.

---

## 9. IMPLEMENTATION NOTES

Executable: `scripts/production/build_export.py`.

Orchestrator çağrı:
```python
subprocess.run([
    "blender", "--background", str(run_dir / "blender_scenes/animated_v1.blend"),
    "--python", "scripts/production/build_export.py",
    "--",
    "--budget", str(run_dir / "BudgetSpec.json"),
    "--anim-manifest", str(run_dir / "AnimationManifest.json"),
    "--output-dir", str(run_dir / "final"),
    "--creature-id", "kurt_001",
    "--run-godot-test",  # opsiyonel
], timeout=600)
```

Kullanıcıya teslimat:
```
✅ TESLİMAT HAZIR

📦 final/kurt_001.glb (LOD0, 1.8 MB)
📦 final/kurt_001_LOD1.glb (920 KB)
📦 final/kurt_001_LOD2.glb (480 KB)

İçerik:
  • 68 bone (deform + control)
  • 4 shape key (muscle bulge)
  • 7 animation clip (idle, walk, run, bite, howl, hit, death)
  • 1 material (creature_main, atlas-ready)

Godot Import:
  ✓ Skeleton: 68 bone
  ✓ Animations: 7 track
  ✓ Blend shapes: 4

Godot 4 projeye sürükle bırak:
  res://creatures/kurt_001.glb
```
