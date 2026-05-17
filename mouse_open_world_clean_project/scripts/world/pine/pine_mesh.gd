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
	var ndens: float = float(cfg.get("needle_lod", 1.0))
	var cardp: int = int(cfg.get("card_planes", 2))
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
					_sprigs(leaf, stem, nlen * 0.42, 1, light_bias, ndens, cardp)
		elif lvl == 2:
			# is_tip uç sürgün de İNCE tüp alır -> yaprak dala
			# yapışık görünür (havada kalan yaprak sorunu çözülür).
			if lvl2_wood:
				var _it: bool = bool(stem.get("is_tip", false))
				_tube(branch, stem, (4 if _it else maxi(4, int(sides / 2.6))), empty, 0.0, cfg)
				has_branch = true
			_sprigs(leaf, stem, nlen * 0.40, 2, light_bias, ndens, cardp)
		elif lvl == 3:
			_tube(branch, stem, 3, empty, 0.0, cfg)
			has_branch = true
			_sprigs(leaf, stem, nlen * 0.16, 3, light_bias, ndens, cardp)

	bark.generate_tangents()
	var out := {}
	out["bark"] = bark.commit()
	if has_branch:
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
	var hollow_on: bool = lvl == 0 and float(cfg.get("hollow_base", 0.0)) > 0.5
	var ho_h: float = float(cfg.get("hollow_h", 0.17))
	var ho_arc: float = float(cfg.get("hollow_arc", 0.95))
	var ho_az: float = float(cfg.get("hollow_az", 0.0))
	var ho_in: float = float(cfg.get("hollow_inner", 0.12))
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
		# Nominal yarıçap (şişmeden ÖNCE): UV.v buna göre -> yaka/
		# knot/burl yalnız KONUMU değiştirir, bark akışını DEĞİL.
		var rn0: float = rad0
		var rn1: float = rad1
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
			rad0 += r0 * 1.05 * pow(maxf(1.0 - f0 * 3.0, 0.0), 1.5)
			rad1 += r0 * 1.05 * pow(maxf(1.0 - f1 * 3.0, 0.0), 1.5)
		# Per-side payanda lobu (yalnız govde; dipte guclu, yukari soner).
		var lobe0: float = (flare_l * pow(maxf(1.0 - f0 * 4.0, 0.0), 2.0)) if lvl == 0 else 0.0
		var lobe1: float = (flare_l * pow(maxf(1.0 - f1 * 4.0, 0.0), 2.0)) if lvl == 0 else 0.0
		var c0: Vector3 = pts[k]
		var c1: Vector3 = pts[k + 1]
		var n0: Vector3 = norms[k]
		var n1: Vector3 = norms[k + 1]
		var b0: Vector3 = (tang[k] as Vector3).cross(n0).normalized()
		var b1: Vector3 = (tang[k + 1] as Vector3).cross(n1).normalized()
		var v0 := arc[k] / (TAU * maxf(rn0, 1e-4))
		var v1 := arc[k + 1] / (TAU * maxf(rn1, 1e-4))
		for si in range(sides):
			var a0 := TAU * float(si) / float(sides)
			# Son yüzde (si+1)%sides=0 -> a1 tam 0.0 (cos/sin(TAU)
			# epsilon'u YOK): kapanış halkası başlangıçla BIT-AYNI ->
			# konum+normal dikişsiz, "arkası görünen ince çizgi" biter.
			var a1 := TAU * float((si + 1) % sides) / float(sides)
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
				r00 *= 1.0 + (flu0 * 0.038 + swy0 * 0.045 + mic0 * 0.007) * hf0
				r10 *= 1.0 + (flu1 * 0.038 + swy0 * 0.045 + mic1 * 0.007) * hf0
				r01 *= 1.0 + (flu0 * 0.038 + swy1 * 0.045 + mic0 * 0.007) * hf1
				r11 *= 1.0 + (flu1 * 0.038 + swy1 * 0.045 + mic1 * 0.007) * hf1
				var bf0: float = pow(maxf(1.0 - f0 * 4.0, 0.0), 2.2)
				var bf1: float = pow(maxf(1.0 - f1 * 4.0, 0.0), 2.2)
				var rl0: float = 0.30 + 0.55 * maxf(sin(ah0 * 3.0 + tseed * 0.5), 0.0)
				var rl1: float = 0.30 + 0.55 * maxf(sin(ah1 * 3.0 + tseed * 0.5), 0.0)
				r00 += rad0 * bf0 * rl0
				r10 += rad0 * bf0 * rl1
				r01 += rad1 * bf1 * rl0
				r11 += rad1 * bf1 * rl1
			if hollow_on and lvl == 0 and _in_door(\
					0.5 * (a0 + a1), 0.5 * (f0 + f1), ho_az, ho_arc, ho_h):
				continue   # kapi: dis duvar YOK (gercek delik)
			var uA := float(si) / float(sides) * 2.0
			var uB := float(si + 1) / float(sides) * 2.0
			var fl0 := Vector2(flex0, 0.0)
			var fl1 := Vector2(flex1, 0.0)
			st.set_normal(d00); st.set_uv2(fl0); st.set_uv(Vector2(uA, v0)); st.add_vertex(c0 + d00 * r00)
			st.set_normal(d01); st.set_uv2(fl1); st.set_uv(Vector2(uA, v1)); st.add_vertex(c1 + d01 * r01)
			st.set_normal(d11); st.set_uv2(fl1); st.set_uv(Vector2(uB, v1)); st.add_vertex(c1 + d11 * r11)
			st.set_normal(d00); st.set_uv2(fl0); st.set_uv(Vector2(uA, v0)); st.add_vertex(c0 + d00 * r00)
			st.set_normal(d11); st.set_uv2(fl1); st.set_uv(Vector2(uB, v1)); st.add_vertex(c1 + d11 * r11)
			st.set_normal(d10); st.set_uv2(fl0); st.set_uv(Vector2(uB, v0)); st.add_vertex(c0 + d10 * r10)

	if hollow_on and lvl == 0:
		_carve_hollow(st, stem, cfg, ho_az, ho_arc, ho_h, ho_in)

