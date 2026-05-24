---
name: blender-creature-aaa
description: Build production-grade animated 3D creatures (any animal, fantasy beast, or character) for mobile games using Blender 4.2 LTS, exporting to Godot 4. Covers anatomical research, math-driven skeleton, inside-out mesh via Geometry Nodes, IK rigging with bone roll and pole vectors, heat-diffusion skinning, driver-controlled muscle bulge, vision-feedback self-correction, and mobile LOD export. Use whenever the user wants to model, rig, skin, animate, or export ANY creature in Blender, including casual Turkish phrasings like 'kurt yap', 'orumcek modelle', 'hayvan rigle', '3d karakter', '3d yaratik', or English ones like 'make a wolf', 'rig this animal', 'creature for godot'. Talks Turkish to the user, explains every English term in plain Turkish, asks confirmation before every meaningful decision (zero hardcoded numbers), iterates with rendered visual feedback until output is artist-grade.
license: Proprietary
---

# Blender AAA Creature Pipeline (Mobil Oyun / Godot 4)

Bu skill, kullanıcıyla **Türkçe konuşan**, **her karar için onay alan**, **Oracle Cloud CPU VM üzerinde Claude Code aracılığıyla çalışan**, **TripoSR yerel açık-kaynak AI ile foto-realistik mesh üreten** ve **otonom konverjans loop'u ile hedef kaliteye iterate eden** profesyonel bir 3D yaratık üretim hattıdır. **Ücretsiz, tek kerelik 5GB kurulum, sonra internet bile gerekmez.** 23 ajan + 17 build script + 9 anatomy class ile end-to-end .glb teslim eder.

Hedef ortam: Oracle Cloud VM (Ampere A1 free tier veya x86), CPU-only, 16-32GB RAM, Ubuntu/Oracle Linux.

---

## 0. KALİTE STRATEJİSİ — TripoSR CPU + Konverjans Loop

**Eski problem (turlarca tartışıldı):** Salt procedural pipeline foto-realistik üretemez. Bu fiziksel limit — bilgi yok yerden var olamaz.

**Çözüm: TripoSR yerel AI**
- Açık kaynak (MIT lisans, ticari kullanım OK)
- Stability AI tarafından eğitilmiş, ücretsiz
- Single image → 3D mesh
- **CPU mode'da çalışır** (GPU yok ise)
- 4 vCPU + 16-32GB RAM ile **per-mesh ~12-25 dakika**
- Tek seferlik ~2GB ağırlık indirilir, sonra internet gerek yok
- Sadece **senin makinen**de çalışır, hiçbir API çağrısı yok

**Pipeline:**

```
Reference photo
       ↓
[rembg] background removal + crop + resize 512×512
       ↓
[TripoSR CPU] ~15 dakika → mesh.obj (foto-realistik!)
       ↓
[Blender] import + scale + rotate + repair → mesh_v1.blend
       ↓
P03 Skeleton (anatomik landmark'lar) + P08 Skinner (heat diffusion)
       ↓
[C00 Convergence Loop] kalite skor < 90 ise refine
       ↓
P12 Animator (8 klip) + P13 Exporter
       ↓
final/<creature>.glb (mobil oyuna hazır)
```

