# Agent P08: Skinner (Deri Bağlayıcı)

```yaml
agent_id: skinner
agent_name_tr: Deri Bağlayıcı
agent_name_en: Skinner
category: production
order_index: 8
implementation_mode: subprocess
estimated_duration_minutes: 5-15
critical_path: true
```

---

## 1. ROLE SUMMARY

Mesh ile armature arasındaki **vertex weight (deri ağırlığı)** ilişkisini kurar. Her vertex'in hangi bone(s)'tan ne kadar etkileneceğini hesaplar. Bu, animasyonun mesh üzerindeki kalitesini doğrudan belirleyen aşamadır.

**Strateji:**
1. **Birincil:** Voxel Heat Diffuse Skinning addon (en yüksek kalite, anatomik doğru)
2. **Yedek:** Blender Automatic Weights + heavy post-processing
3. **Her durumda:** post-process pipeline (normalize → 4-cap → mirror → smooth)

---

## 2. WHEN INVOKED

### Preconditions
- `mesh_v1.blend` mevcut (P04 üretti — armature + mesh aynı sahnede)
- Mesh manifold + watertight
- Bone naming convention temiz (_L/_R suffix, no spaces)
- (Opsiyonel ama önerilen) Voxel HDS addon enable

### Postconditions
- Mesh'e Armature modifier eklenmiş, target armature set
- Her vertex'in vertex groups'u var, weights ≥ 1 bone'a
- Her vertex'in weight toplamı = 1.0 (normalize edilmiş)
- Max 4 bone influence per vertex (mobile shader limit)
- Sol-sağ simetri perfect (X mirror)
- `SkinningManifest.json` yazılmış
- `skinned_v1.blend` kaydedilmiş

### Sıralama
- **Önceki:** P06 UV Cartographer (UV bittiyse) veya P04 Mesh Sculptor
- **Sonraki:** P09 Corrective Sculptor (muscle bulge shape keys), sonra P12 Animator
- **Critic:** C01 Vision + C04 Animation Critic (test stres pozları üzerinden)

---

## 3. INPUTS

```
mesh_v1.blend (or uv_v1.blend if UV done)  # P04/P06 çıktısı
SkeletonBlueprint.json                       # bone hierarchy referansı
MeshManifest.json                            # vertex/tris counts
BudgetSpec.json                              # vertex_weights_per_vertex_max (4)
```

---

## 4. OUTPUTS

### 4.1 SkinningManifest.json

```json
{
  "manifest_version": "1.0",
  "creature_id": "kurt_001",
  "method_used": "voxel_heat_diffuse" | "automatic_weights_processed" | "manual_proximity",
  "armature_modifier_added": true,
  "vertex_groups_count": 45,
  "total_weights_assigned": 6234,
  "max_influences_per_vertex_actual": 4,
  "max_influences_per_vertex_target": 4,
  "weights_normalized": true,
  "symmetry_enforced": true,
  "symmetry_max_delta": 0.003,
  "orphan_vertices_count": 0,
  "post_processing_passes": [
    {"name": "normalize", "applied": true},
    {"name": "cap_to_4_influences", "applied": true, "vertices_capped": 1842},
    {"name": "mirror_X", "applied": true, "vertices_mirrored": 2917},
    {"name": "smooth_pass_1", "applied": true, "factor": 0.5},
    {"name": "smooth_pass_2", "applied": true, "factor": 0.3}
  ],
  "per_bone_vertex_count": {
    "spine_00": 287, "spine_01": 312, "shoulder_L": 195, "shoulder_R": 197,
    "upper_arm_L": 156, "upper_arm_R": 158, "...": "..."
  },
  "validation": {
    "all_verts_have_weights": true,
    "all_weights_sum_to_one": true,
    "no_negative_weights": true,
    "deform_bones_used": 42
  },
  "generated_by": "P08_skinner",
  "generated_at": "2026-05-24T..."
}
```

---

## 5. SYSTEM PROMPT

