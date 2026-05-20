# Fare — Karakter Rig (AAA seviye)

Açık Dünya Fare Simülasyonu için profesyonel rigli fare karakteri.

## İçerik

```
fare/
├── source/
│   ├── mouse3dmodel1k.glb     # Tripo AI export (ham mesh + bozuk auto-rig — referans)
│   └── fare_original.prisma   # Prisma3D kaynak proje (referans)
├── scripts/
│   └── rig_mouse.py           # Blender 4.0 headless rig script (bpy)
├── out/
│   └── mouse.glb              # ÜRETİLEN: rigli fare (Godot'a hazır)
└── README.md
```

## Rig özeti

- **110 kemik**: 77 DEF (deform) + 20 CTRL (controller) + 12 MCH (mechanism) + 1 root
- **Tek mesh, tek material, 3 texture**, 15.8k vert
- Endüstri standardı `.L` / `.R` suffix naming, `DEF-` / `CTRL-` / `MCH-` prefix

### Uygulanan AAA teknikler

| Teknik | Nerede kullanıldı |
|---|---|
| **Mesh-feature-based bone placement** | Patiler (4) ve kulaklar mesh topolojisinden tespit edildi (AABB değil) |
| **Bendy Bones (B-Bones)** | Spine (3 seg), neck (2), tail (2/seg), ears (3), whiskers (4) — smooth deformation |
| **Spline IK (kuyruk)** | Bezier curve + 3 hook control bone → akıcı kuyruk eğrisi |
| **IK + pole target + stretch** | 4 bacakta — `paw_*` chain_count=3, pole = elbow/knee yönü |
| **Twist bones** | Üst kol & uyluk → candy-wrap engellenir |
| **Foot-roll mekanizması** | Heel/ball/toe MCH zinciri (her pati) |
| **Look-at on eyes** | DAMPED_TRACK constraint → `CTRL-eye_aim` master + L/R sub-targets |
| **Breath driver** | `armature["breath"]` ∈ [0,1] → DEF-chest scale_x/y/z'yi sürer |
| **Limit Rotation constraints** | Diz/dirsek sadece tek yönde bükülür; boyun limit'li |
| **Bone collections** | deform / ctrl_main / ctrl_ik / ctrl_face / mch (mch default gizli) |
| **Custom bone shapes** | Daire/küp/küre primitive widget'lar (controller görünürlüğü) |
| **Bone color themes** | THEME01/03/04/09/10 kemik gruplarına göre |
| **Weight smoothing** | 2 iter `vertex_group_smooth` |
| **4 max influence + normalize** | `limit_total` + `normalize_all` (Godot/AAA standardı) |
| **Smart orphan adoption** | Heat weighting'in kaçırdığı vertex'ler en yakın DEF bone segment'ine atanır |

## Kemik hiyerarşisi

```
root
└─ DEF-hips
   ├─ DEF-spine_01 → DEF-spine_02 → DEF-chest
   │  ├─ DEF-neck → DEF-head
   │  │  ├─ DEF-jaw
   │  │  ├─ DEF-ear.L / DEF-ear.R
   │  │  ├─ DEF-eye.L / DEF-eye.R
   │  │  └─ DEF-whisker_01..04.L / DEF-whisker_01..04.R
   │  ├─ DEF-shoulder.L/R → DEF-arm.L/R → DEF-forearm.L/R → DEF-paw_F.L/R
   │  │     └─ DEF-toe_F_1..3_01..03.L/R   (3 parmak × 3 segment × 2 pati)
   │  └─ DEF-tail_01..08                     (Spline IK ile sürülür)
   └─ DEF-thigh.L/R → DEF-shin.L/R → DEF-paw_B.L/R
        └─ DEF-toe_B_1..3_01..03.L/R

CTRL-hips → CTRL-chest → CTRL-head → CTRL-jaw, CTRL-eye_aim
CTRL-foot_F.L/R, CTRL-foot_B.L/R   (IK controllers)
CTRL-pole_F.L/R, CTRL-pole_B.L/R   (IK pole targets)
CTRL-tail_1/2/3                    (Spline hooks)
CTRL-ear.L/R                       (kulak FK)

MCH-arm_twist.L/R, MCH-thigh_twist.L/R    (anti-candywrap)
MCH-heel_F.L/R, MCH-toe_F.L/R              (foot roll)
MCH-heel_B.L/R, MCH-toe_B.L/R
```

## Animasyon hook'ları (sonraki adımda kullanılacak)

| Animasyon | Hangi kemikleri / property'leri kullan |
|---|---|
| **Breathing** (idle loop) | `armature["breath"]` 0↔1 sinüs eğrisi (3-4 sn cycle) |
| **Walk cycle** | `CTRL-foot_F.L/R`, `CTRL-foot_B.L/R` (IK adım), `CTRL-hips` rotation (kalça aktarımı), `CTRL-chest` Y rotation, kuyruk hafif sway |
| **Whisker twitch** | 8 `DEF-whisker_*` kemiği — küçük random Z rotation, 0.1-0.3 sn aralıkta |
| **Ear perk** | `CTRL-ear.L/R` X rotation pozitif (yukarı dik) |
| **Tail sway** | `CTRL-tail_2`, `CTRL-tail_3` Y/Z rotation → spline curve yumuşak eğrilir |
| **Head turn** | `CTRL-head` Z rotation (sağa/sola bakış) |
| **Look** | `CTRL-eye_aim` translation (gözler hedefi takip eder) |
| **Open mouth** | `CTRL-jaw` X rotation |

## Yeniden üretmek

```bash
# Bağımlılıklar
sudo apt-get install -y blender python3-numpy

# Rig'i yeniden üret
blender --background --python fare/scripts/rig_mouse.py
# → fare/out/mouse.glb üretir
```

## Godot entegrasyonu (gelecek)

`mouse.glb` Godot 4.6'ya doğrudan import edilebilir:
- `Skeleton3D` node otomatik oluşur (110 kemik)
- `AnimationPlayer` ile yukarıdaki hook'lar üzerinde animasyon yapılır
- Bone collections Godot tarafında ignore edilir (sadece düz kemik listesi alır)

> **Not**: `armature["breath"]` glTF extras olarak export edilir; Godot tarafında runtime'da `Skeleton3D` üzerinde custom property olarak okunabilir veya doğrudan `chest` kemiğinin scale'i animate edilebilir.

## Kalite raporu

Son `verify()` çıktısı:
```
✓ spine: 7        ✓ ears: 2          ✓ whiskers: 8
✓ tail: 8         ✓ front_limbs: 8   ✓ back_limbs: 6
✓ fingers_front: 18  ✓ fingers_back: 18
✓ controllers: 9
✓ all 15804 verts weighted
✓ IK constraints: 4/4
✓ Spline IK on tail
Result: PASS
```
