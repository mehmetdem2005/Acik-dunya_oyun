"""20 baslangic animasyonu.

Yontem: her kare icin kemik-yerel delta matrisleri (matrix_basis) hesaplanir.
Bacaklar 2-kemikli IK ile cozulur; duruş (stance) fazinda ayak, karakterin ileri
hizini tam olarak dengeleyecek sekilde geriye kayar -> in-place klipte de,
root-motion variantinda da AYAK KAYMASI OLMAZ.
"""

import math
from mathutils import Vector, Matrix, Quaternion

from . import config as C
from .rig import Kinematics, two_bone_ik, aim_matrix
from .core import smoothstep, clamp, lerp

D = math.radians
TAU = math.tau


def R(axis, deg):
    return Matrix.Rotation(D(deg), 4, axis)


# ------------------------------------------------------------------
# yurume/kosma faz tablolari (dortayakli)
# ------------------------------------------------------------------
GAIT_WALK = {"legF_L": 0.00, "legR_R": 0.25, "legF_R": 0.50, "legR_L": 0.75}
GAIT_RUN = {"legF_L": 0.00, "legF_R": 0.14, "legR_L": 0.52, "legR_R": 0.66}

LEG_BONES = {
    "legF_L": ("Shoulder_L", "FrontLeg_L", "FrontLegLow_L", "FrontAnkle_L", "FrontFoot_L"),
    "legF_R": ("Shoulder_R", "FrontLeg_R", "FrontLegLow_R", "FrontAnkle_R", "FrontFoot_R"),
    "legR_L": ("Hip_L", "RearLeg_L", "RearLegLow_L", "RearAnkle_L", "RearFoot_L"),
    "legR_R": ("Hip_R", "RearLeg_R", "RearLegLow_R", "RearAnkle_R", "RearFoot_R"),
}
SPINE_B = ["Pelvis", "Spine_01", "Spine_02", "Spine_03", "Chest"]
NECK_B = ["Neck_01", "Neck_02", "Neck_03", "Neck_04", "Head"]
TAIL_B = ["Tail_%02d" % i for i in range(1, 9)] + ["Tail_Tip"]
FINGERS = lambda s: ["WingFinger%02d_%s" % (k, s) for k in range(1, 5)]
FINGERS_B = lambda s: ["WingFinger%02db_%s" % (k, s) for k in range(1, 5)]


