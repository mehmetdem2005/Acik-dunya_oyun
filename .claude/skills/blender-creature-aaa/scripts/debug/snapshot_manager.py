#!/usr/bin/env python3
"""
snapshot_manager.py — D01 alt bileşen: State Snapshot CRUD

Her ajan çıktısının tam görüntüsünü disk'e yazar, indeksler, sorgular.

Kullanım:
    capture: yeni state oluştur
    get: state_id ile yükle
    list: tüm state'ler
    tree: decision tree
    delete: state ve descendant'ları sil

Filesystem layout:
    memory/states/_index.jsonl          # append-only state index
    memory/states/_tree.json            # parent-child ilişkiler
    memory/states/<state_id>/           # bir state'in tüm verisi
        scene.blend
        manifests/*.json
        renders/*.png
        metrics.json
        parent.txt
        decisions.jsonl
"""

import json
import shutil
import argparse
import sys
import hashlib
import uuid
import os
from pathlib import Path
from datetime import datetime, timezone


STATES_DIR = Path("memory/states")
INDEX_FILE = STATES_DIR / "_index.jsonl"
TREE_FILE = STATES_DIR / "_tree.json"


# =============================================================================
# Core operations
# =============================================================================

def ensure_init():
    STATES_DIR.mkdir(parents=True, exist_ok=True)
    if not INDEX_FILE.exists():
        INDEX_FILE.touch()
    if not TREE_FILE.exists():
        TREE_FILE.write_text(json.dumps({"root": None, "nodes": {}}))


def generate_state_id(agent_name):
    """Unique state ID: timestamp_agent_random."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    short = uuid.uuid4().hex[:6]
    return f"{ts}_{agent_name[:12]}_{short}"


def capture_state(agent_name, workspace_dir, parent_state_id=None,
                    iteration=1, decisions=None, metrics=None):
    """
    Workspace'in current state'inden snapshot al.
    """
    ensure_init()
    
    state_id = generate_state_id(agent_name)
    state_dir = STATES_DIR / state_id
    state_dir.mkdir(parents=True, exist_ok=False)
    
    workspace = Path(workspace_dir)
    
    # 1. Blend file
    blend_files = list(workspace.glob("blender_scenes/*.blend"))
    if blend_files:
        # En son modify olan blend
        latest = max(blend_files, key=lambda p: p.stat().st_mtime)
        shutil.copy(latest, state_dir / "scene.blend")
    
    # 2. Manifests
    manifests_dir = state_dir / "manifests"
    manifests_dir.mkdir()
    for json_file in workspace.glob("*.json"):
        if json_file.stem.endswith("Manifest") or json_file.stem == "BudgetSpec" \
           or json_file.stem == "CreatureSpec" or json_file.stem == "SkeletonBlueprint" \
           or json_file.stem == "ReferenceManifest":
            shutil.copy(json_file, manifests_dir / json_file.name)
    
    # 3. Renders (varsa)
    workspace_renders = workspace / "renders" / "current"
    if workspace_renders.exists():
        renders_dir = state_dir / "renders"
        shutil.copytree(workspace_renders, renders_dir)
    
    # 4. Parent link
    if parent_state_id:
        (state_dir / "parent.txt").write_text(parent_state_id)
    
    # 5. Decisions
    if decisions:
        with open(state_dir / "decisions.jsonl", "w") as f:
            for d in decisions:
                f.write(json.dumps(d) + "\n")
    
    # 6. Metrics
    if metrics is None:
        metrics = compute_metrics_from_manifests(manifests_dir)
    (state_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))
    
    # 7. Index update
    index_entry = {
        "state_id": state_id,
        "parent": parent_state_id,
        "agent": agent_name,
        "iteration": iteration,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metrics": metrics,
        "has_blend": (state_dir / "scene.blend").exists(),
        "has_renders": (state_dir / "renders").exists(),
    }
    
    with open(INDEX_FILE, "a") as f:
        f.write(json.dumps(index_entry) + "\n")
    
    # 8. Tree update
    tree = json.loads(TREE_FILE.read_text())
    tree["nodes"][state_id] = {
        "parent": parent_state_id,
        "children": [],
        "agent": agent_name,
        "timestamp": index_entry["timestamp"],
    }
    if parent_state_id and parent_state_id in tree["nodes"]:
        tree["nodes"][parent_state_id]["children"].append(state_id)
    if parent_state_id is None and tree["root"] is None:
        tree["root"] = state_id
    
    TREE_FILE.write_text(json.dumps(tree, indent=2))
    
    return state_id


def compute_metrics_from_manifests(manifests_dir):
    """Hızlı metric topla, tüm manifestler'den."""
    metrics = {}
    
    files_to_check = {
        "MeshManifest.json": ["tris_count_actual", "verts_count", "is_manifold",
                              "is_watertight"],
        "SkeletonBlueprint.json": ["bone_count_total"],
        "SkinningManifest.json": ["vertex_groups_count", "weights_normalized"],
        "AnimationManifest.json": ["total_actions"],
        "BudgetSpec.json": [],
    }
    
    for fname, fields in files_to_check.items():
        fpath = manifests_dir / fname
        if not fpath.exists():
            continue
        try:
            data = json.loads(fpath.read_text())
            for field in fields:
                if field in data:
                    metrics[f"{fname.replace('.json','').lower()}_{field}"] = data[field]
        except Exception:
            pass
    
    return metrics


