# Agent C03: Topology Critic (Topoloji Eleştirmen)

```yaml
agent_id: topology_critic
agent_name_tr: Topoloji Eleştirmen
agent_name_en: Topology Critic
category: critic
order_index: 3
implementation_mode: subprocess
parallel_with: [C01, C02, C04, C05]
estimated_duration_seconds: 20-60
```

---

## 1. ROLE SUMMARY

Mesh'in **wireframe topoloji**'sini analiz eder. Edge flow, quad/tri/ngon dağılımı, eklem yerlerinde edge loop varlığı, pole vertex (5+ edge buluşan vertex) sayısı gibi teknik metrikler.

**Bu kritik özellikle önemlidir** çünkü kötü topology animasyonda mesh deformasyonunu zehirler — quad olmayan bölgeler bükülünce kıvrımlanır.

---

## 2. WHEN INVOKED

### Preconditions
- Mesh mevcut (`mesh_v1.blend` veya sonrası)
- Wireframe render alınmış (`renders/iter_<n>/<phase>/wireframe_*.png`)

### Postconditions
- `critic_reports/topology_<phase>_<iter>.json`

---

## 3. INPUTS

```
renders_dir: Path             # özellikle wireframe render'lar
mesh_manifest: MeshManifest.json
phase: str
```

---

## 4. OUTPUTS

```json
{
  "critic_id": "C03_topology_critic",
  "phase": "mesh",
  "iteration": 2,
  "topology_quality_score": 82,
  "metrics": {
    "tri_count": 11842,
    "quad_ratio": 0.78,
    "tri_ratio": 0.21,
    "ngon_count": 4,
    "pole_vertex_count_5plus": 28,
    "estimated_edge_loops_at_joints": "incomplete",
    "uniform_density": "mostly"
  },
  "defects": [
    {
      "id": "T001",
      "severity": "major",
      "category": "topology",
      "location": "sol omuz eklemi",
      "description_tr": "Omuz ekleminde edge loop yok, üçgenler dağınık. Animasyonda et yırtılması riski yüksek.",
      "evidence_image_names": ["wireframe_left.png"],
      "suggested_fix_tr": "P05 Topology Surgeon ile manuel retopology yapılması veya P04 Mesh Sculptor'ı daha yüksek subdivision ile re-run."
    }
  ],
  "positives": [
    "Kuyruk topoloji'si temiz, segment-by-segment edge ring var",
    "Karın bölgesi quad ratio yüksek"
  ]
}
```

---

## 5. SYSTEM PROMPT

```
SEN TOPOLOJİ ELEŞTİRMENİSİN — modeling TD'sin.

Görevin: Yaratığın wireframe render'larını analiz et, edge flow
kalitesini değerlendir.

DİKKAT EDECEKLERIN:
1. Quad ratio %75+ (çoğunlukla 4 köşeli yüzeyler)
2. Eklem yerlerinde (omuz, dirsek, diz, kalça, çene) edge loop var mı?
   Edge loop = eklem etrafında halka şeklinde edge'ler. Bunlar
   bükülmede mesh'in düzgün deforme olmasını sağlar.
3. Pole vertex'ler (5+ edge buluşan tepeler) görünür bölgelerde mi?
   Yüzde pole vertex = artifact riski.
4. N-gon (4'ten fazla köşeli face) var mı? Mobile shader bunları
   triangulate eder, predictable değil.
5. Topology yoğunluğu üniform mu? Detail varsa gözde/yüzde, gövdede
   yetersizse uniform değil.

KESİN KURALLAR:
- Wireframe-only render'a bak, shaded olmayanı tercih et
- Her defekt için yaklaşık vertex sayısı / pole count belirt
- topology_quality_score 0-100

ÇIKIŞ: Strict JSON, C01 ile uyumlu schema + metrics objesi.
```

---

## 6. METRİKLER (Otomatik Hesaplanan)

C03 sadece vision kullanmaz. Aynı zamanda **bmesh ile otomatik metrik** hesaplar:

```python
# scripts/critic/compute_topology_metrics.py
import bmesh

def compute_topology_metrics(mesh_obj):
    bm = bmesh.new()
    bm.from_mesh(mesh_obj.data)
    
    tri = quad = ngon = 0
    for face in bm.faces:
        n = len(face.verts)
        if n == 3: tri += 1
        elif n == 4: quad += 1
        else: ngon += 1
    
    pole_5plus = sum(1 for v in bm.verts if len(v.link_edges) >= 5)
    
    total = tri + quad + ngon
    
    bm.free()
    
    return {
        "tri_count": tri,
        "quad_count": quad,
        "ngon_count": ngon,
        "quad_ratio": quad / max(1, total),
        "tri_ratio": tri / max(1, total),
        "pole_vertex_count_5plus": pole_5plus,
    }
```

Vision Claude'a hem metrikler hem wireframe render verilir, beraber değerlendirir.

---

## 7. SEVERITY KURALLAR

| Bulgu | Severity |
|---|---|
| Eklem yerinde edge loop hiç yok | critical |
| Yüzde 5+ pole vertex | critical |
| Ngon görünür yerde | major |
| Quad ratio < %70 | major |
| Uniform olmayan density | minor |

---

## 8. FAILURE MODES

### F1: Wireframe render yok
**Recovery:** render_eval.py'ı wireframe modunda yeniden çalıştır.

### F2: Mesh çok karmaşık, metric computation > 30s
**Recovery:** Sample-based (vertex'lerin %20'sini al) metric.

---

## 9. CROSS-CRITIC

C03 + C01'in birlikte "topology" bulduğu defektler **confirmed**. C03 + C04'ün birlikte raporladığı defekt = "deformation muhtemelen başarısız olacak" → critical.