# --- İğne demeti kartları (sürgün boyunca dağıtılmış) -----------------

static func _sprigs(st: SurfaceTool, stem: Dictionary, size: float, lvl: int,
		light_bias: float, ndens: float = 1.0, cardp: int = 2) -> void:
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
	var r0: float = lerp(0.22, 0.38, age)
	var r1: float = lerp(0.66, 0.86, age)
	if lvl == 1:
		r0 = lerp(0.28, 0.44, age)
		r1 = lerp(0.74, 0.92, age)
	# Seviye-bazlı rüzgâr flex'i (gövde 0 -> iğne ucu en çok).
	var flex: float = 0.6
	if lvl == 3:
		flex = 1.0
	var sun := Vector3(0.6, 0.0, 0.32).normalized()
	# Tek kart = KÜÇÜK iğne demeti (fascicle); çoğu üst üste
	# binerek çam yaprak KÜMESİNİ oluşturur (büyütülmüş tek demet DEĞİL).
	var fl: float = clampf(size * 0.32, 0.11, 0.26)
	var step := maxf(fl * 0.27, 0.02)
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
			# UCA-TOPLU TÜY: yalnız sürgün UCUNDA yuvarlak küme; iç/orta
			# çıplak odun -> açık katmanlı taç (sürekli kılıf/blob DEĞİL).
			var tail: float = 0.40 if tip_full else (0.60 if lvl == 1 else 0.52)
			var dens: float = smoothstep(tail, 1.0, fr)
			if broken and fr > 0.85:
				dens = 0.0
			if dens > 0.02:
				var c: Vector3 = c0 + ax * t
				idx += 1
				var nc: int = (4 if dens > 0.5 else 2)
				if ndens < 0.4:
					nc = 1   # Uzak LOD: kume basina tek kart (perf)
				for s in range(nc):
					var az: float = float(idx) * GOLDEN + PI * float(s)
					var outd: Vector3 = nm.rotated(ax, az).normalized()
					var up: Vector3 = (outd * 0.72 + ax * 0.30 + Vector3.UP * 0.14).normalized()
					var rt: Vector3 = up.cross(Vector3.UP)
					if rt.length() < 0.02:
						rt = up.cross(Vector3.RIGHT)
					rt = rt.normalized()
					# Renk: uca doğru taze açık yeşil, içte koyu/mat.
					var shade: float = clampf(lerp(0.62, 1.14, fr) * tint, 0.48, 1.25)
					var hsh: float = sin(float(idx) * 12.9898 + float(s) * 3.71) * 43758.5453
					var vrnd: float = 0.62 + 0.76 * (hsh - floor(hsh))
					# Küme merkezinde büyür -> yuvarlak pom-pom.
					var ccs: float = fl * (1.05 + 1.05 * dens) * vrnd * (1.3 if tip_full else 1.0)
					# Kume-basina kuruluk (deterministik: dusuk tint=yasli + hash);
					# COLOR.a ile shader'a tasinir -> kuru/sari uc + cesitlilik.
					var dry: float = clampf((1.0 - tint) * 0.7 + (vrnd - 0.62) * 0.55, 0.0, 1.0)
					_card(st, c, up * ccs, rt * (ccs * 0.88), shade, flex, idx % 25, dry, cardp)
			# Uca doğru sıklaş; ışık yönüne göre asimetri.
			var dstep := step / maxf(dens, 0.10)
			if light_bias > 0.0:
				var lb := 1.0 + light_bias * (Vector3(c0.x, 0.0, c0.z).normalized().dot(sun))
				dstep /= clampf(lb, 0.6, 1.4)
			t += clampf(dstep, step * 0.5, step * 6.0) / clampf(ndens, 0.06, 1.0)
		carry = t - seg_len

