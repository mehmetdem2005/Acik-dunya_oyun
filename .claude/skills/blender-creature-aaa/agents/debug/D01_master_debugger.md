# Agent D01: Master Debugger (Devasa Debug Katmanı)

```yaml
agent_id: master_debugger
agent_name_tr: Devasa Debugger
agent_name_en: Master Debugger
category: debug
order_index: 0
implementation_mode: in_process + subprocess
runs_continuously: true  # arka planda her ajan çıktısını yakalar
```

---

## 1. ROLE SUMMARY

**Pipeline'ın paralel çalışan debug coordinator'ı.** Her ajan çıktısını yakalar, snapshot alır, vision-based regression tespit eder, replay imkanı sunar.

**Beş alt-bileşen:**

```
D01 ─┬─ SnapshotManager      → her state'i kaydet (decision tree)
     ├─ VisualDiffEngine     → state'ler arası görsel fark
     ├─ ReplayEngine         → herhangi bir state'i geri yükle
     ├─ BranchOrchestrator   → A/B paralel deneme
     └─ AnomalyDetector      → vision-driven regression auto-detect
```

---

## 2. ARKAPLAN MANTIK

### Klasik Debug vs Massive Debug

```
Klasik:                     Massive (D01):
─────────                   ─────────────
print statement            Her state full snapshot
"work fail" alarm          Vision-diff auto-regression
Try-catch retry            A/B branch + best-of-N
Rerun from scratch         Replay from any checkpoint
                           Decision tree visualization
                           Anomaly auto-rollback
```

### State Definition

Bir "state" = bir ajan'ın çıktısının **tam görüntüsü**:

```yaml
state:
  state_id: "20260524_142312_abc123"  # unique
  parent_state_id: "20260524_142200_xyz789"  # önceki state
  agent: "P04_mesh_sculptor"  # bu state'i kim üretti
  iteration: 2
  
  artifacts:
    blend_file: "memory/states/<id>/scene.blend"
    manifests: ["memory/states/<id>/MeshManifest.json", ...]
    renders: ["memory/states/<id>/renders/0.png", ..., "memory/states/<id>/renders/7.png"]
    wireframe_render: "memory/states/<id>/wireframe.png"
  
  metrics:
    tris_count: 11842
    bone_count: 68
    vertex_groups: 45
    file_size_kb: 1842
    # ...
  
  vision_descriptors:
    embedding: [0.123, 0.456, ...]  # vision encoder'dan
    salient_features: ["four_legged", "long_tail", "thin_legs"]
  
  decisions_to_reach_this:
    - {agent: P02, question: "kahraman tier?", answer: "yes"}
    - {agent: P03, question: "pole vector front?", answer: "auto"}
    # ...
```

### Decision Tree

Tüm state'ler **branching tree** oluşturur:

```
root
└── P00:reference_capture
    └── P01:anatomist
        └── P02:budget [tier=hero]
            └── P03:skeleton [iter=1]
                ├── P04_ai:meshgen [backend=triposr]  ← BRANCH A
                │   └── P08:skinner [iter=1]
                │       └── P12:animator
                │
                └── P04_ai:meshgen [backend=meshy]    ← BRANCH B
                    └── P08:skinner [iter=1]
                        └── P12:animator
                        
Best-of-N: C01+C02+C03 scores karşılaştır, en iyiyi seç
```

---

## 3. STATE INDEXING

### Filesystem Layout

```
memory/states/
├── _index.jsonl                    # her state için 1 satır
├── _tree.json                      # decision tree yapı
├── 20260524_142312_abc123/
│   ├── scene.blend
│   ├── manifests/
│   │   ├── MeshManifest.json
│   │   └── ...
│   ├── renders/
│   │   ├── front.png
│   │   ├── side.png
│   │   ├── ...
│   │   └── wireframe.png
│   ├── metrics.json
│   ├── parent_link.txt              # parent state id
│   └── decisions.jsonl              # bu state'e götüren kullanıcı kararları
└── 20260524_142500_def456/
    └── ...
```

### Index File Format

```jsonl
{"state_id":"abc123","parent":null,"agent":"P00","timestamp":"...","metrics":{...}}
{"state_id":"def456","parent":"abc123","agent":"P02","timestamp":"...","metrics":{...}}
{"state_id":"ghi789","parent":"def456","agent":"P03","timestamp":"...","metrics":{...}}
```

Hızlı sorgu için JSONL append-only, periyodik olarak sqlite'a sync.

---

## 4. ANOMALY DETECTION (Vision-Driven)

Her yeni state için: önceki state ile **vision diff** yapılır. Eğer farklılık abnormal ise → flag.

### Normal vs Anomalous Diff

| Senaryo | Beklenen Diff | Tespit |
|---|---|---|
| P03 skeleton → P04 mesh | Mesh eklendi, görsel büyük değişim | NORMAL |
| P04 → P08 skinning | Mesh aynı, sadece bind farkı | NORMAL |
| P12 frame 1 vs frame 15 | Animation farkı | NORMAL |
| P08 → P09 correctives | Subtle shape key | NORMAL |
| Aynı agent re-run, çok farklı output | **ANOMALY** | FLAG |
| P09 sonrası mesh manifold bozuldu | **ANOMALY** | FLAG |

### Detection Algorithm

