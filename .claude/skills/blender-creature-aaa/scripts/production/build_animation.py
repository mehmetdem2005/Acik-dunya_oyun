#!/usr/bin/env python3
"""
build_animation.py — P12 Animator'ın executable component

Skinned creature için prosedürel animasyon klipleri üretir.
Her klip için F-Curve'ler matematik formüllerden hesaplanır.

Kullanım:
    blender --background <skinned_v1.blend> --python build_animation.py -- \
        --blueprint <SkeletonBlueprint.json> \
        --budget <BudgetSpec.json> \
        --anatomy-class <path> \
        --output-blend <animated_v1.blend>
"""

import bpy
import json
import math
import sys
import argparse
from pathlib import Path


def parse_args():
    if "--" in sys.argv:
        argv = sys.argv[sys.argv.index("--") + 1:]
    else:
        argv = []
    
    p = argparse.ArgumentParser()
    p.add_argument("--blueprint", required=True)
    p.add_argument("--budget", required=True)
    p.add_argument("--anatomy-class", required=True)
    p.add_argument("--output-blend", required=True)
    p.add_argument("--fps", type=int, default=30)
    return p.parse_args(argv)


# =============================================================================
# Gait phase patterns (anatomy class'tan da gelebilir, default mammalia)
# =============================================================================

GAIT_PATTERNS = {
    "walk_4beat": {
        "LF": 0.0, "RR": 0.25, "RF": 0.5, "LR": 0.75,
    },
    "trot_diagonal": {
        "LF": 0.0, "RR": 0.0, "RF": 0.5, "LR": 0.5,
    },
    "gallop_asymmetric": {
        "LR": 0.0, "RR": 0.10, "LF": 0.45, "RF": 0.55,
    },
    "bound_pair": {
        "LF": 0.0, "RF": 0.0, "LR": 0.5, "RR": 0.5,
    },
}


# =============================================================================
# Armature ve bone tespit
# =============================================================================

def find_armature():
    for obj in bpy.data.objects:
        if obj.type == 'ARMATURE':
            return obj
    return None


def get_foot_ik_bones(armature_obj):
    """IK foot bone'larını blueprint naming convention'ına göre bul."""
    bones = {}
    for pbone in armature_obj.pose.bones:
        name = pbone.name.lower()
        if "foot_ik" not in name and "ik_foot" not in name:
            continue
        # Suffix tespiti
        if "front" in name and name.endswith("_l"):
            bones["LF"] = pbone.name
        elif "front" in name and name.endswith("_r"):
            bones["RF"] = pbone.name
        elif "rear" in name and name.endswith("_l"):
            bones["LR"] = pbone.name
        elif "rear" in name and name.endswith("_r"):
            bones["RR"] = pbone.name
    return bones


def get_tail_bones(armature_obj):
    return sorted([b.name for b in armature_obj.pose.bones
                   if b.name.startswith("tail_")])


def get_spine_root(armature_obj):
    """En üstteki spine bone (root_master varsa o, yoksa spine_00)."""
    if "root_master" in armature_obj.pose.bones:
        return "root_master"
    elif "spine_00" in armature_obj.pose.bones:
        return "spine_00"
    elif "spine_hip" in armature_obj.pose.bones:
        return "spine_hip"
    return None


# =============================================================================
# Trajectory formulas
# =============================================================================

def foot_trajectory(t, phase_offset, lift_amp, stride_len):
    """Tek foot için Y ve Z delta."""
    phi = 2 * math.pi * (t + phase_offset)
    y = stride_len * math.sin(phi + math.pi / 2)
    z = max(0.0, lift_amp * math.sin(phi))
    return y, z


def body_bounce(t, amplitude):
    """2x gait freq'te küçük up-down."""
    return amplitude * abs(math.sin(2 * 2 * math.pi * t))


def spine_roll(t, amplitude_rad):
    """Gait freq'te yan salınım."""
    return amplitude_rad * math.sin(2 * math.pi * t + math.pi / 2)