class Rigger:
    def __init__(self, bonedefs, legs, ground_y=0.0):
        self.kin = Kinematics(bonedefs)
        self.defs = {b.name: b for b in bonedefs}
        self.legs = legs
        self.ground = ground_y
        # her bacak icin rest referanslari
        self.leg_ref = {}
        for key, names in LEG_BONES.items():
            d = self.defs[names[4]]          # Foot bone
            ankle = d.head.copy()
            contact = Vector((d.tail.x, ground_y, d.tail.z))
            self.leg_ref[key] = {
                "ankle": ankle,
                "contact": contact,
                "L1": (self.defs[names[1]].tail - self.defs[names[1]].head).length,
                "L2": (self.defs[names[2]].tail - self.defs[names[2]].head).length,
                "foot_dir": (d.tail - d.head).normalized(),
                "foot_len": (d.tail - d.head).length,
            }

    # --------------------------------------------------------------
    def solve_legs(self, pose, targets, pole_fwd=Vector((0.0, 0.0, -1.0))):
        """FK degerlendirmesinden sonra bacaklari IK ile cozer."""
        world = self.kin.evaluate(pose)
        for key, tgt in targets.items():
            names = LEG_BONES[key]
            ref = self.leg_ref[key]
            up_name, low_name, ank_name, foot_name = names[1], names[2], names[3], names[4]
            root_w = self.kin.head_world(world, up_name)
            L1, L2 = ref["L1"], ref["L2"]
            # diz/dirsek yonu: on bacak geri, arka bacak ileri bukulur
            pole = Vector(pole_fwd)
            if key.startswith("legR"):
                pole = -pole
            mid, end = two_bone_ik(root_w, tgt["ankle"], L1, L2, pole)
            # ust kemik
            m_up = aim_matrix(root_w, mid - root_w, self.defs[up_name].up)
            self._set_world(pose, world, up_name, m_up)
            world = self.kin.evaluate(pose)
            m_low = aim_matrix(self.kin.head_world(world, low_name),
                               end - mid, self.defs[low_name].up)
            self._set_world(pose, world, low_name, m_low)
            world = self.kin.evaluate(pose)
            # bilek + ayak: taban duz kalsin
            fdir = tgt.get("foot_dir", ref["foot_dir"])
            m_ank = aim_matrix(self.kin.head_world(world, ank_name),
                               (tgt["ankle"] - end) if (tgt["ankle"] - end).length > 1e-4
                               else fdir, self.defs[ank_name].up)
            self._set_world(pose, world, ank_name, m_ank)
            world = self.kin.evaluate(pose)
            m_ft = aim_matrix(self.kin.head_world(world, foot_name), fdir,
                              Vector((0.0, 1.0, 0.0)))
            self._set_world(pose, world, foot_name, m_ft)
            world = self.kin.evaluate(pose)
        return world

    def _set_world(self, pose, world, name, desired_world):
        par = self.kin.parent[name]
        pw = world[par] if par else Matrix.Identity(4)
        basis = (pw @ self.kin.rest_local[name]).inverted() @ desired_world
        # sadece rotasyon bileseni (kemik uzunlugu korunur)
        q = basis.to_quaternion()
        pose[name] = q.to_matrix().to_4x4()

    # --------------------------------------------------------------
    def gait_targets(self, key, phase, stride, duty, lift, fwd, sway=0.0):
        ref = self.leg_ref[key]
        p = phase % 1.0
        if p < duty:
            f = 0.5 - (p / duty)
            y = 0.0
        else:
            q = (p - duty) / max(1.0 - duty, 1e-4)
            f = -0.5 + q
            y = lift * math.sin(math.pi * q) ** 0.85
        off = fwd * (stride * f) + Vector((0.0, y, 0.0))
        off += Vector((sway, 0.0, 0.0))
        return {"ankle": ref["ankle"] + off,
                "foot_dir": ref["foot_dir"]}


# ==================================================================
# KLIP URETICILERI
# ==================================================================
def _chain(pose, names, axis, amps, phase, t, extra=0.0):
    for i, n in enumerate(names):
        a = amps[i] if i < len(amps) else amps[-1]
        pose[n] = pose.get(n, Matrix.Identity(4)) @ R(
            axis, a * math.sin(TAU * t + phase * i) + extra)


def _tail_wave(pose, t, amp=7.0, speed=1.0, lag=0.55, droop=0.0):
    for i, n in enumerate(TAIL_B):
        pose[n] = pose.get(n, Matrix.Identity(4)) \
            @ R('Z', amp * math.sin(TAU * speed * t - lag * i)) \
            @ R('X', droop + 1.2 * math.sin(TAU * speed * t * 0.5 - 0.4 * i))


def _wing_pose(pose, s, flap, fold, twist=0.0, finger_fold=0.0):
    """flap: dihedral (yukari +), fold: duzlem ici katlanma."""
    pose["WingRoot_" + s] = R('X', flap * 0.35) @ R('Z', fold * 0.20)
    pose["WingArm_" + s] = R('X', flap) @ R('Z', fold * 0.30) @ R('Y', twist)
    pose["WingForearm_" + s] = R('Z', -fold * 0.95) @ R('X', flap * 0.25)
    pose["WingWrist_" + s] = R('Z', -fold * 0.55) @ R('X', flap * 0.10)
    for k, n in enumerate(FINGERS(s)):
        pose[n] = R('Z', -finger_fold * (0.55 + 0.16 * k))
    for k, n in enumerate(FINGERS_B(s)):
        pose[n] = R('Z', -finger_fold * (0.42 + 0.12 * k))


def _breath(pose, t, amt=1.0):
    b = math.sin(TAU * t) * amt
    pose["Chest"] = pose.get("Chest", Matrix.Identity(4)) @ R('X', b * 0.9)
    pose["Spine_03"] = pose.get("Spine_03", Matrix.Identity(4)) @ R('X', -b * 0.5)


def _idle_legs(rg, pose, t=0.0, bob=0.0):
    tg = {}
    for key in LEG_BONES:
        ref = rg.leg_ref[key]
        tg[key] = {"ankle": ref["ankle"] + Vector((0.0, bob, 0.0)),
                   "foot_dir": ref["foot_dir"]}
    return tg


