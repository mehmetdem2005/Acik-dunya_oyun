from __future__ import annotations

from dataclasses import dataclass

import bpy
from mathutils import Vector

from .config import BONE_POINTS, SKELETON_NAME


@dataclass(frozen=True)
class BoneSpec:
    name: str
    head: tuple[float, float, float]
    tail: tuple[float, float, float]
    parent: str | None = None
    connected: bool = False
    deform: bool = True


def build_armature(collection: bpy.types.Collection, root_object: bpy.types.Object) -> bpy.types.Object:
    armature_data = bpy.data.armatures.new(f"{SKELETON_NAME}_Data")
    armature = bpy.data.objects.new(SKELETON_NAME, armature_data)
    collection.objects.link(armature)
    armature.parent = root_object
    armature.show_in_front = True
    armature.display_type = "WIRE"
    armature["asset_role"] = "deformation_skeleton"
    armature["forward_axis"] = "-Y"
    armature["up_axis"] = "+Z"

    bpy.context.view_layer.objects.active = armature
    armature.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")

    specs = _bone_specs()
    created: dict[str, bpy.types.EditBone] = {}
    for spec in specs:
        bone = armature_data.edit_bones.new(spec.name)
        bone.head = spec.head
        bone.tail = spec.tail
        bone.use_deform = spec.deform
        bone.roll = 0.0
        created[spec.name] = bone

    for spec in specs:
        if spec.parent:
            created[spec.name].parent = created[spec.parent]
            created[spec.name].use_connect = spec.connected

    bpy.ops.object.mode_set(mode="POSE")
    for pose_bone in armature.pose.bones:
        pose_bone.rotation_mode = "XYZ"
        pose_bone.lock_scale = (True, True, True)
    bpy.ops.object.mode_set(mode="OBJECT")
    armature.select_set(False)
    return armature


def _bone_specs() -> list[BoneSpec]:
    specs: list[BoneSpec] = []
    parent_map = {
        "Root": None,
        "Pelvis": "Root",
        "Spine_01": "Pelvis",
        "Spine_02": "Spine_01",
        "Chest": "Spine_02",
        "Neck_01": "Chest",
        "Neck_02": "Neck_01",
        "Neck_03": "Neck_02",
        "Neck_04": "Neck_03",
        "Neck_05": "Neck_04",
        "Neck_06": "Neck_05",
        "Head": "Neck_06",
        "Jaw": "Head",
        "Tail_01": "Pelvis",
        "Tail_02": "Tail_01",
        "Tail_03": "Tail_02",
        "Tail_04": "Tail_03",
        "Tail_05": "Tail_04",
        "Tail_06": "Tail_05",
        "Tail_07": "Tail_06",
        "Tail_08": "Tail_07",
        "Tail_09": "Tail_08",
        "Tail_10": "Tail_09",
    }
    for name, (head, tail) in BONE_POINTS.items():
        specs.append(BoneSpec(name, head, tail, parent_map[name], connected=False, deform=True))

    for side, sign in (("L", 1.0), ("R", -1.0)):
        specs.extend(_leg_specs(side, sign))
        specs.extend(_wing_specs(side, sign))
        specs.extend(_face_specs(side, sign))

    specs.extend([
        BoneSpec("Tongue_01", (0.0, -3.84, 6.31), (0.0, -4.15, 6.20), "Jaw"),
        BoneSpec("Tongue_02", (0.0, -4.15, 6.20), (0.0, -4.43, 6.15), "Tongue_01", connected=True),
    ])
    return specs


