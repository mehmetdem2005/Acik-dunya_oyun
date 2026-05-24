#!/usr/bin/env python3
"""
replay_engine.py — D01 alt bileşen: State replay

Bir state_id'nin workspace'ini geri yükler. Pipeline o noktadan devam edebilir.

Kullanım:
    python replay_engine.py replay <state_id> --workspace memory/current
    python replay_engine.py bisect <state_a> <state_b>  # iki state arası bisect
"""

import argparse
import json
import shutil
import sys
from pathlib import Path


STATES_DIR = Path("memory/states")


def replay_state(state_id, workspace_dir, clean=True):
    """
    State'i workspace'e kopyala.
    
    clean=True: workspace'i önce sil
    """
    state_dir = STATES_DIR / state_id
    if not state_dir.exists():
        print(f"❌ State {state_id} yok", file=sys.stderr)
        return False
    
    workspace = Path(workspace_dir)
    
    if clean and workspace.exists():
        # Sadece pipeline file'larını sil, kullanıcı veri korunsun
        for sub in ["manifests", "blender_scenes", "renders", "agent_io",
                    "critic_reports"]:
            target = workspace / sub
            if target.exists():
                shutil.rmtree(target)
        # Manifest JSON'ları
        for jf in workspace.glob("*Manifest.json"):
            jf.unlink()
        for jf in workspace.glob("*Spec.json"):
            jf.unlink()
        for jf in workspace.glob("*Blueprint.json"):
            jf.unlink()
    
    workspace.mkdir(parents=True, exist_ok=True)
    
    # Restore blend
    blend_src = state_dir / "scene.blend"
    if blend_src.exists():
        blend_dst = workspace / "blender_scenes"
        blend_dst.mkdir(parents=True, exist_ok=True)
        # Hangi aşamaya ait olduğu agent_name'den belli olmalı, manifest'e bak
        agent_name = "scene"
        metrics_file = state_dir / "metrics.json"
        if metrics_file.exists():
            # agent name pattern matching: parent.txt veya index'ten
            pass
        shutil.copy(blend_src, blend_dst / f"{agent_name}.blend")
    
    # Restore manifests
    manifests_src = state_dir / "manifests"
    if manifests_src.exists():
        for jf in manifests_src.glob("*.json"):
            shutil.copy(jf, workspace / jf.name)
    
    # Restore renders
    renders_src = state_dir / "renders"
    if renders_src.exists():
        renders_dst = workspace / "renders" / "current"
        renders_dst.mkdir(parents=True, exist_ok=True)
        for f in renders_src.glob("*"):
            shutil.copy(f, renders_dst / f.name)
    
    print(f"✓ Replayed state {state_id} → {workspace}")
    return True


def get_ancestry_chain(state_id):
    """Root → state_id chain."""
    tree_file = STATES_DIR / "_tree.json"
    if not tree_file.exists():
        return [state_id]
    
    tree = json.loads(tree_file.read_text())
    
    chain = []
    curr = state_id
    while curr:
        chain.append(curr)
        node = tree["nodes"].get(curr)
        if node is None:
            break
        curr = node.get("parent")
    
    return chain[::-1]


def bisect_states(state_a, state_b, criterion="regression_detected"):
    """
    İki state arası bisect — defekt nerede başladı?
    
    Algoritma:
      A = healthy state
      B = broken state
      Mid = (A,B) arası middle state
      Mid'i replay et + critic çalıştır
      Mid healthy → defekt B tarafında, A=Mid, recurse
      Mid broken → defekt Mid'de veya öncesinde, B=Mid, recurse
    """
    chain_a = get_ancestry_chain(state_a)
    chain_b = get_ancestry_chain(state_b)
    
    # Common ancestor bulmaca
    common = set(chain_a) & set(chain_b)
    if not common:
        print("❌ A ve B aynı tree'de değil", file=sys.stderr)
        return None
    
    common_ancestor = None
    for s in chain_a[::-1]:
        if s in common:
            common_ancestor = s
            break
    
    print(f"Common ancestor: {common_ancestor}")
    
    # B'nin chain'inde common'dan başlayarak ilerle
    common_idx = chain_b.index(common_ancestor)
    target_chain = chain_b[common_idx:]
    
    # Linear scan (bisect'den daha basit, az state için)
    print(f"Defekt aramak için chain: {[s[:16] for s in target_chain]}")
    
    # Bu noktada her state için critic re-run gerekir
    # Implementation: replay each, run C05 budget compliance (en hızlı)
    # Kritik metric'lerden hangi state'te bozuldu tespit
    
    breaking_state = None
    
    for i, sid in enumerate(target_chain):
        state_dir = STATES_DIR / sid
        metrics = json.loads((state_dir / "metrics.json").read_text())
        
        # Basit kriter: manifold bozuk mu?
        if metrics.get("meshmanifest_is_manifold") is False:
            breaking_state = sid
            print(f"❌ Bisect bulgu: {sid} state'inde manifold bozuldu")
            break
    
    if breaking_state is None:
        print("⚠️ Bisect bir kırılma noktası bulamadı. Linear taramada defekt yok.")
        return None
    
    return breaking_state


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    
    p_r = sub.add_parser("replay")
    p_r.add_argument("state_id")
    p_r.add_argument("--workspace", required=True)
    p_r.add_argument("--no-clean", action="store_true")
    
    p_b = sub.add_parser("bisect")
    p_b.add_argument("state_a")
    p_b.add_argument("state_b")
    
    p_chain = sub.add_parser("chain")
    p_chain.add_argument("state_id")
    
    args = p.parse_args()
    
    if args.cmd == "replay":
        ok = replay_state(args.state_id, args.workspace, clean=not args.no_clean)
        sys.exit(0 if ok else 1)
    
    elif args.cmd == "bisect":
        result = bisect_states(args.state_a, args.state_b)
        if result:
            print(f"Breaking point: {result}")
            sys.exit(0)
        else:
            sys.exit(1)
    
    elif args.cmd == "chain":
        chain = get_ancestry_chain(args.state_id)
        for s in chain:
            print(s)


if __name__ == "__main__":
    main()
