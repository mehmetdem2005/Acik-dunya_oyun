"""Kurt HI-FI katmanı — round 122 anatomisini alır, hiper-real hedefe taşır.

NE YAPAR (gri kil → kürklü, yoğun, renkli):
  1. Tüm parçaları tek mesh'e birleştirir (kürk gövdeyi kesintisiz sarsın).
  2. Yüksek subsurf (render_levels) → milyon+ poligon.
  3. Displace (noise) → pürüzsüz yüzeye deri/kas/kürk mezo-kabartması.
  4. Gerçek kürk: particle HAIR sistemi + interpolated children (yoğun post).
  5. PBR agouti kürk materyali (noise ile koyu-açık varyasyon) + Principled Hair BSDF.
  6. 3-nokta ışık + Cycles CPU render.

Çalıştırma:
    blender --background --python kurt_hifi.py -- \
        [--subsurf 4] [--hair 20000] [--children 30] [--samples 28] \
        [--views three_q] [--tag hifi_01] [--save-blend]
"""

import argparse
import os
import sys

import bpy

DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, DIR)
import kurt_generator as G  # noqa: E402


def join_parts(parts):
    bpy.ops.object.select_all(action="DESELECT")
    for ob in parts:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = "Kurt"
    # birleşim sonrası modifier'ları temizle (subsurf'ları yeniden kuracağız)
    ob.modifiers.clear()
    return ob


