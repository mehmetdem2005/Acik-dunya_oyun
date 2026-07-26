from __future__ import annotations

import math

import bpy

from .config import REQUIRED_ACTIONS


PoseState = dict[str, tuple[float, float, float]]
ObjectState = tuple[tuple[float, float, float], tuple[float, float, float]]


def build_all_actions(armature: bpy.types.Object) -> dict[str, bpy.types.Action]:
    actions: dict[str, bpy.types.Action] = {}

    actions["Idle_Ground"] = _bake_action(
        armature,
        "Idle_Ground",
        120,
        {
            1: {"Chest": (0.0, 0.0, 0.0), "Neck_03": (0.0, 0.0, 0.0), "Tail_05": (0.0, 0.0, -2.0)},
            30: {"Chest": (1.4, 0.0, 0.0), "Neck_03": (-0.8, 0.0, 0.0), "Tail_05": (0.0, 0.0, 1.5)},
            60: {"Chest": (0.0, 0.0, 0.0), "Neck_03": (0.5, 0.0, 0.0), "Tail_05": (0.0, 0.0, 3.0)},
            90: {"Chest": (1.2, 0.0, 0.0), "Neck_03": (-0.5, 0.0, 0.0), "Tail_05": (0.0, 0.0, -1.0)},
            120: {"Chest": (0.0, 0.0, 0.0), "Neck_03": (0.0, 0.0, 0.0), "Tail_05": (0.0, 0.0, -2.0)},
        },
    )

    actions["Idle_Alert"] = _bake_action(
        armature,
        "Idle_Alert",
        72,
        {
            1: _merge(_wing_pose(-12.0, 8.0), {"Neck_04": (-5.0, 0.0, 0.0), "Head": (3.0, 0.0, 0.0)}),
            18: _merge(_wing_pose(-8.0, 5.0), {"Neck_05": (-2.0, 0.0, 4.0), "Head": (0.0, 0.0, -5.0)}),
            36: _merge(_wing_pose(-12.0, 8.0), {"Neck_05": (-2.0, 0.0, -4.0), "Head": (1.5, 0.0, 5.0)}),
            54: _merge(_wing_pose(-9.0, 6.0), {"Neck_04": (-4.0, 0.0, 0.0), "Head": (2.0, 0.0, 0.0)}),
            72: _merge(_wing_pose(-12.0, 8.0), {"Neck_04": (-5.0, 0.0, 0.0), "Head": (3.0, 0.0, 0.0)}),
        },
    )

    actions["Walk"] = _gait_action(armature, "Walk", 48, run=False)
    actions["Run"] = _gait_action(armature, "Run", 32, run=True)

    actions["Turn_Left_90"] = _bake_action(
        armature,
        "Turn_Left_90",
        42,
        {
            1: {"Pelvis": (0.0, 0.0, 0.0), "Neck_04": (0.0, 0.0, 0.0)},
            14: {"Pelvis": (0.0, 0.0, 8.0), "Neck_04": (0.0, 0.0, -10.0), "Tail_03": (0.0, 0.0, -12.0)},
            28: {"Pelvis": (0.0, 0.0, 4.0), "Neck_04": (0.0, 0.0, -5.0), "Tail_03": (0.0, 0.0, -6.0)},
            42: {"Pelvis": (0.0, 0.0, 0.0), "Neck_04": (0.0, 0.0, 0.0), "Tail_03": (0.0, 0.0, 0.0)},
        },
        object_states={1: ((0, 0, 0), (0, 0, 0)), 42: ((0, 0, 0), (0, 0, 90))},
    )
    actions["Turn_Right_90"] = _bake_action(
        armature,
        "Turn_Right_90",
        42,
        {
            1: {"Pelvis": (0.0, 0.0, 0.0), "Neck_04": (0.0, 0.0, 0.0)},
            14: {"Pelvis": (0.0, 0.0, -8.0), "Neck_04": (0.0, 0.0, 10.0), "Tail_03": (0.0, 0.0, 12.0)},
            28: {"Pelvis": (0.0, 0.0, -4.0), "Neck_04": (0.0, 0.0, 5.0), "Tail_03": (0.0, 0.0, 6.0)},
            42: {"Pelvis": (0.0, 0.0, 0.0), "Neck_04": (0.0, 0.0, 0.0), "Tail_03": (0.0, 0.0, 0.0)},
        },
        object_states={1: ((0, 0, 0), (0, 0, 0)), 42: ((0, 0, 0), (0, 0, -90))},
    )

    actions["Takeoff"] = _bake_action(
        armature,
        "Takeoff",
        64,
        {
            1: _merge(_wing_pose(-46.0, 32.0), {"Pelvis": (8.0, 0.0, 0.0), "Neck_03": (-6.0, 0.0, 0.0)}),
            16: _merge(_wing_pose(26.0, -10.0), {"Pelvis": (-10.0, 0.0, 0.0), "Chest": (8.0, 0.0, 0.0)}),
            32: _merge(_wing_pose(-55.0, 38.0), {"Pelvis": (-5.0, 0.0, 0.0), "RearLeg_L_Upper": (22.0, 0.0, 0.0), "RearLeg_R_Upper": (22.0, 0.0, 0.0)}),
            48: _merge(_wing_pose(34.0, -16.0), {"FrontLeg_L_Upper": (34.0, 0.0, 0.0), "FrontLeg_R_Upper": (34.0, 0.0, 0.0)}),
            64: _merge(_wing_pose(-18.0, 12.0), {"Pelvis": (0.0, 0.0, 0.0), "Chest": (0.0, 0.0, 0.0)}),
        },
        object_states={
            1: ((0.0, 0.0, 0.0), (0, 0, 0)),
            32: ((0.0, -0.8, 0.75), (-7, 0, 0)),
            64: ((0.0, -2.2, 2.4), (-10, 0, 0)),
        },
    )

    actions["Flight_Forward"] = _flight_action(armature, "Flight_Forward", 48, hover=False)
    actions["Flight_Hover"] = _flight_action(armature, "Flight_Hover", 60, hover=True)
    actions["Flight_Glide"] = _bake_action(
        armature,
        "Flight_Glide",
        96,
        {
            1: _merge(_wing_pose(-8.0, 4.0), _flight_body_pose(-5.0)),
            32: _merge(_wing_pose(-5.0, 3.0), _flight_body_pose(-3.0), {"Tail_05": (0.0, 0.0, 4.0)}),
            64: _merge(_wing_pose(-10.0, 5.0), _flight_body_pose(-4.0), {"Tail_05": (0.0, 0.0, -4.0)}),
            96: _merge(_wing_pose(-8.0, 4.0), _flight_body_pose(-5.0)),
        },
    )

    actions["Landing"] = _bake_action(
        armature,
        "Landing",
        64,
        {
            1: _merge(_wing_pose(-12.0, 8.0), _flight_body_pose(-4.0)),
            20: _merge(_wing_pose(30.0, -12.0), {"RearLeg_L_Upper": (-28.0, 0.0, 0.0), "RearLeg_R_Upper": (-28.0, 0.0, 0.0)}),
            40: _merge(_wing_pose(-54.0, 36.0), {"FrontLeg_L_Upper": (-18.0, 0.0, 0.0), "FrontLeg_R_Upper": (-18.0, 0.0, 0.0)}),
            54: _merge(_wing_pose(18.0, -8.0), {"Pelvis": (8.0, 0.0, 0.0), "Chest": (-6.0, 0.0, 0.0)}),
            64: _merge(_wing_pose(-42.0, 28.0), {"Pelvis": (0.0, 0.0, 0.0)}),
        },
        object_states={
            1: ((0.0, -2.0, 2.2), (-8, 0, 0)),
            40: ((0.0, -0.8, 0.65), (-3, 0, 0)),
            64: ((0.0, 0.0, 0.0), (0, 0, 0)),
        },
    )

    actions["Wing_Fold"] = _bake_action(
        armature,
        "Wing_Fold",
        50,
        {1: _wing_pose(-5.0, 3.0), 25: _wing_pose(-35.0, 48.0), 50: _wing_pose(-58.0, 72.0)},
    )
    actions["Wing_Unfold"] = _bake_action(
        armature,
        "Wing_Unfold",
        50,
        {1: _wing_pose(-58.0, 72.0), 25: _wing_pose(-35.0, 48.0), 50: _wing_pose(-5.0, 3.0)},
    )

    actions["Roar"] = _bake_action(
        armature,
        "Roar",
        72,
        {
            1: {"Jaw": (0.0, 0.0, 0.0), "Neck_04": (0.0, 0.0, 0.0), "Head": (0.0, 0.0, 0.0)},
            18: {"Jaw": (27.0, 0.0, 0.0), "Neck_04": (-12.0, 0.0, 0.0), "Head": (9.0, 0.0, 0.0), "Chest": (4.0, 0.0, 0.0)},
            36: {"Jaw": (34.0, 0.0, 0.0), "Neck_04": (-16.0, 0.0, 0.0), "Head": (12.0, 0.0, 0.0), "Chest": (6.0, 0.0, 0.0)},
            54: {"Jaw": (25.0, 0.0, 0.0), "Neck_04": (-10.0, 0.0, 0.0), "Head": (7.0, 0.0, 0.0)},
            72: {"Jaw": (0.0, 0.0, 0.0), "Neck_04": (0.0, 0.0, 0.0), "Head": (0.0, 0.0, 0.0)},
        },
    )

    actions["Bite_Attack"] = _bake_action(
        armature,
        "Bite_Attack",
        34,
        {
            1: {"Jaw": (0.0, 0.0, 0.0), "Neck_03": (0.0, 0.0, 0.0)},
            8: {"Jaw": (24.0, 0.0, 0.0), "Neck_03": (9.0, 0.0, 0.0), "Head": (-5.0, 0.0, 0.0)},
            17: {"Jaw": (2.0, 0.0, 0.0), "Neck_03": (-18.0, 0.0, 0.0), "Head": (11.0, 0.0, 0.0)},
            25: {"Jaw": (10.0, 0.0, 0.0), "Neck_03": (-6.0, 0.0, 0.0)},
            34: {"Jaw": (0.0, 0.0, 0.0), "Neck_03": (0.0, 0.0, 0.0), "Head": (0.0, 0.0, 0.0)},
        },
    )

    actions["Claw_Attack_Left"] = _claw_action(armature, "Claw_Attack_Left", "L")
    actions["Claw_Attack_Right"] = _claw_action(armature, "Claw_Attack_Right", "R")

    actions["Tail_Attack"] = _bake_action(
        armature,
        "Tail_Attack",
        46,
        {
            1: _tail_curve(0.0),
            10: _tail_curve(-28.0),
            22: _tail_curve(52.0),
            34: _tail_curve(-18.0),
            46: _tail_curve(0.0),
        },
    )

    actions["Hit_Reaction"] = _bake_action(
        armature,
        "Hit_Reaction",
        30,
        {
            1: {"Chest": (0.0, 0.0, 0.0), "Neck_03": (0.0, 0.0, 0.0), "Head": (0.0, 0.0, 0.0)},
            8: {"Chest": (-10.0, 0.0, 12.0), "Neck_03": (13.0, 0.0, -18.0), "Head": (-9.0, 0.0, -12.0)},
            16: {"Chest": (5.0, 0.0, -5.0), "Neck_03": (-6.0, 0.0, 7.0)},
            30: {"Chest": (0.0, 0.0, 0.0), "Neck_03": (0.0, 0.0, 0.0), "Head": (0.0, 0.0, 0.0)},
        },
    )

    actions["Death"] = _bake_action(
        armature,
        "Death",
        110,
        {
            1: _merge(_wing_pose(-40.0, 30.0), {"Neck_04": (0.0, 0.0, 0.0), "Jaw": (0.0, 0.0, 0.0)}),
            28: _merge(_wing_pose(18.0, 12.0), {"Pelvis": (-12.0, 0.0, -10.0), "Neck_04": (18.0, 0.0, 14.0), "Jaw": (10.0, 0.0, 0.0)}),
            62: _merge(_wing_pose(34.0, 28.0), {"Pelvis": (-24.0, 0.0, -18.0), "Neck_04": (30.0, 0.0, 18.0), "Jaw": (16.0, 0.0, 0.0)}),
            110: _merge(_wing_pose(42.0, 35.0), {"Pelvis": (-35.0, 0.0, -26.0), "Neck_04": (38.0, 0.0, 20.0), "Head": (18.0, 0.0, 0.0), "Jaw": (18.0, 0.0, 0.0)}),
        },
        object_states={
            1: ((0.0, 0.0, 0.0), (0, 0, 0)),
            62: ((-0.3, 0.25, 0.0), (0, 28, 0)),
            110: ((-0.65, 0.55, -0.1), (0, 82, 0)),
        },
    )

    missing = set(REQUIRED_ACTIONS) - set(actions)
    if missing:
        raise RuntimeError(f"Animation build incomplete: {sorted(missing)}")

    armature.animation_data_create()
    armature.animation_data.action = actions["Idle_Ground"]
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = 120
    bpy.context.scene.frame_set(1)
    return actions


