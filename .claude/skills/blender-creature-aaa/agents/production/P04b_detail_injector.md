# Agent P04b: Detail Injector (Detay Enjektörü)

```yaml
agent_id: detail_injector
agent_name_tr: Detay Enjektörü
agent_name_en: Detail Injector
category: production
order_index: 4.5
implementation_mode: subprocess
estimated_duration_minutes: 1-3
critical_path: true
runs_after: P04_mesh_sculptor
```

---

## 1. ROLE SUMMARY

**P04 Mesh Sculptor'ın blockout tavanını kıran ajan.**

P04 anatomy-class proportions'tan curve-to-mesh ile **gövde silüetini** üretir — gövde, boyun, baş, kuyruk, bacaklar **doğru yerde**, doğru kalınlıkta. Ama:

- Bacak uçları sivri (pati yok)
- Yüz düz (göz, burun, ağız çukurları yok)
- Kulak yok (sadece skull bone var)
- Kuyruk ucu iğne gibi

Bu ajan **anatomical landmark'lara** dayalı **küçük primitive'ler** (sphere, cone, boolean cut) ekleyerek bu spesifik eksiklikleri kapatır.

**AI gerekmiyor.** Sadece doğru yerde küre/koni eklenmesi.

---

## 2. NEDEN AI YERINE BU YAKLAŞIM

Meshy AI'nın yaptığı şey: pre-trained 3D diffusion model çıktısı.

Bizim yapacağımız şey: **anatomik bilgi ile yönlendirilmiş primitive bileşim.**

| Defekt | AI çözümü | Procedural çözümü (bizim) |
|---|---|---|
| Pati yok | AI mesh'i pati ile birlikte üretir | leg tip noktasına 4 sphere cluster (paw_pad + 4 toes) |
| Göz yok | AI texture+mesh ile göz üretir | skull bone'a 2 boolean sphere cut (eye sockets) |
| Kulak yok | AI 3D modelde kulak çıkarır | skull bone'a 2 cone primitive |
| Burun/snout | AI doğal snout çıkarır | head bone'a tapered cone primitive |
| Kuyruk iğne | AI uygun kuyruk çıkarır | tail radius profile'a "tuft" sphere ekle |

Sonuç **AI ile aynı kalite** değil ama **anlamlı bir kurt** çıkar — şu anki "lama gibi" tavanından çok üstte.

---

## 3. ANATOMICAL LANDMARK SİSTEMİ

`P03 Skeleton Architect` her yaratık için **landmark points** üretmeli. Bu ajan onları kullanır.

```json
{
  "landmarks": {
    "eye_L":      {"position": [0.08, 0.0, 0.45], "parent_bone": "head"},
    "eye_R":      {"position": [-0.08, 0.0, 0.45], "parent_bone": "head"},
    "nose":       {"position": [0.0, 0.18, 0.40], "parent_bone": "head"},
    "ear_L":      {"position": [0.10, -0.05, 0.55], "parent_bone": "head"},
    "ear_R":      {"position": [-0.10, -0.05, 0.55], "parent_bone": "head"},
    
    "paw_front_L":{"position": [0.12, 0.30, -0.45], "parent_bone": "foot_front_L"},
    "paw_front_R":{"position": [-0.12, 0.30, -0.45], "parent_bone": "foot_front_R"},
    "paw_rear_L": {"position": [0.13, -0.30, -0.45], "parent_bone": "foot_rear_L"},
    "paw_rear_R": {"position": [-0.13, -0.30, -0.45], "parent_bone": "foot_rear_R"},
    
    "tail_tuft":  {"position": [0.0, -0.55, 0.10], "parent_bone": "tail_03"}
  }
}
```

Anatomy class'a göre değişir:
- `mammalia_quadruped`: 11 landmark (2 eyes, nose, 2 ears, 4 paws, tail_tuft, mouth)
- `aves`: beak_tip, eye_L, eye_R, wing_tip_L, wing_tip_R, foot_L, foot_R, tail_fan
- `reptilia_serpent`: snout, eye_L, eye_R, tongue_tip (paw/kulak yok)
- `arthropoda_arachnid`: 8 leg_tip, 8 eye, chelicera_L, chelicera_R, abdomen_tip

---

## 4. INJECTION OPERATIONS

### 4.1 Paw Injection (Pati Ekleme)

Mevcut leg ucundaki sivri vertex bölgesini sil, **5-sphere cluster** ekle:

```
       [main_pad]              ← büyük sphere (radius 0.04)
      /    |    \
[toe1] [toe2] [toe3]           ← 3-4 küçük sphere (radius 0.018)
                               (köpek 4 toe, kedi 4 toe + dewclaw)
```

Algoritma:
1. Foot bone'un dünya koordinatı al
2. Leg mesh ucunda Z-en alt 20 vertex'i sil (loose ucu temizle)
3. Foot pozisyonunda main_pad sphere (UV sphere, 12 segment)
4. Main_pad önünde 4 toe sphere
5. Voxel remesh ile leg + paw birleşir

### 4.2 Ear Injection (Kulak Ekleme)

Skull bone üstüne **2 koni primitive** koy, hafif yana açılı:

```
   __     __
   /\     /\        ← ears (cone, 6 sides)
  /  \   /  \
 /____\_/____\
       O              ← head sphere
       |
```

Algoritma:
1. Skull/head bone'un tepesi (Z+max) ve 2 yan pozisyon
2. Her yan için: cone primitive (vertex 12, height 0.10, base_radius 0.04)
3. Hafif outward rotation (~15° yana)
4. Anatomy class'a göre ear type:
   - wolf/dog: triangular pointed
   - bear: rounded (cone + smooth)
   - rabbit: long elongated
   - cat: triangular small

