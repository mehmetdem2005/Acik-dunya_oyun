@tool
class_name PineMesh
extends RefCounted

# İskelet stem'lerinden geometri üretir:
# - Odun: gövde + ana dallar, frame halkalarıyla pürüzsüz tüp
# - İğne: sürgün boyunca DAĞITILMIŞ küçük çapraz DEMET kartları
#   (her kart atlası tam (0..1) gösterir -> doku gerilmez, gerçek fascicle);
#   yumuşak hacim normalleri, AO/tint vertex rengi
# Dönüş: { "bark": ArrayMesh, "branch": ArrayMesh|null, "needle": ArrayMesh }
# Gövde (level 0) ile dallar (level 1+) AYRI surface -> her biri kendi
# materyalini (gerçek kabuk / dal texture seti) alabilir.

const GOLDEN := 2.399963229728653

static func build(stems: Array, cfg: Dictionary) -> Dictionary:
	var bark := SurfaceTool.new()
	bark.begin(Mesh.PRIMITIVE_TRIANGLES)
	var branch := SurfaceTool.new()
	branch.begin(Mesh.PRIMITIVE_TRIANGLES)
	var leaf := SurfaceTool.new()
	leaf.begin(Mesh.PRIMITIVE_TRIANGLES)

	var sides: int = int(cfg.get("trunk_sides", 12))
	var nlen: float = cfg.get("needle_size", 1.2)
	var light_bias: float = float(cfg.get("light_bias", 0.0))
	var knot_s: float = float(cfg.get("knot_strength", 0.22))
	var empty := PackedFloat32Array()
	var whorls: PackedFloat32Array = empty
	if stems.size() > 0 and (stems[0] as Dictionary).has("whorl_h"):
		whorls = stems[0]["whorl_h"]

	var lvl2_wood: bool = bool(cfg.get("level2_wood", true))
	var has_branch := false
	for stem in stems:
		var lvl: int = int(stem["level"])
		if lvl == 0:
			_tube(bark, stem, sides, whorls, knot_s, cfg)
		elif lvl == 1:
			if bool(stem.get("is_root", false)):
				# Kök payandası gövdeyle aynı kabuk materyalini alır.
				_tube(bark, stem, maxi(6, int(sides * 0.7)), empty, 0.0, cfg)
			else:
				_tube(branch, stem, maxi(5, int(sides / 2.0)), empty, 0.0, cfg)
				has_branch = true
				# Kuru dal iğne taşımaz (yalnız odun çizilir).
				if not bool(stem.get("dry", false)):
					_sprigs(leaf, stem, nlen * 0.22, 1, light_bias)
		elif lvl == 2:
			if lvl2_wood:
				_tube(branch, stem, maxi(4, int(sides / 3.0)), empty, 0.0, cfg)
				has_branch = true
			_sprigs(leaf, stem, nlen * 0.20, 2, light_bias)
		elif lvl == 3:
			_sprigs(leaf, stem, nlen * 0.16, 3, light_bias)

	bark.generate_normals()
	bark.generate_tangents()
	var out := {}
	out["bark"] = bark.commit()
	if has_branch:
		branch.generate_normals()
		branch.generate_tangents()
		out["branch"] = branch.commit()
	else:
		out["branch"] = null
	out["needle"] = leaf.commit()
	return out

# --- Odun tüpü ---------------------------------------------------------