def clip_idle_ground(rg, t):
    pose = {}
    bob = math.sin(TAU * t) * 0.035
    pose["Root_Motion"] = Matrix.Translation(Vector((0.0, bob, 0.0)))
    _breath(pose, t, 1.0)
    _chain(pose, NECK_B, 'X', [1.4, 1.1, 0.9, 0.7, 1.6], 0.5, t)
    pose["Head"] = pose.get("Head", Matrix.Identity(4)) @ R('Z', 2.2 * math.sin(TAU * t * 0.5))
    _tail_wave(pose, t, amp=5.0, speed=0.5, droop=1.5)
    _wing_pose(pose, "L", flap=-2.0 + math.sin(TAU * t) * 1.2, fold=46.0,
               finger_fold=52.0)
    _wing_pose(pose, "R", flap=-2.0 + math.sin(TAU * t + 0.4) * 1.2, fold=46.0,
               finger_fold=52.0)
    pose["Jaw"] = R('X', 1.5 + 1.0 * math.sin(TAU * t))
    return pose, _idle_legs(rg, pose, t, bob * 0.0)


def clip_idle_alert(rg, t):
    pose = {}
    bob = math.sin(TAU * t * 2.0) * 0.02
    pose["Root_Motion"] = Matrix.Translation(Vector((0.0, bob + 0.05, 0.0)))
    _breath(pose, t, 1.8)
    for i, n in enumerate(NECK_B):
        pose[n] = R('X', -4.5 + 1.0 * math.sin(TAU * t * 1.5 + i))
    pose["Head"] = R('X', 6.0) @ R('Z', 7.0 * math.sin(TAU * t * 0.75))
    _tail_wave(pose, t, amp=9.0, speed=1.2, droop=-2.0)
    for s in "LR":
        _wing_pose(pose, s, flap=6.0 + 2.0 * math.sin(TAU * t * 1.5), fold=34.0,
                   finger_fold=40.0)
    pose["Jaw"] = R('X', 3.0)
    return pose, _idle_legs(rg, pose, t)


def _locomotion(rg, t, gait, stride, duty, lift, bob_amp, cycle_speed,
                lean, tail_amp, wing_fold, neck_amp):
    pose = {}
    fwd = Vector((0.0, 0.0, -1.0))
    bob = bob_amp * math.sin(TAU * 2.0 * t)
    roll = 1.6 * math.sin(TAU * t)
    pose["Root_Motion"] = (Matrix.Translation(Vector((0.0, bob, 0.0)))
                           @ R('X', lean))
    pose["Pelvis"] = R('Z', 3.0 * math.sin(TAU * t)) @ R('Y', roll)
    for i, n in enumerate(SPINE_B[1:]):
        pose[n] = R('Z', 2.4 * math.sin(TAU * t - 0.5 * i)) \
            @ R('X', 1.2 * math.sin(TAU * 2.0 * t - 0.4 * i))
    for i, n in enumerate(NECK_B):
        pose[n] = R('X', neck_amp * math.sin(TAU * 2.0 * t - 0.5 * i)) \
            @ R('Z', 1.6 * math.sin(TAU * t - 0.4 * i))
    _tail_wave(pose, t, amp=tail_amp, speed=1.0, lag=0.5, droop=1.0)
    for s in "LR":
        _wing_pose(pose, s, flap=-1.0 + 2.0 * math.sin(TAU * t), fold=wing_fold,
                   finger_fold=wing_fold + 6.0)
    tg = {}
    for key, ph in gait.items():
        tg[key] = rg.gait_targets(key, t * cycle_speed + ph, stride, duty, lift, fwd)
    return pose, tg


def clip_walk(rg, t):
    return _locomotion(rg, t, GAIT_WALK, stride=2.10, duty=0.64, lift=0.42,
                       bob_amp=0.055, cycle_speed=1.0, lean=0.0,
                       tail_amp=7.0, wing_fold=45.0, neck_amp=1.6)