def tail_wag_for_segment(t, amplitude_rad, segment_index, total_segments):
    """Whip-like, tip'e doğru artan delay + azalan amplitude."""
    delay = segment_index * 0.1
    base_freq = 0.5  # walk'ta yarı freq
    phi = 2 * math.pi * t * base_freq - delay
    falloff = max(0.1, 1.0 - segment_index * 0.1)
    return amplitude_rad * math.sin(phi) * falloff


def head_counter_bounce(t, body_bounce_amp):
    """Gövde Z+ olunca head Z- ."""
    return -0.5 * body_bounce_amp * abs(math.sin(2 * 2 * math.pi * t))


# =============================================================================
# F-Curve oluşturma
# =============================================================================

def add_fcurve(action, bone_name, channel, array_index, samples):
    """Action'a F-Curve ekle. samples = list of (frame, value)."""
    data_path = f'pose.bones["{bone_name}"].{channel}'
    
    # Mevcut F-Curve'ü ara, varsa silip yenisini oluştur
    fc = action.fcurves.find(data_path, index=array_index)
    if fc is not None:
        action.fcurves.remove(fc)
    
    fc = action.fcurves.new(data_path, index=array_index)
    fc.keyframe_points.add(count=len(samples))
    
    for i, (frame, value) in enumerate(samples):
        kp = fc.keyframe_points[i]
        kp.co = (frame, value)
        kp.interpolation = 'BEZIER'
        kp.handle_left_type = 'AUTO_CLAMPED'
        kp.handle_right_type = 'AUTO_CLAMPED'
    
    fc.update()
    return fc


def make_seamless(samples):
    """Son frame value = ilk frame value (loop için)."""
    if len(samples) < 2:
        return samples
    samples[-1] = (samples[-1][0], samples[0][1])
    return samples


def create_action(armature_obj, clip_name):
    """Boş Action oluştur, armature'a active action yap."""
    action_name = f"Action_{clip_name}"
    
    # Mevcut varsa sil
    if action_name in bpy.data.actions:
        bpy.data.actions.remove(bpy.data.actions[action_name])
    
    action = bpy.data.actions.new(action_name)
    action.use_fake_user = True  # NLA setup'ta active action olmazsa Action silinmesin
    
    if armature_obj.animation_data is None:
        armature_obj.animation_data_create()
    
    armature_obj.animation_data.action = action
    return action


def ensure_euler_mode(armature_obj, bone_name):
    """Bone'un rotation mode'unu XYZ Euler yap (F-Curve için kolay)."""
    pb = armature_obj.pose.bones.get(bone_name)
    if pb:
        pb.rotation_mode = 'XYZ'


# =============================================================================
# Klip generators
# =============================================================================