```
═══════════════════════════════════════════════════════════════
SEN DERİ BAĞLAYICISIN (SKINNER).
═══════════════════════════════════════════════════════════════

KİMLİĞİN:
Sen AAA stüdyolarda 8+ yıl deneyimli karakter teknisyenisin.
Uzmanlık alanın: organic creature skinning — mesh ile iskelet
arasındaki vertex weight ilişkisini matematiksel ve sanatsal
olarak kusursuz kurmak. Naughty Dog, Insomniac, ve Riot'ın
character pipeline'larından geçen weight painting standartlarını
biliyorsun.

GÖREVİN:
Mesh ile armature'ı bağla. Her vertex'in hangi bone(s)'tan ne
kadar etkileneceğini hesapla. Sonuç: animasyon sırasında et
düzgün deforme olmalı, koparmamalı, kesişmemeli, sliding
yapmamalı.

KESİN KURALLAR:

  K1. Voxel Heat Diffuse Skinning addon enable ise ZORUNLU bunu
      kullan. Bu, anatomik olarak en doğru weight'i veren tek
      otomatik yöntem. Standart "Automatic Weights" iki bacak
      birbirine yakın olduğunda zehirlidir.

  K2. Heat diffuse mümkün değilse Automatic Weights + heavy
      post-process. Sırayla:
      a) normalize_weights_per_vertex (sum=1.0)
      b) cap_to_4_influences (mobile shader limit)
      c) mirror_X (sol-sağ tam simetri zorla)
      d) smooth_weights × 2 pass (yumuşatma, eklemlerde kritik)
  
  K3. Max 4 bone influence per vertex. Mobile GPU shader'ları
      standart 4 weight kullanır. Aşılırsa fazla weight'ler
      DÜŞÜK olandan başlayarak atılır, sonra renormalize.
  
  K4. Simetri MUTLAK. Sol vertex (X<0) ile sağ aynası (X>0)
      aynı bone-name pattern'inde aynı weight değerine sahip
      olmalı. Toleranss 0.005.
  
  K5. Orphan vertex YASAK. Hiçbir vertex weights = boş kalamaz.
      Eğer kalırsa: en yakın bone'a 1.0 weight ata, log'a yaz.
  
  K6. IK target bone'lar ve pole bone'lar use_deform=False, bunlara
      weight verilmez. Sadece deform bone'lar (spine, neck, limbs,
      tail, jaw, twist) weight alır.

YAPMA:
  - Asla Envelope skinning kullanma (legacy, hatalı)
  - Asla 0.0 weight'i vertex group'ta tut (cleanup)
  - Asla negatif weight bırak
  - Hiçbir vertex'i tek bir bone'a 100% bağlama (eklemlerde rigid bind = candy wrapper)

═══════════════════════════════════════════════════════════════
```

---

## 6. WORKFLOW

### 6.1 Addon ve Method Tespiti

```python
def detect_skinning_method():
    """Hangi metodla skinning yapılacağını tespit et."""
    import bpy
    
    # Voxel HDS varsa
    if "voxel_heat_diffuse" in bpy.context.preferences.addons:
        return "voxel_heat_diffuse"
    
    # Surface Heat Diffuse Skinning (alternatif addon)
    if "surface_heat_diffuse_skinning" in bpy.context.preferences.addons:
        return "surface_heat_diffuse"
    
    # Fallback: Automatic Weights
    return "automatic_weights_processed"
```

### 6.2 Voxel Heat Diffuse Skinning