def _leg_specs(side: str, sign: float) -> list[BoneSpec]:
    x_front = 0.88 * sign
    x_rear = 0.95 * sign
    return [
        BoneSpec(f"FrontLeg_{side}_Scapula", (0.45 * sign, -1.23, 3.85), (x_front, -1.52, 3.35), "Chest"),
        BoneSpec(f"FrontLeg_{side}_Upper", (x_front, -1.52, 3.35), (1.03 * sign, -1.70, 2.35), f"FrontLeg_{side}_Scapula", True),
        BoneSpec(f"FrontLeg_{side}_Fore", (1.03 * sign, -1.70, 2.35), (0.90 * sign, -1.91, 1.12), f"FrontLeg_{side}_Upper", True),
        BoneSpec(f"FrontLeg_{side}_Wrist", (0.90 * sign, -1.91, 1.12), (0.92 * sign, -2.05, 0.36), f"FrontLeg_{side}_Fore", True),
        BoneSpec(f"FrontLeg_{side}_Foot", (0.92 * sign, -2.05, 0.36), (0.92 * sign, -2.68, 0.14), f"FrontLeg_{side}_Wrist", True),
        BoneSpec(f"RearLeg_{side}_Hip", (0.52 * sign, 0.83, 3.02), (x_rear, 1.18, 2.54), "Pelvis"),
        BoneSpec(f"RearLeg_{side}_Upper", (x_rear, 1.18, 2.54), (1.38 * sign, 0.87, 1.73), f"RearLeg_{side}_Hip", True),
        BoneSpec(f"RearLeg_{side}_Lower", (1.38 * sign, 0.87, 1.73), (1.08 * sign, 1.45, 0.66), f"RearLeg_{side}_Upper", True),
        BoneSpec(f"RearLeg_{side}_Ankle", (1.08 * sign, 1.45, 0.66), (1.00 * sign, 1.23, 0.24), f"RearLeg_{side}_Lower", True),
        BoneSpec(f"RearLeg_{side}_Foot", (1.00 * sign, 1.23, 0.24), (1.00 * sign, 0.53, 0.12), f"RearLeg_{side}_Ankle", True),
    ]


def _wing_specs(side: str, sign: float) -> list[BoneSpec]:
    root = (0.67 * sign, -1.10, 4.18)
    upper_end = (2.95 * sign, -0.48, 5.55)
    fore_end = (5.15 * sign, -0.15, 6.15)
    wrist_end = (6.20 * sign, -0.02, 6.32)
    return [
        BoneSpec(f"Wing_{side}_Root", root, (1.18 * sign, -0.93, 4.62), "Chest"),
        BoneSpec(f"Wing_{side}_Upper", (1.18 * sign, -0.93, 4.62), upper_end, f"Wing_{side}_Root", True),
        BoneSpec(f"Wing_{side}_Forearm", upper_end, fore_end, f"Wing_{side}_Upper", True),
        BoneSpec(f"Wing_{side}_Wrist", fore_end, wrist_end, f"Wing_{side}_Forearm", True),
        BoneSpec(f"Wing_{side}_Digit_01", wrist_end, (8.45 * sign, -0.25, 7.35), f"Wing_{side}_Wrist", True),
        BoneSpec(f"Wing_{side}_Digit_02", wrist_end, (7.78 * sign, 0.70, 5.73), f"Wing_{side}_Wrist", False),
        BoneSpec(f"Wing_{side}_Digit_03", wrist_end, (6.47 * sign, 1.60, 4.20), f"Wing_{side}_Wrist", False),
        BoneSpec(f"Wing_{side}_Membrane", (1.05 * sign, -0.74, 4.28), (1.12 * sign, 1.22, 3.25), "Chest"),
    ]


def _face_specs(side: str, sign: float) -> list[BoneSpec]:
    return [
        BoneSpec(f"Eye_{side}", (0.29 * sign, -4.03, 6.78), (0.29 * sign, -4.24, 6.78), "Head"),
        BoneSpec(f"Eyelid_Upper_{side}", (0.29 * sign, -4.03, 6.84), (0.29 * sign, -4.20, 6.84), "Head"),
        BoneSpec(f"Eyelid_Lower_{side}", (0.29 * sign, -4.03, 6.72), (0.29 * sign, -4.20, 6.72), "Head"),
    ]


def bone_midpoint(name: str) -> Vector:
    if name in BONE_POINTS:
        head, tail = BONE_POINTS[name]
        return (Vector(head) + Vector(tail)) * 0.5
    raise KeyError(name)