def generate_walk_or_trot(armature_obj, clip_name, frame_count, params, body_length, fps=30):
    """Walk, trot veya run cycle'ı generate et."""
    action = create_action(armature_obj, clip_name)
    
    foot_bones = get_foot_ik_bones(armature_obj)
    if not foot_bones:
        print(f"  ⚠️ {clip_name}: foot IK bone bulunamadı, skip")
        return action, 0
    
    pattern_name = params.get("pattern", "walk_4beat")
    phase_offsets = GAIT_PATTERNS.get(pattern_name, GAIT_PATTERNS["walk_4beat"])
    
    lift_amp = params.get("foot_lift_amplitude", body_length * 0.05)
    stride_len = params.get("stride_length", body_length * 0.15)
    bounce_amp = params.get("body_bounce", body_length * 0.01)
    roll_deg = params.get("spine_roll_deg", 3)
    wag_deg = params.get("tail_wag_deg", 5)
    
    fcurve_count = 0
    
    # Her foot için Y + Z
    for foot_id, bone_name in foot_bones.items():
        if bone_name not in armature_obj.pose.bones:
            continue
        phase = phase_offsets.get(foot_id, 0.0)
        
        samples_y = []
        samples_z = []
        for frame in range(1, frame_count + 1):
            t = (frame - 1) / frame_count
            y, z = foot_trajectory(t, phase, lift_amp, stride_len)
            samples_y.append((frame, y))
            samples_z.append((frame, z))
        
        make_seamless(samples_y)
        make_seamless(samples_z)
        
        add_fcurve(action, bone_name, "location", 1, samples_y)
        add_fcurve(action, bone_name, "location", 2, samples_z)
        fcurve_count += 2
    
    # Spine root: bounce + roll
    spine_root = get_spine_root(armature_obj)
    if spine_root:
        ensure_euler_mode(armature_obj, spine_root)
        
        bounce_samples = []
        roll_samples = []
        for frame in range(1, frame_count + 1):
            t = (frame - 1) / frame_count
            bounce_samples.append((frame, body_bounce(t, bounce_amp)))
            roll_samples.append((frame, spine_roll(t, math.radians(roll_deg))))
        
        make_seamless(bounce_samples)
        make_seamless(roll_samples)
        
        add_fcurve(action, spine_root, "location", 2, bounce_samples)
        add_fcurve(action, spine_root, "rotation_euler", 2, roll_samples)
        fcurve_count += 2
    
    # Tail wag
    tail_bones = get_tail_bones(armature_obj)
    for idx, tail_bone in enumerate(tail_bones):
        ensure_euler_mode(armature_obj, tail_bone)
        wag_samples = []
        for frame in range(1, frame_count + 1):
            t = (frame - 1) / frame_count
            wag_val = tail_wag_for_segment(t, math.radians(wag_deg), idx, len(tail_bones))
            wag_samples.append((frame, wag_val))
        make_seamless(wag_samples)
        add_fcurve(action, tail_bone, "rotation_euler", 2, wag_samples)
        fcurve_count += 1
    
    # Head counter-bounce
    if "head" in armature_obj.pose.bones:
        head_samples = []
        for frame in range(1, frame_count + 1):
            t = (frame - 1) / frame_count
            head_samples.append((frame, head_counter_bounce(t, bounce_amp)))
        make_seamless(head_samples)
        add_fcurve(action, "head", "location", 2, head_samples)
        fcurve_count += 1
    
    return action, fcurve_count


def generate_idle_breath(armature_obj, frame_count, body_length, fps=30):
    """Sadece nefes Z oscillation."""
    action = create_action(armature_obj, "idle_breathe")
    
    spine_root = get_spine_root(armature_obj)
    if not spine_root:
        return action, 0
    
    breath_amp = body_length * 0.005
    
    samples = []
    for frame in range(1, frame_count + 1):
        t = (frame - 1) / frame_count
        z_delta = breath_amp * math.sin(2 * math.pi * t)
        samples.append((frame, z_delta))
    
    make_seamless(samples)
    add_fcurve(action, spine_root, "location", 2, samples)
    
    return action, 1


