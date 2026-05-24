# Agent P11: Material Alchemist (Materyal Simyacısı)

```yaml
agent_id: material_alchemist
agent_name_tr: Materyal Simyacısı
agent_name_en: Material Alchemist
category: production
order_index: 11
implementation_mode: subprocess
estimated_duration_minutes: 2-5
critical_path: false  # opsiyonel
```

---

## 1. ROLE SUMMARY

Mesh'e **PBR (Physically Based Rendering)** Principled BSDF materyali kurar. Mobile-friendly **ORM packing** (Occlusion-Roughness-Metallic single texture) stratejisi. Godot 4'e import edildiğinde StandardMaterial3D'ye sorunsuz map'lenir.

**Bu skill, asıl texture painting YAPMAZ.** Sadece:
- Material node ağacını kurar
- Texture slot'larını hazırlar (placeholder texture önerir)
- Atlas UV varsa onunla bağlar
- Godot .tres material önerisi üretir

Texture içeriği (albedo + normal + ORM map) genellikle 3D paint tool veya Substance/Material Maker gibi external tool'larla yapılır. Skill kullanıcıya bu adım için yönlendirme verir.

---

## 2. WHEN INVOKED

### Preconditions
- `corrective_v1.blend` mevcut veya `skinned_v1.blend` (P09 skip edildiyse)
- `BudgetSpec.texture_budget` tanımlı
- (Opsiyonel) `MeshManifest.json`'da UV mevcut bilgisi

### Postconditions
- Mesh'e `creature_main` materyali atanmış
- Principled BSDF + (varsa) texture image slot'ları kurulu
- Godot uyumlu `<creature_id>.tres` önerisi yazılmış
- `MaterialManifest.json` yazılmış

---

## 3. INPUTS

```
corrective_v1.blend (or skinned_v1.blend)
BudgetSpec.json               # texture_budget
CreatureSpec.json
(opsiyonel) textures_dir/     # kullanıcı sağladığı texture'lar
```

---

## 4. OUTPUTS

### 4.1 MaterialManifest.json

```json
{
  "manifest_version": "1.0",
  "creature_id": "kurt_001",
  "material_name": "creature_main",
  "shader_type": "PrincipledBSDF",
  "texture_strategy": "single_atlas",
  "texture_slots": [
    {
      "slot": "Base Color",
      "image_path": "textures/kurt_001_albedo.png",
      "resolution": [2048, 2048],
      "is_placeholder": true
    },
    {
      "slot": "Normal Map",
      "image_path": "textures/kurt_001_normal.png",
      "resolution": [2048, 2048],
      "is_placeholder": true
    },
    {
      "slot": "ORM (packed)",
      "image_path": "textures/kurt_001_orm.png",
      "resolution": [2048, 2048],
      "is_placeholder": true,
      "packing": {"R": "occlusion", "G": "roughness", "B": "metallic"}
    }
  ],
  "godot_tres_path": "final/kurt_001.tres",
  "user_action_required": [
    "Albedo texture'ı paint et (substance, krita, photoshop, blender texture paint)",
    "Normal map bake et veya manuel oluştur",
    "ORM map paint et (R=AO, G=roughness, B=metallic)"
  ],
  "generated_by": "P11_material_alchemist"
}
```

### 4.2 Godot .tres Material

```ini
; final/kurt_001.tres
[gd_resource type="StandardMaterial3D" load_steps=4 format=3]

[ext_resource type="Texture2D" path="res://creatures/textures/kurt_001_albedo.png" id="1"]
[ext_resource type="Texture2D" path="res://creatures/textures/kurt_001_normal.png" id="2"]
[ext_resource type="Texture2D" path="res://creatures/textures/kurt_001_orm.png" id="3"]

[resource]
albedo_texture = ExtResource("1")
normal_enabled = true
normal_texture = ExtResource("2")
ao_enabled = true
ao_texture = ExtResource("3")
ao_texture_channel = 0  ; R
roughness_texture = ExtResource("3")
roughness_texture_channel = 1  ; G
metallic_texture = ExtResource("3")
metallic_texture_channel = 2  ; B
roughness = 1.0  ; texture'dan modüle ediliyor
metallic = 1.0
```

---

## 5. SYSTEM PROMPT