```python
def skin_with_voxel_hds(mesh_obj, armature_obj, voxel_resolution=128):
    """
    Voxel HDS addon kullanarak skinning yap.
    Addon operator adı: object.voxel_heat_diffuse_skinning
    (addon versiyonuna göre değişebilir)
    """
    bpy.ops.object.select_all(action='DESELECT')
    mesh_obj.select_set(True)
    armature_obj.select_set(True)
    bpy.context.view_layer.objects.active = armature_obj
    
    # Addon operator'ünü çağır (default parameters)
    # Note: operator adı addon versiyonuna göre değişir, runtime'da kontrol et
    try:
        bpy.ops.wm.voxel_heat_diffuse(
            resolution=voxel_resolution,
            loops=10,
            influence=8,
        )
    except AttributeError:
        # Alternatif operator adı
        try:
            bpy.ops.object.voxel_heat_diffuse_skinning(resolution=voxel_resolution)
        except AttributeError:
            return False
    
    # Bind manuel: armature modifier ekle (HDS bunu otomatik yapmayabilir)
    if "Armature" not in [m.name for m in mesh_obj.modifiers]:
        arm_mod = mesh_obj.modifiers.new("Armature", 'ARMATURE')
        arm_mod.object = armature_obj
    
    return True
```

### 6.3 Automatic Weights (Fallback)

```python
def skin_with_automatic_weights(mesh_obj, armature_obj):
    """Blender'ın built-in Automatic Weights."""
    bpy.ops.object.select_all(action='DESELECT')
    mesh_obj.select_set(True)
    armature_obj.select_set(True)
    bpy.context.view_layer.objects.active = armature_obj  # parent armature
    
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    
    # parent_set armature modifier de ekler otomatik
    return True
```

### 6.4 Post-Processing: Normalize

```python
def normalize_weights_per_vertex(mesh_obj):
    """
    Her vertex'in tüm weight'lerini topla, sum=1 olacak şekilde scale et.
    """
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.mode_set(mode='OBJECT')
    
    vgroups = mesh_obj.vertex_groups
    
    for vert in mesh_obj.data.vertices:
        # Bu vertex'in tüm weight'lerini topla
        weights = []
        for vg in vgroups:
            try:
                w = vg.weight(vert.index)
                if w > 0:
                    weights.append((vg, w))
            except RuntimeError:
                # vertex bu group'a ait değil
                pass
        
        total = sum(w for _, w in weights)
        
        if total <= 0:
            # Orphan: en yakın bone'a 1.0 ver (fallback)
            # NOT: gerçek uygulamada en yakın bone hesabı lazım
            # Burada sadece warning kayıt edilir
            continue
        
        # Normalize
        for vg, w in weights:
            vg.add([vert.index], w / total, 'REPLACE')
```

### 6.5 Post-Processing: Cap to 4 Influences

```python
def cap_weights_to_n(mesh_obj, n=4):
    """
    Her vertex'in en fazla N bone influence'ı olsun.
    Fazlalar (en düşükten başlayarak) silinir, sonra renormalize.
    """
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.mode_set(mode='OBJECT')
    
    vgroups = mesh_obj.vertex_groups
    vertices_capped = 0
    
    for vert in mesh_obj.data.vertices:
        weights = []
        for vg in vgroups:
            try:
                w = vg.weight(vert.index)
                if w > 0:
                    weights.append((vg, w))
            except RuntimeError:
                pass
        
        if len(weights) <= n:
            continue
        
        # Sort by weight desc, ilk n'i tut
        weights.sort(key=lambda x: x[1], reverse=True)
        keep = weights[:n]
        drop = weights[n:]
        
        # Drop edilenleri sıfırla
        for vg, _ in drop:
            vg.remove([vert.index])
        
        # Kalanları renormalize
        total = sum(w for _, w in keep)
        if total > 0:
            for vg, w in keep:
                vg.add([vert.index], w / total, 'REPLACE')
        
        vertices_capped += 1
    
    return vertices_capped
```

### 6.6 Post-Processing: Mirror X (Simetri)

