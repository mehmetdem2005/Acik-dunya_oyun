from __future__ import annotations

import math
import random

import bpy
from mathutils import Matrix, Vector

from .config import MATERIAL_NAMES
from .geometry import MeshAssembler, MeshBuildResult, nearest_chain_weights


BODY_CHAIN = [
    ("Pelvis", Vector((0.0, 0.50, 2.92))),
    ("Spine_01", Vector((0.0, -0.15, 3.18))),
    ("Spine_02", Vector((0.0, -0.80, 3.47))),
    ("Chest", Vector((0.0, -1.38, 3.85))),
]

NECK_POINTS = [
    Vector((0.0, -1.48, 3.86)),
    Vector((0.0, -1.76, 4.43)),
    Vector((0.0, -1.96, 5.02)),
    Vector((0.0, -2.18, 5.58)),
    Vector((0.0, -2.48, 6.06)),
    Vector((0.0, -2.86, 6.42)),
    Vector((0.0, -3.28, 6.62)),
]
NECK_RADII = [
    (0.78, 0.78),
    (0.70, 0.72),
    (0.62, 0.65),
    (0.55, 0.59),
    (0.49, 0.53),
    (0.43, 0.47),
    (0.40, 0.43),
]
NECK_BONES = ["Neck_01", "Neck_02", "Neck_03", "Neck_04", "Neck_05", "Neck_06", "Head"]

TAIL_POINTS = [
    Vector((0.0, 0.62, 2.90)),
    Vector((0.0, 1.45, 2.88)),
    Vector((0.0, 2.30, 2.75)),
    Vector((0.0, 3.15, 2.55)),
    Vector((0.0, 4.00, 2.28)),
    Vector((0.0, 4.82, 2.00)),
    Vector((0.0, 5.60, 1.76)),
    Vector((0.0, 6.35, 1.53)),
    Vector((0.0, 7.05, 1.29)),
    Vector((0.0, 7.70, 1.00)),
    Vector((0.0, 8.30, 0.66)),
]
TAIL_RADII = [
    (0.72, 0.70),
    (0.67, 0.64),
    (0.60, 0.57),
    (0.53, 0.50),
    (0.46, 0.43),
    (0.39, 0.36),
    (0.32, 0.30),
    (0.26, 0.24),
    (0.20, 0.19),
    (0.14, 0.14),
    (0.06, 0.06),
]
TAIL_BONES = [f"Tail_{i:02d}" for i in range(1, 11)] + ["Tail_10"]


def build_dragon_geometry(
    render_collection: bpy.types.Collection,
    detail_collection: bpy.types.Collection,
    armature: bpy.types.Object,
    materials: dict[str, bpy.types.Material],
    seed: int,
) -> dict[str, MeshBuildResult]:
    rng = random.Random(seed)
    results: dict[str, MeshBuildResult] = {}

    main = MeshAssembler(MATERIAL_NAMES)
    _build_core_body(main)
    _build_neck_and_tail(main)
    _build_head_and_jaw(main)
    _build_legs(main)
    _build_wings(main)
    _build_ventral_armor(main)
    _build_body_scales(main, rng)
    results["Dragon_LOD0"] = main.to_object("Dragon_LOD0", render_collection, materials, armature)
    results["Dragon_LOD0"].object["asset_role"] = "render_lod"
    results["Dragon_LOD0"].object["lod_index"] = 0

    horns = MeshAssembler(MATERIAL_NAMES)
    _build_horns_spikes_and_claws(horns, rng)
    results["Dragon_Horns"] = horns.to_object("Dragon_Horns", detail_collection, materials, armature)
    results["Dragon_Horns"].object["asset_role"] = "keratin_detail"

    eyes = MeshAssembler(MATERIAL_NAMES)
    _build_eyes(eyes)
    results["Dragon_Eyes"] = eyes.to_object("Dragon_Eyes", detail_collection, materials, armature)
    results["Dragon_Eyes"].object["asset_role"] = "eyes"

    teeth = MeshAssembler(MATERIAL_NAMES)
    _build_teeth(teeth)
    results["Dragon_Teeth"] = teeth.to_object("Dragon_Teeth", detail_collection, materials, armature)
    results["Dragon_Teeth"].object["asset_role"] = "teeth"

    tongue = MeshAssembler(MATERIAL_NAMES)
    tongue.add_tube(
        [
            Vector((0.0, -3.72, 6.25)),
            Vector((0.0, -4.02, 6.17)),
            Vector((0.0, -4.33, 6.13)),
        ],
        [(0.12, 0.065), (0.10, 0.055), (0.045, 0.025)],
        12,
        "M_Dragon_Mouth",
        ["Tongue_01", "Tongue_01", "Tongue_02"],
    )
    results["Dragon_Tongue"] = tongue.to_object("Dragon_Tongue", detail_collection, materials, armature)
    results["Dragon_Tongue"].object["asset_role"] = "tongue"
    return results


