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
	_spawn_roots(cfg, trunk, trunk_idx)
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
	stem["whorl_h"] = PackedFloat32Array()
	return stem

# --- Seviye 1: ana dallar (whorl tabakaları) --------------------------

func _spawn_level1(cfg: Dictionary, trunk: Dictionary, trunk_idx: int) -> void:
	var height: float = cfg.get("height", 7.0)
	var crown_start: float = cfg.get("crown_start", 0.13)
	var crown_radius: float = cfg.get("crown_radius", 2.4)
	var total: int = int(cfg.get("branch_count", 60))
	var droop: float = cfg.get("branch_droop", 0.55)
	var tr: float = float(cfg.get("trunk_radius", 0.16))
	var elev_low: float = float(cfg.get("elev_low", -0.18))
	var elev_high: float = float(cfg.get("elev_high", 0.55))
	var prune_low: float = float(cfg.get("prune_low", 0.30))
	var prune_high: float = float(cfg.get("prune_high", 0.04))
	var dry_low: float = float(cfg.get("dry_chance_low", 0.16))
	var broken_ch: float = float(cfg.get("broken_chance", 0.08))
	var tip_ratio: float = float(cfg.get("branch_taper_tip", 0.18))
	var whorl_gap: float = maxf(float(cfg.get("whorl_gap", 1.0)), 0.3)
	var dal_seg: int = int(cfg.get("dal_segment", 10))
	var dal_yay: float = float(cfg.get("dal_yay", 0.16))
	# Daha seyrek, belirgin whorl katmanları (açık koni silüet).
	var tier_count: int = clampi(int(round(height * 0.95 / whorl_gap)), 6, 10)
	var lean: float = _rng.randf_range(-0.12, 0.12)
	var lean_ph: float = _rng.randf() * TAU
	var whorl_h: PackedFloat32Array = trunk["whorl_h"]
	var az := _rng.randf() * TAU
	for ti in range(tier_count):
		var tf := float(ti) / float(tier_count - 1)
		var h01: float = clampf(lerp(crown_start, 0.95, tf) + _rng.randf_range(-0.012, 0.012), 0.0, 1.0)
		# Koni: tepeye doğru tek-yönlü güçlü kısalma (orta şişlik yok).
		var prof: float = pow(1.0 - tf, 0.9)
		var blen := crown_radius * prof
		if blen < 0.16:
			continue
		whorl_h.append(h01)
		var per := int(round(lerp(float(total) / float(tier_count) * 1.05, 3.0, tf)))
		per = clampi(per + _rng.randi_range(-1, 1), 3, 7)
		az += GOLDEN * 1.3
		var aaccum := az
		var seg := TAU / float(per)
		for bi in range(per):
			# TÜM per-dal rastgele değerleri continue'dan ÖNCE (determinizm).
			aaccum += seg * _rng.randf_range(0.45, 1.75)
			var ajit: float = _rng.randf_range(-0.15, 0.15)
			var up_jit: float = _rng.randf_range(-0.10, 0.10)
			var lvar: float = _rng.randf_range(0.75, 1.30)
			var rjit: float = _rng.randf_range(0.90, 1.10)
			var tipr: float = _rng.randf_range(0.10, 0.25)
			var tvar: float = _rng.randf_range(0.93, 1.07)
			var brk_mul: float = _rng.randf_range(0.4, 0.7)
			var wob: float = _rng.randf_range(-1.0, 1.0)
			var is_dry: bool = _rng.randf() < lerp(dry_low, 0.02, tf)
			var is_broken: bool = _rng.randf() < broken_ch
			var miss: bool = _rng.randf() < lerp(prune_low, prune_high, tf)
			if miss:
				continue
			var a: float = aaccum + ajit + lean * cos(aaccum - lean_ph)
			var sp := _sample(trunk, h01)
			# Yükseklik-bölgeli açı: alt yatay/sarkık, üst dik (koni).
			var up0: float = lerp(elev_low, elev_high, pow(tf, 0.7)) + up_jit
			var dir := (Vector3(cos(a), 0.0, sin(a)) + Vector3.UP * up0).normalized()
			var L: float = blen * lvar
			if is_broken:
				L *= brk_mul
			# Alt tier'ler sert süpürür, üst tier'ler dik durur.
			var grav := droop * (0.55 + 1.1 * (1.0 - tf))
			var child := _grow(sp, dir, L, dal_seg, grav, 0.05, dal_yay, wob)
			var age := 1.0 - tf
			var r0v: float = tr * lerp(0.08, 0.20, age) * rjit
			child["level"] = 1
			child["parent"] = trunk_idx
			child["depth01"] = tf
			child["age"] = age
			child["dry"] = is_dry
			child["broken"] = is_broken
			child["tint"] = lerp(0.72, 1.10, age * age) * tvar
			child["radius0"] = r0v
			# Güçlü güç-yasası incelme (uç gerçekten incelir, min koru).
			child["radius1"] = maxf(r0v * pow(maxf(tip_ratio, 0.01), 1.4) * (0.6 + 0.8 * tipr), 0.006)
			stems.append(child)
			var bidx := stems.size() - 1
			if not is_dry:
				_spawn_level2(cfg, child, bidx, tf, age)
	# PackedFloat32Array değer tipidir -> budak yükseklikleri geri yazılır.
	trunk["whorl_h"] = whorl_h
	# Apeks: tepede dik, kısa lider sürgünler -> doğal sivri uç.
	for ai in range(5):
		var ah: float = lerp(0.93, 0.995, float(ai) / 4.0)
		var sp := _sample(trunk, ah)
		var aa := _rng.randf() * TAU
		var awob := _rng.randf_range(-1.0, 1.0)
		var adir := (Vector3(cos(aa), 0, sin(aa)) * 0.25 + Vector3.UP).normalized()
		var al := crown_radius * 0.20 * (1.0 - float(ai) / 6.0)
		var ac := _grow(sp, adir, maxf(al, 0.18), 4, 0.06, 0.10, 0.05, awob)
		ac["level"] = 1
		ac["parent"] = trunk_idx
		ac["depth01"] = 1.0
		ac["age"] = 0.05
		ac["dry"] = false
		ac["broken"] = false
		ac["tint"] = _rng.randf_range(0.95, 1.15)
		ac["radius0"] = tr * 0.10
		ac["radius1"] = tr * 0.10 * 0.22
		stems.append(ac)
		_spawn_level2(cfg, ac, stems.size() - 1, 0.95, 0.05)

