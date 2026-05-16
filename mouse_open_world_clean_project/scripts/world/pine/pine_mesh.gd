@tool
class_name PineMesh
extends RefCounted

# İskelet stem'lerinden geometri üretir:
# - Odun: gövde + ana dallar, frame halkalarıyla pürüzsüz tüp
# - İğne: yan sürgünler boyunca KATLI (V-kesitli) çapraz şeritler;
#   yumuşak hacim normalleri (karton görünüm yok), AO vertex rengi
# Dönüş: { "wood": ArrayMesh, "needle": ArrayMesh }

static func build(stems: Array, cfg: Dictionary) -> Dictionary:
	var wood := SurfaceTool.new()
	wood.begin(Mesh.PRIMITIVE_TRIANGLES)
	var leaf := SurfaceTool.new()
	leaf.begin(Mesh.PRIMITIVE_TRIANGLES)

	var sides: int = int(cfg.get("trunk_sides", 10))
	var planes: int = clampi(int(cfg.get("needle_planes", 3)), 2, 5)
	var nlen: float = cfg.get("needle_size", 1.0)

	for stem in stems:
		var lvl: int = stem["level"]
		if lvl <= 1:
			_tube(wood, stem, sides if lvl == 0 else maxi(5, int(sides / 2.0)))
		if lvl == 1:
			# Ana dalın kendisi de iğnelenir (çıplak kahverengi dal yok).
			var bp := clampi(planes - 1, 2, 3)
			for pj in range(bp):
				_needle_blade(leaf, stem, TAU * float(pj) / float(bp), nlen * 1.05)
		if lvl == 2:
			for pi in range(planes):
				var roll := TAU * float(pi) / float(planes)
				_needle_blade(leaf, stem, roll, nlen)
		if lvl == 3:
			# İnce dallar: sadece iğne (odun çizilmez), silüet kırılımı.
			for pk in range(2):
				_needle_blade(leaf, stem, TAU * float(pk) / 2.0, nlen * 0.7)

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
	# İnce dallarda kabuk detayını sıklaştır (dev plaka esnemesi yok).
	var det: float = 1.0 if int(stem["level"]) == 0 else 4.5
	for k in range(n - 1):
		var f0 := float(k) / float(n - 1)
		var f1 := float(k + 1) / float(n - 1)
		var rad0: float = lerp(r0, r1, pow(f0, 0.85))
		var rad1: float = lerp(r0, r1, pow(f1, 0.85))
		# Tabanda kök payandası (sadece gövde, level 0).
		if stem["level"] == 0:
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

# --- Katlı iğne şeridi (V-kesit, yumuşak normal) ----------------------

static func _needle_blade(st: SurfaceTool, stem: Dictionary, roll: float, nlen: float) -> void:
	var pts: Array = stem["points"]
	var tang: Array = stem["tangents"]
	var norms: Array = stem["normals"]
	var n := pts.size()
	var depth01: float = stem.get("depth01", 0.5)
	var tint: float = stem.get("tint", 1.0)
	var width := nlen * 0.16
	var acc := 0.0
	for k in range(n - 1):
		var c0: Vector3 = pts[k]
		var c1: Vector3 = pts[k + 1]
		var ax: Vector3 = (c1 - c0)
		var seg_len := ax.length()
		if seg_len < 1e-5:
			continue
		ax = ax / seg_len
		var nm: Vector3 = norms[k]
		var bn: Vector3 = ax.cross(nm).normalized()
		var flat := (nm * cos(roll) + bn * sin(roll)).normalized()
		var pn := ax.cross(flat).normalized()
		var f0 := float(k) / float(n - 1)
		var f1 := float(k + 1) / float(n - 1)
		var w0 := width * _wprof(f0)
		var w1 := width * _wprof(f1)
		var sag0 := Vector3.DOWN * w0 * 0.5
		var sag1 := Vector3.DOWN * w1 * 0.5
		var L0 := c0 - flat * w0 + sag0
		var R0 := c0 + flat * w0 + sag0
		var L1 := c1 - flat * w1 + sag1
		var R1 := c1 + flat * w1 + sag1
		var M0 := c0 + pn * (w0 * 0.55)
		var M1 := c1 + pn * (w1 * 0.55)
		var v0 := acc
		acc += seg_len / maxf(nlen * 0.42, 0.08)
		var v1 := acc
		var ao0: float = clampf((0.40 + 0.55 * f0 + 0.08 * depth01) * tint, 0.0, 1.0)
		var ao1: float = clampf((0.40 + 0.55 * f1 + 0.08 * depth01) * tint, 0.0, 1.0)
		# Sol yarım yüz.
		var nLf := _soft(L0, pn - flat)
		var nRf := _soft(R0, pn + flat)
		_v(st, L0, Vector2(0.0, v0), ao0, nLf)
		_v(st, L1, Vector2(0.0, v1), ao1, _soft(L1, pn - flat))
		_v(st, M1, Vector2(0.5, v1), ao1, _soft(M1, pn))
		_v(st, L0, Vector2(0.0, v0), ao0, nLf)
		_v(st, M1, Vector2(0.5, v1), ao1, _soft(M1, pn))
		_v(st, M0, Vector2(0.5, v0), ao0, _soft(M0, pn))
		# Sağ yarım yüz.
		_v(st, M0, Vector2(0.5, v0), ao0, _soft(M0, pn))
		_v(st, M1, Vector2(0.5, v1), ao1, _soft(M1, pn))
		_v(st, R1, Vector2(1.0, v1), ao1, _soft(R1, pn + flat))
		_v(st, M0, Vector2(0.5, v0), ao0, _soft(M0, pn))
		_v(st, R1, Vector2(1.0, v1), ao1, _soft(R1, pn + flat))
		_v(st, R0, Vector2(1.0, v0), ao0, nRf)

static func _wprof(k: float) -> float:
	return sin(clampf(k, 0.0, 1.0) * PI) * 0.65 + (1.0 - k) * 0.45 + 0.15

# Geometrik kat normalini, gövdeden dışa+yukarı yumuşak hacim
# normaliyle harmanlar -> foliage karton değil, dolgun koni gibi ışıklanır.
static func _soft(p: Vector3, fold: Vector3) -> Vector3:
	var radial := Vector3(p.x, 0.0, p.z)
	var outward: Vector3
	if radial.length() < 0.001:
		outward = Vector3.UP
	else:
		outward = radial.normalized()
	var soft := (outward * 0.6 + Vector3.UP * 0.5).normalized()
	return (fold.normalized() * 0.45 + soft * 0.75).normalized()

static func _v(st: SurfaceTool, p: Vector3, uv: Vector2, ao: float, nrm: Vector3) -> void:
	var a := clampf(ao, 0.0, 1.0)
	st.set_color(Color(a, a, a, 1.0))
	st.set_normal(nrm)
	st.set_uv(uv)
	st.add_vertex(p)
