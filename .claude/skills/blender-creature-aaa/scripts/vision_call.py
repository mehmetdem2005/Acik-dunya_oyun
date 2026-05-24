#!/usr/bin/env python3
"""
vision_call.py — Skill vision-feedback için Claude CLI wrapper

Bu script standalone çalışır (Blender içinde değil). claude -p kullanarak
render'ları vision-capable Claude'a gönderir, structured JSON kritik döner.

Kullanım:
    python vision_call.py \
        --renders-dir <path/to/renders> \
        --refs-dir <path/to/reference_photos> \
        --spec <path/to/CreatureSpec.json> \
        --phase <faz_adı> \
        --output <path/to/vision_result.json> \
        [--fast]  # minör defektleri atla, sadece kritik+major bul
        [--manual-text "kullanıcı feedback'i"]  # vision yerine manuel

ÇIKTI:
    vision_result.json: yapılandırılmış defekt raporu
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


CLI_DETECT_CACHE = Path.home() / ".cache" / "blender-aaa-creature" / "cli_signature.json"


# -----------------------------------------------------------------------------
# Claude CLI tespit ve flag uyumluluğu
# -----------------------------------------------------------------------------

def detect_claude_cli():
    """
    Claude CLI yüklü mü, hangi flag'leri destekliyor (image attachment için)
    tespit eder. Sonucu cache'ler.
    """
    if CLI_DETECT_CACHE.exists():
        try:
            return json.loads(CLI_DETECT_CACHE.read_text())
        except Exception:
            pass
    
    claude_bin = shutil.which("claude")
    if not claude_bin:
        raise RuntimeError(
            "Claude CLI bulunamadı. Kurulum için: npm install -g @anthropic-ai/claude-cli\n"
            "Sonra: claude login"
        )
    
    # --help çıktısını parse et, image flag'ini bul
    help_out = subprocess.run(
        [claude_bin, "--help"],
        capture_output=True,
        text=True,
        timeout=10
    ).stdout
    
    # Olası flag adları (CLI versiyonuna göre değişiyor)
    candidates = ["--image", "--attach", "--file", "-i"]
    image_flag = None
    for flag in candidates:
        if flag in help_out:
            image_flag = flag
            break
    
    if not image_flag:
        # En yaygın default: --image (Anthropic CLI)
        image_flag = "--image"
    
    info = {
        "bin": claude_bin,
        "image_flag": image_flag,
        "supports_json_output": "--output-format" in help_out and "json" in help_out,
    }
    
    CLI_DETECT_CACHE.parent.mkdir(parents=True, exist_ok=True)
    CLI_DETECT_CACHE.write_text(json.dumps(info, indent=2))
    return info


# -----------------------------------------------------------------------------
# Prompt oluşturma
# -----------------------------------------------------------------------------

VISION_SYSTEM_PROMPT = """You are a senior 3D character art technical director (TD) reviewing
a creature asset for a mobile game (Godot 4 engine). The user is Turkish-speaking
but you respond ONLY in structured JSON (no prose outside JSON).

You will be shown:
1. Reference images of the real creature anatomy (if provided)
2. Multi-angle renders of the current state of the asset
3. Wireframe overlay renders (topology check)
4. Stress pose renders (deformation check, if rig is ready)
5. One in-game camera distance render (mobile silhouette check)

YOUR JOB: Identify defects. Be specific, ruthless, honest. Never praise broken work.
Compare to:
- Real anatomy (refs or your knowledge of the species)
- AAA mobile creature standards (clear silhouette, clean topology, proper deformation)
- The creature spec provided

OUTPUT FORMAT (strict JSON, no markdown fences, no prose):
{
  "overall_assessment": "critical_issues_present" | "major_issues_present" | "minor_polish_needed" | "production_ready",
  "defects": [
    {
      "id": "D001",
      "severity": "critical" | "major" | "minor",
      "category": "anatomy" | "topology" | "deformation" | "proportion" | "symmetry" | "intersection" | "silhouette" | "detail" | "uv_texture" | "material",
      "location": "exact location, e.g., 'left front shoulder', 'tail base', 'right paw inner edge'",
      "description_en": "technical description, what's wrong",
      "description_tr": "plain Turkish for user, NO English jargon, max 2 sentences",
      "evidence_image_names": ["which render shows it, e.g., rest_left.png"],
      "suggested_fix_tr": "Turkish, plain language, what should be done",
      "alternatives_tr": ["alternative fix 1 in Turkish", "alternative fix 2"]
    }
  ],
  "positives": ["short Turkish phrase, what looks good (max 5 items)"],
  "silhouette_readability": "excellent" | "good" | "weak" | "poor",
  "anatomical_accuracy_score": 0-100,
  "topology_quality_score": 0-100,
  "next_action_recommendation_tr": "Turkish, what to do next, max 3 sentences"
}