# Tek demet = çapraz 2 dörtgen (X); tabandan uca yelpaze.
static func _card(st: SurfaceTool, c: Vector3, uv_dir: Vector3, rv: Vector3,
		ao: float, flex: float, cell: int, dry: float = 0.0, planes: int = 2) -> void:
	# UV2 = (flex, atlas hücresi). Shader 5x5 atlastan demeti seçer.
	var fb := Vector2(flex, float(cell))
	var ftp := Vector2(flex * 1.25, float(cell))
	# Çapraz X (2 dik dörtgen): tek düzlem yandan kenar-üstü ince
	# dilime çöküyordu (kırık yaprak). X her açıdan hacim verir.
	for q in range(planes):
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
		st.set_color(Color(ao, ao, ao, dry))
		st.set_uv2(fb); st.set_normal(nA); st.set_uv(Vector2(0.32, 1.0)); st.add_vertex(c - base)
		st.set_uv2(fb); st.set_normal(nA); st.set_uv(Vector2(0.68, 1.0)); st.add_vertex(c + base)
		st.set_uv2(ftp); st.set_normal(nT); st.set_uv(Vector2(1.0, 0.0)); st.add_vertex(tip + rq)
		st.set_uv2(fb); st.set_normal(nA); st.set_uv(Vector2(0.32, 1.0)); st.add_vertex(c - base)
		st.set_uv2(ftp); st.set_normal(nT); st.set_uv(Vector2(1.0, 0.0)); st.add_vertex(tip + rq)
		st.set_uv2(ftp); st.set_normal(nT); st.set_uv(Vector2(0.0, 0.0)); st.add_vertex(tip - rq)

# Yüz normalini gövdeden dışa+yukarı yumuşak hacim normaliyle harmanlar.
# Kapi bolgesi mi? (ho_az yonu, ho_arc yari-acisi, ho_h yuks.). True
# -> dis trunk duvari atlanir (gercek delik).
static func _in_door(a: float, f: float, az: float, arc: float,
		hh: float) -> bool:
	if f >= hh * 0.82:
		return false
	var d: float = a - az
	while d > PI: d -= TAU
	while d < -PI: d += TAU
	return absf(d) < arc * 0.80