static func _tube(st: SurfaceTool, stem: Dictionary, sides: int,
		knots: PackedFloat32Array, knot_s: float, cfg: Dictionary) -> void:
	var pts: Array = stem["points"]
	var tang: Array = stem["tangents"]
	var norms: Array = stem["normals"]
	var n := pts.size()
	if n < 2:
		return
	var lvl: int = int(stem["level"])
	var r0: float = float(stem["radius0"])
	var r1: float = float(stem["radius1"])
	var flare_s: float = float(cfg.get("flare_strength", 1.0))
	var flare_l: float = float(cfg.get("flare_lobe", 0.5))
	var roots_n: float = float(int(cfg.get("root_count", 5)))
	# Yay uzunluğu -> UV.V fiziksel: 1 tile ≈ 1 çevre (kabuk kare hücre,
	# dalda smear yok). uv1_scale materyalde (1,1,1) zorlanır.
	var arc := PackedFloat32Array()
	arc.resize(n)
	arc[0] = 0.0
	for ai in range(1, n):
		arc[ai] = arc[ai - 1] + (pts[ai] as Vector3).distance_to(pts[ai - 1])
	for k in range(n - 1):
		var f0 := float(k) / float(n - 1)
		var f1 := float(k + 1) / float(n - 1)
		var rad0: float = lerp(r0, r1, pow(f0, 0.85))
		var rad1: float = lerp(r0, r1, pow(f1, 0.85))
		# Gövdeye yakın odun ince dalda daha çok daralma profili korunur.
		var flex0: float = 0.0 if lvl == 0 else lerp(0.0, 0.40, f0)
		var flex1: float = 0.0 if lvl == 0 else lerp(0.0, 0.40, f1)
		if lvl == 0:
			# Yumuşatılmış dip kabarması (eski sert kubbe değil).
			rad0 += r0 * flare_s * pow(maxf(1.0 - f0 * 5.0, 0.0), 2.2)
			rad1 += r0 * flare_s * pow(maxf(1.0 - f1 * 5.0, 0.0), 2.2)
			# Budak/knot: whorl yüksekliklerinde gövde şişer.
			for wi in range(knots.size()):
				var wh: float = knots[wi]
				var dd0: float = (f0 - wh) / 0.045
				var dd1: float = (f1 - wh) / 0.045
				rad0 += exp(-dd0 * dd0) * r0 * knot_s
				rad1 += exp(-dd1 * dd1) * r0 * knot_s
		# Per-side payanda lobu (yalnız govde; dipte guclu, yukari soner).
		var lobe0: float = (flare_l * pow(maxf(1.0 - f0 * 4.0, 0.0), 2.0)) if lvl == 0 else 0.0
		var lobe1: float = (flare_l * pow(maxf(1.0 - f1 * 4.0, 0.0), 2.0)) if lvl == 0 else 0.0
		var c0: Vector3 = pts[k]
		var c1: Vector3 = pts[k + 1]
		var n0: Vector3 = norms[k]
		var n1: Vector3 = norms[k + 1]
		var b0: Vector3 = (tang[k] as Vector3).cross(n0).normalized()
		var b1: Vector3 = (tang[k + 1] as Vector3).cross(n1).normalized()
		var v0 := arc[k] / (TAU * maxf(rad0, 1e-4))
		var v1 := arc[k + 1] / (TAU * maxf(rad1, 1e-4))
		for si in range(sides):
			var a0 := TAU * float(si) / float(sides)
			var a1 := TAU * float(si + 1) / float(sides)
			var d00 := n0 * cos(a0) + b0 * sin(a0)
			var d10 := n0 * cos(a1) + b0 * sin(a1)
			var d01 := n1 * cos(a0) + b1 * sin(a0)
			var d11 := n1 * cos(a1) + b1 * sin(a1)
			var r00 := rad0 * (1.0 + lobe0 * maxf(cos(a0 * roots_n), 0.0))
			var r10 := rad0 * (1.0 + lobe0 * maxf(cos(a1 * roots_n), 0.0))
			var r01 := rad1 * (1.0 + lobe1 * maxf(cos(a0 * roots_n), 0.0))
			var r11 := rad1 * (1.0 + lobe1 * maxf(cos(a1 * roots_n), 0.0))
			var uA := float(si) / float(sides) * 2.0
			var uB := float(si + 1) / float(sides) * 2.0
			var fl0 := Vector2(flex0, 0.0)
			var fl1 := Vector2(flex1, 0.0)
			st.set_uv2(fl0); st.set_uv(Vector2(uA, v0)); st.add_vertex(c0 + d00 * r00)
			st.set_uv2(fl1); st.set_uv(Vector2(uA, v1)); st.add_vertex(c1 + d01 * r01)
			st.set_uv2(fl1); st.set_uv(Vector2(uB, v1)); st.add_vertex(c1 + d11 * r11)
			st.set_uv2(fl0); st.set_uv(Vector2(uA, v0)); st.add_vertex(c0 + d00 * r00)
			st.set_uv2(fl1); st.set_uv(Vector2(uB, v1)); st.add_vertex(c1 + d11 * r11)
			st.set_uv2(fl0); st.set_uv(Vector2(uB, v0)); st.add_vertex(c0 + d10 * r10)

# --- İğne demeti kartları (sürgün boyunca dağıtılmış) -----------------