def clip_run(rg, t):
    return _locomotion(rg, t, GAIT_RUN, stride=3.60, duty=0.40, lift=0.85,
                       bob_amp=0.16, cycle_speed=1.0, lean=-4.0,
                       tail_amp=11.0, wing_fold=40.0, neck_amp=3.4)


def _turn(rg, t, sign):
    pose = {}
    e = smoothstep(0.05, 0.92, t)
    pose["Root_Motion"] = R('Y', 90.0 * e * sign)
    pose["Pelvis"] = R('Z', 6.0 * sign * math.sin(math.pi * t))
    for i, n in enumerate(SPINE_B[1:]):
        pose[n] = R('Z', -4.5 * sign * math.sin(math.pi * t))
    for i, n in enumerate(NECK_B):
        pose[n] = R('Z', -7.0 * sign * math.sin(math.pi * t) * (1.0 - 0.1 * i))
    _tail_wave(pose, t * 0.5, amp=14.0 * sign, speed=0.5, droop=0.0)
    for s in "LR":
        _wing_pose(pose, s, flap=3.0, fold=44.0, finger_fold=50.0)
    fwd = Vector((0.0, 0.0, -1.0))
    tg = {}
    steps = {"legF_L": 0.0, "legR_R": 0.25, "legF_R": 0.5, "legR_L": 0.75}
    for key, ph in steps.items():
        base = rg.gait_targets(key, t + ph, 0.85, 0.66, 0.30, fwd)
        # adim ayni zamanda yana kayar
        lateral = 0.55 * sign * e * (1.0 if key.endswith("_R") else 0.7)
        base["ankle"] = base["ankle"] + Vector((lateral, 0.0, 0.0))
        tg[key] = base
    return pose, tg


def clip_turn_left(rg, t):
    return _turn(rg, t, 1.0)


def clip_turn_right(rg, t):
    return _turn(rg, t, -1.0)


def _tucked_legs(rg, amount=1.0, t=0.0):
    tg = {}
    for key in LEG_BONES:
        ref = rg.leg_ref[key]
        back = 0.55 if key.startswith("legF") else 0.35
        tg[key] = {"ankle": ref["ankle"] + Vector((0.0, 1.55 * amount,
                                                   back * amount)),
                   "foot_dir": (ref["foot_dir"] + Vector((0.0, -0.9, 0.55))
                                * amount).normalized()}
    return tg


def clip_takeoff(rg, t):
    pose = {}
    crouch = math.sin(math.pi * clamp(t / 0.35, 0, 1)) * (1.0 - smoothstep(0.30, 0.55, t))
    launch = smoothstep(0.32, 0.78, t)
    pose["Root_Motion"] = Matrix.Translation(
        Vector((0.0, -0.55 * crouch + 3.4 * launch, -1.6 * launch))) @ R('X', -12.0 * launch)
    for i, n in enumerate(SPINE_B):
        pose[n] = R('X', 5.0 * crouch - 4.0 * launch)
    for i, n in enumerate(NECK_B):
        pose[n] = R('X', -6.0 * crouch + 7.0 * launch)
    _tail_wave(pose, t * 0.6, amp=6.0, speed=0.6, droop=-8.0 * launch)
    fl = -30.0 + 95.0 * math.sin(math.pi * clamp((t - 0.30) / 0.60, 0, 1))
    for s in "LR":
        _wing_pose(pose, s, flap=lerp(-4.0, fl, launch),
                   fold=lerp(46.0, 4.0, smoothstep(0.05, 0.45, t)),
                   finger_fold=lerp(52.0, 3.0, smoothstep(0.05, 0.45, t)))
    pose["Jaw"] = R('X', 14.0 * crouch)
    tg = {}
    ground = rg.gait_targets
    for key in LEG_BONES:
        ref = rg.leg_ref[key]
        tuck = smoothstep(0.42, 0.95, t)
        tg[key] = {"ankle": ref["ankle"] + Vector((0.0, -0.30 * crouch + 1.5 * tuck,
                                                   0.45 * tuck)),
                   "foot_dir": (ref["foot_dir"] + Vector((0.0, -0.8, 0.5)) * tuck).normalized()}
    return pose, tg