```
═══════════════════════════════════════════════════════════════
SEN MATERYAL SİMYACISISIN.
═══════════════════════════════════════════════════════════════

KİMLİĞİN:
PBR shader uzmanı, mobile graphics pipeline'da deneyimli karakter
TD'sin. Atlas packing, ORM channel mapping, Godot StandardMaterial3D
uyumluluğu konusunda uzmansın.

GÖREVİN:
1. Mesh'e Principled BSDF materyali ata
2. BudgetSpec.texture_budget'a göre slot'ları hazırla (single_atlas
   ise ORM packing, multi_material ise ayrı slot'lar)
3. Placeholder texture'lar üret veya kullanıcının sağladıklarını bağla
4. Godot .tres material dosyası öner

KESİN KURALLAR:

  K1. Shader: Principled BSDF (glTF uyumlu). Eevee Specular veya
      Custom shader kullanma — Godot import'una uymaz.

  K2. ORM packing zorunlu (eğer single_atlas strategy ise):
        R kanal = Ambient Occlusion
        G kanal = Roughness
        B kanal = Metallic
      Bu, mobile shader'da tek texture sample = 3 değer = ucuz.

  K3. Image color space:
        Albedo: sRGB
        Normal: Non-Color (linear)
        ORM: Non-Color (linear)

  K4. Material atlas naming: <creature_id>_<channel>.png

  K5. Eğer kullanıcı texture sağlamadıysa skill placeholder üretir
      (neutral gray albedo, flat blue normal map, mid-gray ORM).
      Kullanıcı sonradan üzerine paint eder.

═══════════════════════════════════════════════════════════════
```

---

## 6. WORKFLOW

### 6.1 Material Setup

```python
def setup_pbr_material(mesh_obj, creature_id, atlas_resolution=2048, 
                        textures_provided=None):
    """
    Principled BSDF + texture slots kuran material.
    """
    mat = bpy.data.materials.new(name=f"{creature_id}_main")
    mat.use_nodes = True
    
    nt = mat.node_tree
    nt.nodes.clear()
    
    # Output
    out_node = nt.nodes.new('ShaderNodeOutputMaterial')
    out_node.location = (600, 0)
    
    # Principled BSDF
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (200, 0)
    bsdf.inputs['Base Color'].default_value = (0.5, 0.45, 0.4, 1.0)  # neutral fur
    bsdf.inputs['Roughness'].default_value = 0.7
    if 'Metallic' in bsdf.inputs:
        bsdf.inputs['Metallic'].default_value = 0.0
    
    nt.links.new(bsdf.outputs['BSDF'], out_node.inputs['Surface'])
    
    # UV Map node
    uv_node = nt.nodes.new('ShaderNodeUVMap')
    uv_node.location = (-800, 0)
    uv_node.uv_map = "UVMap"  # default UV name
    
    # Albedo texture
    albedo_tex = nt.nodes.new('ShaderNodeTexImage')
    albedo_tex.location = (-400, 200)
    albedo_tex.label = "Albedo"
    
    if textures_provided and "albedo" in textures_provided:
        albedo_tex.image = bpy.data.images.load(textures_provided["albedo"])
    else:
        # Placeholder neutral gray
        albedo_img = create_placeholder_texture(
            f"{creature_id}_albedo", atlas_resolution, 
            color=(0.5, 0.45, 0.4, 1.0)
        )
        albedo_tex.image = albedo_img
    
    if albedo_tex.image:
        albedo_tex.image.colorspace_settings.name = 'sRGB'
    
    nt.links.new(uv_node.outputs['UV'], albedo_tex.inputs['Vector'])
    nt.links.new(albedo_tex.outputs['Color'], bsdf.inputs['Base Color'])
    
    # Normal map texture
    normal_tex = nt.nodes.new('ShaderNodeTexImage')
    normal_tex.location = (-400, -100)
    normal_tex.label = "Normal"
    
    if textures_provided and "normal" in textures_provided:
        normal_tex.image = bpy.data.images.load(textures_provided["normal"])
    else:
        normal_img = create_placeholder_texture(
            f"{creature_id}_normal", atlas_resolution,
            color=(0.5, 0.5, 1.0, 1.0)  # flat normal
        )
        normal_tex.image = normal_img
    
    if normal_tex.image:
        normal_tex.image.colorspace_settings.name = 'Non-Color'
    
    # Normal map converter node
    normal_map = nt.nodes.new('ShaderNodeNormalMap')
    normal_map.location = (-100, -100)
    
    nt.links.new(uv_node.outputs['UV'], normal_tex.inputs['Vector'])
    nt.links.new(normal_tex.outputs['Color'], normal_map.inputs['Color'])
    nt.links.new(normal_map.outputs['Normal'], bsdf.inputs['Normal'])
    
    # ORM packed texture (R=AO, G=Roughness, B=Metallic)
    orm_tex = nt.nodes.new('ShaderNodeTexImage')
    orm_tex.location = (-400, -400)
    orm_tex.label = "ORM"
    
    if textures_provided and "orm" in textures_provided:
        orm_tex.image = bpy.data.images.load(textures_provided["orm"])
    else:
        orm_img = create_placeholder_texture(
            f"{creature_id}_orm", atlas_resolution,
            color=(1.0, 0.7, 0.0, 1.0)  # AO=1, roughness=0.7, metallic=0
        )
        orm_tex.image = orm_img
    
    if orm_tex.image:
        orm_tex.image.colorspace_settings.name = 'Non-Color'
    
    nt.links.new(uv_node.outputs['UV'], orm_tex.inputs['Vector'])
    
    # ORM Separate RGB
    separate_orm = nt.nodes.new('ShaderNodeSeparateColor')
    separate_orm.mode = 'RGB'
    separate_orm.location = (-100, -400)
    
    nt.links.new(orm_tex.outputs['Color'], separate_orm.inputs['Color'])
    # R = AO (not directly to BSDF in Cycles, but exported to glTF as "occlusionTexture")
    # G = Roughness
    nt.links.new(separate_orm.outputs['Green'], bsdf.inputs['Roughness'])
    # B = Metallic
    if 'Metallic' in bsdf.inputs:
        nt.links.new(separate_orm.outputs['Blue'], bsdf.inputs['Metallic'])
    
    # Material'i mesh'e ata
    mesh_obj.data.materials.clear()
    mesh_obj.data.materials.append(mat)
    
    return mat


def create_placeholder_texture(name, resolution, color=(0.5, 0.5, 0.5, 1.0)):
    """Düz renkli placeholder texture."""
    img = bpy.data.images.new(
        name, width=resolution, height=resolution, alpha=True
    )
    pixels = [c for _ in range(resolution * resolution) for c in color]
    img.pixels = pixels
    img.pack()
    return img
```