static func _sprigs(st: SurfaceTool, stem: Dictionary, size: float, lvl: int,
		light_bias: float) -> void:
	if bool(stem.get("dry", false)):
		return  # kuru dal iğne taşımaz
	var pts: Array = stem["points"]
	var norms: Array = stem["normals"]
	var n := pts.size()
	if n < 2:
		return
	var tint: float = stem.get("tint", 1.0)
	var age: float = stem.get("age", 0.5)
	var broken: bool = bool(stem.get("broken", false))
	# Yaşa bağlı yoğunluk rampası: yaşlı dal iç kısmı daha çok çıplak.
	# İç kısım çıplak odun, iğne dış ~%55-65'te yoğunlaşır (açık taç).
	var r0: float = lerp(0.38, 0.55, age)
	var r1: float = lerp(0.62, 0.85, age)
	if lvl == 1:
		r0 = lerp(0.45, 0.62, age)
		r1 = lerp(0.70, 0.90, age)
	# Seviye-bazlı rüzgâr flex'i (gövde 0 -> iğne ucu en çok).
	var flex: float = 0.6
	if lvl == 3:
		flex = 1.0
	var sun := Vector3(0.6, 0.0, 0.32).normalized()
	var step := maxf(size * 0.5, 0.035)
	var carry := 0.0
	var idx := 0
	for k in range(n - 1):
		var c0: Vector3 = pts[k]
		var c1: Vector3 = pts[k + 1]
		var seg: Vector3 = c1 - c0
		var seg_len := seg.length()
		if seg_len < 1e-5:
			continue
		var ax: Vector3 = seg / seg_len
		var nm: Vector3 = norms[k]
		var t := carry
		while t < seg_len:
			var fr: float = (float(k) + t / seg_len) / float(n - 1)
			var dens: float = 1.0 if lvl == 3 else smoothstep(r0, r1, fr)
			if broken and fr > 0.85:
				dens = 0.0
			if dens > 0.02:
				var c: Vector3 = c0 + ax * t
				idx += 1
				for s in range(2):
					var az: float = float(idx) * GOLDEN + PI * float(s)
					var outd: Vector3 = nm.rotated(ax, az).normalized()
					var up: Vector3 = (outd * 0.78 + ax * 0.42 + Vector3.DOWN * 0.16).normalized()
					var rt: Vector3 = up.cross(Vector3.UP)
					if rt.length() < 0.02:
						rt = up.cross(Vector3.RIGHT)
					rt = rt.normalized()
					# Renk: uca doğru taze açık yeşil, içte koyu/mat.
					var shade: float = clampf(lerp(0.50, 1.05, fr) * tint, 0.0, 1.0)
					_card(st, c, up * size, rt * (size * 0.55), shade, flex)
			# Uca doğru sıklaş; ışık yönüne göre asimetri.
			var dstep := step / maxf(dens, 0.10)
			if light_bias > 0.0:
				var lb := 1.0 + light_bias * (Vector3(c0.x, 0.0, c0.z).normalized().dot(sun))
				dstep /= clampf(lb, 0.6, 1.4)
			t += clampf(dstep, step * 0.5, step * 6.0)
		carry = t - seg_len

# Tek demet = çapraz 2 dörtgen (X); tabandan uca yelpaze.
static func _card(st: SurfaceTool, c: Vector3, uv_dir: Vector3, rv: Vector3,
		ao: float, flex: float) -> void:
	var fb := Vector2(flex, 0.0)            # taban: orta flex
	var ftp := Vector2(flex * 1.25, 0.0)    # iğne ucu: en hızlı titreşim
	for q in range(2):
		var rq: Vector3
		if q == 0:
			rq = rv
		else:
			rq = uv_dir.normalized().cross(rv).normalized() * rv.length()
		var base := rq * 0.30
		var tip := c + uv_dir
		var fn := uv_dir.cross(rq)
		var nA := _soft(c, fn)
		var nT := _soft(tip, fn)
		st.set_color(Color(ao, ao, ao, 1.0))
		st.set_uv2(fb); st.set_normal(nA); st.set_uv(Vector2(0.32, 1.0)); st.add_vertex(c - base)
		st.set_uv2(fb); st.set_normal(nA); st.set_uv(Vector2(0.68, 1.0)); st.add_vertex(c + base)
		st.set_uv2(ftp); st.set_normal(nT); st.set_uv(Vector2(1.0, 0.0)); st.add_vertex(tip + rq)
		st.set_uv2(fb); st.set_normal(nA); st.set_uv(Vector2(0.32, 1.0)); st.add_vertex(c - base)
		st.set_uv2(ftp); st.set_normal(nT); st.set_uv(Vector2(1.0, 0.0)); st.add_vertex(tip + rq)
		st.set_uv2(ftp); st.set_normal(nT); st.set_uv(Vector2(0.0, 0.0)); st.add_vertex(tip - rq)

# Yüz normalini gövdeden dışa+yukarı yumuşak hacim normaliyle harmanlar.
static func _soft(p: Vector3, fold: Vector3) -> Vector3:
	var radial := Vector3(p.x, 0.0, p.z)
	var outward: Vector3
	if radial.length() < 0.001:
		outward = Vector3.UP
	else:
		outward = radial.normalized()
	var soft := (outward * 0.6 + Vector3.UP * 0.5).normalized()
	return (fold.normalized() * 0.4 + soft * 0.8).normalized()