def _flight(rg, t, amp, base_fold, body_amp, speed=1.0, glide=False):
    pose = {}
    ph = TAU * speed * t
    flap = (0.0 if glide else amp * math.sin(ph))
    pose["Root_Motion"] = Matrix.Translation(
        Vector((0.0, body_amp * math.sin(ph - 0.9), 0.0))) @ R('X', -6.0 + 2.0 * math.sin(ph))
    for i, n in enumerate(SPINE_B):
        pose[n] = R('X', 1.5 * math.sin(ph - 0.3 * i))
    for i, n in enumerate(NECK_B):
        pose[n] = R('X', 3.0 - 2.0 * math.sin(ph - 0.4 * i))
    _tail_wave(pose, t * speed, amp=5.0, speed=1.0, droop=-6.0)
    for s in "LR":
        tw = (0.0 if glide else 12.0 * math.sin(ph - 1.1))
        ff = base_fold + (0.0 if glide else 14.0 * max(0.0, -math.sin(ph)))
        _wing_pose(pose, s, flap=flap, fold=base_fold * 0.25, twist=tw,
                   finger_fold=ff)
    return pose, _tucked_legs(rg, 1.0)


def clip_flight_forward(rg, t):
    return _flight(rg, t, amp=42.0, base_fold=8.0, body_amp=0.28, speed=1.0)


def clip_flight_glide(rg, t):
    p, tg = _flight(rg, t, amp=0.0, base_fold=4.0, body_amp=0.06, speed=0.25,
                    glide=True)
    for s in "LR":
        _wing_pose(p, s, flap=6.0 + 1.5 * math.sin(TAU * t * 0.25), fold=2.0,
                   finger_fold=2.0)
    return p, tg


def clip_flight_hover(rg, t):
    return _flight(rg, t, amp=54.0, base_fold=14.0, body_amp=0.34, speed=1.0)


def clip_landing(rg, t):
    pose = {}
    a = smoothstep(0.0, 0.55, t)
    b = smoothstep(0.50, 1.0, t)
    pose["Root_Motion"] = Matrix.Translation(
        Vector((0.0, 2.6 * (1.0 - a) - 0.30 * math.sin(math.pi * b), 0.0))) \
        @ R('X', 16.0 * (1.0 - a) - 3.0 * b)
    for n in SPINE_B:
        pose[n] = R('X', -6.0 * (1.0 - a) + 4.0 * math.sin(math.pi * b))
    for i, n in enumerate(NECK_B):
        pose[n] = R('X', 8.0 * (1.0 - a) - 5.0 * b)
    _tail_wave(pose, t * 0.5, amp=8.0, speed=0.5, droop=-10.0 * (1.0 - a))
    for s in "LR":
        _wing_pose(pose, s, flap=lerp(75.0, -6.0, b), fold=lerp(6.0, 44.0, b),
                   finger_fold=lerp(4.0, 50.0, b))
    tg = {}
    for key in LEG_BONES:
        ref = rg.leg_ref[key]
        reach = 1.0 - smoothstep(0.30, 0.70, t)
        tg[key] = {"ankle": ref["ankle"] + Vector((0.0, 1.30 * reach
                                                   - 0.22 * math.sin(math.pi * b), 0.0)),
                   "foot_dir": ref["foot_dir"]}
    return pose, tg


def _wing_state(rg, t, a, b):
    pose = {}
    e = smoothstep(0.0, 1.0, t)
    fold = lerp(a, b, e)
    for s in "LR":
        _wing_pose(pose, s, flap=lerp(2.0, -2.0, e) if b > a else lerp(-2.0, 2.0, e),
                   fold=fold, finger_fold=fold + 6.0)
    _tail_wave(pose, t * 0.4, amp=4.0, speed=0.4, droop=1.0)
    return pose, _idle_legs(rg, pose)


def clip_wing_fold(rg, t):
    return _wing_state(rg, t, 4.0, 48.0)


def clip_wing_unfold(rg, t):
    return _wing_state(rg, t, 48.0, 4.0)


