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
	stem["whorl_az"] = PackedFloat32Array()
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
	var tier_count: int = clampi(int(round(height * 1.10 / whorl_gap)), 9, 14)
	var lean: float = _rng.randf_range(-0.12, 0.12)
	var lean_ph: float = _rng.randf() * TAU
	var whorl_h: PackedFloat32Array = trunk["whorl_h"]
	var whorl_az: PackedFloat32Array = trunk["whorl_az"]
	var az := _rng.randf() * TAU
	for ti in range(tier_count):
		var tf := float(ti) / float(tier_count - 1)
		var h01: float = clampf(lerp(crown_start, 0.95, tf) + _rng.randf_range(-0.05, 0.05), 0.0, 1.0)
		# Düz kenarlı çam üçgeni (🌲): üs ~doğrusal (0.92) -> kenarlar
		# içe büzülmez, taban hafif dolgun; dipte en geniş, tepeye
		# doğru düzgün daralma.
		var prof: float = pow(1.0 - tf, 0.92)
		var blen := crown_radius * prof * 1.70
		if blen < 0.16:
			continue
		whorl_h.append(h01)
		var per := int(round(lerp(float(total) / float(tier_count) * 1.05, 3.0, tf)))
		per = clampi(per + _rng.randi_range(-1, 1), 3, 6)
		az += GOLDEN * 1.3
		var aaccum := az
		var seg := TAU / float(per)
		for bi in range(per):
			# TÜM per-dal rastgele değerleri continue'dan ÖNCE (determinizm).
			aaccum += seg * _rng.randf_range(0.80, 1.20)
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
			var a: float = aaccum + ajit + 0.5 * lean * cos(aaccum - lean_ph)
			var age := 1.0 - tf
			var r0v: float = tr * lerp(0.20, 0.36, age) * rjit
			# Dal GÖVDE DERİSİNDEN doğar (eksene değil) ve dibe gömülüdür:
			# çubuk gibi delip geçmez; gövde tümseği + yaka ile kaynaşır.
			var sp_axis := _sample(trunk, h01)
			var radial0 := Vector3(cos(a), 0.0, sin(a))
			var tr_h: float = lerp(tr, tr * float(cfg.get("trunk_top", 0.06)), pow(h01, 0.85)) + tr * float(cfg.get("flare_strength", 1.0)) * 0.30 * pow(maxf(1.0 - h01 * 9.0, 0.0), 2.0)
			var embed: float = minf(r0v, tr_h * 0.6)
			var sp := sp_axis + radial0 * (tr_h - embed)
			# Yükseklik-bölgeli açı: alt yatay/sarkık, üst dik (koni).
			var up0: float = lerp(elev_low, minf(elev_high, 0.20), pow(tf, 0.7)) + up_jit
			var dir := (Vector3(cos(a), 0.0, sin(a)) + Vector3.UP * up0).normalized()
			var L: float = blen * lvar
			if is_broken:
				L *= brk_mul
			# Alt tier'ler sert süpürür, üst tier'ler dik durur.
			var grav := droop * (0.50 + 1.45 * (1.0 - tf))
			# knee=1.0 -> dal gövdeden YUKARI çıkıp sonra dışa kıvrılır.
			var child := _grow(sp, dir, L, dal_seg, grav, 0.05, dal_yay, wob, 0.40)
			whorl_az.append(h01)
			whorl_az.append(a)
			whorl_az.append(r0v)
			child["level"] = 1
			child["parent"] = trunk_idx
			child["depth01"] = tf
			child["age"] = age
			child["dry"] = is_dry
			child["broken"] = is_broken
			child["tint"] = lerp(0.72, 1.10, age * age) * tvar
			child["radius0"] = r0v
			# Yumuşak incelme: uç tabanın ~%22-34'ü (ANİ kesilme YOK).
			child["radius1"] = maxf(r0v * lerp(0.34, 0.22, tf) * (0.85 + 0.6 * tipr), 0.012)
			stems.append(child)
			var bidx := stems.size() - 1
			if not is_dry:
				_spawn_level2(cfg, child, bidx, tf, age)
	# PackedFloat32Array değer tipidir -> geri yazılır.
	trunk["whorl_h"] = whorl_h
	trunk["whorl_az"] = whorl_az
	# Apeks: merkezde uzun-kalın dik LİDER + çevresinde kısalan sürgünler
	# -> dolgun, özenli, sivri konik tepe (referans gibi).
	for ai in range(13):
		var ah: float = lerp(0.80, 0.99, float(ai) / 12.0)
		var sp := _sample(trunk, ah)
		var aa := _rng.randf() * TAU
		var awob := _rng.randf_range(-1.0, 1.0)
		var afr := float(ai) / 12.0
		# Kısa-dolgun sivri tepe: tek uzun antenimsi lider YOK; alçaktan
		# başlayıp koniyle sürekli kaynaşan, tepeye doğru kısalan püskül.
		var adir := (Vector3(cos(aa), 0, sin(aa)) * (0.10 + 0.62 * afr) + Vector3.UP * (1.5 if ai == 0 else 1.15)).normalized()
		var al := (crown_radius * 0.40) if ai == 0 else (crown_radius * lerpf(0.52, 0.12, afr))
		var ac := _grow(sp, adir, maxf(al, 0.18), 4, 0.06, 0.10, 0.05, awob)
		ac["level"] = 1
		ac["parent"] = trunk_idx
		ac["depth01"] = 1.0
		ac["age"] = 0.05
		ac["dry"] = false
		ac["broken"] = false
		ac["tint"] = _rng.randf_range(0.95, 1.15)
		ac["radius0"] = tr * (0.55 if ai == 0 else lerp(0.30, 0.10, afr))
		ac["radius1"] = tr * lerp(0.36, 0.12, afr) * 0.32
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
		var u: float = lerp(0.10, 0.96, float(si) / float(maxi(shoots - 1, 1)))
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
		var r0v: float = maxf(p_r1 * rmul, 0.014)
		child["level"] = 2
		child["parent"] = pidx
		child["depth01"] = tf
		child["age"] = age
		child["dry"] = false
		child["broken"] = false
		child["tint"] = lerp(0.78, 1.12, age * age) * _rng.randf_range(0.93, 1.07)
		child["radius0"] = r0v
		child["radius1"] = maxf(r0v * (0.55 + float(cfg.get("shoot_taper", 0.14))), 0.010)
		stems.append(child)
		if bool(cfg.get("fine_twigs", true)):
			_fork(cfg, child, stems.size() - 1, tf, age, int(cfg.get("fork_depth", 2)))

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

