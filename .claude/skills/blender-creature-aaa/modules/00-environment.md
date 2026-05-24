# Modül 00 — Ortam Hazırlığı (Windows)

**Amaç:** Skill çalışmaya başlamadan önce Blender 4.2 LTS, gerekli Blender addon'ları, Godot 4 stable, Python paketleri ve Claude CLI'nin yüklü ve erişilebilir olduğundan emin olmak. Hiçbir kurulum kullanıcı onayı olmadan yapılmaz (§8).

**Hedef OS:** Windows 10+ (PowerShell 5.1+). macOS/Linux için uyumluluk şu an yok; gerekirse kullanıcı isteyince eklenir.

---

## 1. KONTROL LİSTESİ

Skill bu modüle girdiğinde **önce probe** yapar. Her bileşeni tek tek kontrol eder, sonuçları tek bir tabloda kullanıcıya gösterir:

| Bileşen | Beklenen | Kontrol Yöntemi |
|---|---|---|
| Blender | 4.2.x LTS | `Get-Command blender` → `--version` |
| Blender bundled Python | 3.11.x | `<blender_path>\4.2\python\bin\python.exe --version` |
| Voxel Heat Diffuse Skinning addon | Enabled | `bpy.context.preferences.addons` listesi |
| Godot 4 | 4.x stable, mobile renderer | `Get-Command godot` → `--version` |
| Claude CLI (`claude`) | Available, authenticated | `claude --version` |
| Python deps (numpy, scipy, Pillow) | Installed in Blender bundled Python | `pip list` |
| Working directory | `C:\dev\aaa-creature\` veya kısa path | length check, MAX_PATH=260 |
| Skill memory dir | Yazılabilir | `Test-Path` + write probe |

---

## 2. PROBE SCRIPT (önce çalıştır)

PowerShell script'i çalıştır, `probe_result.json` üret:

```powershell
# scripts/probe_environment.ps1
$result = @{
    blender = $null
    blender_python = $null
    godot = $null
    claude_cli = $null
    addons = @()
    python_deps = @()
    working_dir_ok = $false
    issues = @()
}

# Blender
try {
    $blenderVer = & blender --version 2>$null | Select-Object -First 1
    if ($blenderVer -match "Blender (\d+\.\d+\.\d+)") {
        $result.blender = $matches[1]
        if ($matches[1] -notlike "4.2.*") {
            $result.issues += "Blender versiyonu 4.2 LTS değil: $($matches[1])"
        }
    }
} catch { $result.issues += "Blender yüklü değil veya PATH'te yok" }

# Godot
try {
    $godotVer = & godot --version 2>$null
    if ($godotVer) { $result.godot = $godotVer }
} catch { $result.issues += "Godot yüklü değil veya PATH'te yok" }

# Claude CLI
try {
    $claudeVer = & claude --version 2>$null
    if ($claudeVer) { $result.claude_cli = $claudeVer }
} catch { $result.issues += "Claude CLI yüklü değil (vision feedback çalışmaz)" }

# Working dir
$cwd = (Get-Location).Path
if ($cwd.Length -gt 80) {
    $result.issues += "Çalışma dizini çok uzun ($($cwd.Length) karakter), MAX_PATH sorunu çıkar. C:\dev\aaa-creature\ gibi kısa bir path öner."
}

$result | ConvertTo-Json -Depth 5 | Out-File probe_result.json
```

---

## 3. KULLANICIYA SUNUM (probe sonrası)

Skill probe sonucunu **tek bir tablo + öneri listesi** olarak gösterir:

```
══════════════════════════════════════════════════
ORTAM KONTROLÜ TAMAMLANDI

✅ Blender 4.2.3 LTS bulundu — C:\Program Files\Blender Foundation\Blender 4.2\
✅ Blender Python 3.11.x — bundled
❌ Godot 4 bulunamadı
❌ Claude CLI bulunamadı  
⚠️  Voxel Heat Diffuse Skinning addon enable değil
⚠️  Çalışma dizinin C:\Users\Mehmet\Desktop\Projects\... çok uzun. Kısalt.

EKSİK BİLEŞENLER (her birini ayrı onayınla kuracağım):

  [1] Godot 4.3 stable kurulumu (~280 MB, ~3 dakika)
      Açıklama: Godot oyun motoru. Yaratık .glb dosyasını test etmek
      ve mobil renderer'da görüntülemek için lazım. Yoksa export
      yaptık ama test edemedik durumu olur.
      Yöntem: winget install GodotEngine.GodotEngine
      Onay? [evet / hayır / sonra / başka versiyon istiyorum]

  [2] Claude CLI kurulumu (~50 MB, ~2 dakika)
      Açıklama: "claude -p" komutu. Skill'in vision feedback adımında
      render'ları sana göndermek yerine ben (bu skill) Claude'a
      gönderip "şu hatalar var mı?" diye soracağım. Bunsuz görsel
      hata tespiti yapılamaz.
      Yöntem: npm install -g @anthropic-ai/claude-cli
      (Node.js gerekli, varsa kurulu, yoksa o da kurulacak)
      Onay? [evet / hayır / sonra / detay]

  [3] Voxel Heat Diffuse Skinning addon enable
      Açıklama: Addon zaten kurulu ama aktif değil. Bu addon, kemiklerin
      mesh'i ne kadar etkileyeceğini matematiksel olarak hesaplar
      ("skinning weight" denilen şey). Blender'ın standart "Automatic
      Weights" özelliği bacaklar birbirine yakınsa kötü sonuç verir,
      bu addon kusursuz yapar.
      Yöntem: bpy.ops.preferences.addon_enable(module="voxel_heat_diffuse")
      Onay? [evet / hayır / başka skinning yöntemi tercih ediyorum]

  [4] Çalışma dizinini değiştir
      Mevcut: C:\Users\Mehmet\Desktop\Projects\... (çok uzun)
      Öneri: C:\dev\aaa-creature\
      Açıklama: Windows'un eski bir kuralı var, dosya yollarının
      260 karakterden uzun olamayacağına dair. Skill'in alt klasörleri
      derinleştikçe bu limiti aşarız ve dosyalar açılmaz. Kısa root
      lazım.
      Onay? [evet, taşı / başka path öneriyorum / yoksay]