def clip_roar(rg, t):
    pose = {}
    rear = math.sin(math.pi * smoothstep(0.0, 0.42, t)) * (1.0 - smoothstep(0.72, 1.0, t))
    open_j = smoothstep(0.22, 0.42, t) * (1.0 - smoothstep(0.78, 0.96, t))
    shake = math.sin(TAU * t * 9.0) * open_j
    pose["Root_Motion"] = Matrix.Translation(Vector((0.0, 0.12 * rear, 0.10 * rear)))
    for n in SPINE_B:
        pose[n] = R('X', 6.0 * rear)
    for i, n in enumerate(NECK_B):
        pose[n] = R('X', -13.0 * rear + 1.2 * shake) @ R('Z', 1.0 * shake)
    pose["Head"] = R('X', -22.0 * rear + 2.0 * shake)
    pose["Jaw"] = R('X', 6.0 + 46.0 * open_j + 2.5 * shake)
    pose["Tongue_01"] = R('X', -12.0 * open_j)
    pose["Tongue_02"] = R('X', -16.0 * open_j)
    _tail_wave(pose, t * 0.7, amp=12.0, speed=0.7, droop=-4.0 * rear)
    for s in "LR":
        _wing_pose(pose, s, flap=lerp(-2.0, 46.0, rear),
                   fold=lerp(46.0, 10.0, rear), finger_fold=lerp(52.0, 12.0, rear))
    tg = _idle_legs(rg, pose)
    for key in ("legF_L", "legF_R"):
        tg[key]["ankle"] = tg[key]["ankle"] + Vector((0.0, 0.0, -0.18 * rear))
    return pose, tg


def clip_bite(rg, t):
    pose = {}
    wind = math.sin(math.pi * smoothstep(0.0, 0.30, t)) * (1.0 - smoothstep(0.30, 0.52, t))
    lunge = smoothstep(0.28, 0.58, t) * (1.0 - smoothstep(0.72, 1.0, t))
    snap = smoothstep(0.46, 0.60, t)
    jaw = 44.0 * (smoothstep(0.10, 0.44, t) * (1.0 - snap)) + 2.0
    pose["Root_Motion"] = Matrix.Translation(Vector((0.0, 0.0, -0.55 * lunge)))
    for n in SPINE_B:
        pose[n] = R('X', 3.0 * wind - 4.0 * lunge)
    for i, n in enumerate(NECK_B):
        pose[n] = R('X', -9.0 * wind + 12.0 * lunge)
    pose["Head"] = R('X', -8.0 * wind + 14.0 * lunge)
    pose["Jaw"] = R('X', jaw)
    _tail_wave(pose, t * 0.6, amp=9.0, speed=0.6, droop=2.0)
    for s in "LR":
        _wing_pose(pose, s, flap=8.0 * lunge, fold=lerp(46.0, 30.0, lunge),
                   finger_fold=lerp(52.0, 36.0, lunge))
    tg = _idle_legs(rg, pose)
    for key in ("legF_L", "legF_R"):
        tg[key]["ankle"] = tg[key]["ankle"] + Vector((0.0, 0.0, -0.35 * lunge))
    return pose, tg


def _claw(rg, t, side):
    pose = {}
    s = 1.0 if side == "L" else -1.0
    wind = math.sin(math.pi * smoothstep(0.0, 0.32, t)) * (1.0 - smoothstep(0.30, 0.50, t))
    strike = smoothstep(0.30, 0.56, t) * (1.0 - smoothstep(0.78, 1.0, t))
    pose["Root_Motion"] = R('Y', -8.0 * s * wind + 12.0 * s * strike)
    for i, n in enumerate(SPINE_B):
        pose[n] = R('Z', (-4.0 * wind + 6.0 * strike) * s) @ R('X', -3.0 * strike)
    for i, n in enumerate(NECK_B):
        pose[n] = R('Z', (5.0 * wind - 7.0 * strike) * s) @ R('X', 4.0 * strike)
    pose["Jaw"] = R('X', 10.0 * strike)
    _tail_wave(pose, t * 0.6, amp=10.0, speed=0.6, droop=0.0)
    for w in "LR":
        _wing_pose(pose, w, flap=10.0 * strike, fold=lerp(46.0, 28.0, strike),
                   finger_fold=lerp(52.0, 34.0, strike))
    key = "legF_L" if side == "L" else "legF_R"
    tg = _idle_legs(rg, pose)
    ref = rg.leg_ref[key]
    lift = 1.65 * (wind * 0.55 + strike)
    swing = -1.75 * strike + 0.55 * wind
    tg[key] = {"ankle": ref["ankle"] + Vector((0.65 * s * wind, lift, swing)),
               "foot_dir": (ref["foot_dir"] + Vector((0.25 * s, -0.55, -0.85))
                            * (wind + strike)).normalized()}
    return pose, tg