def _build_core_body(builder: MeshAssembler) -> None:
    body_weights = lambda co: nearest_chain_weights(co, BODY_CHAIN)
    builder.add_uv_ellipsoid(
        Vector((0.0, -0.12, 3.28)),
        Vector((1.46, 2.18, 1.53)),
        rings=28,
        segments=56,
        material="M_Dragon_Body",
        weights=body_weights,
        rotation=Matrix.Rotation(math.radians(-2.5), 3, "X"),
        uv_scale=(2.5, 2.0),
    )
    builder.add_uv_ellipsoid(
        Vector((0.0, -1.22, 3.70)),
        Vector((1.33, 1.42, 1.33)),
        rings=24,
        segments=48,
        material="M_Dragon_Body",
        weights=lambda co: {"Chest": 0.72, "Spine_02": 0.28},
        uv_scale=(2.0, 1.6),
    )
    builder.add_uv_ellipsoid(
        Vector((0.0, 0.83, 3.00)),
        Vector((1.30, 1.18, 1.12)),
        rings=22,
        segments=44,
        material="M_Dragon_Body",
        weights=lambda co: {"Pelvis": 0.82, "Spine_01": 0.18},
        uv_scale=(1.8, 1.4),
    )


def _build_neck_and_tail(builder: MeshAssembler) -> None:
    builder.add_tube(
        NECK_POINTS,
        NECK_RADII,
        segments=32,
        material="M_Dragon_Body",
        bone_chain=NECK_BONES,
        uv_v_scale=3.0,
    )
    builder.add_tube(
        TAIL_POINTS,
        TAIL_RADII,
        segments=28,
        material="M_Dragon_Body",
        bone_chain=TAIL_BONES,
        uv_v_scale=6.0,
    )


def _build_head_and_jaw(builder: MeshAssembler) -> None:
    head_rotation = Matrix.Rotation(math.radians(4.0), 3, "X")
    builder.add_uv_ellipsoid(
        Vector((0.0, -3.78, 6.67)),
        Vector((0.65, 1.02, 0.64)),
        rings=24,
        segments=44,
        material="M_Dragon_Body",
        weights=lambda co: {"Head": 1.0},
        rotation=head_rotation,
        uv_scale=(1.6, 1.2),
    )
    builder.add_uv_ellipsoid(
        Vector((0.0, -4.35, 6.50)),
        Vector((0.52, 0.72, 0.39)),
        rings=18,
        segments=36,
        material="M_Dragon_Body",
        weights=lambda co: {"Head": 1.0},
        rotation=head_rotation,
    )
    builder.add_uv_ellipsoid(
        Vector((0.0, -4.04, 6.25)),
        Vector((0.50, 0.75, 0.22)),
        rings=16,
        segments=34,
        material="M_Dragon_Body",
        weights=lambda co: {"Jaw": 1.0},
        rotation=Matrix.Rotation(math.radians(-8.0), 3, "X"),
    )
    builder.add_uv_ellipsoid(
        Vector((0.0, -4.06, 6.31)),
        Vector((0.42, 0.62, 0.10)),
        rings=10,
        segments=28,
        material="M_Dragon_Mouth",
        weights=lambda co: {"Jaw": 0.75, "Head": 0.25},
    )
    # Brow ridges.
    for sign, side in ((1.0, "L"), (-1.0, "R")):
        builder.add_cylinder_between(
            Vector((0.18 * sign, -3.93, 6.88)),
            Vector((0.49 * sign, -4.18, 6.78)),
            (0.13, 0.11),
            (0.07, 0.06),
            12,
            "M_Dragon_Body",
            f"Eye_{side}",
        )


