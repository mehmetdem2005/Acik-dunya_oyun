# Agent M03: Tool Procurer (Araç Tedarikçisi)

```yaml
agent_id: tool_procurer
agent_name_tr: Araç Tedarikçisi
agent_name_en: Tool Procurer
category: meta
order_index: 3
implementation_mode: in_process
invocation: on_demand_or_setup
```

---

## 1. ROLE SUMMARY

Skill çalışması için gereken **araçların (Blender addon, external CLI tool, Python paketi)** mevcut olup olmadığını kontrol eder. Eksikse:

1. Kullanıcıya nazikçe bildirir
2. **Otomatik kurmaz** — sadece öner ve linkle
3. Kullanıcı onaylarsa kurulum komutunu gösterir

**Politika K8 (Version/Addon/Repo Approval)** bu ajanın özünü oluşturur. Asla kullanıcı bilgisi olmadan sistem değiştirilmez.

---

## 2. WHEN INVOKED

- **Setup başlangıcında:** modules/00-environment kontrolü çağrıldığında
- **Çalıştırma sırasında:** bir araç fail ettiğinde (örn: Voxel HDS yok)
- **Kullanıcı isteğinde:** "araçları kontrol et" / "eksik var mı"

---

## 3. INPUTS

```
phase: "setup" | "runtime" | "audit"
trigger_reason: str          # neden çağrıldı
required_for_module: str     # hangi modül istedi (runtime'da)
```

---

## 4. OUTPUTS

### 4.1 ToolAudit.json

```json
{
  "audit_date": "2026-05-24T...",
  "phase": "audit",
  "tools_checked": [
    {
      "name": "blender",
      "version_required": "4.2 LTS",
      "version_found": "4.2.3",
      "status": "ok",
      "binary_path": "C:/Program Files/Blender Foundation/Blender 4.2/blender.exe"
    },
    {
      "name": "claude_cli",
      "version_required": "any",
      "version_found": "0.4.5",
      "status": "ok"
    },
    {
      "name": "voxel_heat_diffuse_skinning_addon",
      "version_required": "any",
      "status": "not_found",
      "impact": "P08 Skinner Automatic Weights fallback'a düşer (kalite kaybı)",
      "install_suggestion": {
        "method": "Manuel addon install",
        "steps_tr": [
          "https://github.com/mmolero/blender-voxel-heat-diffuse-skinning sayfasına git",
          "Releases'tan en son .zip indir",
          "Blender → Edit → Preferences → Add-ons → Install... ile zip'i yükle",
          "Aktifleştir, sonra skill'i yeniden başlat"
        ]
      }
    },
    {
      "name": "godot_4",
      "version_required": "4.0+",
      "status": "not_found",
      "impact": "P13 Exporter smoke test atlanır (export yine de çalışır)",
      "install_suggestion": {
        "method": "winget veya download",
        "command_windows": "winget install GodotEngine.GodotEngine",
        "url": "https://godotengine.org/download"
      }
    },
    {
      "name": "python_numpy",
      "version_required": "any",
      "status": "ok"
    }
  ],
  "recommendations_priority_order": [
    "Voxel HDS addon kur (skinning kalitesi için kritik)",
    "Godot 4 kur (export validation için)"
  ],
  "all_critical_tools_present": true,
  "skill_can_run": true,
  "skill_can_run_with_full_quality": false
}
```

---

## 5. CHECK MEKANİZMASI