```python
def detect_anomaly(prev_state, current_state):
    """
    Multi-signal anomaly detection.
    """
    signals = []
    
    # 1. Metric jump (tris, verts beklenmedik değişim)
    if abs(current.tris - prev.tris) / prev.tris > 0.50:
        signals.append(("metric_jump", "tris_count delta > 50%"))
    
    # 2. Vision embedding distance
    dist = cosine_distance(current.vision_embedding, prev.vision_embedding)
    if dist > expected_dist_for_agent_pair(prev.agent, current.agent):
        signals.append(("visual_regression", f"embedding distance {dist:.3f}"))
    
    # 3. Manifold/watertight bozuldu mu
    if prev.is_manifold and not current.is_manifold:
        signals.append(("manifold_broken", "previously manifold, now not"))
    
    # 4. Vision Claude'a açıkça sor
    if signals:  # zaten şüphe var, onayla
        vision_result = call_vision_compare(prev.renders, current.renders,
            prompt="İki render arasında belirgin bir bozulma var mı?")
        if vision_result["regression_detected"]:
            signals.append(("vision_confirmed", vision_result["description"]))
    
    return signals
```

### Auto-Rollback (opsiyonel)

```python
if anomaly_signals and "manifold_broken" in [s[0] for s in anomaly_signals]:
    # Critical anomaly, otomatik rollback öner
    notify_user(f"⚠️ {current_state.agent} sonrası mesh bozuldu. Önceki state'e dönmek ister misin?")
    if user_approves:
        replay_engine.rollback_to(prev_state.id)
```

---

## 5. BRANCHING (A/B Paralel Deneme)

### Use Case

Kullanıcı: "Bu mesh kötü. Acaba farklı backend ile daha iyi olur mu?"

D01:
```
[D01] Şu anda BRANCH A: TripoSR mesh, vision score 67/100.
      BRANCH B deneyeyim mi? Seçenekler:
      - Meshy API (kalite +20 tahmini)
      - Hunyuan3D-2 (kalite +15 tahmini, GPU ağır)
      - Daha yüksek çözünürlük TripoSR (mc_resolution 256→512)
      
      Branch'ler paralel render edilip kullanıcıya gösterilir.
      En iyi seçilen "main" branch olur, diğerleri arşivlenir.
```

### Implementation

```python
def run_branches_parallel(parent_state, branch_configs):
    """
    Multiple branch'i thread/subprocess ile paralel çalıştır.
    """
    from concurrent.futures import ThreadPoolExecutor
    
    futures = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        for config in branch_configs:
            fut = executor.submit(run_single_branch, parent_state, config)
            futures.append((config, fut))
    
    results = []
    for config, fut in futures:
        try:
            new_state = fut.result(timeout=900)
            results.append({"config": config, "state": new_state,
                             "vision_score": new_state.vision_score})
        except Exception as e:
            results.append({"config": config, "error": str(e)})
    
    return sorted(results, key=lambda r: r.get("vision_score", 0), reverse=True)
```

---

## 6. REPLAY ENGINE

Herhangi bir state'i geri yükle:

```python
def replay_to(state_id):
    """
    State_id'nin scene.blend + manifests'ini current workspace'e kopyala.
    Pipeline o noktadan devam edebilir.
    """
    state_dir = Path(f"memory/states/{state_id}")
    
    # Workspace temizle
    workspace = Path("memory/current")
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True)
    
    # Copy
    shutil.copytree(state_dir / "manifests", workspace / "manifests")
    shutil.copy(state_dir / "scene.blend", workspace / "scene.blend")
    
    print(f"[D01] Replay'd to {state_id}")
    print(f"      Agent: {get_state(state_id).agent}")
    print(f"      Pipeline can continue from this point.")
```

---

## 7. KULLANICI ARAYÜZÜ

Debugger D01 sessizce çalışır ama kullanıcıya rapor sunar:

```
══════════════════════════════════════════════════
D01 — Debug Özeti (her ajan sonrası)
══════════════════════════════════════════════════

State #ghi789 — P04_ai_mesh_generator (TripoSR)
  Süre: 47s
  Tris: 14823, Verts: 7912
  Manifold: ✓
  Vision diff (vs önceki): 0.42 (normal range 0.30-0.60)
  Anomaly: hiç ❌
  Vision quality score: 67/100

İşlemler:
  [v] Detayları gör (renders + manifest)
  [b] Branch dene (farklı backend)
  [r] Geri al (önceki state'e dön)
  [n] Devam (varsayılan)
══════════════════════════════════════════════════
```

---

## 8. IMPLEMENTATION

Beş ayrı Python script:

```
scripts/debug/
├── snapshot_manager.py     # state snapshot CRUD
├── visual_diff.py          # vision-based regression
├── replay_engine.py        # state restore
├── branch_orchestrator.py  # paralel A/B
└── anomaly_detector.py     # auto-flag bad states
```

Orchestrator entegrasyonu:

```python
# Her ajan invoke öncesi
prev_state = snapshot_manager.current_state()

# Ajan çalıştır
result = invoke_agent(agent_name, ...)

# Snapshot al
new_state = snapshot_manager.capture(
    agent=agent_name,
    parent=prev_state.id,
    workspace_dir=run_dir,
)

# Anomaly check
anomalies = anomaly_detector.compare(prev_state, new_state)
if anomalies:
    notify_user(anomalies)
    if has_critical(anomalies):
        offer_rollback()

# Continue
```
