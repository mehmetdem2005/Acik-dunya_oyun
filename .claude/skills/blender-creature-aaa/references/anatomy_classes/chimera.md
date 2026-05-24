# Anatomy Class: Chimera (Hibrit Yaratıklar)

Birden fazla anatomi sınıfının özelliklerini birleştiren **fantastik yaratıklar**. Gerçek karşılığı yok — anatomik tutarlılık skill tarafından **modular olarak** kurulur.

**Örnekler:** Ejderha (reptilia_quadruped + aves wings), griffin (aves + mammalia_quadruped), Pegasus (mammalia + aves wings), kentauros (mammalia_biped üst + mammalia_quadruped alt), hellhound (mammalia_quadruped + insect mandibles + tail variation).

---

## Bileşim Stratejisi

Skill chimera istendiğinde **base class seçer**, sonra **modifier'lar ekler**:

```yaml
base_class: <bir_sınıf>            # ana iskelet stratejisi
added_modules:
  - <başka_sınıftan_alınan_organ>  # mesela: aves.wings
  - <başka_sınıftan_alınan_organ>  # mesela: reptilia.tail
modifications:
  - {feature: ..., from: ..., scale: ...}
```

### Örnek: Ejderha (Wyvern)

```yaml
base_class: reptilia_quadruped
added_modules:
  - aves.wings                     # 2 büyük kanat
modifications:
  - feature: head
    from: reptilia_quadruped
    modifications:
      - {add: horns, count: 2}
      - {add: spines_along_neck, count: 5}
      - {snout_length_multiplier: 1.3}
  - feature: body_armor_scales
    coverage: full
  - feature: claws
    from: aves.eagle
    on_legs: front_only
```

### Örnek: Griffin

```yaml
base_class: aves  # baş ve ön kısım kuş
added_modules:
  - mammalia_quadruped.legs        # arka bacaklar aslan
  - mammalia_quadruped.tail        # aslan kuyruğu
modifications:
  - feature: head
    from: aves.eagle
  - feature: front_legs
    from: aves.eagle.talons        # ön bacaklar kuş pençesi
  - feature: rear_legs
    from: mammalia_quadruped.lion
  - feature: tail
    from: mammalia_quadruped.lion
    tail_tuft_at_end: true
  - feature: chest_feathers
    coverage: front_half_body
  - feature: hindquarters_fur
    coverage: rear_half_body
```

### Örnek: Pegasus

```yaml
base_class: mammalia_quadruped     # at
added_modules:
  - aves.wings                     # at omzundan kanat
modifications:
  - feature: head
    from: mammalia_quadruped.horse
  - feature: wings
    attachment_point: shoulder      # at omuz ile kanat birleşim
    feather_pattern: large
```

### Örnek: Kentauros

```yaml
base_class: mammalia_biped         # üst kısım insan
added_modules:
  - mammalia_quadruped.body_rear   # alt kısım at gövdesi
modifications:
  - feature: torso_upper_half
    from: mammalia_biped
  - feature: torso_lower_half
    from: mammalia_quadruped.horse
    merge_point: hip_human → shoulder_horse  # birleşim hassas
  - feature: legs
    count: 4 (horse rear) + 2 (human... wait)
    # Karar: 4 at bacağı (insan bacağı YOK)
```

---

## Genel Hibrit Kuralları

```yaml
rules:
  # Birleşim noktaları "smooth blend" olmalı
  joint_blend_strategy:
    method: voxel_remesh_with_extended_zone
    blend_zone_radius: body_length * 0.15
  
  # Hibrit gövdede iki anatomical class
  # birleşim varsa, her iki side'ın bone count'ı kendi sınıfından gelir
  bone_count: sum_from_all_modules
  # Örnek wyvern: reptilia_quad (35) + aves.wings (8) = ~43
  
  # Gait pattern: base_class'tan alınır
  gait_inheritance: base_class.gait
  # Yardımcı klipler (örn: wing flap) added_modules'tan
  auxiliary_clips:
    - source: aves.flap_flight_loop  # if has wings
  
  # Symmetry: tüm hibrit X simetrik (asimetri tek-off case)
  symmetry: enforce_x_mirror
```

---

## Skeleton Composition Algorithm

```python
def compose_chimera_skeleton(spec):
    """
    spec = chimera spec (base_class + added_modules + modifications)
    Returns: composed bone list
    """
    base = load_anatomy_class(spec["base_class"])
    composed_bones = list(base["bones"])
    
    for module_path in spec["added_modules"]:
        # module_path = "aves.wings" gibi
        cls_name, organ = module_path.split(".")
        cls_data = load_anatomy_class(cls_name)
        
        # Sadece o organ'a ait bone'ları al
        organ_bones = filter_bones_by_organ(cls_data["bones"], organ)
        
        # Attachment point belirle (spec.modifications içinde)
        attachment = get_attachment_point(spec, module_path)
        
        # Bone parent'larını base skeleton'a re-route
        organ_bones = re_parent_bones(organ_bones, attachment)
        
        composed_bones.extend(organ_bones)
    
    return composed_bones
```

---

## Common Defects

- Hibrit birleşim noktalarında mesh seam görünüyor (kaba clipping)
- Bir modülün skeleton'ı diğeriyle senkronize değil (örn: kanat çırparken gövde rigid)
- Hibrit yaratığa ait yeni animation (örn: wing flap + walk) eksik
- Texture seam birleşim bölgesinde belirgin

---

## Recommended Clips (her hibrit için özel)

```yaml
# Wyvern (dragon)
wyvern_clips:
  - idle_perch_breathe
  - walk_quad_ground
  - takeoff
  - flap_flight_loop
  - dive_attack
  - bite + tail_whip
  - breath_attack  # fire/ice (head pitch up + jaw open + particle anchor)
  - hit_react
  - death

# Griffin
griffin_clips:
  - idle_alert
  - walk_quad
  - run
  - takeoff
  - flap_flight_loop
  - swoop_attack
  - bite_eagle
  - hit_react
  - death

# Pegasus
pegasus_clips:
  - idle_breathe
  - walk
  - trot
  - canter
  - takeoff
  - flap_flight_loop
  - landing
  - rear_up  # iki ön bacak yukarda
  - hit_react
```

---

## Workflow Notes

Chimera için P01 Anatomist farklı çalışır:
1. Kullanıcı yaratık tarifi verir
2. Skill base_class'ı belirler
3. Eklenecek modülleri belirler (kullanıcıya teyit ettirerek)
4. Her modifikasyon için onay alır
5. Composed spec'i kaydeder
6. Normal pipeline başlar ama P03 Skeleton Architect compose_chimera_skeleton kullanır

Chimera, **diğer anatomi sınıflarının kombinasyonu** olduğu için tek başına çalışmaz — her zaman 1+ diğer sınıfa bağlıdır.
