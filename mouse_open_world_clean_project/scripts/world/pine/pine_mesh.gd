@tool
class_name PineMesh
extends RefCounted

# İskelet stem'lerinden geometri üretir:
# - Odun: gövde + ana dallar, frame halkalarıyla pürüzsüz tüp
# - İğne: sürgün boyunca DAĞITILMIŞ küçük çapraz DEMET kartları
#   (her kart atlası tam (0..1) gösterir -> doku gerilmez, gerçek fascicle);
#   yumuşak hacim normalleri, AO/tint vertex rengi
# Dönüş: { "wood": ArrayMesh, "needle": ArrayMesh }

const GOLDEN := 2.399963229728653

static func build(stems: Array, cfg: Dictionary) -> Dictionary:
	var wood := SurfaceTool.new()
	wood.begin(Mesh.PRIMITIVE_TRIANGLES)
	var leaf := SurfaceTool.new()
	leaf.begin(Mesh.PRIMITIVE_TRIANGLES)

	var sides: int = int(cfg.get("trunk_sides", 12))
	var nlen: float = cfg.get("needle_size", 1.2)

	for stem in stems:
		var lvl: int = int(stem["level"])
		if lvl == 0:
			_tube(wood, stem, sides)
		elif lvl == 1:
			_tube(wood, stem, maxi(5, int(sides / 2.0)))
			# Ana dalın yalnız DIŞ yarısı iğnelenir -> açık, çıplak-içli çam.
			_sprigs(leaf, stem, nlen * 0.22, 0.45)
		elif lvl == 2:
			_sprigs(leaf, stem, nlen * 0.20, 0.0)
		elif lvl == 3:
			_sprigs(leaf, stem, nlen * 0.16, 0.0)

	wood.generate_normals()
	wood.generate_tangents()
	var out := {}
	out["wood"] = wood.commit()
	out["needle"] = leaf.commit()
	return out

# --- Odun tüpü ---------------------------------------------------------

static func _tube(st: SurfaceTool, stem: Dictionary, sides: int) -> void:
	var pts: Array = stem["points"]
	var tang: Array = stem["tangents"]
	var norms: Array = stem["normals"]
	var n := pts.size()
	var r0: float = stem["radius0"]
	var r1: float = stem["radius1"]
	var det: float = 1.0 if int(stem["level"]) == 0 else 4.5
	for k in range(n - 1):
		var f0 := float(k) / float(n - 1)
		var f1 := float(k + 1) / float(n - 1)
		var rad0: float = lerp(r0, r1, pow(f0, 0.85))
		var rad1: float = lerp(r0, r1, pow(f1, 0.85))
		if int(stem["level"]) == 0:
			rad0 += r0 * 1.4 * pow(maxf(1.0 - f0 * 6.0, 0.0), 2.0)
			rad1 += r0 * 1.4 * pow(maxf(1.0 - f1 * 6.0, 0.0), 2.0)
		var c0: Vector3 = pts[k]
		var c1: Vector3 = pts[k + 1]
		var n0: Vector3 = norms[k]
		var n1: Vector3 = norms[k + 1]
		var b0: Vector3 = (tang[k] as Vector3).cross(n0).normalized()
		var b1: Vector3 = (tang[k + 1] as Vector3).cross(n1).normalized()
		for si in range(sides):
			var a0 := TAU * float(si) / float(sides)
			var a1 := TAU * float(si + 1) / float(sides)
			var d00 := n0 * cos(a0) + b0 * sin(a0)
			var d10 := n0 * cos(a1) + b0 * sin(a1)
			var d01 := n1 * cos(a0) + b1 * sin(a0)
			var d11 := n1 * cos(a1) + b1 * sin(a1)
			var uA := float(si) / float(sides) * 2.0
			var uB := float(si + 1) / float(sides) * 2.0
			var v0 := f0 * 5.0 * det
			var v1 := f1 * 5.0 * det
			st.set_uv(Vector2(uA, v0)); st.add_vertex(c0 + d00 * rad0)
			st.set_uv(Vector2(uA, v1)); st.add_vertex(c1 + d01 * rad1)
			st.set_uv(Vector2(uB, v1)); st.add_vertex(c1 + d11 * rad1)
			st.set_uv(Vector2(uA, v0)); st.add_vertex(c0 + d00 * rad0)
			st.set_uv(Vector2(uB, v1)); st.add_vertex(c1 + d11 * rad1)
			st.set_uv(Vector2(uB, v0)); st.add_vertex(c0 + d10 * rad0)

# --- İğne demeti kartları (sürgün boyunca dağıtılmış) -----------------

static func _sprigs(st: SurfaceTool, stem: Dictionary, size: float, start_u: float) -> void:
	var pts: Array = stem["points"]
	var norms: Array = stem["normals"]
	var n := pts.size()
	if n < 2:
		return
	var depth01: float = stem.get("depth01", 0.5)
	var tint: float = stem.get("tint", 1.0)
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
			if fr >= start_u:
				var c: Vector3 = c0 + ax * t
				idx += 1
				# İstasyon başına 2 zıt demet -> sürgünü saran fırça.
				for s in range(2):
					var az: float = float(idx) * GOLDEN + PI * float(s)
					var outd: Vector3 = nm.rotated(ax, az).normalized()
					var up: Vector3 = (outd * 0.78 + ax * 0.42 + Vector3.DOWN * 0.16).normalized()
					var rt: Vector3 = up.cross(Vector3.UP)
					if rt.length() < 0.02:
						rt = up.cross(Vector3.RIGHT)
					rt = rt.normalized()
					var ao: float = clampf((0.46 + 0.50 * fr + 0.06 * depth01) * tint, 0.0, 1.0)
					_card(st, c, up * size, rt * (size * 0.55), ao)
			t += step
		carry = t - seg_len

# Tek demet = çapraz 2 dörtgen (X); tabandan uca yelpaze.
static func _card(st: SurfaceTool, c: Vector3, uv_dir: Vector3, rv: Vector3, ao: float) -> void:
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
		st.set_normal(nA); st.set_uv(Vector2(0.32, 1.0)); st.add_vertex(c - base)
		st.set_normal(nA); st.set_uv(Vector2(0.68, 1.0)); st.add_vertex(c + base)
		st.set_normal(nT); st.set_uv(Vector2(1.0, 0.0)); st.add_vertex(tip + rq)
		st.set_normal(nA); st.set_uv(Vector2(0.32, 1.0)); st.add_vertex(c - base)
		st.set_normal(nT); st.set_uv(Vector2(1.0, 0.0)); st.add_vertex(tip + rq)
		st.set_normal(nT); st.set_uv(Vector2(0.0, 0.0)); st.add_vertex(tip - rq)

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
