#!/usr/bin/env bash
# Bir eleştiri turunun render'ını üretir.
# Kullanım: ./run_round.sh round_01
set -e
TAG="${1:?tag gerekli, orn: round_01}"
cd "$(dirname "$0")"
blender --background --python kurt_generator.py -- \
    --params wolf_params.json --render --save-blend --out-tag "$TAG" 2>&1 \
    | grep -E "tri \(subsurf\)|RENDERED|Error|Traceback" || true
echo "RENDERS: renders/${TAG}_{side,front,three_q,top,rear_q}.png"