def clip_claw_left(rg, t):
    return _claw(rg, t, "L")


def clip_claw_right(rg, t):
    return _claw(rg, t, "R")


def clip_tail_attack(rg, t):
    pose = {}
    wind = math.sin(math.pi * smoothstep(0.0, 0.34, t)) * (1.0 - smoothstep(0.32, 0.50, t))
    whip = smoothstep(0.30, 0.62, t) * (1.0 - smoothstep(0.80, 1.0, t))
    pose["Root_Motion"] = R('Y', 6.0 * wind - 9.0 * whip)
    pose["Pelvis"] = R('Z', 8.0 * wind - 12.0 * whip)
    for i, n in enumerate(SPINE_B[1:]):
        pose[n] = R('Z', (5.0 * wind - 8.0 * whip) * (1.0 - 0.12 * i))
    for i, n in enumerate(NECK_B):
        pose[n] = R('Z', -6.0 * wind + 9.0 * whip)
    for i, n in enumerate(TAIL_B):
        lag = clamp(t - 0.055 * i, 0.0, 1.0)
        w2 = math.sin(math.pi * smoothstep(0.0, 0.34, lag)) * (1.0 - smoothstep(0.32, 0.50, lag))
        p2 = smoothstep(0.30, 0.62, lag) * (1.0 - smoothstep(0.80, 1.0, lag))
        pose[n] = R('Z', 16.0 * w2 - 26.0 * p2) @ R('X', 3.0 * p2)
    for s in "LR":
        _wing_pose(pose, s, flap=6.0 * whip, fold=lerp(46.0, 36.0, whip),
                   finger_fold=lerp(52.0, 42.0, whip))
    return pose, _idle_legs(rg, pose)


def clip_hit(rg, t):
    pose = {}
    k = math.exp(-4.5 * t) * math.sin(TAU * 3.4 * t)
    pose["Root_Motion"] = Matrix.Translation(Vector((0.10 * k, 0.06 * k, 0.22 * k))) \
        @ R('X', 7.0 * k)
    for i, n in enumerate(SPINE_B):
        pose[n] = R('X', -6.0 * k) @ R('Z', 4.0 * k * (1 - 0.1 * i))
    for i, n in enumerate(NECK_B):
        pose[n] = R('X', 9.0 * k) @ R('Z', -5.0 * k)
    pose["Jaw"] = R('X', 16.0 * max(0.0, k))
    _tail_wave(pose, t, amp=12.0 * abs(k), speed=1.5, droop=0.0)
    for s in "LR":
        _wing_pose(pose, s, flap=-4.0 + 16.0 * abs(k), fold=44.0, finger_fold=50.0)
    return pose, _idle_legs(rg, pose)


def clip_death(rg, t):
    pose = {}
    stagger = math.sin(math.pi * smoothstep(0.0, 0.30, t)) * (1.0 - smoothstep(0.26, 0.42, t))
    fall = smoothstep(0.30, 0.74, t)
    settle = smoothstep(0.70, 1.0, t)
    pose["Root_Motion"] = Matrix.Translation(
        Vector((0.9 * fall, -1.85 * fall - 0.10 * settle, 0.25 * stagger))) \
        @ R('Z', -34.0 * fall) @ R('X', 6.0 * stagger - 4.0 * fall)
    for i, n in enumerate(SPINE_B):
        pose[n] = R('Z', 6.0 * stagger - 9.0 * fall) @ R('X', -5.0 * fall)
    for i, n in enumerate(NECK_B):
        pose[n] = R('X', -8.0 * stagger + 16.0 * fall + 4.0 * settle) \
            @ R('Z', 7.0 * fall)
    pose["Head"] = R('X', 20.0 * fall + 8.0 * settle)
    pose["Jaw"] = R('X', 8.0 + 14.0 * fall - 8.0 * settle)
    for i, n in enumerate(TAIL_B):
        lag = clamp((t - 0.05 * i) * 1.15, 0.0, 1.0)
        pose[n] = R('Z', -12.0 * smoothstep(0.3, 0.9, lag)) \
            @ R('X', 4.0 * smoothstep(0.35, 0.95, lag))
    for s, sg in (("L", 1.0), ("R", -1.0)):
        _wing_pose(pose, s, flap=lerp(-2.0, -26.0 if sg > 0 else 12.0, fall),
                   fold=lerp(46.0, 22.0, fall), finger_fold=lerp(52.0, 26.0, fall))
    tg = {}
    for key in LEG_BONES:
        ref = rg.leg_ref[key]
        collapse = fall
        tg[key] = {"ankle": ref["ankle"] + Vector((0.85 * collapse,
                                                   -0.55 * collapse,
                                                   0.35 * collapse)),
                   "foot_dir": ref["foot_dir"]}
    return pose, tg


