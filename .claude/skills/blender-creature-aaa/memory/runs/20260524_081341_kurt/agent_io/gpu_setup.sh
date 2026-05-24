#!/usr/bin/env bash
# ============================================================================
# GPU ORTAMI KURULUM — TripoSG foto-real kurt pipeline
# CUDA GPU'lu bir makinede (>=8GB VRAM) calistir. CPU'da CALISMAZ (diso CUDA ister).
#   bash gpu_setup.sh
# ============================================================================
set -e
echo ">>> [1/5] CUDA PyTorch"
# CUDA 12.1 wheel (GPU surucune gore cu118/cu121/cu124 sec)
pip install --break-system-packages torch torchvision --index-url https://download.pytorch.org/whl/cu121

echo ">>> [2/5] TripoSG repo"
[ -d ~/TripoSG_repo ] || git clone https://github.com/VAST-AI-Research/TripoSG.git ~/TripoSG_repo

echo ">>> [3/5] TripoSG bagimliliklari (diso GPU'da derlenir)"
pip install --break-system-packages diffusers transformers einops huggingface_hub \
    opencv-python trimesh omegaconf scikit-image peft jaxtyping typeguard pymeshlab diso

echo ">>> [4/5] Blender 4.2 (yoksa indir)"
if ! command -v blender >/dev/null 2>&1 && [ ! -x ~/blender42/blender-4.2.9-linux-x64/blender ]; then
  mkdir -p ~/blender42 && cd ~/blender42
  curl -sL -o b.tar.xz "https://download.blender.org/release/Blender4.2/blender-4.2.9-linux-x64.tar.xz"
  tar xf b.tar.xz
  ln -sf ~/blender42/blender-4.2.9-linux-x64/blender /usr/local/bin/blender || true
fi

echo ">>> [5/5] GL libs (headless render icin)"
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  libegl1 libgl1 libglx-mesa0 libgl1-mesa-dri libgles2 libxi6 libxrender1 libxxf86vm1 \
  libxfixes3 libxkbcommon0 libsm6 libice6 libxext6 libxrandr2 libgomp1 2>/dev/null || true

echo ">>> KURULUM TAMAM. Sonra: bash gpu_run.sh"