def _build_legs(builder: MeshAssembler) -> None:
    for side, sign in (("L", 1.0), ("R", -1.0)):
        front = [
            (Vector((0.52 * sign, -1.28, 3.72)), Vector((0.91 * sign, -1.55, 3.28)), 0.48, 0.40, f"FrontLeg_{side}_Scapula"),
            (Vector((0.91 * sign, -1.55, 3.28)), Vector((1.03 * sign, -1.72, 2.34)), 0.42, 0.33, f"FrontLeg_{side}_Upper"),
            (Vector((1.03 * sign, -1.72, 2.34)), Vector((0.90 * sign, -1.92, 1.12)), 0.34, 0.23, f"FrontLeg_{side}_Fore"),
            (Vector((0.90 * sign, -1.92, 1.12)), Vector((0.92 * sign, -2.08, 0.34)), 0.24, 0.18, f"FrontLeg_{side}_Wrist"),
        ]
        for start, end, r0, r1, bone in front:
            builder.add_cylinder_between(start, end, (r0, r0 * 0.88), (r1, r1 * 0.86), 20, "M_Dragon_Body", bone)
        builder.add_uv_ellipsoid(
            Vector((0.92 * sign, -2.38, 0.26)),
            Vector((0.34, 0.68, 0.23)),
            12,
            24,
            "M_Dragon_Body",
            lambda co, s=side: {f"FrontLeg_{s}_Foot": 1.0},
            rotation=Matrix.Rotation(math.radians(10), 3, "X"),
        )

        rear = [
            (Vector((0.58 * sign, 0.78, 3.02)), Vector((0.97 * sign, 1.17, 2.55)), 0.62, 0.52, f"RearLeg_{side}_Hip"),
            (Vector((0.97 * sign, 1.17, 2.55)), Vector((1.38 * sign, 0.87, 1.73)), 0.56, 0.39, f"RearLeg_{side}_Upper"),
            (Vector((1.38 * sign, 0.87, 1.73)), Vector((1.08 * sign, 1.45, 0.66)), 0.38, 0.24, f"RearLeg_{side}_Lower"),
            (Vector((1.08 * sign, 1.45, 0.66)), Vector((1.00 * sign, 1.24, 0.23)), 0.24, 0.18, f"RearLeg_{side}_Ankle"),
        ]
        for start, end, r0, r1, bone in rear:
            builder.add_cylinder_between(start, end, (r0, r0 * 0.90), (r1, r1 * 0.88), 22, "M_Dragon_Body", bone)
        builder.add_uv_ellipsoid(
            Vector((1.00 * sign, 0.86, 0.24)),
            Vector((0.39, 0.73, 0.25)),
            12,
            24,
            "M_Dragon_Body",
            lambda co, s=side: {f"RearLeg_{s}_Foot": 1.0},
            rotation=Matrix.Rotation(math.radians(-8), 3, "X"),
        )