### 4.3 Eye Socket Injection (Göz Çukurları)

Skull üstüne **2 küçük göz** çukurluğu cut + ufak küre yerleştir:

```
def add_eyes(head_mesh, landmarks):
    """
    1. Eye_L ve eye_R landmark pozisyonuna ufak sphere boolean DIFFERENCE
    2. Aynı pozisyona daha küçük sphere ADD (göz küresi)
    """
    for side in ['L', 'R']:
        pos = landmarks[f'eye_{side}']
        
        # Çukur (boolean cut)
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.018, location=pos)
        cutter = bpy.context.active_object
        
        bool_mod = head_mesh.modifiers.new("eye_cut", 'BOOLEAN')
        bool_mod.operation = 'DIFFERENCE'
        bool_mod.object = cutter
        bool_mod.solver = 'EXACT'
        # apply, delete cutter
        
        # Göz küresi (daha küçük, biraz içerde)
        eye_pos = (pos[0], pos[1] - 0.005, pos[2])
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.012, location=eye_pos)
        eye = bpy.context.active_object
        eye.name = f"eye_{side}"
```

### 4.4 Snout/Nose Injection (Burun)

Head bone'unun ön ucuna **tapered cone**:

```
        ___
       /   \
      |  •  |            ← head
      |  __ |
       \/__\              ← snout (tapered cone)
        nose
```

Algoritma:
1. Head bone front direction'da
2. Tapered cylinder: base_radius=0.06, tip_radius=0.03, length=0.10
3. Tip'e küçük sphere (burun ucu) — siyah material için marker

### 4.5 Tail Tuft (Kuyruk Yumağı)

Tail uç vertex'inde **radius'u arttıran sphere**:

```python
def add_tail_tuft(mesh, landmark_pos, species):
    """
    Kuyruğun ucuna gür/tüylü etkisi için sphere cluster.
    """
    if species in ['wolf', 'dog', 'fox']:
        # Tüylü, kalın
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.045, location=landmark_pos)
    elif species in ['cat']:
        # Daha ince
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.025, location=landmark_pos)
    elif species in ['lion']:
        # Lion tuft - belirgin uç
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.05, location=landmark_pos)
```

### 4.6 Mouth Line (Ağız İzi)

Boolean cut yerine **edge crease + light displacement** ile basit ağız çizgisi.

Algoritma:
1. Head ön yüzünde dudak hattını bulan loop seçimi (en geniş Y, en geniş X)
2. Bu edge loop'a `crease = 1.0` + ufak `bevel`
3. Subdivision'da dudak çizgisi belirginleşir

---

## 5. POST-INJECTION CLEANUP

Tüm primitive'ler ana mesh'e **voxel remesh** ile bağlanır:

```python
def merge_injections(main_mesh, injected_objects):
    """
    1. Tüm injection objelerini main mesh'e join
    2. Voxel remesh (resolution 256+) → unified manifold
    3. Smooth shading
    4. Normal recalculate
    """
    # Join all
    for obj in injected_objects:
        obj.select_set(True)
    main_mesh.select_set(True)
    bpy.context.view_layer.objects.active = main_mesh
    bpy.ops.object.join()
    
    # Voxel remesh
    rem = main_mesh.modifiers.new("FinalRemesh", 'REMESH')
    rem.mode = 'VOXEL'
    rem.voxel_size = 0.008  # 8mm
    rem.use_smooth_shade = True
    bpy.ops.object.modifier_apply(modifier=rem.name)
    
    # Decimate to budget
    final_target = 15000  # tris
    current = len(main_mesh.data.polygons)
    if current > final_target:
        dec = main_mesh.modifiers.new("FinalDecimate", 'DECIMATE')
        dec.ratio = final_target / current
        bpy.ops.object.modifier_apply(modifier=dec.name)
```

---

## 6. OUTPUTS

### `mesh_v2.blend` + `DetailInjectionManifest.json`

```json
{
  "manifest_version": "1.0",
  "injections_applied": {
    "paws": 4,
    "ears": 2,
    "eye_sockets": 2,
    "eye_balls": 2,
    "snout": 1,
    "tail_tuft": 1,
    "mouth_line": 1
  },
  "before": {"tris": 11842, "verts": 6234},
  "after_remesh":  {"tris": 14823, "verts": 7510},
  "voxel_size_used": 0.008,
  "generated_by": "P04b_detail_injector"
}
```

---

## 7. VISION DRIVEN ITERATION (Claude as Visual Engine)

P04b sonrası **C01 Vision Critic** çalışır. Claude (vision):

1. Mesh'i 4 açıdan render alır
2. Reference'la karşılaştırır (varsa) veya beklenen anatomi ile
3. Spesifik defekt listesi üretir
4. Her defekt → P04b'ye dönüş + ilgili primitive yeniden ekle

Örnek vision defect → action mapping:

| Vision tespiti | P04b aksiyonu |
|---|---|
| "Kulaklar çok küçük" | ear cone height ×1.5 |
| "Patiler simetrik değil" | paw position'ı her tarafta aynı landmark'tan al |
| "Burun belirsiz" | snout cone length ×1.3 + tip sphere ekle |
| "Kuyruk hala ince" | tail_tuft radius ×1.5 |

Bu **gerçek Claude-driven vision loop**. Dış servis yok, ben (Claude) görsel beyin görevi yapıyorum.
