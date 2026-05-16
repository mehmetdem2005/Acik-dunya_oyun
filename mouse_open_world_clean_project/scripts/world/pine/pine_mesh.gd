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
	var azs: PackedFloat32Array = empty
	if stems.size() > 0 and (stems[0] as Dictionary).has("whorl_h"):
		whorls = stems[0]["whorl_h"]
	if stems.size() > 0 and (stems[0] as Dictionary).has("whorl_az"):
		azs = stems[0]["whorl_az"]

	var lvl2_wood: bool = bool(cfg.get("level2_wood", true))
	var has_branch := false
	for stem in stems:
		var lvl: int = int(stem["level"])
		if lvl == 0:
			_tube(bark, stem, sides, whorls, knot_s, cfg, azs)
		elif lvl == 1:
			if bool(stem.get("is_root", false)):
				# Kök payandası gövdeyle aynı kabuk materyalini alır.
				_tube(bark, stem, maxi(6, int(sides * 0.7)), empty, 0.0, cfg)
			else:
				_tube(branch, stem, maxi(5, int(sides / 2.0)), empty, 0.0, cfg)
				has_branch = true
				# Kuru dal iğne taşımaz (yalnız odun çizilir).
				if not bool(stem.get("dry", false)):
					_sprigs(leaf, stem, nlen * 0.42, 1, light_bias)
		elif lvl == 2:
			if lvl2_wood and not bool(stem.get("is_tip", false)):
				_tube(branch, stem, maxi(3, int(sides / 4.0)), empty, 0.0, cfg)
				has_branch = true
			_sprigs(leaf, stem, nlen * 0.40, 2, light_bias)
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
	# İğne normalleri _card'da elle (yumuşak hacim) -> generate_normals
	# ÇAĞIRMA. NORMAL_MAP için tangent şart: UV+normal'den üret.
	leaf.generate_tangents()
	out["needle"] = leaf.commit()
	return out

# --- Odun tüpü ---------------------------------------------------------