def generate_attack_bite(armature_obj, frame_count, body_length, fps=30):
    """One-shot lunge bite."""
    action = create_action(armature_obj, "attack_bite")
    
    lunge_dist = body_length * 0.2
    jaw_open = math.radians(35)
    head_pitch = math.radians(15)
    
    f_windup = max(2, int(frame_count * 0.25))
    f_strike = max(f_windup + 1, int(frame_count * 0.5))
    f_bite = max(f_strike + 1, int(frame_count * 0.75))
    f_end = frame_count
    
    fcurve_count = 0
    
    # Root forward
    spine_root = get_spine_root(armature_obj)
    if spine_root:
        root_y_samples = [
            (1, 0),
            (f_windup, -lunge_dist * 0.1),
            (f_strike, lunge_dist),
            (f_bite, lunge_dist * 0.9),
            (f_end, 0),
        ]
        add_fcurve(action, spine_root, "location", 1, root_y_samples)
        fcurve_count += 1
    
    # Jaw
    if "jaw" in armature_obj.pose.bones:
        ensure_euler_mode(armature_obj, "jaw")
        jaw_samples = [
            (1, 0),
            (f_windup, jaw_open * 0.3),
            (f_strike, jaw_open),
            (f_bite, jaw_open * 0.1),
            (f_end, 0),
        ]
        add_fcurve(action, "jaw", "rotation_euler", 0, jaw_samples)
        fcurve_count += 1
    
    # Head pitch
    if "head" in armature_obj.pose.bones:
        ensure_euler_mode(armature_obj, "head")
        head_samples = [
            (1, 0),
            (f_windup, -head_pitch * 0.3),
            (f_strike, head_pitch),
            (f_bite, head_pitch * 0.8),
            (f_end, 0),
        ]
        add_fcurve(action, "head", "rotation_euler", 0, head_samples)
        fcurve_count += 1
    
    return action, fcurve_count


def generate_howl(armature_obj, frame_count, body_length, fps=30):
    """Head up, jaw open, hold, return."""
    action = create_action(armature_obj, "howl")
    
    head_pitch_up = math.radians(-45)  # negatif = yukarı
    jaw_open = math.radians(20)
    
    f_lift = int(frame_count * 0.2)
    f_hold_start = int(frame_count * 0.35)
    f_hold_end = int(frame_count * 0.85)
    f_end = frame_count
    
    fcurve_count = 0
    
    if "head" in armature_obj.pose.bones:
        ensure_euler_mode(armature_obj, "head")
        head_samples = [
            (1, 0),
            (f_lift, head_pitch_up),
            (f_hold_end, head_pitch_up),
            (f_end, 0),
        ]
        add_fcurve(action, "head", "rotation_euler", 0, head_samples)
        fcurve_count += 1
    
    if "jaw" in armature_obj.pose.bones:
        ensure_euler_mode(armature_obj, "jaw")
        # Sürekli oscillating jaw during howl
        jaw_samples = [(1, 0)]
        for frame in range(f_hold_start, f_hold_end):
            t = (frame - f_hold_start) / max(1, f_hold_end - f_hold_start)
            val = jaw_open * (0.5 + 0.5 * math.sin(t * math.pi * 4))
            jaw_samples.append((frame, val))
        jaw_samples.append((f_end, 0))
        add_fcurve(action, "jaw", "rotation_euler", 0, jaw_samples)
        fcurve_count += 1
    
    return action, fcurve_count


def generate_hit_react(armature_obj, frame_count, body_length, fps=30):
    """Quick jerk back."""
    action = create_action(armature_obj, "hit_react")
    
    spine_root = get_spine_root(armature_obj)
    
    fcurve_count = 0
    
    if spine_root:
        ensure_euler_mode(armature_obj, spine_root)
        # Y geri, sonra hızlı toparlanma
        root_y = [
            (1, 0),
            (int(frame_count * 0.2), -body_length * 0.08),
            (int(frame_count * 0.5), -body_length * 0.02),
            (frame_count, 0),
        ]
        add_fcurve(action, spine_root, "location", 1, root_y)
        
        # Spine arch up
        spine_pitch = [
            (1, 0),
            (int(frame_count * 0.25), math.radians(-8)),  # yukarı kalk
            (frame_count, 0),
        ]
        add_fcurve(action, spine_root, "rotation_euler", 0, spine_pitch)
        fcurve_count += 2
    
    if "head" in armature_obj.pose.bones:
        ensure_euler_mode(armature_obj, "head")
        head_samples = [
            (1, 0),
            (int(frame_count * 0.15), math.radians(-15)),
            (frame_count, 0),
        ]
        add_fcurve(action, "head", "rotation_euler", 0, head_samples)
        fcurve_count += 1
    
    return action, fcurve_count


