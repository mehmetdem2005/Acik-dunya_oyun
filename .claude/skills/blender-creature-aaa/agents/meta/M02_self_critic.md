# Agent M02: Self-Critic (Öz Eleştirmen)

```yaml
agent_id: self_critic
agent_name_tr: Öz Eleştirmen
agent_name_en: Self-Critic
category: meta
order_index: 2
implementation_mode: subprocess  # claude -p
invocation: on_demand  # kullanıcı "skill'i geliştir" derse
```

---

## 1. ROLE SUMMARY

Skill'in **kendi modüllerini** eleştiren meta-ajan. Her ajan dokümantasyonunu, build script'lerini, ve genel pipeline'ı yeniden okur, **iyileştirme önerileri** üretir.

**Bu, skill'in zaman içinde kendi kalitesini artırması için temel mekanizmadır.**

---

## 2. WHEN INVOKED

- Kullanıcı açıkça "skill'i geliştir" / "kendini eleştir" / "v2'ye hazırlan" derse
- M01 patterns.json'da belirli bir sorun threshold aşılmışsa (örn: %30+ run'da aynı defekt türü tekrar ediyor)
- Versiyon güncellemesinde Tool Procurer (M03) yeni addon önerirse

**Asla otomatik çalıştırılmaz** — kullanıcı onayıyla.

---

## 3. INPUTS

```
skill_root_dir: Path                     # tüm skill dosyaları
patterns_json: memory/patterns.json     # M01'in pattern'leri
recent_runs: List[run_log.json]         # son 5 run
critique_focus: str                      # "all" | "agent_xxx" | "build_scripts"
```

---

## 4. OUTPUTS

### 4.1 SelfCritique.json

```json
{
  "critic_id": "M02_self_critic",
  "skill_version_evaluated": "0.1.0",
  "evaluation_date": "2026-05-24T...",
  "improvements_proposed": [
    {
      "priority": "high",
      "module": "P04_mesh_sculptor",
      "issue": "Boolean union FAST solver fallback başarısızlık oranı yüksek (son 5 run'da 3 kez)",
      "suggested_change": "Voxel remesh'i her part için ayrı uygula (intermediate manifold), sonra final union dene.",
      "impact": "P04 reliability artar, F1 failure mode azalır",
      "estimated_loc_change": 30
    },
    {
      "priority": "medium",
      "module": "P08_skinner",
      "issue": "Mirror weights operator bazı Blender versiyonlarında 'use_topology' parametresi yok",
      "suggested_change": "Try/except blok ile parametre detect, fallback path ekle",
      "estimated_loc_change": 12
    },
    {
      "priority": "low",
      "module": "build_animation.py",
      "issue": "Gallop pattern phase offset'leri eksik, sadece walk/trot var",
      "suggested_change": "GAIT_PATTERNS dict'ine gallop entries ekle",
      "estimated_loc_change": 8
    }
  ],
  "general_observations": [
    "Skill 13 modülden oluşuyor, ortalama modül uzunluğu 450 satır — bakım kolaylığı için iyi",
    "Türkçe comment oranı yüksek, kullanıcı anlayabilir",
    "Test coverage yok — birim test eklenmeli"
  ],
  "anti_patterns_detected": [
    "P04 ve P08'de bazı magic number kullanımı (örn: voxel_size=0.012 hardcoded fallback)",
    "render_eval.py'da timeout hardcoded 60 — büyük mesh'ler için yetersiz olabilir"
  ]
}
```

---

## 5. SYSTEM PROMPT (claude -p'ye gider)

```
SEN BU SKILL'İN KENDİ ÖZ ELEŞTİRMENİSİN.

Görevin: blender-creature-aaa skill'inin tüm modüllerini oku,
şu açılardan değerlendir:

1. KOD KALİTESİ:
   - Hardcoded magic number var mı? Konfigüre edilebilir mi?
   - Error handling yeterli mi? Recovery path'ler var mı?
   - Türkçe comment'ler doğru ve faydalı mı?

2. PIPELINE TUTARLILIĞI:
   - Manifest'ler arası tutarlı mı? Field naming convention aynı mı?
   - JSON schema'lar dokümante mi?
   - Failure handling cross-module uyumlu mu?

3. KULLANICI DENEYİMİ:
   - Politikalar (K1-K11) gerçekten her ajan tarafından uygulanıyor mu?
   - Soru sorma pattern'i tutarlı mı?
   - Vision feedback raporları kullanıcıya net mi?

4. PATTERN ANALİZİ:
   - patterns.json'da hangi sorunlar tekrar ediyor?
   - Hangi defekt türü en sık? Bu, hangi ajanın iyileştirilmesi gerektiğini gösterir.

5. ANTI-PATTERNS:
   - Spaghetti dependency var mı?
   - Hangi modüller birbirine fazla bağlı?
   - Skill kendini "büyük" hissettiriyor mu (kullanıcı için intimidating)?

ÇIKIŞ: Strict JSON, improvements_proposed listesi öncelik sırasına göre.
Her improvement uygulanabilir (concrete file path + exact line range)
olmalı.
```

---

## 6. KULLANIM

```python
# Kullanıcı "skill'i geliştir" dedi
result = self_critic.evaluate(
    skill_root_dir=".",
    patterns=load("memory/patterns.json"),
    recent_runs=load_recent_run_logs(5),
    critique_focus="all",
)

# Kullanıcıya sun
print("Skill v2 için öneriler:")
for imp in result["improvements_proposed"]:
    print(f"  [{imp['priority']}] {imp['module']}: {imp['issue']}")
    print(f"     → {imp['suggested_change']}")

# Onay → her improvement için sayfa sayfa edit
```

---

## 7. SAFETY

M02 **dosya yazmaz**. Sadece öneri çıkarır. Önerileri kullanıcı onayladıktan sonra kullanıcı (veya başka bir tool, örn: Cursor) edit'leri uygular.

Bu, skill'in kendi kendine değişmesini önler (kontrolsüz drift'ten kaçınır).

---

## 8. DEPENDENCIES

- claude -p (subprocess)
- memory/patterns.json (varsa)
- Tüm skill dosyaları (read-only)

---

## 9. FAILURE MODES

### F1: Çok büyük context (tüm modülleri prompt'a koy = token aşımı)
**Recovery:** Modülleri batch'le, her seferinde 3-5 modül analiz. Sonuçları birleştir.

### F2: claude -p timeout (analiz uzun sürdü)
**Recovery:** Timeout 5 dk → 15 dk, fail ise focused mode (`critique_focus='single_agent'`).