══════════════════════════════════════════════════
```

Kullanıcı seçimleri verdikten sonra **sadece onaylananlar** kurulur.

---

## 4. KURULUM ADIMLARI (her bileşen için)

### 4.1 Blender 4.2 LTS

Kurulu değilse:
```powershell
winget install BlenderFoundation.Blender --version 4.2.3 --accept-source-agreements --accept-package-agreements
```
Versiyonu farklıysa (örn: 4.5 kurulu): skill **silmez**, yan yana 4.2'yi izole path'e kurar:
```powershell
$installerUrl = "https://download.blender.org/release/Blender4.2/blender-4.2.3-windows-x64.zip"
$dest = "C:\dev\blender-4.2-aaa-creature\"
Invoke-WebRequest -Uri $installerUrl -OutFile blender42.zip
Expand-Archive blender42.zip -DestinationPath $dest
# Skill bu path'i kullanır, sistem Blender'ına dokunmaz
```

### 4.2 Skill İzole Config

Skill kendi Blender config path'ini izole tutar (kullanıcının kendi Blender prefs'ine dokunmaz):
```powershell
$env:BLENDER_USER_RESOURCES = "C:\dev\aaa-creature\blender_config"
# Bu env var skill her başladığında set edilir, addon'lar buraya kurulur
```

### 4.3 Voxel Heat Diffuse Skinning Addon

GitHub: https://github.com/HavenTong/voxel-heat-diffuse-skinning (kullanıcı onayıyla klonlanır)

```powershell
git clone https://github.com/HavenTong/voxel-heat-diffuse-skinning.git C:\dev\aaa-creature\addons\voxel_heat_diffuse
# Sonra Blender bpy script'iyle enable
```

`enable_addon.py`:
```python
import bpy
import addon_utils
addon_utils.enable("voxel_heat_diffuse", default_set=True, persistent=True)
bpy.ops.wm.save_userpref()
```

### 4.4 Python Dependencies (Blender bundled Python'a)

```powershell
$blenderPython = "C:\Program Files\Blender Foundation\Blender 4.2\4.2\python\bin\python.exe"
& $blenderPython -m ensurepip
& $blenderPython -m pip install --upgrade pip
& $blenderPython -m pip install numpy scipy Pillow
```

### 4.5 Godot 4 Stable

```powershell
winget install GodotEngine.GodotEngine
# Veya export templates için: portable zip indirip belirli path'e koy
```

### 4.6 Claude CLI

Önce Node.js kontrolü:
```powershell
$nodeVer = node --version 2>$null
if (-not $nodeVer) {
    Write-Host "Node.js kurulu değil. Önce onu kurmam lazım. Onay?"
    # winget install OpenJS.NodeJS.LTS
}
npm install -g @anthropic-ai/claude-cli
claude --version
# Auth check
$authStatus = claude config get 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Claude CLI auth lazım. 'claude login' çalıştırman gerekiyor."
}
```

### 4.7 Çalışma Dizini

```powershell
$workDir = "C:\dev\aaa-creature"
if (-not (Test-Path $workDir)) {
    New-Item -ItemType Directory -Path $workDir -Force
}
Set-Location $workDir
```

---

## 5. POST-INSTALL DOĞRULAMA

Her kurulum sonrası probe yeniden çalıştırılır. Tüm bileşenler ✅ olana kadar yeni eksiklikler kullanıcıya bildirilir.

---

## 6. HATA DURUMUNDA

Bir kurulum başarısız olursa:
1. Hatanın **tam çıktısı** kullanıcıya gösterilir (gizleme yok)
2. Skill 3 olası neden + her birinin Türkçe açıklaması ile gelir
3. Kullanıcı seçer veya manuel müdahale eder
4. Skill "ya manuel kurar mısın, ya da farklı bir yöntem deneyeyim?" diye sorar

---

## 7. BU MODÜL TAMAMLANDIĞINDA

`memory/decisions.jsonl`'a yazılır:
```json
{"timestamp": "...", "module": "00-environment", "installed": ["godot-4.3", "claude-cli", "voxel-heat-diffuse"], "skipped": [], "blender_path": "...", "work_dir": "..."}
```

Sonra kullanıcıya:
```
✅ Ortam hazır. Faz 1 (Anatomik Araştırma) modülüne geçeyim mi?
[evet / önce şunu yapmak istiyorum / dur, bir saatim var sadece]
```