# --- V/Y çatallanma: düzlemsel frond (gerçek çam dalı topolojisi) ----
# Üst sürgünün ucundan AYNI düzlemde +/- açıyla 2 çatal; her çatal
# yine çatallanır (recursive). Uç çatallar is_tip -> mesh'te odun YOK,
# sadece iğne püskülü. Çam dalının yassı yelpaze görünümünü verir.

func _fork(cfg: Dictionary, parent_stem: Dictionary, parent_idx: int,
		tf: float, age: float, depth: int) -> void:
	if depth <= 0:
		return
	var pp: Array = parent_stem["points"]
	var ptn: Array = parent_stem["tangents"]
	var tip: Vector3 = pp[pp.size() - 1]
	var tdir: Vector3 = ptn[ptn.size() - 1]
	var p_r1: float = float(parent_stem["radius1"])
	var p_len: float = float(parent_stem["len"])
	# Yelpaze düzlemi DAL'A bağlı (dünyaya kilitli DEĞİL): parent RMF
	# normalinden türetilir -> her dal farklı yöne bakar, hiçbiri tek
	# tip yandan kenar-üstü kalmaz. RMF normali daima iyi koşulludur.
	var pn_arr: Array = parent_stem["normals"]
	var lat: Vector3 = pn_arr[pn_arr.size() - 1]
	lat = lat - tdir * lat.dot(tdir)
	if lat.length() < 0.01:
		lat = tdir.cross(Vector3.RIGHT)
	lat = lat.normalized()
	var plane_n: Vector3 = tdir.cross(lat).normalized()
	# Eksen boyunca PİNNAT yan dalcıklar: çatallanma yalnız uçta değil,
	# orta/dipte de (gerçek çam frond'u). Uç (is_tip) -> ucuz, odun yok.
	if depth >= 2:
		for li in range(1):
			var lu: float = 0.40 + 0.26 * float(li)        # ~0.40, 0.66
			var lwob: float = _rng.randf_range(-1.0, 1.0)
			var lang: float = deg_to_rad(_rng.randf_range(32.0, 55.0))
			var lrand: float = _rng.randf_range(0.32, 0.48)
			var llen: float = p_len * lrand
			if llen < 0.06:
				continue
			var lsgn: float = 1.0 if li == 0 else -1.0
			var lpos: Vector3 = _sample(parent_stem, lu)
			var lt: Vector3 = _tangent_at(parent_stem, lu)
			var ldir: Vector3 = lt.rotated(plane_n, lang * lsgn).normalized()
			var lc := _grow(lpos, ldir, llen, 3, 0.30, 0.05, 0.10, lwob)
			lc["level"] = 2
			lc["parent"] = parent_idx
			lc["depth01"] = tf
			lc["age"] = age
			lc["dry"] = false
			lc["broken"] = false
			lc["is_tip"] = true
			lc["tint"] = lerp(0.82, 1.14, age) * _rng.randf_range(0.93, 1.08)
			lc["radius0"] = maxf(p_r1 * 0.5, 0.004)
			lc["radius1"] = maxf(p_r1 * 0.25, 0.0025)
			stems.append(lc)
	for fi in range(2):
		var wob: float = _rng.randf_range(-1.0, 1.0)
		var ang: float = deg_to_rad(_rng.randf_range(17.0, 35.0))
		var lmul: float = _rng.randf_range(0.55, 0.74)
		var tnt: float = _rng.randf_range(0.93, 1.08)
		var sgn: float = 1.0 if fi == 0 else -1.0
		var L: float = p_len * lmul
		if L < 0.05:
			continue
		var dir: Vector3 = tdir.rotated(plane_n, ang * sgn).normalized()
		# Düzlem-dışı eğim: yelpaze artık MÜKEMMEL düzlem değil ->
		# yandan tamamen kaybolmaz (kenar-üstü çökme biter).
		dir = dir.rotated(tdir, wob * 0.34).normalized()
		var is_tip: bool = depth <= 1 or L < 0.14
		var seg: int = 3 if is_tip else maxi(4, int(cfg.get("shoot_segment", 7)))
		var child := _grow(tip, dir, L, seg, 0.28 + 0.40 * tf, 0.06, 0.09, wob)
		var r0v: float = maxf(p_r1 * 0.86, 0.006)
		child["level"] = 2
		child["parent"] = parent_idx
		child["depth01"] = tf
		child["age"] = age
		child["dry"] = false
		child["broken"] = false
		child["is_tip"] = is_tip
		child["tint"] = lerp(0.82, 1.14, age) * tnt
		child["radius0"] = r0v
		child["radius1"] = maxf(r0v * 0.58, 0.004)
		stems.append(child)
		if not is_tip:
			_fork(cfg, child, stems.size() - 1, tf, age, depth - 1)

# --- Büyüme entegrasyonu ----------------------------------------------

func _grow(start: Vector3, dir0: Vector3, length: float, segs: int,
		grav: float, photo: float, curve: float, wob: float,
		knee: float = 0.0) -> Dictionary:
	if segs < 2:
		segs = 2
	var pts: Array[Vector3] = [start]
	var dir := dir0.normalized()
	# Bazal DİZ: dal gövdeden yukarı doğru çıkar; kümülatif çekim (g)
	# sonra dışa/aşağı kıvırır -> doğal dirsekli ayrılış (çubuk değil).
	if knee > 0.0:
		dir = (dir + Vector3.UP * 1.3 * knee).normalized()
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
		var kdir: float = 1.0 if (s % 2) == 0 else -1.15
		dir = dir.rotated(curve_ax, wob * 0.085 * kdir).normalized()
		var ax2: Vector3 = curve_ax.cross(dir)
		if ax2.length() > 0.01:
			dir = dir.rotated(ax2.normalized(), wob * 0.04 * kdir).normalized()
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