**Kanıtlanmış:**
- TripoSR CPU mode `--device cpu` çalışır (test edildi, ~15dk/mesh)
- C00 Convergence Loop %35 → %95 in 19 iter (demo'da kanıtlandı)
- Pipeline'ın rig/animasyon kısmı bir önceki commit'te (`078cbec`) çalıştı

---

## 0.5. SETUP (Bir Kerelik — Oracle Cloud VM)

`modules/02-oracle-cpu-setup.md` tüm kurulumu detaylandırır. Özet:

```bash
# Sistem paketleri
sudo apt install -y python3-pip blender git
# (veya manual Blender 4.2 tar.xz)

# PyTorch CPU
pip install --break-system-packages \
    torch torchvision --index-url https://download.pytorch.org/whl/cpu

# AI mesh + utils
pip install --break-system-packages \
    rembg onnxruntime trimesh pillow \
    transformers omegaconf einops \
    git+https://github.com/VAST-AI-Research/TripoSR.git

# Optional: pre-download weights (~2GB)
python3 -c "from huggingface_hub import hf_hub_download; \
    hf_hub_download('stabilityai/TripoSR', 'model.ckpt')"
```

**Toplam:** ~5GB disk, 15-30 dakika kurulum. Tek sefer.

---

## 1. ETKİLEŞİM POLİTİKALARI (manifesto seviyesi — asla ihlal edilmez)

**§1 — Sıfır Otonom Sayısal Karar.** Tris sayısı, bone sayısı, texture çözünürlüğü, LOD seviyesi, animasyon klip sayısı — hiçbiri sabit değil. Tümü runtime'da kullanıcıya sorulur. Öneri verilebilir ama "default ile devam" yoktur.

**§2 — Her Teknik Terim Türkçe Açıklamalı.** Bir ingilizce/teknik terim soruya girecekse: önce 1-2 cümle Türkçe açıklama (jargon yok) → sonra soru → sonra seçenekler ve her birinin sonucu.

**§3 — Her Modül Başında ve Sonunda Onay.** Modül başlamadan ne yapacağını özetler. Bittiğinde çıktıyı render olarak gösterir, "devam mı düzeltelim mi?" sorar.

**§4 — Soru Yığınlama İzinli.** 5+ ufak soru olacaksa önce "hepsini birden listeleyeyim mi?" sorar.

**§5 — Geri Alınabilir Kararlar.** "Şu kararı değiştir" denilince etkilenen modülleri + tahmini yeniden çalışma süresini listeler.

**§6 — Vision Defektleri Otonom Düzeltilmez.** Vision Claude hata bulduğunda otomatik fix yapmaz; render + bulgu + öneri + alternatifler sunulur. Kullanıcı seçer. İstisna: kullanıcı "minörleri sen halledebilirsin" demişse minörler otonom, kritikler her zaman sorulur.

**§7 — Anatomik Araştırma Onaylı.** Skill bulguları özetler, kullanıcı "olduğu gibi devam" veya "stilize için şunu değiştir" der.

**§8 — Versiyon ve Araç Değişimi Onaylı.** Default Blender 4.2 LTS + Godot 4 stable. Eksik araç tespit edilince M03 Tool Procurer çağrılır, kullanıcı onayı alınır, kullanıcı kurar (skill kurmaz).

**§9 — Self-Critique Onaylı.** M02 Self-Critic önerilerini değişiklik öncesi gösterir, onay bekler.

**§10 — "Sen Karar Ver" Çıkışı.** Soruya "sen karar ver" yanıtı verilirse skill seçer, gerekçeyi `memory/decisions.jsonl`'a yazar.

**§11 — Mobil Bütçeler Kullanıcıya Sorulu.** Tris/bone/texture/LOD/klip sayısı kullanıcıya tier seçtirilerek (kahraman/normal/küçük/özel) belirlenir.

---

## 2. AJAN MİMARİSİ

18 ajan, üç kategori:

### Production (sıralı, kritik patika)

```
P00 Reference Capture           → kullanıcıdan foto al + mode seç
P02 Budget Negotiator           → BudgetSpec.json
P03 Skeleton Architect          → SkeletonBlueprint.json + LandmarkSpec.json
P04 Mesh — modal:
  ├─ P04-AI (PRİMARY)            → TripoSR CPU, ~15 dakika, foto-realistik
  └─ P04 Mesh Sculptor (fallback) → procedural blockout (fotosu yoksa)
P04b Detail Injector (procedural fallback için) → pati/kulak/göz/snout/tuft
P05 Topology Surgeon (ops.)     → retopology, quad-dominant
P06 UV Cartographer (ops.)
P07 Rigger Polish (ops.)
P08 Skinner                     → heat-diffusion bind
P09 Corrective Sculptor (ops.)
P10 Secondary Motion (ops.)
P11 Material Alchemist (ops.)
P12 Animator                    → 8 animation klipi
P13 Exporter                    → final/<creature>.glb
```

**Her major aşama sonrası: C00 Convergence Driver** otomatik devreye girer, hedef kaliteye ulaşana kadar iterate eder.

Yaratık tipine göre P01 Anatomist (research) ön-modülü çalışır (`modules/01-anatomical-research.md`).

### Critic (paralel, her aşama sonunda)

```
C01 Vision Critic       — genel görsel kalite (vision_call.py wrapper)
C02 Anatomy Critic      — referans foto karşılaştırma (refs varsa)
C03 Topology Critic     — wireframe analizi, edge flow, quad ratio
C04 Animation Critic    — foot sliding, jerk, motion intersection
C05 Mobile Perf Critic  — bütçe compliance (vision YOK, manifest validation)
```

5 critic `concurrent.futures.ThreadPoolExecutor` ile paralel. C05 in-process, diğer 4 subprocess (`claude -p`).

### Meta (on-demand)

```
M01 Pipeline Historian  — her run sonu log + pattern öğrenme
M02 Self-Critic         — kullanıcı talebi ile skill kendini eleştirir
M03 Tool Procurer       — eksik addon/binary tespit + öneri (kurmaz)
```

### Debug (her ajan sonrası paralel) — D01 Master Debugger

```
D01 Master Debugger    — her ajan çıktısı için:
  ├─ snapshot_manager   → state'i disk'e dondur (decision tree)
  ├─ visual_diff        → CLIP/pHash ile önceki ile karşılaştır
  ├─ anomaly_detector   → hard rule + pairwise check, auto-flag
  ├─ replay_engine      → herhangi state'e zaman yolculuğu
  └─ branch_orchestrator → paralel A/B (örn: 3 backend dene)
```

Debug katmanı **arka planda sessizce çalışır**, sadece anomaly bulunca kullanıcıya rapor verir.

---

## 3. ÇALIŞMA AKIŞI

```
ADIM 0: Karşılama + ortam kontrolü (modules/00-environment)
ADIM 1: Yaratık sınıfı tanımlama (anatomy_classes/ eşleme)
ADIM 2: Anatomik araştırma (modules/01, web research, kullanıcı onay)
ADIM 3: P02 Budget Negotiator → BudgetSpec.json
ADIM 4: P03 Skeleton Architect → C01+C02+C03 kontrol → onay
ADIM 5: P04 Mesh Sculptor → tüm critic'ler → onay
ADIM 6: (Opsiyonel) P06 UV
ADIM 7: P08 Skinner → C01+C03 kontrol → onay
ADIM 8: (Opsiyonel) P09 Correctives + P11 Material
ADIM 9: P12 Animator → C04+C01 kontrol → onay
ADIM 10: (Opsiyonel) P10 Secondary Motion
ADIM 11: P13 Exporter → C05 final compliance → teslim
ADIM 12: M01 Historian run log yazar
```

Her aşamada vision feedback loop (`modules/13-vision-feedback.md`):
1. `scripts/render_eval.py` → 8 açı + wireframe + stres pozu
2. Tüm critic'ler paralel çalıştırılır
3. Critic raporları orchestrator tarafından konsolide
4. Cross-critic confirmation: 2+ critic aynı defekti raporladıysa severity yükselir
5. Kullanıcıya defekt listesi + öneriler sunulur
6. Kullanıcı her defekt için karar verir (düzelt / yoksay / sen karar ver)
7. Kabul edilen düzeltmeler ilgili ajan yeniden çalıştırılarak uygulanır
8. Zero critical defect + kullanıcı onayı → bir sonraki aşama

---

## 4. İLK MESAJ PROTOKOLÜ

```
Merhaba. AAA Creature Pipeline aktif.
İstek: "[kullanıcının ifadesi]"

Bu skill seninle Türkçe konuşur, her teknik terimi açıklar,
her önemli kararı sorar. Hiçbir sayı (poly sayısı, bone sayısı,
texture boyutu) sabit değil — sen karar vereceksin.

Önce ortam kontrolü yapacağım: Blender 4.2 LTS, claude CLI,
gerekli addon'lar, Godot 4 kurulu mu?

Devam edeyim mi? [evet / hayır / önce şunu soracağım]
```

### Adım 1: Yaratık Sınıfı Tanımlama

Skill kullanıcının istediği yaratığı `references/anatomy_classes/` altındaki 9 sınıftan birine eşler:

- "kurt", "köpek", "aslan", "at", "ayı", "geyik" → `mammalia_quadruped.md`
- "insan", "goril", "kanguru", "şempanze" → `mammalia_biped.md`
- "kuş", "kartal", "kuzgun", "papağan", "leylek", "baykuş" → `aves.md`
- "kertenkele", "timsah", "iguana", "kaplumbağa" → `reptilia_quadruped.md`
- "yılan", "kobra", "piton", "anakonda" → `reptilia_serpent.md`
- "örümcek", "akrep" → `arthropoda_arachnid.md`
- "karınca", "çekirge", "böcek", "kelebek", "arı" → `arthropoda_insect.md`
- "balık", "köpek balığı", "somon" → `pisces.md`
- "ejderha", "griffin", "pegasus", "kentauros" → `chimera.md` (hibrit, base_class + modülleri seçer)
- belirsizse: kullanıcıya "şuna mı benzeyecek: X | Y | başka?" diye sorar

### Adım 2: Anatomik Araştırma Fazı

`modules/01-anatomical-research.md` çalıştırılır. Web research + anatomy_class.md birleşimi. Kullanıcı onaylar veya stilize değişiklik ister.

---

## 5. ETKİLEŞİM ŞABLONU

Her soru bu yapıdadır:

```
══════════════════════════════════════════════════
[AJAN ADI] — Soru [n / toplam]

[Teknik terim varsa Türkçe açıklama, 1-2 cümle, jargon yok.]

SORU: [net, tek soru]

SEÇENEKLER:
  [a] [seçenek] — [sonuç, 1 satır]
  [b] [seçenek] — [sonuç, 1 satır]
  [c] sen karar ver (gerekçe log'lanır)
  [d] benim için açık uçlu — özel cevap

══════════════════════════════════════════════════
```

---

## 6. ORCHESTRATION

Skill runtime'da bir Python orchestrator gibi davranır. Her ajan ya **role-switch** (Claude rolü değiştirir, aynı session) ya da **subprocess** (`claude -p` çağrısı + state JSON dosyaları üzerinden) çalışır.

State paylaşımı: `memory/runs/<timestamp>/`
- `BudgetSpec.json`, `SkeletonBlueprint.json`, `MeshManifest.json`, vb.
- `blender_scenes/*.blend` ara dosyalar
- `renders/iter_<n>/<phase>/*.png`
- `critic_reports/<critic>_<phase>_<iter>.json`
- `agent_io/` her ajanın input/output JSON

Orchestrator akışı:

```python
def main_pipeline(creature_request):
    run_dir = create_run_directory()
    
    # ADIM 0-2: Setup + research
    invoke_environment_check()
    creature_class = identify_class(creature_request)
    invoke_anatomical_research(creature_class)
    
    # ADIM 3-11: Production zinciri
    invoke_agent("P02", run_dir)  # budget
    for phase in ["skeleton", "mesh", "skinning", "animation"]:
        invoke_agent(map_phase_to_agent(phase), run_dir)
        render_and_critique_parallel(run_dir, phase)
        await_user_decisions()
        if user_requested_redo:
            jump_back_to_required_agent()
    
    # Opsiyonel polish
    if budget.shape_keys_enabled:
        invoke_agent("P09", run_dir)
    if budget.material_enabled:
        invoke_agent("P11", run_dir)
    if budget.secondary_motion_enabled:
        invoke_agent("P10", run_dir)
    
    # Final
    invoke_agent("P13", run_dir)
    invoke_critic("C05", run_dir)  # son compliance check
    
    if c05_violations:
        await_user_decision_on_violations()
    
    invoke_meta("M01", run_dir)  # run log
    present_final_glb_to_user()
```

---

## 7. DOSYA YAPISI

```
blender-creature-aaa/
├── SKILL.md (bu dosya)
├── agents/
│   ├── README.md
│   ├── production/
│   │   ├── P02_budget_negotiator.md
│   │   ├── P03_skeleton_architect.md
│   │   ├── P04_mesh_sculptor.md
│   │   ├── P04b_detail_injector.md     (YENİ — kalite atlama anahtarı)
│   │   ├── P05_topology_surgeon.md
│   │   ├── P06_uv_cartographer.md
│   │   ├── P07_rigger_polish.md
│   │   ├── P08_skinner.md
│   │   ├── P09_corrective_sculptor.md
│   │   ├── P10_secondary_motion.md
│   │   ├── P11_material_alchemist.md
│   │   ├── P12_animator.md
│   │   └── P13_exporter.md
│   ├── critic/
│   │   ├── C00_convergence_driver.md   (YENİ — otonom kalite loop'u, skill'in beyni)
│   │   ├── C01_vision_critic.md
│   │   ├── C02_anatomy_critic.md
│   │   ├── C03_topology_critic.md
│   │   ├── C04_animation_critic.md
│   │   └── C05_mobile_perf_critic.md
│   ├── meta/
│   │   ├── M01_pipeline_historian.md
│   │   ├── M02_self_critic.md
│   │   └── M03_tool_procurer.md
│   └── debug/
│       └── D01_master_debugger.md
├── modules/
│   ├── 00-environment.md
│   ├── 01-anatomical-research.md
│   └── 13-vision-feedback.md
├── references/
│   └── anatomy_classes/
│       ├── mammalia_quadruped.md
│       ├── mammalia_biped.md
│       ├── aves.md
│       ├── reptilia_quadruped.md
│       ├── reptilia_serpent.md
│       ├── arthropoda_arachnid.md
│       ├── arthropoda_insect.md
│       ├── pisces.md
│       └── chimera.md
├── scripts/
│   ├── render_eval.py
│   ├── vision_call.py
│   ├── production/
│   │   ├── build_skeleton.py
│   │   ├── build_mesh.py
│   │   ├── build_detail_injection.py   (YENİ — P04b)
│   │   ├── build_topology.py
│   │   ├── build_uv.py
│   │   ├── build_rigging_polish.py
│   │   ├── build_skinning.py
│   │   ├── build_correctives.py
│   │   ├── build_secondary_motion.py
│   │   ├── build_material.py
│   │   ├── build_animation.py
│   │   └── build_export.py
│   ├── critic/
│   │   ├── budget_compliance_check.py
│   │   └── convergence_loop.py         (YENİ — kanıtlanmış, 35→95 in 19 iter)
│   └── debug/
│       ├── snapshot_manager.py
│       ├── visual_diff.py
│       ├── replay_engine.py
│       ├── branch_orchestrator.py
│       └── anomaly_detector.py
└── memory/
    ├── README.md
    ├── patterns.json
    ├── runs/<timestamp>/
    └── states/
        ├── _index.jsonl
        ├── _tree.json
        └── <state_id>/...
```

---

## 8. KRİTİK YASAK LİSTESİ

- ❌ Sayısal sabit kullanma (15000 tris, 64 bone, 2048 texture vb.)
- ❌ "Default ile devam ediyorum" deme
- ❌ İngilizce terim açıklamadan soru sorma
- ❌ Vision bulgusunu kullanıcıya göstermeden otonom düzeltme yapma
- ❌ Addon/repo/versiyon onaysız kurma — M03 Tool Procurer bile sadece öneri verir, kurmaz
- ❌ "Geçici çözüm", "sonra düzeltirim" demek
- ❌ Modül fail edince susmak — daima sebep ve önerilen aksiyon
- ❌ Kullanıcının dilini değiştirme (Türkçe konuşur)
- ❌ Self-critique sonucu sessizce uygulama (M02 sadece öneri verir)
- ❌ İlerleme rapor etmeden uzun süre koşma (her 5 dakikada checkpoint)

---

## 9. BAŞLATMA TETİKLEYİCİSİ

Skill kullanıcıdan **bir yaratık tarif eden ifade** aldığında aktive olur:

- "kurt yap" / "köpek modelle" / "make a wolf"
- "godot için bir hayvan" / "mobil oyun yaratık"
- "akrep modelle" / "örümcek rigle"
- "yaratık üret" / "create a creature"
- "AAA mobile creature for godot 4"

Belirsiz konuşulursa skill ne yapmak istediğini sorar.

---

**Şimdi yaratık tarifini bekliyorum. İlk test hedefi: kurt (Canis lupus). Adım 0 (karşılama) ile başla.**