def get_state(state_id):
    """State_id ile state metadata yükle."""
    state_dir = STATES_DIR / state_id
    if not state_dir.exists():
        return None
    
    metrics_file = state_dir / "metrics.json"
    metrics = json.loads(metrics_file.read_text()) if metrics_file.exists() else {}
    
    parent = None
    parent_file = state_dir / "parent.txt"
    if parent_file.exists():
        parent = parent_file.read_text().strip()
    
    return {
        "state_id": state_id,
        "state_dir": str(state_dir),
        "parent": parent,
        "metrics": metrics,
        "has_blend": (state_dir / "scene.blend").exists(),
        "has_renders": (state_dir / "renders").exists(),
        "render_paths": [str(p) for p in (state_dir / "renders").glob("*.png")]
                         if (state_dir / "renders").exists() else [],
    }


def list_states(limit=20, agent_filter=None):
    """Tüm state'leri listele (en yenisi başta)."""
    ensure_init()
    if not INDEX_FILE.exists():
        return []
    
    entries = []
    with open(INDEX_FILE) as f:
        for line in f:
            try:
                entries.append(json.loads(line))
            except Exception:
                pass
    
    if agent_filter:
        entries = [e for e in entries if e.get("agent") == agent_filter]
    
    return entries[-limit:][::-1]


def get_tree():
    """Decision tree."""
    ensure_init()
    return json.loads(TREE_FILE.read_text())


def print_tree(node_id=None, indent=0, tree=None):
    """ASCII tree görselleştirme."""
    if tree is None:
        tree = get_tree()
    if node_id is None:
        node_id = tree["root"]
    if node_id is None:
        print("(empty tree)")
        return
    
    node = tree["nodes"].get(node_id)
    if node is None:
        return
    
    prefix = "  " * indent + ("└─ " if indent > 0 else "")
    short_id = node_id.split("_")[-1][:6]
    print(f"{prefix}[{node['agent']}] {short_id}")
    
    for child in node["children"]:
        print_tree(child, indent + 1, tree)


def get_ancestry(state_id):
    """state_id'den root'a giden chain."""
    tree = get_tree()
    chain = []
    current = state_id
    while current is not None:
        chain.append(current)
        node = tree["nodes"].get(current)
        if node is None:
            break
        current = node["parent"]
    return chain[::-1]  # root → current


def delete_state(state_id, cascade=True):
    """State sil. Cascade: tüm descendant'ları da."""
    tree = get_tree()
    
    to_delete = [state_id]
    
    if cascade:
        # BFS descendants
        queue = [state_id]
        while queue:
            curr = queue.pop()
            node = tree["nodes"].get(curr)
            if node:
                for c in node["children"]:
                    to_delete.append(c)
                    queue.append(c)
    
    for sid in to_delete:
        sd = STATES_DIR / sid
        if sd.exists():
            shutil.rmtree(sd)
        if sid in tree["nodes"]:
            # Parent'tan child link kaldır
            parent = tree["nodes"][sid].get("parent")
            if parent and parent in tree["nodes"]:
                if sid in tree["nodes"][parent]["children"]:
                    tree["nodes"][parent]["children"].remove(sid)
            del tree["nodes"][sid]
    
    TREE_FILE.write_text(json.dumps(tree, indent=2))
    
    # Index'ten de sil (rebuild)
    if INDEX_FILE.exists():
        entries = []
        with open(INDEX_FILE) as f:
            for line in f:
                try:
                    e = json.loads(line)
                    if e["state_id"] not in to_delete:
                        entries.append(e)
                except Exception:
                    pass
        
        with open(INDEX_FILE, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")
    
    return len(to_delete)


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    
    p_cap = sub.add_parser("capture")
    p_cap.add_argument("--agent", required=True)
    p_cap.add_argument("--workspace", required=True)
    p_cap.add_argument("--parent", default=None)
    p_cap.add_argument("--iteration", type=int, default=1)
    
    p_get = sub.add_parser("get")
    p_get.add_argument("state_id")
    
    p_list = sub.add_parser("list")
    p_list.add_argument("--limit", type=int, default=20)
    p_list.add_argument("--agent", default=None)
    
    sub.add_parser("tree")
    
    p_del = sub.add_parser("delete")
    p_del.add_argument("state_id")
    p_del.add_argument("--no-cascade", action="store_true")
    
    args = parser.parse_args()
    
    if args.cmd == "capture":
        sid = capture_state(args.agent, args.workspace, args.parent, args.iteration)
        print(sid)
    
    elif args.cmd == "get":
        s = get_state(args.state_id)
        if s is None:
            print(f"State {args.state_id} not found", file=sys.stderr)
            sys.exit(1)
        print(json.dumps(s, indent=2))
    
    elif args.cmd == "list":
        states = list_states(args.limit, args.agent)
        for s in states:
            print(f"{s['timestamp']:25} {s['agent']:25} {s['state_id']}")
    
    elif args.cmd == "tree":
        print_tree()
    
    elif args.cmd == "delete":
        n = delete_state(args.state_id, cascade=not args.no_cascade)
        print(f"Deleted {n} state(s)")


if __name__ == "__main__":
    main()