static func _tube(st: SurfaceTool, stem: Dictionary, sides: int,
		knots: PackedFloat32Array, knot_s: float, cfg: Dictionary,
		azs: PackedFloat32Array = PackedFloat32Array()) -> void:
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
	var tseed: float = float(int(cfg.get("seed", 12345)) % 1000)
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
			# Çok hafif, pürüzsüz dip genişlemesi (trompet/eteklenme YOK;
			# referans çamda gövde zemine düz girer).
			rad0 += r0 * flare_s * 0.30 * pow(maxf(1.0 - f0 * 9.0, 0.0), 2.0)
			rad1 += r0 * flare_s * 0.30 * pow(maxf(1.0 - f1 * 9.0, 0.0), 2.0)
			# Budak/knot: whorl yüksekliklerinde gövde şişer.
			for wi in range(knots.size()):
				var wh: float = knots[wi]
				var dd0: float = (f0 - wh) / 0.045
				var dd1: float = (f1 - wh) / 0.045
				rad0 += exp(-dd0 * dd0) * r0 * knot_s
				rad1 += exp(-dd1 * dd1) * r0 * knot_s
		elif lvl == 1 and not bool(stem.get("is_root", false)):
			# Dal-gövde YAKASI: dipte yumuşak şişme + hızlı incelme ->
			# dal gövdeye saplanmış çubuk değil, organik bağlanır.
			rad0 += r0 * 0.6 * pow(maxf(1.0 - f0 * 5.0, 0.0), 2.0)
			rad1 += r0 * 0.6 * pow(maxf(1.0 - f1 * 5.0, 0.0), 2.0)
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
			if lvl == 0:
					for bz in range(azs.size() / 3):
						var bh: float = azs[bz * 3]
						var ba: float = azs[bz * 3 + 1]
						var br: float = azs[bz * 3 + 2]
						var fz0: float = (f0 - bh) / 0.055
						var fz1: float = (f1 - bh) / 0.055
						var g0: float = exp(-fz0 * fz0) * br * 0.45
						var g1: float = exp(-fz1 * fz1) * br * 0.45
						var s0a: float = pow(maxf(cos(a0 - ba), 0.0), 3.0)
						var s1a: float = pow(maxf(cos(a1 - ba), 0.0), 3.0)
						r00 += g0 * s0a
						r10 += g0 * s1a
						r01 += g1 * s0a
						r11 += g1 * s1a
			if lvl == 0:
				# Gerçek odun: dikey oluk + eksenel şişme + mikro kırılma
				# + ölçülü düzensiz dip kök payandası (mükemmel silindir DEĞİL).
				var ah0: float = a0 + tseed * 0.011
				var ah1: float = a1 + tseed * 0.011
				var flu0: float = sin(ah0 * 7.0) * 0.5 + sin(ah0 * 3.0 + 1.7) * 0.5
				var flu1: float = sin(ah1 * 7.0) * 0.5 + sin(ah1 * 3.0 + 1.7) * 0.5
				var swy0: float = sin(f0 * 5.3 + tseed * 0.07) * 0.6 + sin(f0 * 12.0 + tseed * 0.3) * 0.4
				var swy1: float = sin(f1 * 5.3 + tseed * 0.07) * 0.6 + sin(f1 * 12.0 + tseed * 0.3) * 0.4
				var mic0: float = sin(ah0 * 21.0 + f0 * 27.0)
				var mic1: float = sin(ah1 * 21.0 + f1 * 27.0)
				var hf0: float = clampf(1.0 - f0 * 0.55, 0.45, 1.0)
				var hf1: float = clampf(1.0 - f1 * 0.55, 0.45, 1.0)
				r00 *= 1.0 + (flu0 * 0.07 + swy0 * 0.045 + mic0 * 0.014) * hf0
				r10 *= 1.0 + (flu1 * 0.07 + swy0 * 0.045 + mic1 * 0.014) * hf0
				r01 *= 1.0 + (flu0 * 0.07 + swy1 * 0.045 + mic0 * 0.014) * hf1
				r11 *= 1.0 + (flu1 * 0.07 + swy1 * 0.045 + mic1 * 0.014) * hf1
				var bf0: float = pow(maxf(1.0 - f0 * 4.0, 0.0), 2.2)
				var bf1: float = pow(maxf(1.0 - f1 * 4.0, 0.0), 2.2)
				var rl0: float = 0.30 + 0.55 * maxf(sin(ah0 * 3.0 + tseed * 0.5), 0.0)
				var rl1: float = 0.30 + 0.55 * maxf(sin(ah1 * 3.0 + tseed * 0.5), 0.0)
				r00 += rad0 * bf0 * rl0
				r10 += rad0 * bf0 * rl1
				r01 += rad1 * bf1 * rl0
				r11 += rad1 * bf1 * rl1
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
	var tip_full: bool = bool(stem.get("is_tip", false))
	# İç kısım hafif çıplak, iğne dışta yoğun. Uç frond'lar TAM dolu
	# (kel bırakma) -> taç dolgun, referans gibi.
	# Açık/tüylü taç: iç boş, iğne dış ~%40'ta yuvarlak küme (uç=tam).
	var r0: float = lerp(0.34, 0.50, age)
	var r1: float = lerp(0.66, 0.86, age)
	if lvl == 1:
		r0 = lerp(0.40, 0.56, age)
		r1 = lerp(0.74, 0.92, age)
	# Seviye-bazlı rüzgâr flex'i (gövde 0 -> iğne ucu en çok).
	var flex: float = 0.6
	if lvl == 3:
		flex = 1.0
	var sun := Vector3(0.6, 0.0, 0.32).normalized()
	# Tek kart = KÜÇÜK iğne demeti (fascicle); çoğu üst üste
	# binerek çam yaprak KÜMESİNİ oluşturur (büyütülmüş tek demet DEĞİL).
	var fl: float = clampf(size * 0.32, 0.11, 0.26)
	var step := maxf(fl * 0.50, 0.028)
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
			var dens: float = 1.0 if (lvl == 3 or tip_full) else smoothstep(r0, r1, fr)
			if broken and fr > 0.85:
				dens = 0.0
			if dens > 0.02:
				var c: Vector3 = c0 + ax * t
				idx += 1
				for s in range(2):
					var az: float = float(idx) * GOLDEN + PI * float(s)
					var outd: Vector3 = nm.rotated(ax, az).normalized()
					var up: Vector3 = (outd * 0.72 + ax * 0.30 + Vector3.UP * 0.14).normalized()
					var rt: Vector3 = up.cross(Vector3.UP)
					if rt.length() < 0.02:
						rt = up.cross(Vector3.RIGHT)
					rt = rt.normalized()
					# Renk: uca doğru taze açık yeşil, içte koyu/mat.
					var shade: float = clampf(lerp(0.62, 1.14, fr) * tint, 0.48, 1.25)
					var ccs: float = fl * (0.80 + 0.40 * fr) * (1.2 if tip_full else 1.0)
					_card(st, c, up * ccs, rt * (ccs * 0.60), shade, flex, idx % 25)
			# Uca doğru sıklaş; ışık yönüne göre asimetri.
			var dstep := step / maxf(dens, 0.10)
			if light_bias > 0.0:
				var lb := 1.0 + light_bias * (Vector3(c0.x, 0.0, c0.z).normalized().dot(sun))
				dstep /= clampf(lb, 0.6, 1.4)
			t += clampf(dstep, step * 0.5, step * 6.0)
		carry = t - seg_len

# Tek demet = çapraz 2 dörtgen (X); tabandan uca yelpaze.
static func _card(st: SurfaceTool, c: Vector3, uv_dir: Vector3, rv: Vector3,
		ao: float, flex: float, cell: int) -> void:
	# UV2 = (flex, atlas hücresi). Shader 5x5 atlastan demeti seçer.
	var fb := Vector2(flex, float(cell))
	var ftp := Vector2(flex * 1.25, float(cell))
	# Tek dörtgen (çapraz X kaldırıldı) -> ~%50 daha az iğne üçgeni;
	# atlas + normal map hacmi taşıdığı için görünüm ~korunur (mobil).
	for q in range(1):
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