CLIP_FN = {
    "Idle_Ground": clip_idle_ground,
    "Idle_Alert": clip_idle_alert,
    "Walk": clip_walk,
    "Run": clip_run,
    "Turn_Left_90": clip_turn_left,
    "Turn_Right_90": clip_turn_right,
    "Takeoff": clip_takeoff,
    "Flight_Forward": clip_flight_forward,
    "Flight_Glide": clip_flight_glide,
    "Flight_Hover": clip_flight_hover,
    "Landing": clip_landing,
    "Wing_Fold": clip_wing_fold,
    "Wing_Unfold": clip_wing_unfold,
    "Roar": clip_roar,
    "Bite_Attack": clip_bite,
    "Claw_Attack_Left": clip_claw_left,
    "Claw_Attack_Right": clip_claw_right,
    "Tail_Attack": clip_tail_attack,
    "Hit_Reaction": clip_hit,
    "Death": clip_death,
}


# ==================================================================
# BLENDER'A YAZMA
# ==================================================================
def bake_clips(arm_obj, bonedefs, legs, ground_y=0.0, fps=C.FPS,
               root_motion=True):
    import bpy
    rg = Rigger(bonedefs, legs, ground_y)
    made = []
    for name, dur, loop in C.ANIM_CLIPS:
        variants = [(name, 0.0)]
        if root_motion and name in C.ROOT_MOTION_CLIPS:
            variants.append((name + "_RM", C.ROOT_MOTION_CLIPS[name]))
        for clip_name, speed in variants:
            nframes = max(2, int(round(dur * fps)))
            act = bpy.data.actions.new(clip_name)
            act.use_fake_user = True
            arm_obj.animation_data_create()
            arm_obj.animation_data.action = act
            for pb in arm_obj.pose.bones:
                pb.rotation_mode = 'QUATERNION'
                pb.matrix_basis = Matrix.Identity(4)
            end = nframes if loop else nframes
            for f in range(end + 1):
                t = (f / nframes) if loop else (f / max(nframes, 1))
                if loop and f == nframes:
                    t = 0.0
                pose, targets = CLIP_FN[name](rg, clamp(t, 0.0, 1.0))
                rg.solve_legs(pose, targets)
                if speed > 0.0:
                    fwd = Vector((0.0, 0.0, -1.0)) * (speed * dur * t)
                    base = pose.get("Root_Motion", Matrix.Identity(4))
                    pose["Root_Motion"] = Matrix.Translation(fwd) @ base
                frame = f + 1
                for pb in arm_obj.pose.bones:
                    m = pose.get(pb.name)
                    if m is None:
                        pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
                        pb.location = (0.0, 0.0, 0.0)
                    else:
                        pb.rotation_quaternion = m.to_quaternion()
                        pb.location = m.to_translation()
                    pb.keyframe_insert("rotation_quaternion", frame=frame,
                                       group=pb.name)
                    if pb.name in ("Root_Motion", "Dragon_Root"):
                        pb.keyframe_insert("location", frame=frame, group=pb.name)
            for fc in act.fcurves:
                for kp in fc.keyframe_points:
                    kp.interpolation = 'BEZIER'
                    kp.handle_left_type = 'AUTO_CLAMPED'
                    kp.handle_right_type = 'AUTO_CLAMPED'
            act.frame_range  # tetikle
            made.append((clip_name, dur, loop))
            print("  anim:", clip_name, "%d frame" % (end + 1))
    arm_obj.animation_data.action = None
    return made