# Kadim DIP KOVUGU: kapida dis duvar atlanmistir; burada ic oda
# duvari + yan sove + ust kemer + zemin eklenir (CULL_DISABLED).
static func _carve_hollow(st: SurfaceTool, stem: Dictionary,
		cfg: Dictionary, az: float, arc: float, hh: float,
		inner: float) -> void:
	var pts: Array = stem["points"]
	var tang: Array = stem["tangents"]
	var norms: Array = stem["normals"]
	var n := pts.size()
	if n < 3:
		return
	var r0: float = float(stem["radius0"])
	var r1: float = float(stem["radius1"])
	var flare_s: float = float(cfg.get("flare_strength", 1.0))
	var aw: float = arc * 0.78
	var fT: float = hh * 0.80
	var cav: float = maxf(r0 * (1.0 + 0.30 * flare_s) * 0.55, r0 * 0.6)
	var M := 7
	var kmax := 2
	for k in range(n):
		if float(k) / float(n - 1) <= fT:
			kmax = k
	kmax = maxi(kmax, 2)
	var Rout := func(ff: float) -> float:
		return lerp(r0, r1, pow(clampf(ff, 0.0, 1.0), 0.85)) + r0 * flare_s * 0.30 * pow(maxf(1.0 - ff * 9.0, 0.0), 2.0)
	var dir_at := func(kk: int, a: float) -> Vector3:
		var nn: Vector3 = norms[kk]
		var bb: Vector3 = (tang[kk] as Vector3).cross(nn).normalized()
		return (nn * cos(a) + bb * sin(a)).normalized()
	for k in range(kmax):
		var c0: Vector3 = pts[k]
		var c1: Vector3 = pts[k + 1]
		for j in range(M):
			var a0: float = az - aw + 2.0 * aw * float(j) / float(M)
			var a1: float = az - aw + 2.0 * aw * float(j + 1) / float(M)
			var d00: Vector3 = dir_at.call(k, a0)
			var d01: Vector3 = dir_at.call(k, a1)
			var e00: Vector3 = dir_at.call(k + 1, a0)
			var e01: Vector3 = dir_at.call(k + 1, a1)
			st.set_normal(-d00); st.set_uv2(Vector2.ZERO); st.set_uv(Vector2(float(j) / float(M) * 1.5, float(k) * 0.5)); st.add_vertex(c0 + d00 * cav)
			st.set_normal(-d00); st.set_uv2(Vector2.ZERO); st.set_uv(Vector2(float(j) / float(M) * 1.5, float(k + 1) * 0.5)); st.add_vertex(c1 + e00 * cav)
			st.set_normal(-d01); st.set_uv2(Vector2.ZERO); st.set_uv(Vector2(float(j + 1) / float(M) * 1.5, float(k + 1) * 0.5)); st.add_vertex(c1 + e01 * cav)
			st.set_normal(-d00); st.set_uv2(Vector2.ZERO); st.set_uv(Vector2(float(j) / float(M) * 1.5, float(k) * 0.5)); st.add_vertex(c0 + d00 * cav)
			st.set_normal(-d01); st.set_uv2(Vector2.ZERO); st.set_uv(Vector2(float(j + 1) / float(M) * 1.5, float(k + 1) * 0.5)); st.add_vertex(c1 + e01 * cav)
			st.set_normal(-d01); st.set_uv2(Vector2.ZERO); st.set_uv(Vector2(float(j + 1) / float(M) * 1.5, float(k) * 0.5)); st.add_vertex(c0 + d01 * cav)
	for side in [0, 1]:
		var a: float = (az - aw) if side == 0 else (az + aw)
		for k in range(kmax):
			var f0: float = float(k) / float(n - 1)
			var f1: float = float(k + 1) / float(n - 1)
			var c0: Vector3 = pts[k]
			var c1: Vector3 = pts[k + 1]
			var g0: Vector3 = dir_at.call(k, a)
			var g1: Vector3 = dir_at.call(k + 1, a)
			var Ro0: float = Rout.call(f0)
			var Ro1: float = Rout.call(f1)
			st.set_normal(g0); st.set_uv2(Vector2.ZERO); st.set_uv(Vector2(0.0, f0 * 4.0)); st.add_vertex(c0 + g0 * Ro0)
			st.set_normal(g0); st.set_uv2(Vector2.ZERO); st.set_uv(Vector2(1.0, f1 * 4.0)); st.add_vertex(c1 + g1 * Ro1)
			st.set_normal(g0); st.set_uv2(Vector2.ZERO); st.set_uv(Vector2(0.0, f1 * 4.0)); st.add_vertex(c1 + g1 * cav)
			st.set_normal(g0); st.set_uv2(Vector2.ZERO); st.set_uv(Vector2(0.0, f0 * 4.0)); st.add_vertex(c0 + g0 * Ro0)
			st.set_normal(g0); st.set_uv2(Vector2.ZERO); st.set_uv(Vector2(0.0, f1 * 4.0)); st.add_vertex(c1 + g1 * cav)
			st.set_normal(g0); st.set_uv2(Vector2.ZERO); st.set_uv(Vector2(0.0, f0 * 4.0)); st.add_vertex(c0 + g0 * cav)
	var kt: int = clampi(kmax, 1, n - 1)
	var cT: Vector3 = pts[kt]
	var fTk: float = float(kt) / float(n - 1)
	var dn := -(tang[kt] as Vector3).normalized()
	for j in range(M):
		var a0: float = az - aw + 2.0 * aw * float(j) / float(M)
		var a1: float = az - aw + 2.0 * aw * float(j + 1) / float(M)
		var h0: Vector3 = dir_at.call(kt, a0)
		var h1: Vector3 = dir_at.call(kt, a1)
		var Ro: float = Rout.call(fTk)
		st.set_normal(dn); st.set_uv2(Vector2.ZERO); st.set_uv(Vector2(0.0, 0.0)); st.add_vertex(cT + h0 * Ro)
		st.set_normal(dn); st.set_uv2(Vector2.ZERO); st.set_uv(Vector2(1.0, 0.0)); st.add_vertex(cT + h1 * Ro)
		st.set_normal(dn); st.set_uv2(Vector2.ZERO); st.set_uv(Vector2(1.0, 1.0)); st.add_vertex(cT + h1 * cav)
		st.set_normal(dn); st.set_uv2(Vector2.ZERO); st.set_uv(Vector2(0.0, 0.0)); st.add_vertex(cT + h0 * Ro)
		st.set_normal(dn); st.set_uv2(Vector2.ZERO); st.set_uv(Vector2(1.0, 1.0)); st.add_vertex(cT + h1 * cav)
		st.set_normal(dn); st.set_uv2(Vector2.ZERO); st.set_uv(Vector2(0.0, 1.0)); st.add_vertex(cT + h0 * cav)
	var cB: Vector3 = pts[0]
	for j in range(M):
		var a0: float = az - aw + 2.0 * aw * float(j) / float(M)
		var a1: float = az - aw + 2.0 * aw * float(j + 1) / float(M)
		var p0: Vector3 = cB + dir_at.call(0, a0) * cav
		var p1: Vector3 = cB + dir_at.call(0, a1) * cav
		st.set_normal(Vector3.UP); st.set_uv2(Vector2.ZERO); st.set_uv(Vector2(0.5, 0.5)); st.add_vertex(cB)
		st.set_normal(Vector3.UP); st.set_uv2(Vector2.ZERO); st.set_uv(Vector2(0.0, 1.0)); st.add_vertex(p0)
		st.set_normal(Vector3.UP); st.set_uv2(Vector2.ZERO); st.set_uv(Vector2(1.0, 1.0)); st.add_vertex(p1)

static func _soft(p: Vector3, fold: Vector3) -> Vector3:
	var radial := Vector3(p.x, 0.0, p.z)
	var outward: Vector3
	if radial.length() < 0.001:
		outward = Vector3.UP
	else:
		outward = radial.normalized()
	var soft := (outward * 0.6 + Vector3.UP * 0.5).normalized()
	return (fold.normalized() * 0.4 + soft * 0.8).normalized()