```python
TOOLS_REGISTRY = {
    "blender": {
        "type": "binary",
        "required": True,
        "check_command": ["blender", "--version"],
        "version_regex": r"Blender (\d+\.\d+(\.\d+)?)",
        "min_version": "4.2",
        "windows_install": "winget install BlenderFoundation.Blender",
        "fallback_paths": [
            "C:/Program Files/Blender Foundation/Blender 4.2/blender.exe",
            "C:/Program Files/Blender Foundation/Blender 4.6/blender.exe",
        ],
    },
    "claude_cli": {
        "type": "binary",
        "required": True,
        "check_command": ["claude", "--version"],
        "install_note": "Anthropic Claude CLI manuel kurulum: https://docs.claude.com/cli",
    },
    "godot_4": {
        "type": "binary",
        "required": False,
        "check_command": ["godot", "--version"],
        "min_version": "4.0",
        "impact_if_missing": "Smoke test atlanır",
        "windows_install": "winget install GodotEngine.GodotEngine",
    },
    "voxel_heat_diffuse_skinning_addon": {
        "type": "blender_addon",
        "required": False,
        "check_via_blender": True,
        "addon_module_name": "voxel_heat_diffuse_skinning",
        "impact_if_missing": "P08 Skinner Automatic Weights fallback (kalite kaybı)",
        "install_note": "Manuel: https://github.com/mmolero/blender-voxel-heat-diffuse-skinning",
    },
    "python_numpy": {
        "type": "python_module",
        "required": True,  # P03/P08 mirror functions için
        "module_name": "numpy",
        "install_command": "pip install numpy",
    },
}


def check_tool(name, info):
    """Tek aracı kontrol et."""
    result = {"name": name, "status": "unknown"}
    
    if info["type"] == "binary":
        # Önce PATH'te ara
        try:
            r = subprocess.run(info["check_command"],
                                capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                output = r.stdout + r.stderr
                if "version_regex" in info:
                    m = re.search(info["version_regex"], output)
                    if m:
                        result["version_found"] = m.group(1)
                        # Version check
                        if "min_version" in info and not version_geq(m.group(1), info["min_version"]):
                            result["status"] = "version_too_old"
                            return result
                result["status"] = "ok"
                return result
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        
        # Fallback paths dene
        for path in info.get("fallback_paths", []):
            if Path(path).exists():
                result["status"] = "ok"
                result["binary_path"] = path
                return result
        
        result["status"] = "not_found"
        return result
    
    elif info["type"] == "blender_addon":
        # Blender'ı subprocess olarak çağır, addon'u check et
        check_script = f"""
import bpy
addon_name = "{info['addon_module_name']}"
import sys
result = addon_name in bpy.context.preferences.addons
print("ADDON_STATUS:", "found" if result else "not_found")
sys.exit(0)
"""
        # Geçici dosyaya yaz, blender'ı --python ile çalıştır
        try:
            tmp = Path("/tmp/check_addon.py")
            tmp.write_text(check_script)
            r = subprocess.run(["blender", "--background", "--python", str(tmp)],
                                 capture_output=True, text=True, timeout=30)
            if "ADDON_STATUS: found" in r.stdout:
                result["status"] = "ok"
            else:
                result["status"] = "not_found"
        except Exception as e:
            result["status"] = "check_failed"
            result["error"] = str(e)
        
        return result
    
    elif info["type"] == "python_module":
        try:
            __import__(info["module_name"])
            result["status"] = "ok"
        except ImportError:
            result["status"] = "not_found"
        
        return result
    
    return result


def version_geq(v1, v2):
    """v1 >= v2?"""
    p1 = [int(x) for x in v1.split(".")[:3]]
    p2 = [int(x) for x in v2.split(".")[:3]]
    return p1 >= p2


def run_audit():
    """Tüm araçları kontrol et."""
    results = []
    for name, info in TOOLS_REGISTRY.items():
        results.append(check_tool(name, info))
    
    return results
```

---

## 6. KULLANICI ETKİLEŞİMİ

Eksik tool tespit edildiğinde:

```
[tool_procurer] Audit sonucu:

✅ blender 4.2.3 — bulundu (C:/Program Files/Blender Foundation/Blender 4.2/blender.exe)
✅ claude CLI 0.4.5 — bulundu
✅ python numpy — bulundu
⚠️ voxel_heat_diffuse_skinning_addon — BULUNAMADI
   Etki: P08 Skinner Automatic Weights fallback'a düşer.
   Skinning kalitesi düşer (eklemlerde candy-wrapper effect riski).
   
   Kurmak ister misin?
   
   Manuel kurulum adımları:
   1. https://github.com/mmolero/blender-voxel-heat-diffuse-skinning sayfasını aç
   2. Releases > en son .zip indir
   3. Blender → Edit → Preferences → Add-ons → Install... ile zip yükle
   4. Aktifleştir
   5. Bana "kuruldu" de, devam edelim
   
   Veya bu addon olmadan devam etmek istersem "skip" de, fallback ile çalışırım.

⚠️ godot — BULUNAMADI
   Etki: P13 Exporter smoke test atlanır. Export yine çalışır.
   
   Önerilen kurulum: winget install GodotEngine.GodotEngine
   Sen yetkili misin yoksa "skip" mi diyelim?
```

Kullanıcı kararı:
- "kuruldu" → Re-audit, ok ise devam
- "skip" → bu run için fallback path kullan
- "asla sorma" → bu addon için skip persistent

---

## 7. PERSISTENT PREFERENCES

`memory/tool_preferences.json`:

```json
{
  "user_skipped_tools": ["godot_4"],
  "user_preferred_blender_path": "C:/Program Files/Blender Foundation/Blender 4.2/blender.exe",
  "auto_check_on_every_run": true
}
```

---

## 8. FAILURE MODES

### F1: Blender binary bulundu ama --version timeout
**Recovery:** Manuel test, kullanıcıya path doğrula sor.

### F2: Required tool (Blender) yok
**Recovery:** Skill **çalışmaz**, kullanıcıya açık mesaj:
```
❌ Blender 4.2 bulunamadı.
Skill bu olmadan çalışamaz.

Kurulum:
   Windows: winget install BlenderFoundation.Blender
   Mac: brew install --cask blender
   Linux: apt install blender (4.2 için PPA gerekebilir)

Kurulduktan sonra "tekrar dene" de.
```