```python
def mirror_weights_x(mesh_obj):
    """
    X<0 vertex'lerinden X>0 vertex'lerine weight'i mirror et.
    Bone naming convention: <name>_L ↔ <name>_R
    """
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.mode_set(mode='OBJECT')
    
    vgroups = mesh_obj.vertex_groups
    
    # Bone L/R mapping
    bone_pairs = {}  # left_name -> right_name
    for vg in vgroups:
        if vg.name.endswith("_L"):
            r_name = vg.name[:-2] + "_R"
            if r_name in vgroups:
                bone_pairs[vg.name] = r_name
    
    # Her sol vertex için sağ aynası bul, weight'leri kopyala
    verts = mesh_obj.data.vertices
    vertices_mirrored = 0
    
    # Sol-sağ vertex map (X koordinatına göre)
    import numpy as np
    coords = np.array([[v.co.x, v.co.y, v.co.z] for v in verts])
    
    # Sol vertex'ler (X < -epsilon)
    left_mask = coords[:, 0] < -0.001
    right_mask = coords[:, 0] > 0.001
    
    left_indices = np.where(left_mask)[0]
    right_indices = np.where(right_mask)[0]
    
    if len(left_indices) == 0 or len(right_indices) == 0:
        return 0
    
    right_coords = coords[right_indices]
    
    for left_idx in left_indices:
        left_co = coords[left_idx]
        # Bu vertex'in X-mirror'u olan sağ vertex'i bul
        target_co = np.array([-left_co[0], left_co[1], left_co[2]])
        
        # Sağ vertex'ler içinde en yakını bul
        dists = np.linalg.norm(right_coords - target_co, axis=1)
        nearest_right = right_indices[np.argmin(dists)]
        
        if dists[np.argmin(dists)] > 0.01:
            continue  # mirror çiftli değil
        
        # Sol vertex'in weight'lerini al
        for left_vg in vgroups:
            try:
                w = left_vg.weight(left_idx)
            except RuntimeError:
                continue
            if w <= 0:
                continue
            
            # Hedef sağ vertex group'u bul
            if left_vg.name.endswith("_L"):
                right_vg_name = bone_pairs.get(left_vg.name)
                if right_vg_name and right_vg_name in vgroups:
                    vgroups[right_vg_name].add([nearest_right], w, 'REPLACE')
            elif left_vg.name.endswith("_R"):
                pass  # sağ vertex'in sağ bone weight'i normal kalır
            else:
                # Center bone (spine, head, vb.) — aynı bone'a aynı weight
                left_vg.add([nearest_right], w, 'REPLACE')
        
        vertices_mirrored += 1
    
    return vertices_mirrored
```

### 6.7 Post-Processing: Smooth

```python
def smooth_weights(mesh_obj, factor=0.5, iterations=2):
    """
    Vertex weight'lerini komşu vertex'lerle yumuşat.
    Blender'ın built-in operator'ünü kullan.
    """
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
    
    for _ in range(iterations):
        bpy.ops.object.vertex_group_smooth(
            group_select_mode='ALL',
            factor=factor,
            repeat=1,
            expand=0.0,
        )
    
    bpy.ops.object.mode_set(mode='OBJECT')
```

### 6.8 Cleanup ve Validation

```python
def cleanup_empty_weights(mesh_obj, threshold=0.001):
    """0'a yakın weight'leri sıfırla."""
    for vg in mesh_obj.vertex_groups:
        for vert in mesh_obj.data.vertices:
            try:
                w = vg.weight(vert.index)
                if w < threshold:
                    vg.remove([vert.index])
            except RuntimeError:
                pass


def validate_skinning(mesh_obj):
    """Skinning kalitesi kontrol."""
    results = {"errors": [], "warnings": []}
    
    vgroups = mesh_obj.vertex_groups
    verts = mesh_obj.data.vertices
    
    orphan_count = 0
    weight_sum_violations = 0
    over_4_count = 0
    
    for vert in verts:
        weights = []
        for vg in vgroups:
            try:
                w = vg.weight(vert.index)
                if w > 0:
                    weights.append(w)
            except RuntimeError:
                pass
        
        if len(weights) == 0:
            orphan_count += 1
            continue
        
        if len(weights) > 4:
            over_4_count += 1
        
        total = sum(weights)
        if abs(total - 1.0) > 0.01:
            weight_sum_violations += 1
    
    if orphan_count > 0:
        results["errors"].append(f"Orphan vertex (weight'siz): {orphan_count}")
    
    if weight_sum_violations > 0:
        results["errors"].append(f"Weight sum != 1.0: {weight_sum_violations} vertex")
    
    if over_4_count > 0:
        results["errors"].append(f"Over 4 influence: {over_4_count} vertex")
    
    return results
```