def _build_wings(builder: MeshAssembler) -> None:
    for side, sign in (("L", 1.0), ("R", -1.0)):
        root = Vector((0.70 * sign, -1.05, 4.16))
        upper = Vector((2.95 * sign, -0.48, 5.55))
        wrist = Vector((5.15 * sign, -0.15, 6.15))
        palm = Vector((6.20 * sign, -0.02, 6.32))
        d1 = Vector((8.45 * sign, -0.25, 7.35))
        d2 = Vector((7.78 * sign, 0.70, 5.73))
        d3 = Vector((6.47 * sign, 1.60, 4.20))
        trailing = Vector((1.12 * sign, 1.22, 3.25))

        builder.add_cylinder_between(root, upper, (0.24, 0.20), (0.20, 0.17), 18, "M_Dragon_Body", f"Wing_{side}_Upper")
        builder.add_cylinder_between(upper, wrist, (0.20, 0.17), (0.14, 0.12), 16, "M_Dragon_Body", f"Wing_{side}_Forearm")
        builder.add_cylinder_between(wrist, palm, (0.15, 0.12), (0.12, 0.10), 14, "M_Dragon_Body", f"Wing_{side}_Wrist")
        for tip, bone, radius in (
            (d1, f"Wing_{side}_Digit_01", 0.095),
            (d2, f"Wing_{side}_Digit_02", 0.085),
            (d3, f"Wing_{side}_Digit_03", 0.075),
        ):
            builder.add_cylinder_between(palm, tip, (radius * 1.35, radius), (radius * 0.28, radius * 0.22), 12, "M_Dragon_Body", bone)

        points = [root, upper, wrist, palm, d1, d2, d3, trailing]
        uvs = [(0.0, 0.1), (0.20, 0.04), (0.45, 0.02), (0.58, 0.04), (1.0, 0.0), (0.92, 0.47), (0.74, 0.88), (0.04, 1.0)]
        weights = [
            {f"Wing_{side}_Root": 0.75, "Chest": 0.25},
            {f"Wing_{side}_Upper": 1.0},
            {f"Wing_{side}_Forearm": 1.0},
            {f"Wing_{side}_Wrist": 1.0},
            {f"Wing_{side}_Digit_01": 1.0},
            {f"Wing_{side}_Digit_02": 1.0},
            {f"Wing_{side}_Digit_03": 1.0},
            {f"Wing_{side}_Membrane": 0.72, "Chest": 0.28},
        ]
        builder.add_membrane_polygon(points, uvs, weights, "M_Dragon_WingMembrane", thickness=0.045)

        # Secondary membrane panels create fold lines and avoid a single flat fan.
        inner = [
            root,
            (root + upper) * 0.5 + Vector((0.0, 0.20, -0.18)),
            (upper + wrist) * 0.5 + Vector((0.0, 0.42, -0.42)),
            (wrist + d2) * 0.5 + Vector((0.0, 0.34, -0.28)),
            trailing,
        ]
        builder.add_membrane_polygon(
            inner,
            [(0.0, 0.0), (0.25, 0.12), (0.52, 0.25), (0.82, 0.52), (0.05, 1.0)],
            [
                {f"Wing_{side}_Root": 1.0},
                {f"Wing_{side}_Upper": 0.75, f"Wing_{side}_Membrane": 0.25},
                {f"Wing_{side}_Forearm": 0.72, f"Wing_{side}_Membrane": 0.28},
                {f"Wing_{side}_Digit_02": 0.65, f"Wing_{side}_Membrane": 0.35},
                {f"Wing_{side}_Membrane": 1.0},
            ],
            "M_Dragon_WingMembrane",
            thickness=0.035,
        )


def _build_ventral_armor(builder: MeshAssembler) -> None:
    for index, point in enumerate(NECK_POINTS[:-1]):
        tangent = _path_tangent(NECK_POINTS, index)
        normal = Vector((0.0, -0.24, -1.0)).normalized()
        center = point + normal * (NECK_RADII[index][1] * 0.82)
        builder.add_scale_plate(
            center,
            normal,
            length=0.42 + index * 0.018,
            width=0.72 - index * 0.035,
            height=0.055,
            material="M_Dragon_Ventral",
            weights={NECK_BONES[index]: 0.9, NECK_BONES[min(index + 1, len(NECK_BONES) - 1)]: 0.1},
            roll=0.0,
        )
    for row in range(8):
        y = -1.35 + row * 0.33
        z = 2.02 + 0.11 * math.cos(row / 7 * math.pi)
        center = Vector((0.0, y, z))
        builder.add_scale_plate(
            center,
            Vector((0.0, -0.10, -1.0)).normalized(),
            length=0.50,
            width=1.55 - abs(row - 3.5) * 0.09,
            height=0.07,
            material="M_Dragon_Ventral",
            weights=nearest_chain_weights(center, BODY_CHAIN),
        )


