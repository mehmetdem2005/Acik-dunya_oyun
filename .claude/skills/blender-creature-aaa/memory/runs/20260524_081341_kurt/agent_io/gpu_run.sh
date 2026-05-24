#!/usr/bin/env bash
# ============================================================================
# GPU PIPELINE — TripoSG kurt mesh uretimi + Blender import
# Once: bash gpu_setup.sh
#   bash gpu_run.sh
# ============================================================================
set -e
RUN="$(cd "$(dirname "$0")/.." && pwd)"          # .../memory/runs/<ts>
REF="$RUN/refs/wolf_side.png"
BL="$(command -v blender || echo ~/blender42/blender-4.2.9-linux-x64/blender)"
OUT="$RUN/blender_scenes"
mkdir -p "$OUT"

echo ">>> [1/2] TripoSG mesh uretimi (GPU) — tris'i Tripo belirler (--faces yok)"
cd ~/TripoSG_repo
# Yuksek kalite: --faces vermeden native; istersen --faces 80000
python3 -m scripts.inference_triposg \
  --image-input "$REF" \
  --output-path "$OUT/triposg_wolf.glb"
echo "    -> $OUT/triposg_wolf.glb"

echo ">>> [2/2] Blender import + auto-orient + olcek + onizleme render"
"$BL" --background --factory-startup --python "$RUN/agent_io/ai_import_textured.py" -- \
  "$OUT/triposg_wolf.glb" "$OUT/triposg_wolf.blend" "$RUN/renders/iter_gpu_triposg" 56 || \
"$BL" --background --factory-startup --python "$RUN/agent_io/ai_render_white.py" -- \
  "$OUT/triposg_wolf.glb" "$OUT/triposg_wolf.blend" "$RUN/renders/iter_gpu_triposg" 56

echo ">>> TAMAM. Render: $RUN/renders/iter_gpu_triposg/"
echo ">>> Sonraki: rig (skeleton fit + skin_proximity) -> wolf_animate -> build_export (bkz gpu_runbook.md)"