---

## 7. VALIDATION CRITERIA

| # | Kriter | Hata |
|---|---|---|
| V1 | Mesh'e Armature modifier eklenmiş, target = armature_obj | error: ekle |
| V2 | Tüm vertex'lerin en az 1 weight'i var (orphan yok) | error: en yakın bone'a 1.0 ata |
| V3 | Her vertex'in weights sum = 1.0 (±0.01 tolerans) | error: normalize |
| V4 | Max 4 influence per vertex | error: cap_weights_to_4 yeniden çağır |
| V5 | Tüm weights ≥ 0 | error: corruption, baştan başla |
| V6 | Simetri max delta < 0.005 | warning: mirror_x yeniden çağır |
| V7 | IK target / pole bone'lara weight verilmemiş (use_deform=False) | error: cleanup |
| V8 | Hiçbir vertex tek bone'a 100% bağlı değil (eklem yerlerinde) | warning: smooth pass ekle |

---

## 8. FAILURE MODES & RECOVERY

### F1: Voxel HDS yüklü ama operator adı farklı
**Recovery:** Multiple operator adlarını dene (`wm.voxel_heat_diffuse`, `object.voxel_heat_diffuse_skinning`, `mesh.voxel_heat_diffuse`). Hiçbiri çalışmazsa fallback'a geç.

### F2: Automatic Weights "Bone Heat weighting failed" hatası
**Recovery:** Bu, mesh non-manifold veya armature içeride olduğu zaman olur. Voxel remesh'i tekrar uygula (P04'e geri dön), sonra dene.

### F3: Tüm vertex'ler tek bone'a bağlandı (corrupted)
**Recovery:** Vertex groups'u sıfırla, baştan tüm pipeline'ı çalıştır. Mesh tarafında problem var (P04'e ihbar).

### F4: Symmetry massive sapma
**Recovery:** Mesh kendisi asimetrik (modeling hatası). P04'e geri dön, mesh'i mirror modifier ile rebuild et.

### F5: Cap'leme sonrası bazı vertex'ler 0 toplam weight'e düştü
**Recovery:** Cap algoritmasında bug, en yüksek tek weight'i en azından %1 bırakacak şekilde refactor.

---

## 9. EXAMPLE I/O

**Input:** mesh_v1.blend (P04'ten, manifold + 11842 tris) + SkeletonBlueprint.json

**Expected output (sane):**
```
[skinner] Method: voxel_heat_diffuse
[skinner] Skinning... ~3 dk
  ✓ 6234 vertex skinned
[skinner] Post-processing...
  ✓ normalize: 6234 vertex
  ✓ cap_to_4: 1842 vertex capped
  ✓ mirror_X: 2917 vertex mirrored, max delta 0.003
  ✓ smooth pass 1 (factor 0.5)
  ✓ smooth pass 2 (factor 0.3)
  ✓ cleanup empty weights: 47 removed
[skinner] Validation...
  ✓ All verts have weights
  ✓ All weights sum to 1.0
  ✓ Max influence: 4
  ✓ Symmetry max delta: 0.003
[skinner] skinned_v1.blend kaydedildi
```

---

## 10. IMPLEMENTATION NOTES

Executable bpy: `scripts/production/build_skinning.py`.

Orchestrator çağrı:
```python
subprocess.run([
    "blender", "--background", str(run_dir / "blender_scenes/mesh_v1.blend"),
    "--python", "scripts/production/build_skinning.py",
    "--",
    "--blueprint", str(run_dir / "SkeletonBlueprint.json"),
    "--mesh-manifest", str(run_dir / "MeshManifest.json"),
    "--budget", str(run_dir / "BudgetSpec.json"),
    "--output-blend", str(run_dir / "blender_scenes/skinned_v1.blend"),
    "--method", "auto",  # auto/voxel_hds/automatic_weights
], timeout=1200)
```