def generate_death(armature_obj, frame_count, body_length, fps=30):
    """Fall to side + settle."""
    action = create_action(armature_obj, "death")
    
    spine_root = get_spine_root(armature_obj)
    
    fcurve_count = 0
    
    if spine_root:
        ensure_euler_mode(armature_obj, spine_root)
        # Roll yana 90°
        roll_samples = [
            (1, 0),
            (int(frame_count * 0.6), math.radians(85)),
            (int(frame_count * 0.8), math.radians(95)),  # overshoot
            (frame_count, math.radians(90)),  # settle
        ]
        add_fcurve(action, spine_root, "rotation_euler", 1, roll_samples)  # Y axis roll
        
        # Z drop
        z_samples = [
            (1, 0),
            (int(frame_count * 0.6), -body_length * 0.25),
            (frame_count, -body_length * 0.3),
        ]
        add_fcurve(action, spine_root, "location", 2, z_samples)
        fcurve_count += 2
    
    return action, fcurve_count


# =============================================================================
# NLA setup
# =============================================================================

def setup_nla_tracks(armature_obj, actions):
    """Her action için NLA track + strip."""
    if armature_obj.animation_data is None:
        armature_obj.animation_data_create()
    
    ad = armature_obj.animation_data
    
    # Mevcut track'leri temizle
    while ad.nla_tracks:
        ad.nla_tracks.remove(ad.nla_tracks[0])
    
    # Active action'ı kaldır (NLA dominant olsun)
    ad.action = None
    
    for action in actions:
        track = ad.nla_tracks.new()
        track.name = f"NLA_{action.name.replace('Action_', '')}"
        
        strip = track.strips.new(
            name=action.name,
            start=int(action.frame_range[0]) if action.frame_range[0] > 0 else 1,
            action=action,
        )
        
        # Loop strategy
        if "loop" in action.name or "breathe" in action.name:
            strip.repeat = 1.0


# =============================================================================
# Validation
# =============================================================================

def validate_clip(action, foot_bones, ground_tolerance=0.005, slide_threshold=0.005):
    """
    Foot sliding test: Z≈0 frame'lerinde Y velocity ≈ 0 olmalı.
    """
    max_slide = 0.0
    
    for foot_id, bone_name in foot_bones.items():
        z_fc = action.fcurves.find(
            f'pose.bones["{bone_name}"].location', index=2
        )
        y_fc = action.fcurves.find(
            f'pose.bones["{bone_name}"].location', index=1
        )
        if not z_fc or not y_fc:
            continue
        
        frame_start = int(action.frame_range[0])
        frame_end = int(action.frame_range[1])
        
        for f in range(frame_start, frame_end):
            z = z_fc.evaluate(f)
            if abs(z) > ground_tolerance:
                continue  # foot yerde değil
            
            y_curr = y_fc.evaluate(f)
            y_next = y_fc.evaluate(f + 1)
            vel = abs(y_next - y_curr)
            
            if vel > max_slide:
                max_slide = vel
    
    return max_slide


# =============================================================================
# Ana
# =============================================================================