# --- Kök payandası: dipte zemine yayılan kısa, kalın, kıvrımlı kökler -
# level=1 + is_root: mesh bunları KABUK surface'ine plain tube olarak
# basar (gövdeyle materyal sürekliliği; lvl0 dip/lob koduna girmez).
# build()'de _spawn_level1 SONRASI çağrılır -> RNG sırası en sonda.

func _spawn_roots(cfg: Dictionary, trunk: Dictionary, trunk_idx: int) -> void:
	var rc: int = int(cfg.get("root_count", 5))
	if rc <= 0:
		return
	var tr: float = float(cfg.get("trunk_radius", 0.16))
	var dal_seg: int = int(cfg.get("dal_segment", 10))
	var base := _sample(trunk, 0.0)
	var a0 := _rng.randf() * TAU
	for ri in range(rc):
		var ajit: float = _rng.randf_range(-0.30, 0.30)
		var spread: float = _rng.randf_range(0.55, 0.85)
		var lmul: float = _rng.randf_range(1.4, 2.2)
		var rmul: float = _rng.randf_range(0.85, 1.15)
		var tnt: float = _rng.randf_range(0.70, 0.95)
		var wob: float = _rng.randf_range(-1.0, 1.0)
		var a: float = a0 + TAU * float(ri) / float(rc) + ajit
		var dir := (Vector3(cos(a), 0.0, sin(a)) * spread + Vector3.DOWN * 1.3).normalized()
		var rt := _grow(base, dir, tr * lmul, maxi(4, int(dal_seg / 2)), 0.35, 0.0, 0.06, wob)
		rt["level"] = 1
		rt["is_root"] = true
		rt["parent"] = trunk_idx
		rt["depth01"] = 0.0
		rt["age"] = 1.0
		rt["dry"] = false
		rt["broken"] = false
		rt["tint"] = tnt
		rt["radius0"] = tr * 0.85 * rmul
		rt["radius1"] = tr * 0.05
		stems.append(rt)

# --- Seviye 2: yan sürgünler (iğneleri taşır) -------------------------