def _build_body_scales(builder: MeshAssembler, rng: random.Random) -> None:
    center = Vector((0.0, -0.10, 3.30))
    radii = Vector((1.48, 2.22, 1.56))
    rows = 26
    columns = 58
    for row in range(rows):
        phi = 0.16 * math.pi + (row / max(rows - 1, 1)) * 0.70 * math.pi
        for col in range(columns):
            theta = (col / columns) * math.tau + (row % 2) * (math.pi / columns)
            local = Vector((
                radii.x * math.sin(phi) * math.cos(theta),
                radii.y * math.sin(phi) * math.sin(theta),
                radii.z * math.cos(phi),
            ))
            point = center + local
            if point.z < 2.55 or point.y < -1.75:
                continue
            normal = Vector((
                local.x / (radii.x * radii.x),
                local.y / (radii.y * radii.y),
                local.z / (radii.z * radii.z),
            )).normalized()
            size = 0.105 + rng.random() * 0.055
            builder.add_scale_plate(
                point + normal * 0.035,
                normal,
                length=size * 1.25,
                width=size,
                height=size * (0.18 + rng.random() * 0.12),
                material="M_Dragon_Body",
                weights=nearest_chain_weights(point, BODY_CHAIN),
                roll=(rng.random() - 0.5) * 0.20,
            )

    _add_tube_scales(builder, NECK_POINTS, NECK_RADII, NECK_BONES, rings_per_segment=3, around=16, rng=rng)
    _add_tube_scales(builder, TAIL_POINTS[:-1], TAIL_RADII[:-1], TAIL_BONES[:-1], rings_per_segment=2, around=12, rng=rng)

    # Scar plates on the right shoulder and muzzle.
    for i in range(14):
        angle = i / 14 * math.tau
        point = Vector((-1.20 + math.cos(angle) * 0.10, -1.00 + math.sin(angle) * 0.24, 3.78 + math.sin(angle * 0.5) * 0.14))
        normal = Vector((-0.85, -0.25, 0.35)).normalized()
        builder.add_scale_plate(point, normal, 0.22, 0.09, 0.025, "M_Dragon_Scars", {"Chest": 1.0}, roll=angle)


def _add_tube_scales(
    builder: MeshAssembler,
    points: list[Vector],
    radii: list[tuple[float, float]],
    bones: list[str],
    rings_per_segment: int,
    around: int,
    rng: random.Random,
) -> None:
    for segment_index in range(len(points) - 1):
        for sub in range(rings_per_segment):
            t = (sub + 0.5) / rings_per_segment
            point = points[segment_index].lerp(points[segment_index + 1], t)
            radius = (
                radii[segment_index][0] * (1.0 - t) + radii[segment_index + 1][0] * t,
                radii[segment_index][1] * (1.0 - t) + radii[segment_index + 1][1] * t,
            )
            tangent = (points[segment_index + 1] - points[segment_index]).normalized()
            side, up = _frame(tangent)
            for i in range(around):
                angle = i / around * math.tau + (sub % 2) * math.pi / around
                normal = (side * math.cos(angle) + up * math.sin(angle)).normalized()
                surface = point + side * math.cos(angle) * radius[0] + up * math.sin(angle) * radius[1]
                size = max(0.055, radius[0] * 0.14) * (0.8 + rng.random() * 0.4)
                builder.add_scale_plate(
                    surface + normal * 0.02,
                    normal,
                    size * 1.35,
                    size,
                    size * 0.18,
                    "M_Dragon_Body",
                    {bones[segment_index]: 0.75, bones[min(segment_index + 1, len(bones) - 1)]: 0.25},
                    roll=(rng.random() - 0.5) * 0.16,
                )


