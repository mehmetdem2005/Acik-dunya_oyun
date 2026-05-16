@tool
class_name PineSkeleton
extends RefCounted

# Özyinelemeli konifer iskeleti (Blender Sapling mantığı).
# Gövde -> ana dal -> yan sürgün. Her stem bir spline'dır; çocuklar
# rotation-minimizing frame (RMF) ile yerleştirilir (kontrolsüz twist yok).
# Yerçekimi (gravitropizm) + ışığa yönelim (fototropizm) + altın açı.
#
# Stem sözlüğü:
# {
#   level:int, points:Array[Vector3], tangents:Array[Vector3],
#   normals:Array[Vector3], radius0:float, radius1:float,
#   parent:int, depth01:float   # taçtaki normalize derinlik (AO için)
# }

const GOLDEN := 2.399963229728653

var _rng := RandomNumberGenerator.new()
var stems: Array = []

func build(cfg: Dictionary) -> Array:
	stems.clear()
	_rng.seed = int(cfg.get("seed", 12345))
	var trunk := _make_trunk(cfg)
	stems.append(trunk)
	var trunk_idx := stems.size() - 1
	_spawn_level1(cfg, trunk, trunk_idx)
	return stems

# --- Gövde -------------------------------------------------------------

func _make_trunk(cfg: Dictionary) -> Dictionary:
	var height: float = cfg.get("height", 7.0)
	var bend: float = cfg.get("trunk_bend", 0.04)
	var segs := 16
	var pts: Array[Vector3] = []
	var phase := _rng.randf() * TAU
	for i in range(segs + 1):
		var t := float(i) / float(segs)
		var sway := bend * height * t * t
		var x := sin(t * 1.5 + phase) * sway
		var z := cos(t * 1.1 + phase) * sway * 0.6
		pts.append(Vector3(x, t * height, z))
	var stem := _frame_stem(pts, 0, -1, 0.0)
	stem["radius0"] = float(cfg.get("trunk_radius", 0.16))
	stem["radius1"] = float(cfg.get("trunk_radius", 0.16)) * float(cfg.get("trunk_top", 0.06))
	return stem

# --- Seviye 1: ana dallar (whorl tabakaları) --------------------------

func _spawn_level1(cfg: Dictionary, trunk: Dictionary, trunk_idx: int) -> void:
	var height: float = cfg.get("height", 7.0)
	var crown_start: float = cfg.get("crown_start", 0.13)
	var crown_radius: float = cfg.get("crown_radius", 2.4)
	var total: int = int(cfg.get("branch_count", 60))
	var droop: float = cfg.get("branch_droop", 0.55)
	var tier_count: int = clampi(int(round(height * 2.2)), 9, 20)
	var az := _rng.randf() * TAU
	for ti in range(tier_count):
		var tf := float(ti) / float(tier_count - 1)
		var h01: float = lerp(crown_start, 0.955, tf)
		var prof: float = pow(1.0 - tf, 0.80) * (0.45 + 0.55 * smoothstep(0.0, 0.18, tf))
		var blen := crown_radius * prof
		if blen < 0.18:
			continue
		var per := int(round(lerp(float(total) / float(tier_count) * 1.5, 3.0, tf)))
		per = clampi(per, 3, 10)
		az += GOLDEN * 1.3
		for bi in range(per):
			var a := az + TAU * float(bi) / float(per) + _rng.randf_range(-0.16, 0.16)
			var sp := _sample(trunk, h01 + _rng.randf_range(-0.012, 0.012))
			# Dal: gövdeden hafif yukarı çıkışlı, uca doğru yerçekimiyle düşen.
			var up0: float = lerp(0.32, 0.05, tf)
			var dir := (Vector3(cos(a), 0.0, sin(a)) + Vector3.UP * up0).normalized()
			var L := blen * _rng.randf_range(0.82, 1.14)
			var grav := droop * (0.4 + 0.6 * (1.0 - tf))
			var child := _grow(sp, dir, L, 6, grav, 0.04, 0.12)
			child["level"] = 1
			child["parent"] = trunk_idx
			child["depth01"] = tf
			child["radius0"] = float(cfg.get("trunk_radius", 0.16)) * 0.26
			child["radius1"] = 0.004
			stems.append(child)
			var bidx := stems.size() - 1
			_spawn_level2(cfg, child, bidx, tf)
	# Apeks: tepede dik, kısa lider sürgünler -> doğal sivri uç.
	for ai in range(5):
		var ah: float = lerp(0.93, 0.995, float(ai) / 4.0)
		var sp := _sample(trunk, ah)
		var aa := _rng.randf() * TAU
		var adir := (Vector3(cos(aa), 0, sin(aa)) * 0.25 + Vector3.UP).normalized()
		var al := crown_radius * 0.20 * (1.0 - float(ai) / 6.0)
		var ac := _grow(sp, adir, maxf(al, 0.18), 4, 0.06, 0.10, 0.05)
		ac["level"] = 1
		ac["parent"] = trunk_idx
		ac["depth01"] = 1.0
		ac["radius0"] = float(cfg.get("trunk_radius", 0.16)) * 0.18
		ac["radius1"] = 0.003
		stems.append(ac)
		_spawn_level2(cfg, ac, stems.size() - 1, 0.95)