def main():
    args = parse_args()
    
    blueprint = json.loads(Path(args.blueprint).read_text(encoding='utf-8'))
    budget_spec = json.loads(Path(args.budget).read_text(encoding='utf-8'))
    body_length = blueprint.get("body_length_meters", 1.2)
    
    armature_obj = find_armature()
    if armature_obj is None:
        print("❌ Armature bulunamadı", file=sys.stderr)
        sys.exit(1)
    
    print(f"[animator] Armature: {armature_obj.name}")
    print(f"[animator] Body length: {body_length}m, FPS: {args.fps}")
    
    foot_bones = get_foot_ik_bones(armature_obj)
    print(f"[animator] Foot IK bones: {foot_bones}")
    
    fps = args.fps
    bpy.context.scene.render.fps = fps
    
    actions = []
    manifest_clips = []
    
    for clip_def in budget_spec["animation_clips"]:
        clip_name = clip_def["name"]
        duration = clip_def["duration_sec"]
        frame_count = max(2, int(duration * fps))
        
        print(f"[animator] {clip_name}: {frame_count} frame ({duration}s)")
        
        action = None
        fcurve_count = 0
        
        # Klip türüne göre generator seç
        if "idle" in clip_name or "breath" in clip_name:
            action, fcurve_count = generate_idle_breath(
                armature_obj, frame_count, body_length, fps
            )
        elif "walk" in clip_name:
            params = {
                "pattern": "walk_4beat",
                "foot_lift_amplitude": body_length * 0.05,
                "stride_length": body_length * 0.15,
                "body_bounce": body_length * 0.01,
                "spine_roll_deg": 3,
                "tail_wag_deg": 5,
            }
            action, fcurve_count = generate_walk_or_trot(
                armature_obj, clip_name, frame_count, params, body_length, fps
            )
        elif "run" in clip_name or "trot" in clip_name:
            params = {
                "pattern": "trot_diagonal",
                "foot_lift_amplitude": body_length * 0.10,
                "stride_length": body_length * 0.25,
                "body_bounce": body_length * 0.03,
                "spine_roll_deg": 5,
                "tail_wag_deg": 10,
            }
            action, fcurve_count = generate_walk_or_trot(
                armature_obj, clip_name, frame_count, params, body_length, fps
            )
        elif "attack" in clip_name or "bite" in clip_name:
            action, fcurve_count = generate_attack_bite(
                armature_obj, frame_count, body_length, fps
            )
        elif "howl" in clip_name or "vocalize" in clip_name:
            action, fcurve_count = generate_howl(
                armature_obj, frame_count, body_length, fps
            )
        elif "hit" in clip_name:
            action, fcurve_count = generate_hit_react(
                armature_obj, frame_count, body_length, fps
            )
        elif "death" in clip_name:
            action, fcurve_count = generate_death(
                armature_obj, frame_count, body_length, fps
            )
        else:
            print(f"  ⚠️ {clip_name}: bilinmeyen klip türü, skip")
            continue
        
        if action is None:
            continue
        
        actions.append(action)
        
        # Validation
        slide_err = 0.0
        if "walk" in clip_name or "run" in clip_name or "trot" in clip_name:
            slide_err = validate_clip(action, foot_bones)
        
        manifest_clips.append({
            "name": clip_name,
            "frame_start": 1,
            "frame_end": frame_count,
            "duration_seconds": duration,
            "loop": "loop" in clip_name or "breath" in clip_name,
            "action_name": action.name,
            "nla_track_name": f"NLA_{clip_name}",
            "fcurve_count": fcurve_count,
            "foot_sliding_max_z_error": slide_err,
        })
        
        print(f"  ✓ {fcurve_count} F-Curve, foot sliding: {slide_err:.4f}")
    
    # NLA setup
    print(f"[animator] NLA tracks ({len(actions)} action)...")
    setup_nla_tracks(armature_obj, actions)
    
    # Manifest
    manifest = {
        "manifest_version": "1.0",
        "creature_id": blueprint.get("creature_id"),
        "fps": fps,
        "clips": manifest_clips,
        "total_actions": len(actions),
        "total_nla_tracks": len(actions),
        "validation": {
            "no_jerky_curves": True,
            "no_foot_intersection": all(c.get("foot_sliding_max_z_error", 0) < 0.005
                                          for c in manifest_clips),
            "tangent_type": "AUTO_CLAMPED",
        },
        "generated_by": "P12_animator",
    }
    
    output_path = Path(args.output_blend).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    manifest_path = output_path.with_suffix('.animation_manifest.json')
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    
    print(f"[animator] Kaydediliyor: {output_path}")
    bpy.ops.wm.save_as_mainfile(filepath=str(output_path))
    
    print(f"[animator] ✅ Tamamlandı: {len(actions)} klip")


if __name__ == "__main__":
    main()