def _build_horns_spikes_and_claws(builder: MeshAssembler, rng: random.Random) -> None:
    # Primary crown horns.
    for side, sign in (("L", 1.0), ("R", -1.0)):
        primary = [
            (Vector((0.36 * sign, -3.52, 7.08)), Vector((0.78 * sign, -2.74, 7.95)), 0.23),
            (Vector((0.48 * sign, -3.38, 6.94)), Vector((1.12 * sign, -2.78, 7.47)), 0.19),
            (Vector((0.54 * sign, -3.58, 6.72)), Vector((1.10 * sign, -3.06, 6.95)), 0.14),
        ]
        for base, tip, radius in primary:
            builder.add_cone(base, tip, radius, 16, "M_Dragon_Horns_Claws", "Head", elliptical=0.82)
        # Jawline spikes.
        for i in range(5):
            base = Vector((0.48 * sign, -3.68 - i * 0.16, 6.48 - i * 0.045))
            tip = base + Vector((0.32 * sign, -0.04, -0.12 - i * 0.018))
            builder.add_cone(base, tip, 0.09 - i * 0.007, 10, "M_Dragon_Horns_Claws", "Head", elliptical=0.75)

    # Dorsal spikes from neck to tail.
    dorsal = list(zip(NECK_POINTS, NECK_RADII, NECK_BONES))
    for i, (point, radius, bone) in enumerate(dorsal):
        base = point + Vector((0.0, 0.12, radius[1] * 0.92))
        tip = base + Vector((0.0, 0.12 + i * 0.02, 0.55 - i * 0.035))
        builder.add_cone(base, tip, 0.15 - i * 0.009, 12, "M_Dragon_Horns_Claws", bone, elliptical=0.72)
    for i, (point, radius, bone) in enumerate(zip(TAIL_POINTS[1:-1], TAIL_RADII[1:-1], TAIL_BONES[1:-1])):
        base = point + Vector((0.0, 0.0, radius[1] * 0.96))
        height = max(0.12, 0.48 - i * 0.042)
        builder.add_cone(base, base + Vector((0.0, 0.02, height)), max(0.045, 0.13 - i * 0.008), 10, "M_Dragon_Horns_Claws", bone, elliptical=0.72)

    # Claws and dewclaws.
    for side, sign in (("L", 1.0), ("R", -1.0)):
        for front_rear, y, z, bone, spread in (
            ("front", -2.68, 0.17, f"FrontLeg_{side}_Foot", 0.34),
            ("rear", 0.52, 0.15, f"RearLeg_{side}_Foot", 0.39),
        ):
            for toe in range(4):
                x = (0.92 if front_rear == "front" else 1.00) * sign + (toe - 1.5) * spread * 0.34 * sign
                base = Vector((x, y, z))
                direction_y = -0.55 if front_rear == "front" else -0.48
                tip = base + Vector((0.04 * (toe - 1.5) * sign, direction_y, -0.10))
                builder.add_cone(base, tip, 0.075, 10, "M_Dragon_Horns_Claws", bone, elliptical=0.72)

    # Wingtip talons.
    for side, sign in (("L", 1.0), ("R", -1.0)):
        for index, (base, bone) in enumerate((
            (Vector((8.45 * sign, -0.25, 7.35)), f"Wing_{side}_Digit_01"),
            (Vector((7.78 * sign, 0.70, 5.73)), f"Wing_{side}_Digit_02"),
            (Vector((6.47 * sign, 1.60, 4.20)), f"Wing_{side}_Digit_03"),
        )):
            tip = base + Vector((0.28 * sign, 0.08, -0.15 - index * 0.04))
            builder.add_cone(base, tip, 0.095 - index * 0.012, 10, "M_Dragon_Horns_Claws", bone, elliptical=0.70)


def _build_eyes(builder: MeshAssembler) -> None:
    for side, sign in (("L", 1.0), ("R", -1.0)):
        builder.add_uv_ellipsoid(
            Vector((0.30 * sign, -4.18, 6.77)),
            Vector((0.145, 0.105, 0.13)),
            14,
            24,
            "M_Dragon_Eyes",
            lambda co, s=side: {f"Eye_{s}": 1.0},
        )


def _build_teeth(builder: MeshAssembler) -> None:
    for side_sign in (-1.0, 1.0):
        for row, z, bone, tip_z in (("upper", 6.43, "Head", 6.18), ("lower", 6.20, "Jaw", 6.42)):
            for i in range(8):
                x = side_sign * (0.10 + i * 0.047)
                y = -4.18 - i * 0.055
                base = Vector((x, y, z + (0.02 if row == "upper" else -0.01)))
                tip = Vector((x * 0.96, y - 0.04, tip_z + (i % 2) * 0.018))
                builder.add_cone(base, tip, 0.036 + (7 - i) * 0.002, 8, "M_Dragon_Teeth", bone, elliptical=0.82)
    # Four canines.
    for sign in (-1.0, 1.0):
        builder.add_cone(Vector((0.36 * sign, -4.30, 6.43)), Vector((0.34 * sign, -4.40, 6.04)), 0.075, 10, "M_Dragon_Teeth", "Head", 0.78)
        builder.add_cone(Vector((0.32 * sign, -4.25, 6.20)), Vector((0.30 * sign, -4.35, 6.49)), 0.068, 10, "M_Dragon_Teeth", "Jaw", 0.78)


def _path_tangent(points: list[Vector], index: int) -> Vector:
    if index == 0:
        return (points[1] - points[0]).normalized()
    if index == len(points) - 1:
        return (points[-1] - points[-2]).normalized()
    return (points[index + 1] - points[index - 1]).normalized()


def _frame(direction: Vector) -> tuple[Vector, Vector]:
    reference = Vector((0.0, 0.0, 1.0))
    if abs(direction.dot(reference)) > 0.92:
        reference = Vector((0.0, 1.0, 0.0))
    side = direction.cross(reference).normalized()
    up = side.cross(direction).normalized()
    return side, up
