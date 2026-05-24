# Module 02: Oracle Cloud CPU Setup

```yaml
module_id: oracle_cpu_setup
runs_once: true
estimated_duration_minutes: 15-30  # ilk seferlik kurulum
```

---

## 1. AMAÇ

Oracle Cloud VM (CPU-only, 16-32GB RAM) üzerinde skill'in tüm bağımlılıklarını **tek seferlik** kurar:

- Blender 4.x headless
- Python 3.10+ + dev tools
- PyTorch CPU build
- TripoSR + dependencies
- rembg + onnxruntime
- Diğer Python deps

**Toplam disk:** ~5GB
**Toplam süre:** 15-30 dakika (internet hızına bağlı)
**Bir kerelik.** Sonra her yaratık için bu kurulum tekrar gerekmez.

---

## 2. SİSTEM TESPİTİ

İlk adım: Hangi Oracle VM tipinde olduğumuzu bulalım.

```bash
# Mimari
uname -m
# x86_64 → x86 VM
# aarch64 → Ampere A1 (ARM)

# CPU
nproc
cat /proc/cpuinfo | grep "model name" | head -1

# RAM
free -h

# Disk
df -h /

# OS
cat /etc/os-release | head -2
```

Beklenen Oracle defaults:
- **Ampere A1 Free:** aarch64, 4 vCPU, 24GB RAM, Oracle Linux 8 / Ubuntu 22.04
- **x86 VM Standard:** x86_64, 1-8 OCPU, 16-128GB RAM, Oracle Linux 8 / Ubuntu

---

## 3. KURULUM ADIMLARI

### 3.1 Ubuntu/Debian (yaygın)

```bash
# Update
sudo apt update && sudo apt upgrade -y

# Sistem paketleri
sudo apt install -y \
    python3 python3-pip python3-dev python3-venv \
    build-essential cmake git wget curl \
    libgl1-mesa-glx libglib2.0-0 libxi6 libxrender1 libxkbcommon0 \
    libxxf86vm1 libsm6 libxext6 libxrandr2 \
    libgomp1

# Blender 4.x (snap veya manual)
# Option A: snap (en kolay)
sudo snap install blender --classic

# Option B: manuel (en güvenli versiyon kontrolü)
cd /tmp
ARCH=$(uname -m)
if [ "$ARCH" = "x86_64" ]; then
    wget https://download.blender.org/release/Blender4.2/blender-4.2.0-linux-x64.tar.xz
    sudo tar -xJf blender-4.2.0-linux-x64.tar.xz -C /opt/
    sudo ln -sf /opt/blender-4.2.0-linux-x64/blender /usr/local/bin/blender
elif [ "$ARCH" = "aarch64" ]; then
    # ARM için: snap, yoksa kaynak derleme (uzun)
    sudo snap install blender --classic
fi

blender --version  # 4.x doğrula
```

### 3.2 Oracle Linux 8/9

```bash
sudo dnf install -y \
    python3 python3-pip python3-devel \
    gcc gcc-c++ make cmake git wget \
    mesa-libGL mesa-libEGL libglvnd-glx \
    libXi libXrender libXrandr libXcursor libXinerama

# Blender (Flatpak)
sudo dnf install -y flatpak
flatpak install -y flathub org.blender.Blender
# Veya manuel tar download (yukarıdaki Ubuntu'daki gibi)
```

### 3.3 Python Bağımlılıkları (tüm distros)

```bash
# Pip upgrade
python3 -m pip install --upgrade pip --break-system-packages

# CPU-only PyTorch (en kritik, en büyük)
pip install --break-system-packages \
    torch torchvision \
    --index-url https://download.pytorch.org/whl/cpu

# Doğrula
python3 -c "import torch; print(f'torch {torch.__version__}, CPU only: {not torch.cuda.is_available()}')"

# AI mesh generation deps
pip install --break-system-packages \
    rembg onnxruntime \
    transformers omegaconf einops \
    trimesh pillow numpy

# TripoSR
pip install --break-system-packages \
    git+https://github.com/VAST-AI-Research/TripoSR.git

# Vision/utility
pip install --break-system-packages \
    matplotlib pygltflib opencv-python-headless
```