CRITICAL RULES:
- description_tr and suggested_fix_tr MUST be jargon-free Turkish. No English words.
  If a technical term is unavoidable, explain it in parentheses: 
  'mesh (model yüzeyi)', 'bone (kemik)', 'topology (yüzey düzeni)'
- If no defects of a severity exist, omit them (don't include placeholder defects).
- evidence_image_names must match actual filenames you see.
- Do not invent defects. If asset looks good, say "production_ready".
- Mobile context: silhouette readability matters more than fine detail.
"""


def build_prompt(spec_summary, render_names, ref_names, phase, fast_mode):
    """
    Vision Claude'a gidecek user prompt.
    """
    parts = [
        VISION_SYSTEM_PROMPT,
        "\n---\n\nCREATURE SPEC SUMMARY:\n",
        spec_summary,
        f"\n\nCURRENT PHASE: {phase}",
        "\n\nREFERENCE IMAGES (real anatomy):",
        ", ".join(ref_names) if ref_names else "(none provided)",
        "\n\nCURRENT STATE RENDERS:",
        ", ".join(render_names),
    ]
    
    if fast_mode:
        parts.append(
            "\n\nFAST MODE: Find only critical and major defects. "
            "Skip minor cosmetic issues."
        )
    
    parts.append("\n\nProduce the JSON now. Nothing else, just the JSON object.")
    
    return "\n".join(parts)


def summarize_spec(spec):
    """CreatureSpec'in vision için kısa özetini üret."""
    out = [
        f"Common name: {spec.get('common_name_tr', 'unknown')}",
        f"Scientific name: {spec.get('scientific_name', 'unknown')}",
        f"Class: {spec.get('anatomy_class', 'unknown')}",
        f"Stylization: {spec.get('stylization_level', 'unknown')}",
    ]
    
    if 'proportions' in spec:
        out.append("Proportions (normalized to body length=1.0):")
        for k, v in spec['proportions'].items():
            out.append(f"  {k}: {v}")
    
    if 'user_modifications' in spec and spec['user_modifications']:
        out.append("User stylization overrides:")
        for k, v in spec['user_modifications'].items():
            out.append(f"  {k}: {v}")
    
    return "\n".join(out)


# -----------------------------------------------------------------------------
# Claude CLI çağrısı
# -----------------------------------------------------------------------------

def call_claude(prompt, image_paths, cli_info, timeout=300):
    """
    claude -p ile prompt + images gönder, output parse et.
    """
    cmd = [cli_info["bin"], "-p"]
    
    if cli_info.get("supports_json_output"):
        cmd.extend(["--output-format", "json"])
    
    # Görüntü ekle
    image_flag = cli_info["image_flag"]
    for img in image_paths:
        cmd.extend([image_flag, str(img)])
    
    print(f"[vision_call] {len(image_paths)} görüntü Claude'a gönderiliyor...")
    
    try:
        result = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding='utf-8',
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Vision call timeout ({timeout}s) — Claude cevap vermedi.")
    
    if result.returncode != 0:
        raise RuntimeError(
            f"Claude CLI hata döndü (exit {result.returncode}):\n"
            f"STDERR: {result.stderr}\n"
            f"STDOUT: {result.stdout}"
        )
    
    return result.stdout


# -----------------------------------------------------------------------------
# JSON extract (Claude bazen JSON'ı text içinde gömer)
# -----------------------------------------------------------------------------

def extract_json(raw_text):
    """
    Raw Claude output'tan ilk geçerli JSON object'i çek.
    """
    # Doğrudan parse dene
    text = raw_text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # ```json ... ``` blok'u var mı
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except json.JSONDecodeError:
            pass
    
    # İlk { ile en son } arası
    first = text.find('{')
    last = text.rfind('}')
    if first >= 0 and last > first:
        try:
            return json.loads(text[first:last+1])
        except json.JSONDecodeError:
            pass
    
    raise ValueError(f"JSON parse edilemedi. Raw output:\n{raw_text[:2000]}")


# -----------------------------------------------------------------------------
# Result validation
# -----------------------------------------------------------------------------

REQUIRED_KEYS = {"overall_assessment", "defects"}
VALID_ASSESSMENTS = {
    "critical_issues_present",
    "major_issues_present", 
    "minor_polish_needed",
    "production_ready",
}


def validate_result(result):
    """Vision çıktısı schema'ya uyuyor mu kontrol."""
    if not isinstance(result, dict):
        raise ValueError("Vision result dict değil")
    
    missing = REQUIRED_KEYS - set(result.keys())
    if missing:
        raise ValueError(f"Eksik alanlar: {missing}")
    
    if result["overall_assessment"] not in VALID_ASSESSMENTS:
        raise ValueError(
            f"Geçersiz assessment: {result['overall_assessment']}. "
            f"Geçerli: {VALID_ASSESSMENTS}"
        )
    
    if not isinstance(result.get("defects"), list):
        raise ValueError("'defects' liste olmalı")
    
    # Defekt minimum alanları
    for i, d in enumerate(result["defects"]):
        for k in ["id", "severity", "category", "description_tr", "suggested_fix_tr"]:
            if k not in d:
                raise ValueError(f"Defect[{i}] eksik alan: {k}")
    
    return True


# -----------------------------------------------------------------------------
# Manual feedback (kullanıcı vision Claude'a katılmazsa)
# -----------------------------------------------------------------------------

def parse_manual_feedback(text):
    """
    Kullanıcı format:
        CRIT: bla bla
        MAJOR: bla bla
        MINOR: bla bla
    
    Bunu vision-result formatına çevirir.
    """
    defects = []
    severity_map = {"CRIT": "critical", "MAJOR": "major", "MINOR": "minor"}
    
    counter = 1
    for line in text.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^(CRIT|MAJOR|MINOR):\s*(.+)$", line, re.IGNORECASE)
        if m:
            severity = severity_map[m.group(1).upper()]
            desc = m.group(2).strip()
            defects.append({
                "id": f"M{counter:03d}",
                "severity": severity,
                "category": "manual_user_feedback",
                "location": "unspecified",
                "description_en": desc,
                "description_tr": desc,
                "evidence_image_names": [],
                "suggested_fix_tr": "Kullanıcı manuel söylemiş, daha fazla detay alınmalı veya yorum üzerinden devam edilmeli.",
                "alternatives_tr": [],
            })
            counter += 1
    
    if not defects:
        # Hiç parse edilmediyse, tüm metin tek major defekt
        defects.append({
            "id": "M001",
            "severity": "major",
            "category": "manual_user_feedback",
            "location": "unspecified",
            "description_en": text,
            "description_tr": text,
            "evidence_image_names": [],
            "suggested_fix_tr": "Kullanıcı serbest format feedback verdi, yorumlanmalı.",
            "alternatives_tr": [],
        })
    
    overall = "critical_issues_present" if any(d["severity"] == "critical" for d in defects) else \
              "major_issues_present" if any(d["severity"] == "major" for d in defects) else \
              "minor_polish_needed"
    
    return {
        "overall_assessment": overall,
        "defects": defects,
        "positives": [],
        "silhouette_readability": "unspecified",
        "anatomical_accuracy_score": None,
        "topology_quality_score": None,
        "next_action_recommendation_tr": "Kullanıcı manuel feedback verdi, defektleri tek tek değerlendir.",
        "source": "manual_user_feedback",
    }


# -----------------------------------------------------------------------------
# Ana akış
# -----------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--renders-dir", required=True)
    p.add_argument("--refs-dir", default=None, help="Referans foto klasörü (opsiyonel)")
    p.add_argument("--spec", required=True, help="CreatureSpec.json path")
    p.add_argument("--phase", required=True, help="Hangi faz: mesh/rig/skin/anim")
    p.add_argument("--output", required=True, help="Vision result JSON output path")
    p.add_argument("--fast", action="store_true")
    p.add_argument("--manual-text", default=None, help="Manuel feedback metni (vision yerine)")
    p.add_argument("--timeout", type=int, default=300)
    p.add_argument("--max-images", type=int, default=20,
                   help="Tek call'a giden max image (token bütçesi koruma)")
    args = p.parse_args()
    
    renders_dir = Path(args.renders_dir).resolve()
    spec_path = Path(args.spec).resolve()
    output_path = Path(args.output).resolve()
    
    if not renders_dir.exists():
        print(f"❌ Renders dir yok: {renders_dir}", file=sys.stderr)
        sys.exit(1)
    
    if not spec_path.exists():
        print(f"❌ Spec yok: {spec_path}", file=sys.stderr)
        sys.exit(1)
    
    spec = json.loads(spec_path.read_text(encoding='utf-8'))
    
    # Manuel mod
    if args.manual_text:
        result = parse_manual_feedback(args.manual_text)
        result["phase"] = args.phase
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
        print(f"✅ Manuel feedback parse edildi → {output_path}")
        return
    
    # Render dosyalarını topla
    renders = sorted(renders_dir.glob("*.png"))
    if not renders:
        print(f"❌ Render dir'da PNG yok: {renders_dir}", file=sys.stderr)
        sys.exit(1)
    
    # Refs
    ref_images = []
    if args.refs_dir:
        refs_dir = Path(args.refs_dir).resolve()
        if refs_dir.exists():
            ref_images = sorted(refs_dir.glob("*.jpg")) + \
                         sorted(refs_dir.glob("*.png")) + \
                         sorted(refs_dir.glob("*.jpeg"))
    
    # Image limit koruması (Claude context window)
    all_images = renders + ref_images
    if len(all_images) > args.max_images:
        print(f"⚠️ {len(all_images)} görüntü var, {args.max_images}'e düşürülüyor "
              f"(rest pose + wireframe + en az 2 stres pozu)")
        # Prioritize: rest_*, wire_top + wire_left, 2 stres, 1 ingame, refs
        priority = []
        for img in renders:
            if img.name.startswith("rest_"):
                priority.append(img)
        for img in renders:
            if img.name in ("wire_top.png", "wire_left.png", "wire_34_front.png"):
                priority.append(img)
        stress_added = 0
        for img in renders:
            if img.name.startswith("stress_") and stress_added < 4:
                priority.append(img)
                stress_added += 1
        for img in renders:
            if img.name == "ingame_camera.png":
                priority.append(img)
        priority.extend(ref_images[:5])
        
        # Dedup
        all_images = list(dict.fromkeys(priority))[:args.max_images]
    
    # CLI tespit
    try:
        cli_info = detect_claude_cli()
    except RuntimeError as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(2)
    
    # Prompt
    spec_summary = summarize_spec(spec)
    prompt = build_prompt(
        spec_summary=spec_summary,
        render_names=[r.name for r in renders],
        ref_names=[r.name for r in ref_images],
        phase=args.phase,
        fast_mode=args.fast,
    )
    
    # Çağrı
    try:
        raw = call_claude(prompt, all_images, cli_info, timeout=args.timeout)
    except RuntimeError as e:
        print(f"❌ Claude çağrı hatası: {e}", file=sys.stderr)
        sys.exit(3)
    
    # Parse + validate
    try:
        result = extract_json(raw)
        validate_result(result)
    except (ValueError, json.JSONDecodeError) as e:
        print(f"❌ Vision çıktısı parse edilemedi: {e}", file=sys.stderr)
        # Raw'ı yine de kaydet
        debug_path = output_path.with_suffix('.raw.txt')
        debug_path.write_text(raw, encoding='utf-8')
        print(f"   Raw çıktı: {debug_path}", file=sys.stderr)
        sys.exit(4)
    
    result["phase"] = args.phase
    result["source"] = "claude_vision"
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    
    # Özet
    n_crit = sum(1 for d in result["defects"] if d["severity"] == "critical")
    n_maj = sum(1 for d in result["defects"] if d["severity"] == "major")
    n_min = sum(1 for d in result["defects"] if d["severity"] == "minor")
    
    print(f"✅ Vision check tamamlandı → {output_path}")
    print(f"   Assessment: {result['overall_assessment']}")
    print(f"   Defektler: {n_crit} kritik, {n_maj} majör, {n_min} minör")


if __name__ == "__main__":
    main()
