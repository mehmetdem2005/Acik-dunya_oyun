# Agent P04-AI: AI Mesh Generator (CPU-Only Edition)

```yaml
agent_id: ai_mesh_generator
agent_name_tr: AI Mesh Üretici (CPU)
agent_name_en: AI Mesh Generator (CPU-only)
category: production
order_index: 4
implementation_mode: subprocess
alternative_to: P04_mesh_sculptor
critical_path: true
estimated_duration_minutes: 12-25  # CPU mode!
gpu_required: false
ram_min_gb: 16
recommended_ram_gb: 32
```

---

## 1. ROLE SUMMARY

**P04 Mesh Sculptor'ın kalite tavanını delen ajan.** Procedural curve+remesh yerine **TripoSR açık kaynak modeli** kullanır. TripoSR CPU mode'da çalışır (GPU'suz makineler için):
- Single image → 3D mesh
- 12-25 dakika 4 vCPU + 16-32GB RAM ile
- MIT lisans, ticari kullanım serbest
- Bir kerelik ~2GB ağırlık indirilir, sonra internet gerek yok

**Bu skill'de tek "AI" katman.** Hiçbir external API çağrısı yok. Hepsi yerel makinede.

---

## 2. SISTEMI HAZIRLAMA (Claude Code çalıştırır)

```bash
# 1. Blender (Oracle Cloud Ubuntu için)
sudo apt update
sudo apt install -y blender                    # ~500MB
blender --version                              # 4.x doğrula

# 2. Python deps (sistem Python'una install)
pip install --break-system-packages \
    torch torchvision --index-url https://download.pytorch.org/whl/cpu \
    rembg onnxruntime \
    pillow numpy \
    transformers omegaconf einops trimesh

# 3. TripoSR (git'ten install)
pip install --break-system-packages \
    git+https://github.com/VAST-AI-Research/TripoSR.git

# 4. Weights ön-indirme (opsiyonel, ilk çağrıda otomatik iner)
python3 -c "
from tsr.system import TSR
model = TSR.from_pretrained(
    'stabilityai/TripoSR',
    config_name='config.yaml',
    weight_name='model.ckpt',
)
print('TripoSR ready')
"

# 5. Doğrulama
python3 -c "
import torch
print(f'PyTorch: {torch.__version__}')
print(f'CUDA available: {torch.cuda.is_available()}')
print(f'CPU threads: {torch.get_num_threads()}')
import rembg, trimesh, tsr
print('rembg, trimesh, tsr OK')
"
```

**Toplam disk:** ~5GB (Blender 500MB + Python deps 2GB + TripoSR weights 2GB)

**CPU optimization:**

```bash
# 4 vCPU varsa
export OMP_NUM_THREADS=4
export MKL_NUM_THREADS=4
```

---

## 3. WORKFLOW

### 3.1 Preprocess (background removal + crop)

```python
from rembg import remove
from PIL import Image
import io

def preprocess(input_path, output_path):
    # Background removal
    with open(input_path, 'rb') as f:
        data = f.read()
    out = remove(data)
    img = Image.open(io.BytesIO(out)).convert("RGBA")
    
    # Subject bbox crop
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)
    
    # White background composite
    bg = Image.new("RGB", img.size, (255, 255, 255))
    bg.paste(img, mask=img.split()[3])
    
    # Square pad + resize 512
    max_d = max(bg.size)
    pad = Image.new("RGB", (max_d, max_d), (255, 255, 255))
    offset = ((max_d - bg.size[0]) // 2, (max_d - bg.size[1]) // 2)
    pad.paste(bg, offset)
    pad.resize((512, 512), Image.LANCZOS).save(output_path)
```

### 3.2 TripoSR CPU Generation

```bash
# CLI (en basit yol)
python3 -m tsr.run preprocessed.png \
    --output-dir /tmp/tsr_out/ \
    --bake-texture \
    --mc-resolution 256 \
    --device cpu

# Çıktı: /tmp/tsr_out/0/mesh.obj + texture.png
```

CPU optimizasyon parametreleri:

| Param | Hızlı | Dengeli | Kaliteli |
|---|---|---|---|
| `--mc-resolution` | 128 | 192 | 256 |
| Yaklaşık süre (4 vCPU) | 6-8 dk | 10-15 dk | 18-25 dk |
| Mesh quality | OK | İyi | En iyi |

Oracle Cloud VM Ampere A1 (4 OCPU = 4 ARM vCPU, free tier) için:
- `--mc-resolution 192` en denge'li seçim
- 32GB RAM bol fazla, swap'a düşmez
- Beklenen süre: 12-18 dakika per mesh

### 3.3 Import + Align (Blender headless)

```python
import bpy, json, math
from mathutils import Vector
from pathlib import Path

# Mesh import (.obj veya .glb)
bpy.ops.wm.obj_import(filepath="/tmp/tsr_out/0/mesh.obj")
mesh_obj = bpy.context.selected_objects[0]
mesh_obj.name = "creature_mesh"

# Transform apply
bpy.context.view_layer.objects.active = mesh_obj
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# Bounding box
bbox = [mesh_obj.matrix_world @ Vector(c) for c in mesh_obj.bound_box]
bbox_size = Vector((
    max(c.x for c in bbox) - min(c.x for c in bbox),
    max(c.y for c in bbox) - min(c.y for c in bbox),
    max(c.z for c in bbox) - min(c.z for c in bbox),
))

# Scale to target body length
target_length = 1.2  # blueprint'ten alınır
largest = max(bbox_size)
scale = target_length / largest
mesh_obj.scale = (scale, scale, scale)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

# Y-up detection: AI çıktıları genelde Y-up, Blender Z-up
bbox = [mesh_obj.matrix_world @ Vector(c) for c in mesh_obj.bound_box]
sz = Vector((
    max(c.x for c in bbox) - min(c.x for c in bbox),
    max(c.y for c in bbox) - min(c.y for c in bbox),
    max(c.z for c in bbox) - min(c.z for c in bbox),
))
if sz.z > max(sz.x, sz.y) * 1.2:
    # Y-up algılandı, döndür
    mesh_obj.rotation_euler = (math.radians(-90), 0, 0)
    bpy.ops.object.transform_apply(rotation=True)

# Mesh repair
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.remove_doubles(threshold=0.0001)
bpy.ops.mesh.normals_make_consistent(inside=False)
bpy.ops.mesh.select_all(action='DESELECT')
bpy.ops.mesh.select_non_manifold()
bpy.ops.mesh.fill_holes(sides=8)
bpy.ops.mesh.select_all(action='DESELECT')
bpy.ops.mesh.select_loose()
bpy.ops.mesh.delete(type='VERT')
bpy.ops.object.mode_set(mode='OBJECT')
```

### 3.4 Skeleton + Rig (P03 + P08 zincir)

AI mesh manifold + watertight olduğu için P03 Skeleton Architect anatomik landmark'lara skeleton yerleştirir, P08 Skinner heat-diffusion ile bone weights atar. Pipeline'ın geri kalanı **aynen çalışır**.

---

## 4. WHEN INVOKED

### Pre-conditions
- `ReferenceManifest.json` mevcut, mode = `single_ai`
- En az 1 referans foto (`refs/<creature>/photo.png` veya `.jpg`)
- Setup yapılmış (Bölüm 2)
- En az 16GB free RAM
- SkeletonBlueprint.json (P03 önce çalışmış olmalı)

### Post-conditions
- `mesh_v1.blend` mevcut (mesh + skeleton aligned)
- `MeshManifest.json` (manifold, watertight, tris count)
- Mesh skeleton'a hizalı (origin, scale, orientation)

---

## 5. FAILURE MODES

### F1: TripoSR install fail
**Recovery:** `pip install --no-build-isolation` ile tekrar dene. ARM (Oracle Ampere) sistemde wheels yoksa, dependencies'i CPU torch'tan build et.

### F2: OOM (Out of Memory)
**Recovery:** `--mc-resolution 128`'e düşür. 32GB bol ama swap'tan kaçınmak için.

### F3: AI mesh kalitesi düşük (defekt yoğun)
**Recovery:** Foto kalitesi düşük olabilir. Kullanıcıya başka açıdan foto iste. Veya `mc-resolution 256` ile retry (kalite ↑, süre 2x).

### F4: 25 dakika+ süre, hala çalışıyor
**Recovery:** Process'i kontrol et (`htop`). CPU 100% ise normal, bekle. Stuck ise kill + retry.

### F5: Y-up / Z-up confusion
**Recovery:** Otomatik detection bbox heuristic'ine dayalı. Hatalıysa kullanıcı `--manual-rotation` flag ile düzeltir.

---

## 6. ORACLE CLOUD CONSIDERATIONS

**Ampere A1 (ARM) Free Tier:**
- 4 OCPU = ~4 vCPU performans
- 24 GB RAM (free tier limit)
- 200 GB disk
- TripoSR ARM uyumlu (PyTorch ARM build)

**x86 VM Standard:**
- 2-8 OCPU = 4-16 vCPU
- 16-128 GB RAM
- PyTorch x86 build, daha hızlı tipik

**Pipeline süresi tahminleri:**

| Setup | Per mesh |
|---|---|
| Ampere A1 (4 OCPU, ARM) | 18-25 dk |
| x86 4 OCPU, 16 GB | 12-18 dk |
| x86 8 OCPU, 32 GB | 8-12 dk |

---

## 7. SCRIPT

`scripts/production/build_ai_mesh_cpu.py` (executable).