def agouti_skin_material():
    """Deri/dip kürk rengi: noise ile koyu gri-kahve↔açık ton agouti varyasyon."""
    mat = bpy.data.materials.new("KurtDeri")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.88
    if "Specular" in bsdf.inputs:
        bsdf.inputs["Specular"].default_value = 0.25
    # agouti renk rampası
    tex = nt.nodes.new("ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value = 8.0
    tex.inputs["Detail"].default_value = 6.0
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.35
    ramp.color_ramp.elements[0].color = (0.045, 0.038, 0.032, 1)   # koyu kahve-gri
    ramp.color_ramp.elements[1].position = 0.72
    ramp.color_ramp.elements[1].color = (0.32, 0.28, 0.23, 1)       # açık tan
    nt.links.new(tex.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(bsdf.outputs[0], out.inputs[0])
    return mat


def hair_material():
    """Kürk teli: Principled Hair BSDF, agouti kahve-gri."""
    mat = bpy.data.materials.new("KurtKil")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    try:
        h = nt.nodes.new("ShaderNodeBsdfHairPrincipled")
        # renk
        if "Color" in h.inputs:
            h.inputs["Color"].default_value = (0.14, 0.115, 0.092, 1)
        if "Roughness" in h.inputs:
            h.inputs["Roughness"].default_value = 0.55
    except Exception:
        h = nt.nodes.new("ShaderNodeBsdfHair")
    nt.links.new(h.outputs[0], out.inputs[0])
    return mat


def add_displace_relief(ob):
    tex = bpy.data.textures.new("furrelief", "CLOUDS")
    tex.noise_scale = 0.05
    tex.noise_depth = 3
    m = ob.modifiers.new("relief", "DISPLACE")
    m.texture = tex
    m.strength = 0.010
    m.mid_level = 0.5


def add_subsurf_hi(ob, view_lvl, render_lvl):
    m = ob.modifiers.new("subsurf", "SUBSURF")
    m.levels = view_lvl
    m.render_levels = render_lvl


def add_fur(ob, count, children, length=0.055):
    mod = ob.modifiers.new("Fur", "PARTICLE_SYSTEM")
    ps = ob.particle_systems[mod.name]
    s = ps.settings
    s.type = "HAIR"
    s.count = count
    s.hair_length = length
    s.use_advanced_hair = True
    s.hair_step = 4
    s.use_hair_bspline = True
    # incelen tel
    try:
        s.root_radius = 0.0010
        s.tip_radius = 0.0
        s.shape = 0.3
    except Exception:
        pass
    # uzunluk varyasyonu
    s.factor_random = 0.5
    # children (yoğunluk)
    s.child_type = "INTERPOLATED"
    s.child_percent = max(2, children // 4)
    s.rendered_child_count = children
    try:
        s.clump_factor = 0.45
        s.roughness_endpoint = 0.18
        s.roughness_end_shape = 1.0
        s.roughness_2 = 0.12
    except Exception:
        pass
    # kürk materyali = 2. slot
    try:
        s.material = 2
    except Exception:
        pass
    return ps


def setup_cycles(samples, w, h):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = False
    sc.render.resolution_x = w
    sc.render.resolution_y = h
    world = bpy.data.worlds.new("W")
    sc.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.045, 0.05, 0.06, 1.0)
    bg.inputs[1].default_value = 0.6


def add_lights():
    for loc, e, sz in (((2.4, -2.2, 2.6), 900, 1.4),
                       ((-2.4, -1.4, 1.0), 280, 2.2),
                       ((0.0, 2.8, 2.0), 520, 1.0)):
        bpy.ops.object.light_add(type="AREA", location=loc)
        L = bpy.context.object
        L.data.energy = e
        L.data.size = sz


VIEWS = {
    "side":    (2.7, 0.25, 0.55),
    "front":   (0.0, -2.7, 0.5),
    "three_q": (1.9, -1.9, 0.7),
    "top":     (0.0, 0.25, 2.7),
    "rear_q":  (1.9, 1.9, 0.7),
}


def render_views(view_names, tag):
    sc = bpy.context.scene
    aim = bpy.data.objects.new("aim", None)
    sc.collection.objects.link(aim)
    aim.location = (0, 0.2, 0.5)
    bpy.ops.object.camera_add()
    cam = bpy.context.object
    cam.data.lens = 55
    sc.camera = cam
    c = cam.constraints.new("TRACK_TO")
    c.target = aim
    c.track_axis = "TRACK_NEGATIVE_Z"
    c.up_axis = "UP_Y"
    os.makedirs(os.path.join(DIR, "renders"), exist_ok=True)
    for name in view_names:
        cam.location = VIEWS[name]
        bpy.context.view_layer.update()
        fp = os.path.join(DIR, "renders", f"{tag}_{name}.png")
        sc.render.filepath = fp
        import time
        t0 = time.time()
        bpy.ops.render.render(write_still=True)
        print(f"RENDERED {fp}  ({time.time()-t0:.1f}s)")


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--params", default=os.path.join(DIR, "wolf_params.json"))
    p.add_argument("--subsurf", type=int, default=4)
    p.add_argument("--hair", type=int, default=20000)
    p.add_argument("--children", type=int, default=30)
    p.add_argument("--length", type=float, default=0.055)
    p.add_argument("--samples", type=int, default=28)
    p.add_argument("--width", type=int, default=800)
    p.add_argument("--height", type=int, default=640)
    p.add_argument("--views", default="three_q")
    p.add_argument("--tag", default="hifi_01")
    p.add_argument("--save-blend", action="store_true")
    return p.parse_args(argv)


def main():
    a = parse_args()
    P = G.load_params(a.params)
    G.fresh_scene()
    parts = G.build_wolf(P)
    ob = join_parts(parts)

    # materyaller: slot1 deri, slot2 kürk
    ob.data.materials.clear()
    ob.data.materials.append(agouti_skin_material())
    ob.data.materials.append(hair_material())

    add_displace_relief(ob)
    add_subsurf_hi(ob, view_lvl=min(2, a.subsurf), render_lvl=a.subsurf)
    add_fur(ob, a.hair, a.children, a.length)

    # poligon raporu (render seviyesinde)
    deps = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(deps)
    me = ev.to_mesh()
    print(f"=== {a.tag}: yüzey {len(me.polygons)} poligon (subsurf {a.subsurf}), "
          f"kürk {a.hair} parent x {a.children} child ===")
    ev.to_mesh_clear()

    if a.save_blend:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(DIR, "kurt_hifi.blend"))

    setup_cycles(a.samples, a.width, a.height)
    add_lights()
    render_views(a.views.split(","), a.tag)


if __name__ == "__main__":
    main()