### 6.2 Godot .tres Üretimi

```python
def write_godot_tres(output_path, creature_id):
    """Godot 4 StandardMaterial3D .tres material önerisi."""
    tres_content = f"""[gd_resource type="StandardMaterial3D" load_steps=4 format=3]

[ext_resource type="Texture2D" path="res://creatures/{creature_id}/textures/{creature_id}_albedo.png" id="1_albedo"]
[ext_resource type="Texture2D" path="res://creatures/{creature_id}/textures/{creature_id}_normal.png" id="2_normal"]
[ext_resource type="Texture2D" path="res://creatures/{creature_id}/textures/{creature_id}_orm.png" id="3_orm"]

[resource]
resource_name = "{creature_id}_main"

albedo_texture = ExtResource("1_albedo")

normal_enabled = true
normal_texture = ExtResource("2_normal")
normal_scale = 1.0

ao_enabled = true
ao_texture = ExtResource("3_orm")
ao_texture_channel = 0
ao_light_affect = 0.0

roughness = 1.0
roughness_texture = ExtResource("3_orm")
roughness_texture_channel = 1

metallic = 1.0
metallic_texture = ExtResource("3_orm")
metallic_texture_channel = 2
metallic_specular = 0.5
"""
    
    Path(output_path).write_text(tres_content, encoding='utf-8')
```

---

## 7. VALIDATION CRITERIA

| # | Kriter | Hata |
|---|---|---|
| V1 | Mesh'te en az 1 material slot | error: material ata |
| V2 | Material'da Principled BSDF node var | error: shader recreate |
| V3 | UV map node ve bağlantıları doğru | error: link recreate |
| V4 | Texture image'lar yüklü (placeholder olsa bile) | error: missing image |
| V5 | Color space ayarları doğru (albedo=sRGB, normal/orm=Non-Color) | warning + fix |
| V6 | Godot .tres dosyası valid (`gd_resource` header) | error |

---

## 8. FAILURE MODES

### F1: UV layer yok (P06 atlandıysa veya fail ettiyse)
**Recovery:** Smart UV unwrap fallback yap, sonra material'ı bağla. Veya kullanıcıya "UV yok, P06 çalıştırılmalı" sinyali.

### F2: Texture image yüklenemiyor (placeholder bile)
**Recovery:** Bpy generated solid color image kullan (bpy.data.images.new ile pixel data set).

### F3: Mesh'te birden fazla material slot var (kullanıcı manuel eklemiş)
**Recovery:** Sadece slot 0'ı override et, diğerlerini uyarı ile koru.

---

## 9. IMPLEMENTATION NOTES

Executable: `scripts/production/build_material.py`.

```python
subprocess.run([
    "blender", "--background", str(run_dir / "blender_scenes/corrective_v1.blend"),
    "--python", "scripts/production/build_material.py",
    "--",
    "--budget", str(run_dir / "BudgetSpec.json"),
    "--creature-id", "kurt_001",
    "--output-blend", str(run_dir / "blender_scenes/material_v1.blend"),
    "--output-tres", str(run_dir / "final/kurt_001.tres"),
    "--textures-dir", str(run_dir / "textures"),  # opsiyonel, kullanıcı sağladıysa
], timeout=180)
```