### 3.4 TripoSR Weights Ön İndirme (opsiyonel)

İlk çağrıda otomatik iner. Ama önceden indir ki ilk çalıştırmada beklemeyelim:

```bash
python3 << 'EOF'
from huggingface_hub import hf_hub_download

# TripoSR weights (~2GB)
print("Downloading TripoSR weights...")
hf_hub_download(repo_id="stabilityai/TripoSR", filename="config.yaml")
hf_hub_download(repo_id="stabilityai/TripoSR", filename="model.ckpt")
print("✓ TripoSR weights downloaded to ~/.cache/huggingface/")
EOF
```

### 3.5 Doğrulama

```bash
# Hepsi kurulu mu kontrol
python3 << 'EOF'
import sys

modules = ["torch", "torchvision", "rembg", "onnxruntime",
           "transformers", "einops", "trimesh", "PIL",
           "numpy", "tsr", "matplotlib"]

print("Module check:")
for m in modules:
    try:
        mod = __import__(m)
        version = getattr(mod, '__version__', 'OK')
        print(f"  ✓ {m}: {version}")
    except ImportError as e:
        print(f"  ❌ {m}: NOT INSTALLED")
        sys.exit(1)

# CPU/RAM
import os
print(f"\nCPU count: {os.cpu_count()}")

import psutil
ram_gb = psutil.virtual_memory().total / (1024**3)
print(f"RAM total: {ram_gb:.1f} GB")
print(f"RAM available: {psutil.virtual_memory().available / (1024**3):.1f} GB")

# Blender
import subprocess
r = subprocess.run(["blender", "--version"], capture_output=True, text=True)
print(f"\nBlender: {r.stdout.split(chr(10))[0]}")

print("\n✅ Setup complete. P04-AI çalıştırılabilir.")
EOF
```

---

## 4. CPU OPTİMİZASYON

Pipeline öncesi her zaman:

```bash
# Tüm CPU çekirdeklerini kullan
export OMP_NUM_THREADS=$(nproc)
export MKL_NUM_THREADS=$(nproc)
export NUMEXPR_NUM_THREADS=$(nproc)
export OPENBLAS_NUM_THREADS=$(nproc)

# PyTorch CPU optim
export MKL_DYNAMIC=FALSE
export OMP_DYNAMIC=FALSE
```

`.bashrc`'a ekle, persistent yap.

---

## 5. SWAP (16GB RAM sistemler için)

32GB RAM'i varsa gerekli değil. 16GB RAM Oracle Free Tier için TripoSR mc_res 256 sırasında swap'a düşebilir. Önleme:

```bash
# 8GB swap file (Oracle 200GB disk'i bol)
sudo fallocate -l 8G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Kalıcı
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Doğrula
free -h
```

---

## 6. KURULUM SONUÇ ÇIKTILARI

`memory/system_capabilities.json`:

```json
{
  "os": "Ubuntu 22.04",
  "arch": "x86_64",
  "cpu_count": 4,
  "ram_gb_total": 32,
  "ram_gb_available": 28,
  "disk_free_gb": 180,
  "blender_version": "4.2.0",
  "python_version": "3.10.12",
  "torch_version": "2.1.0",
  "torch_cuda": false,
  "tsr_installed": true,
  "rembg_installed": true,
  "expected_mesh_gen_time_min": 18,
  "recommended_mc_resolution": 192
}
```

`build_ai_mesh_cpu.py` bunu okuyup CPU optimizasyon parametrelerini buradan alır.

---

## 7. ANTI-PATTERNS

- ❌ `--break-system-packages` olmadan pip install (Ubuntu 23+ PEP 668 nedeniyle fail)
- ❌ GPU PyTorch (yanlış index): `pip install torch` (CUDA istemeden çekilebilir, CPU index lazım)
- ❌ TripoSR'ı `--mc-resolution 320` ile CPU'da çalıştırma (45+ dakika sürer)
- ❌ Background removal (rembg) atlanırsa AI mesh kalitesi düşer
- ❌ `OMP_NUM_THREADS=1` (CPU yarı kapasitede)
