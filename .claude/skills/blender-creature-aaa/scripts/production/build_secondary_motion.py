#!/usr/bin/env python3
"""
build_secondary_motion.py — P10 Secondary Motion Designer

Mevcut animation clip'lerinin üzerine gecikmeli ikincil hareket ekler.
"""

import bpy
import json
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
    p.add_argument("--anim-manifest", required=True)
    p.add_argument("--output-blend", required=True)
    p.add_argument("--tail-lag-base", type=int, default=1)
    p.add_argument("--tail-lag-increment", type=int, default=1)
    return p.parse_args(argv)


def find_armature():
    for obj in bpy.data.objects:
        if obj.type == 'ARMATURE':
            return obj
    return None


def get_tail_bones(armature_obj):
    return sorted([b.name for b in armature_obj.pose.bones
                   if b.name.startswith("tail_")])


def get_ear_bones(armature_obj):
    return sorted([b.name for b in armature_obj.pose.bones
                   if "ear" in b.name.lower()])


def find_action(name):
    """Action'ı bul."""
    return bpy.data.actions.get(name)


def time_offset_fcurve(action, source_bone, target_bone, channel, array_index,
                        lag_frames, amplitude_mult=1.0):
    """Source bone'un F-Curve'üne lag uygulayıp target'a yaz."""
    src_path = f'pose.bones["{source_bone}"].{channel}'
    src_fc = action.fcurves.find(src_path, index=array_index)
    if src_fc is None:
        return False
    
    tgt_path = f'pose.bones["{target_bone}"].{channel}'
    tgt_fc = action.fcurves.find(tgt_path, index=array_index)
    if tgt_fc is not None:
        # Mevcut F-Curve'ü sil
        action.fcurves.remove(tgt_fc)
    
    tgt_fc = action.fcurves.new(tgt_path, index=array_index)
    
    frame_start = int(action.frame_range[0])
    frame_end = int(action.frame_range[1])
    frame_count = max(1, frame_end - frame_start + 1)
    
    samples = []
    for frame in range(frame_start, frame_end + 1):
        src_frame = ((frame - lag_frames - frame_start) % frame_count) + frame_start
        value = src_fc.evaluate(src_frame) * amplitude_mult
        samples.append((frame, value))
    
    # Loop seamless
    if samples and len(samples) > 1:
        samples[-1] = (samples[-1][0], samples[0][1])
    
    tgt_fc.keyframe_points.add(count=len(samples))
    for i, (f, v) in enumerate(samples):
        kp = tgt_fc.keyframe_points[i]
        kp.co = (f, v)
        kp.interpolation = 'BEZIER'
        kp.handle_left_type = 'AUTO_CLAMPED'
        kp.handle_right_type = 'AUTO_CLAMPED'
    
    tgt_fc.update()
    return True


def enhance_tail_for_action(action, tail_bones, base_lag, lag_increment):
    """Tek bir action için tail overshoot."""
    affected = []
    sorted_tail = sorted(tail_bones)
    
    if len(sorted_tail) < 2:
        return affected
    
    for i, tail_bone in enumerate(sorted_tail):
        if i == 0:
            continue
        
        lag = base_lag + i * lag_increment
        amp = max(0.6, 1.0 + i * 0.04)
        
        prev_tail = sorted_tail[i - 1]
        
        # Z rotation (kuyruk wag)
        ok = time_offset_fcurve(action, prev_tail, tail_bone,
                                "rotation_euler", 2, lag, amp)
        if ok:
            affected.append(tail_bone)
    
    return affected


def enhance_ear_for_action(action, ear_bones, head_bone="head"):
    """
    Ears head rotation'ı küçük lag ile takip etsin.
    """
    if not ear_bones:
        return []
    
    affected = []
    for ear in ear_bones:
        # Head'in X rotation (pitch) lag ile ear'a
        ok = time_offset_fcurve(action, head_bone, ear,
                                "rotation_euler", 0, lag_frames=3,
                                amplitude_mult=0.3)  # ear daha az pitch
        if ok:
            affected.append(ear)
    
    return affected


def main():
    args = parse_args()
    
    anim_manifest = json.loads(Path(args.anim_manifest).read_text(encoding='utf-8'))
    
    armature_obj = find_armature()
    if armature_obj is None:
        print("❌ Armature yok", file=sys.stderr)
        sys.exit(1)
    
    tail_bones = get_tail_bones(armature_obj)
    ear_bones = get_ear_bones(armature_obj)
    
    print(f"[secondary] Tail bones: {len(tail_bones)}")
    print(f"[secondary] Ear bones: {len(ear_bones)}")
    
    # Sadece loop ve idle klipler için
    target_clips = [c["name"] for c in anim_manifest["clips"]
                    if c.get("loop", False) or "idle" in c["name"] or "breath" in c["name"]]
    
    print(f"[secondary] Etkilenecek klipler: {target_clips}")
    
    enhancements = []
    affected_clips = []
    
    for clip_name in target_clips:
        action_name = f"Action_{clip_name}"
        action = find_action(action_name)
        if action is None:
            print(f"  ⚠️ Action {action_name} yok, skip")
            continue
        
        # Tail
        if tail_bones:
            tail_affected = enhance_tail_for_action(
                action, tail_bones, args.tail_lag_base, args.tail_lag_increment
            )
            if tail_affected:
                print(f"  ✓ {clip_name}: tail lag → {len(tail_affected)} bone")
                if not affected_clips or affected_clips[-1] != clip_name:
                    affected_clips.append(clip_name)
        
        # Ears
        if ear_bones:
            ear_affected = enhance_ear_for_action(action, ear_bones)
            if ear_affected:
                print(f"  ✓ {clip_name}: ear lag → {len(ear_affected)} bone")
                if not affected_clips or affected_clips[-1] != clip_name:
                    affected_clips.append(clip_name)
    
    if tail_bones:
        enhancements.append({
            "type": "tail_overshoot",
            "affected_bones": tail_bones,
            "lag_frames_base": args.tail_lag_base,
            "lag_increment_per_segment": args.tail_lag_increment,
        })
    else:
        enhancements.append({
            "type": "tail_overshoot",
            "skipped_reason": "Bu yaratıkta tail bone yok",
        })
    
    if ear_bones:
        enhancements.append({
            "type": "ear_lag",
            "affected_bones": ear_bones,
            "lag_frames": 3,
        })
    else:
        enhancements.append({
            "type": "ear_lag",
            "skipped_reason": "Bu yaratıkta ear bone yok",
        })
    
    # Manifest
    manifest = {
        "manifest_version": "1.0",
        "secondary_motion_added_to_clips": affected_clips,
        "enhancements": enhancements,
        "method": "fcurve_post_process",
        "generated_by": "P10_secondary_motion_designer",
    }
    
    output_path = Path(args.output_blend).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    manifest_path = output_path.with_suffix('.secondary_motion_manifest.json')
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    
    print(f"[secondary] Kaydediliyor: {output_path}")
    bpy.ops.wm.save_as_mainfile(filepath=str(output_path))
    
    print(f"[secondary] ✅ Tamamlandı: {len(affected_clips)} klip enhance edildi")


if __name__ == "__main__":
    main()