func _spawn_level2(cfg: Dictionary, parent: Dictionary, pidx: int, tf: float, age: float) -> void:
	var shoots: int = int(cfg.get("shoots_per_branch", 7))
	# Sürgünler ana dalın DIŞ kısmına yoğunlaşır (iç çıplak kalır).
	var p_r1: float = float(parent["radius1"])
	var p_len: float = float(parent["len"])
	var az := _rng.randf() * TAU
	for si in range(shoots):
		var u: float = lerp(0.30, 0.97, float(si) / float(maxi(shoots - 1, 1)))
		var sp := _sample(parent, u)
		az += GOLDEN
		var pt := _tangent_at(parent, u)
		var nm := _normal_at(parent, u)
		var azdir := nm.rotated(pt, az)
		var down := deg_to_rad(_rng.randf_range(40.0, 62.0))
		var dir := (pt * cos(down) + azdir * sin(down)).normalized()
		var L: float = p_len * lerp(0.55, 0.22, u) * _rng.randf_range(0.8, 1.15)
		var wob: float = _rng.randf_range(-1.0, 1.0)
		var rmul: float = _rng.randf_range(0.7, 1.0)
		if L < 0.1:
			continue
		var child := _grow(sp, dir, L, int(cfg.get("shoot_segment", 7)), 0.3 + 0.45 * tf, 0.08, 0.10, wob)
		var r0v: float = maxf(p_r1 * rmul, 0.004)
		child["level"] = 2
		child["parent"] = pidx
		child["depth01"] = tf
		child["age"] = age
		child["dry"] = false
		child["broken"] = false
		child["tint"] = lerp(0.78, 1.12, age * age) * _rng.randf_range(0.93, 1.07)
		child["radius0"] = r0v
		child["radius1"] = maxf(r0v * float(cfg.get("shoot_taper", 0.14)), 0.003)
		stems.append(child)
		if bool(cfg.get("fine_twigs", true)):
			_spawn_level3(cfg, child, tf, age)

# --- Seviye 3: ince dallar (sadece iğne, silüet kırılımı) ------------

func _spawn_level3(cfg: Dictionary, parent: Dictionary, tf: float, age: float) -> void:
	var twigs: int = int(cfg.get("twigs_per_shoot", 2))
	if twigs <= 0:
		return
	var p_r1: float = float(parent["radius1"])
	var p_len: float = float(parent["len"])
	var az := _rng.randf() * TAU
	for ti in range(twigs):
		var u: float = lerp(0.4, 0.92, float(ti) / float(maxi(twigs - 1, 1)))
		var sp := _sample(parent, u)
		az += GOLDEN
		var pt := _tangent_at(parent, u)
		var nm := _normal_at(parent, u)
		var azdir := nm.rotated(pt, az)
		var down := deg_to_rad(_rng.randf_range(35.0, 58.0))
		var dir := (pt * cos(down) + azdir * sin(down)).normalized()
		var L: float = p_len * 0.32 * _rng.randf_range(0.8, 1.15)
		var wob: float = _rng.randf_range(-1.0, 1.0)
		if L < 0.06:
			continue
		var child := _grow(sp, dir, L, int(cfg.get("twig_segment", 4)), 0.25 + 0.35 * tf, 0.06, 0.08, wob)
		var r0v: float = maxf(p_r1 * 0.6, 0.0018)
		child["level"] = 3
		child["parent"] = -1
		child["depth01"] = tf
		child["age"] = age
		child["dry"] = false
		child["broken"] = false
		child["tint"] = lerp(0.85, 1.15, age) * _rng.randf_range(0.95, 1.06)
		child["radius0"] = r0v
		child["radius1"] = r0v * 0.35
		stems.append(child)

# --- Büyüme entegrasyonu ----------------------------------------------

func _grow(start: Vector3, dir0: Vector3, length: float, segs: int,
		grav: float, photo: float, curve: float, wob: float) -> Dictionary:
	if segs < 2:
		segs = 2
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
		# İvmeli sarkma (uca doğru gittikçe artan kümülatif çekim) +
		# yalnız dış %45'te uç kalkması (fototropizm) -> S süpürme.
		var g: float = grav * (0.25 + 0.75 * f) * f
		var ph: float = photo * smoothstep(0.55, 1.0, f)
		dir = (dir + Vector3.DOWN * g + Vector3.UP * ph).normalized()
		# Öne-yüklü yay: erken aşağı süpürür, sonra düzelir.
		dir = dir.rotated(curve_ax, curve * (0.6 - 0.5 * f)).normalized()
		# Per-dal organik gürültü (uçlarda 0, ortada en çok).
		dir = dir.rotated(curve_ax, wob * 0.05 * sin(f * PI)).normalized()
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
