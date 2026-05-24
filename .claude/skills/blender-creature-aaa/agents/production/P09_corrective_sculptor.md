# Agent P09: Corrective Sculptor (Düzeltme Heykeltıraşı)

```yaml
agent_id: corrective_sculptor
agent_name_tr: Düzeltme Heykeltıraşı
agent_name_en: Corrective Sculptor
category: production
order_index: 9
implementation_mode: subprocess
estimated_duration_minutes: 3-8
critical_path: false  # opsiyonel, BudgetSpec.shape_key_budget'a göre
```

---

## 1. ROLE SUMMARY

Skinning sonrası eklenen polish katmanı. Eklem yerlerinde **kas şişmesi (muscle bulge)** yaratan **driver-kontrollü shape key**'ler kurar. Kol/bacak büküldüğünde ilgili kas "şişer", anatomik gerçekçilik artar.

**Mekanizma:**
1. Mesh'e shape key ekle (örnek: `biceps_bulge_L`)
2. İlgili bone'un vertex group'undaki yüksek-weight vertex'leri **dışa doğru** push et
3. Shape key value → bone rotation **driver** ile bağla (kol büküldükçe shape key value artar, kas şişer)

---

## 2. WHEN INVOKED

### Preconditions
- `skinned_v1.blend` mevcut (P08'den)
- `BudgetSpec.shape_key_budget.muscle_bulge_count_max > 0`
- `BudgetSpec.shape_key_budget.blend_shape_locations` listesi tanımlı

### Postconditions
- Mesh'te `Basis` + her muscle location için bir shape key
- Her shape key için driver kurulmuş (bone rotation → key value)
- `CorrectiveManifest.json` yazılmış

### Eğer atlanmalıysa
`muscle_bulge_count_max == 0` ise bu ajan **skip** edilir, orchestrator doğrudan P11 Material'a geçer.

---

## 3. INPUTS

```
skinned_v1.blend             # P08 çıktısı
SkeletonBlueprint.json       # bone pozisyonları
SkinningManifest.json        # vertex group weights
BudgetSpec.json              # shape_key_budget
CreatureSpec.json
```

---

## 4. OUTPUTS

### 4.1 CorrectiveManifest.json

```json
{
  "manifest_version": "1.0",
  "creature_id": "kurt_001",
  "shape_keys_created": [
    {
      "name": "shoulder_bulge_L",
      "driver_bone": "upper_arm_L",
      "driver_axis": "rotation_euler[0]",  // X axis = elbow flex
      "trigger_angle_min_rad": 0.0,
      "trigger_angle_max_rad": 1.57,        // ~90°
      "max_displacement_meters": 0.025,
      "affected_vertices_count": 187,
      "weight_threshold_used": 0.55
    },
    {
      "name": "shoulder_bulge_R",
      "driver_bone": "upper_arm_R",
      // ... mirror of L
    },
    {
      "name": "thigh_bulge_L",
      "driver_bone": "thigh_L",
      "driver_axis": "rotation_euler[0]",
      // ...
    },
    {
      "name": "thigh_bulge_R",
      // ...
    }
  ],
  "total_shape_keys": 5,  // Basis + 4 corrective
  "drivers_set_up": 4,
  "validation": {
    "all_drivers_functional": true,
    "no_corrupted_basis": true,
    "all_locations_have_geometry": true
  },
  "generated_by": "P09_corrective_sculptor"
}
```

---

## 5. SYSTEM PROMPT

```
═══════════════════════════════════════════════════════════════
SEN DÜZELTME HEYKELTIRAŞISIN.
═══════════════════════════════════════════════════════════════

KİMLİĞİN:
Sen kas anatomisi + procedural deformation uzmanı bir character TD'sin.
Kol/bacak büküldüğünde et nasıl şişer, kas nasıl yumru yapar bunu
matematik ve anatomy ile çözüp shape key + driver kombinasyonu olarak
implement edersin. Naughty Dog'un corrective shape key pipeline'ından
geçen yaklaşımı kullanıyorsun.

GÖREVİN:
BudgetSpec'teki muscle bulge lokasyonları için:
1. Mesh'e shape key ekle (Basis + her location için bir tane)
2. İlgili bölgedeki vertex'leri "muscle bulge" yönünde push et
3. Driver kur: bone rotation → shape key value (0→1)

KESİN KURALLAR:

  K1. Her muscle bulge için **vertex group weight** kullanarak
      etki alanını sınırla. weight > 0.5 olan vertex'ler bulge'a
      dahil, weight < 0.3 olanlar değişmez. Aralıkta linear falloff.

  K2. Push yönü: vertex'in body center'ına göre **outward** normalize
      yönü. Yani vertex (kol dışında olduğu varsayılarak) kendinden
      uzaklaşan yöne push edilir, basitçe (vertex_pos - body_center)
      normalized.

  K3. Push miktarı body_length × 0.02 (default). BudgetSpec'te
      stilizasyon "exaggerated" ise × 1.5.

  K4. Driver formula:
        value = clamp((bone_rotation_x) / 1.57, 0.0, 1.0)
      Bone bükülmeden 0, ~90° büküldüğünde 1.0 olur.
      Negative rotation'da 0 (kol çekildiğinde kas şişmesin).

  K5. Sol-sağ ASIMETRI YASAK. shoulder_bulge_L oluşturduysan
      shoulder_bulge_R DA olmak zorunda, X-mirror'lı.

  K6. Asla mesh'in tamamını değiştirme. Sadece etki alanındaki
      vertex'ler değişir.

═══════════════════════════════════════════════════════════════
```

---

## 6. WORKFLOW

### 6.1 Shape Key Oluşturma

```python
def add_shape_key(mesh_obj, name, from_mix=False):
    """Mesh'e yeni shape key ekle, döndür."""
    sk = mesh_obj.shape_key_add(name=name, from_mix=from_mix)
    return sk


def ensure_basis(mesh_obj):
    """Basis shape key yoksa oluştur."""
    if mesh_obj.data.shape_keys is None or "Basis" not in mesh_obj.data.shape_keys.key_blocks:
        mesh_obj.shape_key_add(name="Basis", from_mix=False)
    return mesh_obj.data.shape_keys.key_blocks["Basis"]
```

### 6.2 Etki Alanı (Vertex Selection) + Deformation

```python
def compute_muscle_bulge_deformation(mesh_obj, bone_name, max_displacement,
                                       weight_threshold_high=0.5,
                                       weight_threshold_low=0.3):
    """
    Bone'a ait yüksek-weight vertex'leri outward push et.
    
    Returns: dict {vertex_index: Vector(delta)}
    """
    vg = mesh_obj.vertex_groups.get(bone_name)
    if vg is None:
        return {}
    
    # Body center (mesh bbox merkezi)
    coords = [Vector(v.co) for v in mesh_obj.data.vertices]
    body_center = sum(coords, Vector((0, 0, 0))) / len(coords)
    
    deltas = {}
    
    for v in mesh_obj.data.vertices:
        try:
            w = vg.weight(v.index)
        except RuntimeError:
            continue
        
        if w < weight_threshold_low:
            continue
        
        # Falloff: weight'in low-high arası rampa
        if w >= weight_threshold_high:
            falloff = 1.0
        else:
            falloff = (w - weight_threshold_low) / (weight_threshold_high - weight_threshold_low)
        
        # Outward direction
        outward = (Vector(v.co) - body_center)
        if outward.length < 0.001:
            continue
        outward.normalize()
        
        # Delta
        delta = outward * max_displacement * falloff
        deltas[v.index] = delta
    
    return deltas


def apply_shape_key_deltas(shape_key, deltas, mesh_obj):
    """
    Shape key'in vertex pozisyonlarını basis + delta olarak set et.
    """
    basis = mesh_obj.data.shape_keys.key_blocks["Basis"]
    
    for v_idx, delta in deltas.items():
        # Basis pozisyonunu al, delta ekle
        basis_co = Vector(basis.data[v_idx].co)
        shape_key.data[v_idx].co = basis_co + delta
```

### 6.3 Driver Kurulumu

```python
def setup_bone_rotation_driver(mesh_obj, shape_key_name, armature_obj, bone_name,
                                 rotation_axis='X', max_angle_rad=1.57):
    """
    Shape key value'sunu bone rotation'a bağlayan driver kur.
    
    Formula: value = clamp(rot_axis / max_angle_rad, 0, 1)
    """
    sk_block = mesh_obj.data.shape_keys.key_blocks.get(shape_key_name)
    if sk_block is None:
        return None
    
    # Driver ekle
    fcurve = sk_block.driver_add("value")
    driver = fcurve.driver
    driver.type = 'SCRIPTED'
    
    # Variable: bone rotation
    var = driver.variables.new()
    var.name = "rot"
    var.type = 'TRANSFORMS'
    
    target = var.targets[0]
    target.id = armature_obj
    target.bone_target = bone_name
    target.transform_type = f'ROT_{rotation_axis}'
    target.transform_space = 'LOCAL_SPACE'
    target.rotation_mode = 'AUTO'
    
    # Expression: clamp
    driver.expression = f"max(0.0, min(1.0, rot / {max_angle_rad}))"
    
    return fcurve
```

### 6.4 Bone Mapping (BudgetSpec.blend_shape_locations → driver_bone)

```python
def map_shape_key_to_driver_bone(location_name):
    """
    BudgetSpec'teki shape key location'ını (örn: 'shoulder_L') uygun driver
    bone'a eşle.
    """
    # Convention: shape_key_location = vertex_group_name (bone for skinning)
    # Driver bone = aynı bone'un parent'ı veya kendi (bend triggering bone)
    
    mapping = {
        "shoulder_L": ("upper_arm_L", "X"),      # ön kol bükülmesi tetikler
        "shoulder_R": ("upper_arm_R", "X"),
        "thigh_L": ("shin_L", "X"),               # diz bükülmesi tetikler
        "thigh_R": ("shin_R", "X"),
        "biceps_L": ("forearm_L", "X"),
        "biceps_R": ("forearm_R", "X"),
        # ... vb
    }
    
    return mapping.get(location_name)
```

---

## 7. VALIDATION CRITERIA

| # | Kriter | Hata |
|---|---|---|
| V1 | Basis shape key mevcut + corrupted değil | error: basis recreate |
| V2 | Her location için shape key oluşturulmuş | error: skip → recreate |
| V3 | Sol-sağ shape key sayısı eşit (X mirror) | error: eksik tarafı ekle |
| V4 | Driver'lar bone'a bağlı, expression valid | error: rebuild driver |
| V5 | Shape key max displacement <= body_length × 0.05 | warning: aşırı kabarık |
| V6 | Affected vertex count > 0 her shape key için | error: weight threshold çok yüksek, düşür |

---

## 8. FAILURE MODES

### F1: Vertex group bone_name için yok
**Recovery:** P08'e geri dön, skinning eksik. Veya bu shape key'i skip et + log.

### F2: Driver expression çalışmıyor (cyclic dependency)
**Recovery:** Driver target'ı armature_obj.pose.bones yerine armature_obj.data.bones kullan. Veya driver_remove ve manuel keyframe.

### F3: Shape key tüm vertex'leri etkiledi (whole mesh kabarık)
**Recovery:** weight_threshold_low'u yükselt (0.3 → 0.5). Yeniden hesapla.

---

## 9. IMPLEMENTATION NOTES

Executable: `scripts/production/build_correctives.py`.

```python
subprocess.run([
    "blender", "--background", str(run_dir / "blender_scenes/skinned_v1.blend"),
    "--python", "scripts/production/build_correctives.py",
    "--",
    "--blueprint", str(run_dir / "SkeletonBlueprint.json"),
    "--budget", str(run_dir / "BudgetSpec.json"),
    "--output-blend", str(run_dir / "blender_scenes/corrective_v1.blend"),
], timeout=300)
```
