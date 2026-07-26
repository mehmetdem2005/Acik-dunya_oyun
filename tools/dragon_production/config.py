from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ASSET_NAME = "Dragon_Master"
ROOT_NAME = "Dragon_Root"
SKELETON_NAME = "Dragon_Skeleton"

MATERIAL_NAMES = (
    "M_Dragon_Body",
    "M_Dragon_Ventral",
    "M_Dragon_WingMembrane",
    "M_Dragon_Horns_Claws",
    "M_Dragon_Eyes",
    "M_Dragon_Mouth",
    "M_Dragon_Teeth",
    "M_Dragon_Scars",
)

REQUIRED_ACTIONS = (
    "Idle_Ground",
    "Idle_Alert",
    "Walk",
    "Run",
    "Turn_Left_90",
    "Turn_Right_90",
    "Takeoff",
    "Flight_Forward",
    "Flight_Glide",
    "Flight_Hover",
    "Landing",
    "Wing_Fold",
    "Wing_Unfold",
    "Roar",
    "Bite_Attack",
    "Claw_Attack_Left",
    "Claw_Attack_Right",
    "Tail_Attack",
    "Hit_Reaction",
    "Death",
)

LOD_RATIOS = {
    "Dragon_LOD0": 1.0,
    "Dragon_LOD1": 0.62,
    "Dragon_LOD2": 0.36,
    "Dragon_LOD3": 0.18,
    "Dragon_LOD4": 0.08,
    "Dragon_Mobile": 0.42,
}

LOD_DISTANCE_HINTS_M = {
    "Dragon_LOD0": (0.0, 10.0),
    "Dragon_LOD1": (8.0, 24.0),
    "Dragon_LOD2": (20.0, 52.0),
    "Dragon_LOD3": (45.0, 110.0),
    "Dragon_LOD4": (95.0, 1000.0),
    "Dragon_Mobile": (0.0, 55.0),
}

COLLISION_PARTS = (
    "Head_Collision",
    "Neck_Collision",
    "Chest_Collision",
    "Pelvis_Collision",
    "Tail_Collision_01",
    "Tail_Collision_02",
    "Tail_Collision_03",
    "FrontLeg_Collision_L",
    "FrontLeg_Collision_R",
    "RearLeg_Collision_L",
    "RearLeg_Collision_R",
    "Wing_Collision_L",
    "Wing_Collision_R",
)


@dataclass(frozen=True)
class BuildSettings:
    output_dir: Path
    texture_size: int = 1024
    preview_size: int = 768
    render_previews: bool = True
    export_gltf_separate: bool = True
    export_glb: bool = True
    seed: int = 731992

    @property
    def textures_dir(self) -> Path:
        return self.output_dir / "textures"

    @property
    def previews_dir(self) -> Path:
        return self.output_dir / "previews"


BONE_POINTS = {
    "Root": ((0.0, 0.45, 0.0), (0.0, 0.45, 1.1)),
    "Pelvis": ((0.0, 0.55, 2.55), (0.0, 0.15, 3.05)),
    "Spine_01": ((0.0, 0.15, 3.05), (0.0, -0.55, 3.30)),
    "Spine_02": ((0.0, -0.55, 3.30), (0.0, -1.15, 3.72)),
    "Chest": ((0.0, -1.15, 3.72), (0.0, -1.65, 4.05)),
    "Neck_01": ((0.0, -1.55, 3.92), (0.0, -1.80, 4.55)),
    "Neck_02": ((0.0, -1.80, 4.55), (0.0, -2.00, 5.15)),
    "Neck_03": ((0.0, -2.00, 5.15), (0.0, -2.25, 5.72)),
    "Neck_04": ((0.0, -2.25, 5.72), (0.0, -2.55, 6.20)),
    "Neck_05": ((0.0, -2.55, 6.20), (0.0, -2.95, 6.55)),
    "Neck_06": ((0.0, -2.95, 6.55), (0.0, -3.38, 6.72)),
    "Head": ((0.0, -3.38, 6.72), (0.0, -4.35, 6.62)),
    "Jaw": ((0.0, -3.72, 6.40), (0.0, -4.40, 6.16)),
    "Tail_01": ((0.0, 0.70, 2.88), (0.0, 1.55, 2.88)),
    "Tail_02": ((0.0, 1.55, 2.88), (0.0, 2.40, 2.74)),
    "Tail_03": ((0.0, 2.40, 2.74), (0.0, 3.25, 2.53)),
    "Tail_04": ((0.0, 3.25, 2.53), (0.0, 4.10, 2.25)),
    "Tail_05": ((0.0, 4.10, 2.25), (0.0, 4.92, 1.98)),
    "Tail_06": ((0.0, 4.92, 1.98), (0.0, 5.70, 1.73)),
    "Tail_07": ((0.0, 5.70, 1.73), (0.0, 6.45, 1.50)),
    "Tail_08": ((0.0, 6.45, 1.50), (0.0, 7.15, 1.25)),
    "Tail_09": ((0.0, 7.15, 1.25), (0.0, 7.78, 0.97)),
    "Tail_10": ((0.0, 7.78, 0.97), (0.0, 8.35, 0.65)),
}


def mirrored_name(side: str, stem: str) -> str:
    return f"{stem}_{side}"
