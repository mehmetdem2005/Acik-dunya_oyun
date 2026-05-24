# Agent System Overview

Bu klasör, skill'in "AAA Creature Studio" multi-agent mimarisini içerir.

## Hiyerarşi

```
ORCHESTRATOR (Stüdyo Müdürü, doğrudan kullanıcıyla konuşur)
    │
    ├── production/ — Yaratık üreten ajanlar (sıralı çalışır)
    │   ├── P01_anatomist.md
    │   ├── P02_budget_negotiator.md
    │   ├── P03_skeleton_architect.md
    │   ├── P04_mesh_sculptor.md
    │   ├── P05_topology_surgeon.md
    │   ├── P06_uv_cartographer.md
    │   ├── P07_rigger.md
    │   ├── P08_skinner.md
    │   ├── P09_corrective_sculptor.md
    │   ├── P10_secondary_motion.md
    │   ├── P11_material_alchemist.md
    │   ├── P12_animator.md
    │   └── P13_exporter.md
    │
    ├── critic/ — Eleştirmen panel (paralel çalışır, checkpoint'lerde)
    │   ├── C01_vision_critic.md
    │   ├── C02_anatomy_critic.md
    │   ├── C03_topology_critic.md
    │   ├── C04_animation_critic.md
    │   └── C05_mobile_perf_critic.md
    │
    └── meta/ — Öğrenen / evolve eden ajanlar (background)
        ├── M01_pipeline_historian.md
        ├── M02_self_critic.md
        └── M03_tool_procurer.md
```

## Implementation Pattern

Karma yaklaşım (orchestrator karar verir):

| Çağırma Yöntemi | Hangi Ajan | Neden |
|---|---|---|
| **Role-switching** (aynı session) | Hafif ajanlar: Anatomist, Budget Negotiator, Exporter, Material Alchemist | Hız, context paylaşımı kritik |
| **Subprocess** (`claude -p`) | Ağır ajanlar: Skeleton Architect, Mesh Sculptor, Rigger, Skinner, Animator | Token isolation, bpy kod doğruluğu |
| **Parallel subprocess** | Critic Panel (5 ajan paralel) | Bağımsız değerlendirme, hız |
| **Background subprocess** | Meta ajanlar (M01, M02, M03) | Ana flow'u bloke etmemeli |

## Agent File Format

Her ajan dosyası şu sıralamayı izler:

1. **Header** — agent_id, name_tr, role_summary
2. **When Invoked** — preconditions, postconditions, ordering
3. **Inputs** — JSON schema, kaynak dosyalar
4. **Outputs** — JSON schema, üretilen dosyalar
5. **System Prompt** — ajanın "kişiliği", Türkçe, jargon-free
6. **Conversation/Action Flow** — adım adım ne yapar
7. **Validation Criteria** — çıktının doğruluğu nasıl kontrol edilir
8. **Failure Modes & Recovery** — ne yanlış gidebilir, nasıl düzeltilir
9. **Example I/O** — test verisi
10. **Implementation Notes** — orchestrator nasıl çağırır

## State Paylaşımı

Tüm ajanlar `memory/runs/<timestamp>/agent_io/` altındaki JSON dosyaları üzerinden konuşur:

```
memory/runs/<timestamp>/
├── CreatureSpec.json           ← Anatomist üretir
├── BudgetSpec.json             ← Budget Negotiator üretir
├── SkeletonBlueprint.json      ← Skeleton Architect üretir
├── MeshManifest.json           ← Mesh Sculptor üretir
├── RigManifest.json            ← Rigger üretir
├── SkinningManifest.json       ← Skinner üretir
├── AnimationManifest.json      ← Animator üretir
├── ExportManifest.json         ← Exporter üretir
│
├── critic_reports/
│   ├── vision_<phase>_<iter>.json
│   ├── anatomy_<phase>_<iter>.json
│   ├── topology_<phase>_<iter>.json
│   ├── animation_<phase>_<iter>.json
│   └── mobile_perf_<phase>_<iter>.json
│
└── blender_scenes/
    ├── skeleton_v1.blend
    ├── mesh_v1.blend
    ├── rigged_v1.blend
    └── final.blend
```

Bu pattern: her ajan input'unu okur, çalışır, output'u yazar, log'a kaydolur. Orchestrator validation yapar, sonraki ajana geçer veya geri döner.

## Validation Gates

Her ajan çıktısı **schema validation**'dan geçer. Schema'lar `agents/schemas/` altında (sonradan oluşturulacak). Validation fail ederse:

1. Ajan yeniden çağrılır (bir kez daha)
2. Hala fail ediyorsa orchestrator kullanıcıya bildirir
3. Kullanıcı manuel müdahale veya "ajanı bypass et" seçeneği

## Ajan Çağrı Komutları (Orchestrator için)

Orchestrator bu pattern'i takip eder:

```python
# Role-switching pattern (örnek: Budget Negotiator)
agent_spec = read_file("agents/production/P02_budget_negotiator.md")
system_prompt = extract_section(agent_spec, "System Prompt")
# Orchestrator "şu an Budget Negotiator olarak çalışıyorum" diye context'e gömer
# Aynı session içinde user ile konuşur
# Output'u BudgetSpec.json'a yazar

# Subprocess pattern (örnek: Skeleton Architect)
subprocess.run([
    "claude", "-p",
    "--system-prompt-file", "agents/production/P03_skeleton_architect.md",
    "--input-file", "memory/runs/<ts>/CreatureSpec.json",
    "--output-format", "json",
])
# Output BlueprintSkeleton.json'a yazılır
# Sonra "blender_script.py" üretip subprocess olarak çalıştırılır

# Parallel critic panel
import concurrent.futures
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
    futures = [
        pool.submit(call_critic, "vision", renders_dir),
        pool.submit(call_critic, "anatomy", renders_dir, refs_dir),
        pool.submit(call_critic, "topology", wireframe_dir),
        pool.submit(call_critic, "animation", stress_dir),
        pool.submit(call_critic, "mobile_perf", stats_json),
    ]
    reports = [f.result() for f in futures]
# Orchestrator 5 raporu konsolide eder
```