# --- Seviye 2: yan sürgünler (iğneleri taşır) -------------------------

func _spawn_level2(cfg: Dictionary, parent: Dictionary, pidx: int, tf: float) -> void:
	var shoots: int = int(cfg.get("shoots_per_branch", 7))
	var az := _rng.randf() * TAU
	for si in range(shoots):
		var u: float = lerp(0.18, 0.95, float(si) / float(maxi(shoots - 1, 1)))
		var sp := _sample(parent, u)
		az += GOLDEN
		var pt := _tangent_at(parent, u)
		var nm := _normal_at(parent, u)
		var azdir := nm.rotated(pt, az)
		var down := deg_to_rad(_rng.randf_range(38.0, 60.0))
		var dir := (pt * cos(down) + azdir * sin(down)).normalized()
		var L: float = parent["len"] * lerp(0.55, 0.25, u) * _rng.randf_range(0.8, 1.15)
		if L < 0.12:
			continue
		var child := _grow(sp, dir, L, 4, 0.35 + 0.4 * tf, 0.08, 0.10)
		child["level"] = 2
		child["parent"] = pidx
		child["depth01"] = tf
		child["radius0"] = 0.006
		child["radius1"] = 0.002
		stems.append(child)

# --- Büyüme entegrasyonu ----------------------------------------------

func _grow(start: Vector3, dir0: Vector3, length: float, segs: int,
		grav: float, photo: float, curve: float) -> Dictionary:
	var pts: Array[Vector3] = [start]
	var dir := dir0.normalized()
	var pos := start
	var seg_len := length / float(segs)
	var curve_ax := dir.cross(Vector3.UP).normalized()
	if curve_ax.length() < 0.01:
		curve_ax = Vector3.RIGHT
	for s in range(segs):
		pos += dir * seg_len
		pts.append(pos)
		var f := float(s + 1) / float(segs)
		dir = (dir + Vector3.DOWN * grav * f + Vector3.UP * photo).normalized()
		dir = dir.rotated(curve_ax, curve * 0.5).normalized()
	var stem := _frame_stem(pts, 1, -1, 0.0)
	stem["len"] = length
	return stem

# --- Frame (RMF / çift yansıma) ---------------------------------------

func _frame_stem(pts: Array, level: int, parent: int, depth01: float) -> Dictionary:
	var n := pts.size()
	var tang: Array[Vector3] = []
	for i in range(n):
		var t: Vector3
		if i == 0:
			t = (pts[1] - pts[0])
		elif i == n - 1:
			t = (pts[n - 1] - pts[n - 2])
		else:
			t = (pts[i + 1] - pts[i - 1])
		if t.length() < 1e-5:
			t = Vector3.UP
		tang.append(t.normalized())

	var norms: Array[Vector3] = []
	norms.resize(n)
	var t0 := tang[0]
	var up := Vector3.UP if absf(t0.y) < 0.99 else Vector3.RIGHT
	var r := (up - t0 * up.dot(t0)).normalized()
	norms[0] = r
	for i in range(n - 1):
		var v1: Vector3 = pts[i + 1] - pts[i]
		var c1: float = v1.dot(v1)
		if c1 < 1e-9:
			norms[i + 1] = norms[i]
			continue
		var rl: Vector3 = r - (2.0 / c1) * v1.dot(r) * v1
		var ti: Vector3 = tang[i]
		var tl: Vector3 = ti - (2.0 / c1) * v1.dot(ti) * v1
		var v2: Vector3 = tang[i + 1] - tl
		var c2: float = v2.dot(v2)
		if c2 < 1e-9:
			r = rl
		else:
			r = rl - (2.0 / c2) * v2.dot(rl) * v2
		r = r.normalized()
		norms[i + 1] = r

	return {
		"level": level, "parent": parent, "depth01": depth01,
		"points": pts, "tangents": tang, "normals": norms,
		"radius0": 0.05, "radius1": 0.01, "len": 0.0,
	}

# --- Örnekleme yardımcıları -------------------------------------------

func _sample(stem: Dictionary, u: float) -> Vector3:
	var pts: Array = stem["points"]
	var n := pts.size()
	var f: float = clampf(u, 0.0, 1.0) * float(n - 1)
	var i: int = clampi(int(f), 0, n - 2)
	return (pts[i] as Vector3).lerp(pts[i + 1], f - float(i))

func _tangent_at(stem: Dictionary, u: float) -> Vector3:
	var arr: Array = stem["tangents"]
	var n := arr.size()
	var i: int = clampi(int(clampf(u, 0.0, 1.0) * float(n - 1)), 0, n - 1)
	return arr[i]

func _normal_at(stem: Dictionary, u: float) -> Vector3:
	var arr: Array = stem["normals"]
	var n := arr.size()
	var i: int = clampi(int(clampf(u, 0.0, 1.0) * float(n - 1)), 0, n - 1)
	return arr[i]