def _gait_action(armature: bpy.types.Object, name: str, frame_end: int, run: bool) -> bpy.types.Action:
    amplitude_front = 32.0 if run else 22.0
    amplitude_rear = 36.0 if run else 25.0
    knee = 28.0 if run else 17.0
    body_bob = 4.0 if run else 2.0
    frames = [1, frame_end // 4 + 1, frame_end // 2 + 1, frame_end * 3 // 4 + 1, frame_end + 1]
    states: dict[int, PoseState] = {}
    for phase_index, frame in enumerate(frames):
        phase = phase_index * math.pi / 2.0
        state: PoseState = {
            "Chest": (math.sin(phase * 2.0) * body_bob, 0.0, math.sin(phase) * 1.5),
            "Pelvis": (-math.sin(phase * 2.0) * body_bob * 0.7, 0.0, -math.sin(phase) * 1.0),
            "Neck_03": (-math.sin(phase * 2.0) * body_bob * 0.45, 0.0, 0.0),
            "Tail_03": (0.0, 0.0, math.sin(phase) * (10.0 if run else 6.0)),
        }
        for side, offset in (("L", 0.0), ("R", math.pi)):
            front_phase = phase + offset
            rear_phase = phase + offset + math.pi
            state[f"FrontLeg_{side}_Upper"] = (math.sin(front_phase) * amplitude_front, 0.0, 0.0)
            state[f"FrontLeg_{side}_Fore"] = (max(0.0, -math.sin(front_phase)) * knee, 0.0, 0.0)
            state[f"FrontLeg_{side}_Wrist"] = (-max(0.0, -math.sin(front_phase)) * knee * 0.45, 0.0, 0.0)
            state[f"RearLeg_{side}_Upper"] = (math.sin(rear_phase) * amplitude_rear, 0.0, 0.0)
            state[f"RearLeg_{side}_Lower"] = (max(0.0, -math.sin(rear_phase)) * knee, 0.0, 0.0)
            state[f"RearLeg_{side}_Ankle"] = (-max(0.0, -math.sin(rear_phase)) * knee * 0.55, 0.0, 0.0)
        states[frame] = state
    return _bake_action(armature, name, frame_end + 1, states)


def _flight_action(armature: bpy.types.Object, name: str, frame_end: int, hover: bool) -> bpy.types.Action:
    frames = [1, frame_end // 4 + 1, frame_end // 2 + 1, frame_end * 3 // 4 + 1, frame_end + 1]
    states: dict[int, PoseState] = {}
    object_states: dict[int, ObjectState] = {}
    for i, frame in enumerate(frames):
        phase = i * math.pi / 2.0
        upper = -12.0 + math.sin(phase) * (46.0 if hover else 38.0)
        fold = 8.0 - math.sin(phase) * (26.0 if hover else 20.0)
        state = _merge(
            _wing_pose(upper, fold),
            _flight_body_pose(-4.0 + math.sin(phase * 2.0) * 2.0),
            {"Tail_04": (0.0, 0.0, math.sin(phase) * 5.0)},
        )
        states[frame] = state
        if hover:
            object_states[frame] = ((0.0, 0.0, math.sin(phase * 2.0) * 0.16), (0, 0, 0))
    return _bake_action(armature, name, frame_end + 1, states, object_states=object_states or None)


def _claw_action(armature: bpy.types.Object, name: str, side: str) -> bpy.types.Action:
    opposite = "R" if side == "L" else "L"
    sign = 1.0 if side == "L" else -1.0
    return _bake_action(
        armature,
        name,
        38,
        {
            1: {f"FrontLeg_{side}_Upper": (0.0, 0.0, 0.0), "Chest": (0.0, 0.0, 0.0)},
            10: {f"FrontLeg_{side}_Upper": (-55.0, 0.0, -16.0 * sign), f"FrontLeg_{side}_Fore": (44.0, 0.0, 0.0), "Chest": (0.0, 0.0, -8.0 * sign)},
            20: {f"FrontLeg_{side}_Upper": (34.0, 0.0, 24.0 * sign), f"FrontLeg_{side}_Fore": (-28.0, 0.0, 0.0), f"FrontLeg_{side}_Wrist": (-24.0, 0.0, 0.0), "Chest": (2.0, 0.0, 13.0 * sign), f"FrontLeg_{opposite}_Upper": (-8.0, 0.0, 0.0)},
            30: {f"FrontLeg_{side}_Upper": (8.0, 0.0, 5.0 * sign), f"FrontLeg_{side}_Fore": (0.0, 0.0, 0.0), "Chest": (0.0, 0.0, 2.0 * sign)},
            38: {f"FrontLeg_{side}_Upper": (0.0, 0.0, 0.0), f"FrontLeg_{side}_Fore": (0.0, 0.0, 0.0), f"FrontLeg_{side}_Wrist": (0.0, 0.0, 0.0), "Chest": (0.0, 0.0, 0.0)},
        },
    )


def _wing_pose(upper_angle: float, fold_angle: float) -> PoseState:
    state: PoseState = {}
    for side, sign in (("L", 1.0), ("R", -1.0)):
        state[f"Wing_{side}_Root"] = (upper_angle * 0.32, 0.0, sign * upper_angle * 0.16)
        state[f"Wing_{side}_Upper"] = (upper_angle, sign * upper_angle * 0.08, sign * upper_angle * 0.10)
        state[f"Wing_{side}_Forearm"] = (upper_angle * 0.42, sign * fold_angle * 0.25, sign * fold_angle * 0.22)
        state[f"Wing_{side}_Wrist"] = (upper_angle * 0.18, sign * fold_angle * 0.40, sign * fold_angle * 0.35)
        state[f"Wing_{side}_Digit_01"] = (0.0, sign * fold_angle * 0.18, sign * fold_angle * 0.16)
        state[f"Wing_{side}_Digit_02"] = (0.0, sign * fold_angle * 0.38, sign * fold_angle * 0.36)
        state[f"Wing_{side}_Digit_03"] = (0.0, sign * fold_angle * 0.58, sign * fold_angle * 0.52)
    return state


def _flight_body_pose(pitch: float) -> PoseState:
    return {
        "Pelvis": (pitch * 0.40, 0.0, 0.0),
        "Spine_01": (pitch * 0.25, 0.0, 0.0),
        "Chest": (pitch * 0.35, 0.0, 0.0),
        "Neck_03": (-pitch * 0.55, 0.0, 0.0),
        "Head": (pitch * 0.20, 0.0, 0.0),
        "FrontLeg_L_Upper": (30.0, 0.0, 0.0),
        "FrontLeg_R_Upper": (30.0, 0.0, 0.0),
        "RearLeg_L_Upper": (24.0, 0.0, 0.0),
        "RearLeg_R_Upper": (24.0, 0.0, 0.0),
    }


def _tail_curve(amplitude: float) -> PoseState:
    return {
        f"Tail_{i:02d}": (0.0, 0.0, amplitude * math.sin(i / 10.0 * math.pi) * (0.35 + i / 14.0))
        for i in range(1, 11)
    }


def _bake_action(
    armature: bpy.types.Object,
    name: str,
    frame_end: int,
    pose_states: dict[int, PoseState],
    object_states: dict[int, ObjectState] | None = None,
) -> bpy.types.Action:
    old = bpy.data.actions.get(name)
    if old is not None:
        bpy.data.actions.remove(old)
    action = bpy.data.actions.new(name=name)
    action.use_fake_user = True
    action["dragon_clip"] = True
    action["loop"] = name in {"Idle_Ground", "Idle_Alert", "Walk", "Run", "Flight_Forward", "Flight_Glide", "Flight_Hover"}

    armature.animation_data_create()
    armature.animation_data.action = action

    used_bones = sorted({bone for state in pose_states.values() for bone in state})
    all_frames = sorted(set(pose_states) | set(object_states or {}))
    for frame in all_frames:
        for bone_name in used_bones:
            pose_bone = armature.pose.bones.get(bone_name)
            if pose_bone is None:
                raise RuntimeError(f"Animation {name} references missing bone {bone_name}")
            pose_bone.rotation_mode = "XYZ"
            pose_bone.rotation_euler = (0.0, 0.0, 0.0)
        for bone_name, rotation_deg in pose_states.get(frame, {}).items():
            pose_bone = armature.pose.bones[bone_name]
            pose_bone.rotation_euler = tuple(math.radians(value) for value in rotation_deg)
        for bone_name in used_bones:
            armature.pose.bones[bone_name].keyframe_insert(data_path="rotation_euler", frame=frame)

        if object_states and frame in object_states:
            location, rotation_deg = object_states[frame]
            armature.location = location
            armature.rotation_mode = "XYZ"
            armature.rotation_euler = tuple(math.radians(value) for value in rotation_deg)
            armature.keyframe_insert(data_path="location", frame=frame)
            armature.keyframe_insert(data_path="rotation_euler", frame=frame)

    for fcurve in action.fcurves:
        for keyframe in fcurve.keyframe_points:
            keyframe.interpolation = "BEZIER"
            keyframe.handle_left_type = "AUTO_CLAMPED"
            keyframe.handle_right_type = "AUTO_CLAMPED"
    armature.location = (0.0, 0.0, 0.0)
    armature.rotation_euler = (0.0, 0.0, 0.0)
    return action


def _merge(*states: PoseState) -> PoseState:
    merged: PoseState = {}
    for state in states:
        merged.update(state)
    return merged
