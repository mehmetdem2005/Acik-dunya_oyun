@tool
extends Node3D
class_name PineTree

# AAA prosedürel iğne yapraklı ağaç (ladin/çam tipi konifer).
# - Kök payandalı, plakalı kabuk dokulu, hafif eğimli gövde
# - Belirgin KATMANLI (whorl) dal tabakaları -> net kozalak silüeti
# - Her dal boyunca yoğun, tilelenen iğne şeridi (çok katmanlı, sarkık)
# - Silüeti dolduran karanlık iç koni (delik/şeffaflık yok)
# - AO + yükseklik vertex rengi; hacimsel foliage normali (karton değil)
# - Rüzgar + alt-yüzey ışık shader'ı
# Dokular tüm ağaçlarda paylaşılır (static cache) -> orman ucuz kalır.

@export_group("Boyut")
@export var total_height: float = 7.0
@export var trunk_radius: float = 0.16
@export_range(0.03, 0.4, 0.01) var trunk_top_ratio: float = 0.06
@export_range(0.0, 0.3, 0.01) var trunk_bend: float = 0.05

@export_group("Taç / Dallar")
@export var crown_start_ratio: float = 0.12
@export_range(1.5, 6.0, 0.1) var crown_radius: float = 2.4
@export_range(20, 90, 1) var branch_count: int = 56
@export_range(0.15, 1.2, 0.02) var branch_droop: float = 0.55

@export_group("İğne Yaprak")
@export_range(2, 6, 1) var fronds_per_branch: int = 4
@export_range(0.4, 2.0, 0.05) var frond_size: float = 1.0
@export var inner_fill: bool = true

@export_group("Detay / Performans")
@export_range(6, 14, 1) var trunk_sides: int = 10
@export var seed: int = 0
@export var generate_collision: bool = true
@export var enable_wind: bool = true

@export_group("Renk")
@export var bark_color: Color = Color(0.32, 0.21, 0.14)
@export var needle_base: Color = Color(0.06, 0.16, 0.08)
@export var needle_tip: Color = Color(0.28, 0.44, 0.20)

const GOLDEN_ANGLE := 2.399963229728653

static var _shared_needle_tex: Texture2D
static var _shared_bark_tex: Texture2D

var _rng := RandomNumberGenerator.new()

func _ready() -> void:
	rebuild()

func rebuild() -> void:
	for c in get_children():
		c.queue_free()
	_rng.seed = seed if seed != 0 else hash(name)

	var bark := SurfaceTool.new()
	bark.begin(Mesh.PRIMITIVE_TRIANGLES)
	var leaf := SurfaceTool.new()
	leaf.begin(Mesh.PRIMITIVE_TRIANGLES)

	var phase := _rng.randf() * TAU
	_build_trunk(bark, phase)
	if inner_fill:
		_build_inner_cone(leaf, phase)
	_build_tiers(bark, leaf, phase)

	bark.generate_normals()
	bark.generate_tangents()
	var bark_mi := MeshInstance3D.new()
	bark_mi.name = "Bark"
	bark_mi.mesh = bark.commit()
	bark_mi.material_override = _bark_material()
	add_child(bark_mi)

	leaf.generate_normals()
	var leaf_mi := MeshInstance3D.new()
	leaf_mi.name = "Foliage"
	leaf_mi.mesh = leaf.commit()
	leaf_mi.material_override = _needle_material()
	add_child(leaf_mi)

	if generate_collision and not Engine.is_editor_hint():
		_build_collision()

# --- Gövde -------------------------------------------------------------

func _bend_offset(h01: float, phase: float) -> Vector3:
	var amt := trunk_bend * total_height
	return Vector3(sin(h01 * 1.4 + phase) * amt * h01 * h01, 0.0,
		cos(h01 * 1.1 + phase) * amt * 0.5 * h01 * h01)

func _trunk_point(h01: float, phase: float) -> Vector3:
	return Vector3(0.0, h01 * total_height, 0.0) + _bend_offset(h01, phase)

func _trunk_radius_at(t: float) -> float:
	# Konik gövde + tabanda kök payandası şişkinliği.
	var base: float = lerp(trunk_radius, trunk_radius * trunk_top_ratio, pow(t, 0.85))
	var buttress := trunk_radius * 1.4 * pow(maxf(1.0 - t * 6.0, 0.0), 2.0)
	return base + buttress

func _build_trunk(st: SurfaceTool, phase: float) -> void:
	var rings := 20
	var side_jit := PackedFloat32Array()
	for s in range(trunk_sides):
		side_jit.append(1.0 + _rng.randf_range(-0.06, 0.08))
	for ri in range(rings):
		var t0 := float(ri) / float(rings)
		var t1 := float(ri + 1) / float(rings)
		var c0 := _trunk_point(t0, phase)
		var c1 := _trunk_point(t1, phase)
		var rr0 := _trunk_radius_at(t0)
		var rr1 := _trunk_radius_at(t1)
		for si in range(trunk_sides):
			var a0 := TAU * float(si) / float(trunk_sides)
			var a1 := TAU * float(si + 1) / float(trunk_sides)
			var j0: float = side_jit[si]
			var j1: float = side_jit[(si + 1) % trunk_sides]
			var uA := float(si) / float(trunk_sides) * 2.0
			var uB := float(si + 1) / float(trunk_sides) * 2.0
			var v0 := t0 * 6.0
			var v1 := t1 * 6.0
			var p00 := c0 + Vector3(cos(a0) * rr0 * j0, 0, sin(a0) * rr0 * j0)
			var p10 := c0 + Vector3(cos(a1) * rr0 * j1, 0, sin(a1) * rr0 * j1)
			var p01 := c1 + Vector3(cos(a0) * rr1 * j0, 0, sin(a0) * rr1 * j0)
			var p11 := c1 + Vector3(cos(a1) * rr1 * j1, 0, sin(a1) * rr1 * j1)
			st.set_uv(Vector2(uA, v0)); st.add_vertex(p00)
			st.set_uv(Vector2(uA, v1)); st.add_vertex(p01)
			st.set_uv(Vector2(uB, v1)); st.add_vertex(p11)
			st.set_uv(Vector2(uA, v0)); st.add_vertex(p00)
			st.set_uv(Vector2(uB, v1)); st.add_vertex(p11)
			st.set_uv(Vector2(uB, v0)); st.add_vertex(p10)

# --- İç dolgu konisi (silüeti kapatır, derinlik verir) ----------------

func _build_inner_cone(st: SurfaceTool, phase: float) -> void:
	var sides := 9
	var rings := 7
	var c_start := crown_start_ratio
	for ri in range(rings):
		var t0 := float(ri) / float(rings)
		var t1 := float(ri + 1) / float(rings)
		var h0: float = lerp(c_start, 0.97, t0)
		var h1: float = lerp(c_start, 0.97, t1)
		var c0 := _trunk_point(h0, phase)
		var c1 := _trunk_point(h1, phase)
		var rr0 := crown_radius * 0.55 * pow(1.0 - t0, 0.8)
		var rr1 := crown_radius * 0.55 * pow(1.0 - t1, 0.8)
		var ao0 := 0.35 + 0.15 * t0
		var ao1 := 0.35 + 0.15 * t1
		for si in range(sides):
			var a0 := TAU * float(si) / float(sides)
			var a1 := TAU * float(si + 1) / float(sides)
			_leaf_vert(st, c0 + Vector3(cos(a0) * rr0, 0, sin(a0) * rr0), Vector2(0, t0 * 3.0), ao0, c0.y)
			_leaf_vert(st, c1 + Vector3(cos(a0) * rr1, 0, sin(a0) * rr1), Vector2(0, t1 * 3.0), ao1, c1.y)
			_leaf_vert(st, c1 + Vector3(cos(a1) * rr1, 0, sin(a1) * rr1), Vector2(1, t1 * 3.0), ao1, c1.y)
			_leaf_vert(st, c0 + Vector3(cos(a0) * rr0, 0, sin(a0) * rr0), Vector2(0, t0 * 3.0), ao0, c0.y)
			_leaf_vert(st, c1 + Vector3(cos(a1) * rr1, 0, sin(a1) * rr1), Vector2(1, t1 * 3.0), ao1, c1.y)
			_leaf_vert(st, c0 + Vector3(cos(a1) * rr0, 0, sin(a1) * rr0), Vector2(1, t0 * 3.0), ao0, c0.y)

# --- Katmanlı dal tabakaları ------------------------------------------

func _build_tiers(bark: SurfaceTool, leaf: SurfaceTool, phase: float) -> void:
	var tier_count := clampi(int(round(total_height * 2.0)), 8, 18)
	var c_start := crown_start_ratio
	var tier_az := _rng.randf() * TAU
	for ti in range(tier_count):
		var tf := float(ti) / float(tier_count - 1)
		var h01: float = lerp(c_start, 0.965, tf)
		# Konifer profili: orta-altta en uzun, tepede sıfıra.
		var prof: float = pow(1.0 - tf, 0.78) * (0.55 + 0.45 * smoothstep(0.0, 0.22, tf))
		var tier_len := crown_radius * prof
		if tier_len < 0.18:
			continue
		var per_tier := int(round(lerp(float(branch_count) / float(tier_count) * 1.4, 3.0, tf)))
		per_tier = clampi(per_tier, 3, 9)
		tier_az += GOLDEN_ANGLE * 1.3
		for bi in range(per_tier):
			var az := tier_az + TAU * float(bi) / float(per_tier) + _rng.randf_range(-0.18, 0.18)
			var jitter_h := h01 + _rng.randf_range(-0.015, 0.015)
			var attach := _trunk_point(jitter_h, phase)
			var length := tier_len * _rng.randf_range(0.85, 1.12)
			var droop_amt := branch_droop * (0.4 + 0.6 * (1.0 - tf))
			_make_branch(bark, leaf, attach, az, length, droop_amt, tf)

func _make_branch(bark: SurfaceTool, leaf: SurfaceTool, attach: Vector3, az: float,
		length: float, droop_amt: float, tf: float) -> void:
	var dir := Vector3(cos(az), 0.0, sin(az))
	var up0: float = lerp(0.28, 0.06, tf)  # alt tabakalar daha yatay
	var segs := 5
	var pts: Array[Vector3] = [attach]
	var cur := attach
	var seg_dir := (dir + Vector3.UP * up0).normalized()
	for s in range(segs):
		var sl := length / float(segs)
		cur += seg_dir * sl
		pts.append(cur)
		var d := droop_amt * (0.12 + 0.5 * float(s) / float(segs))
		seg_dir = (seg_dir + Vector3.DOWN * d).normalized()
	_emit_branch_wood(bark, pts)
	# Çok katmanlı yoğun iğne şeritleri (hacim için döndürülmüş kopyalar).
	var strips := clampi(fronds_per_branch, 2, 5)
	for spi in range(strips):
		var roll := PI * float(spi) / float(strips) + _rng.randf_range(-0.2, 0.2)
		_emit_needle_strip(leaf, pts, length, tf, roll, spi == 0)

func _emit_branch_wood(st: SurfaceTool, pts: Array[Vector3]) -> void:
	var sides := 4
	var n := pts.size()
	for k in range(n - 1):
		var r0: float = lerp(trunk_radius * 0.26, 0.005, float(k) / float(n - 1))
		var r1: float = lerp(trunk_radius * 0.26, 0.005, float(k + 1) / float(n - 1))
		var axis := (pts[k + 1] - pts[k]).normalized()
		var up := Vector3.UP if absf(axis.y) < 0.95 else Vector3.RIGHT
		var nx := axis.cross(up).normalized()
		var nz := axis.cross(nx).normalized()
		for si in range(sides):
			var a0 := TAU * float(si) / float(sides)
			var a1 := TAU * float(si + 1) / float(sides)
			var o0 := nx * cos(a0) + nz * sin(a0)
			var o1 := nx * cos(a1) + nz * sin(a1)
			var p00 := pts[k] + o0 * r0
			var p10 := pts[k] + o1 * r0
			var p01 := pts[k + 1] + o0 * r1
			var p11 := pts[k + 1] + o1 * r1
			st.set_uv(Vector2(0, 0)); st.add_vertex(p00)
			st.set_uv(Vector2(0, 1)); st.add_vertex(p01)
			st.set_uv(Vector2(1, 1)); st.add_vertex(p11)
			st.set_uv(Vector2(0, 0)); st.add_vertex(p00)
			st.set_uv(Vector2(1, 1)); st.add_vertex(p11)
			st.set_uv(Vector2(1, 0)); st.add_vertex(p10)

func _emit_needle_strip(st: SurfaceTool, pts: Array[Vector3], length: float,
		tf: float, roll: float, primary: bool) -> void:
	# Dalı izleyen, ekseni saran düz iğne şeridi; doku V'de tilelenir.
	var n := pts.size()
	var axis0 := (pts[1] - pts[0]).normalized()
	var up := Vector3.UP if absf(axis0.y) < 0.95 else Vector3.FORWARD
	var ref := axis0.cross(up).normalized()
	var width := frond_size * (0.34 + 0.34 * (1.0 - tf))
	var acc := 0.0
	for k in range(n - 1):
		var seg := pts[k + 1] - pts[k]
		var seg_len := seg.length()
		var axis := seg.normalized()
		# Şerit düzlemi: eksen + döndürülmüş referans (her şerit farklı açı).
		var bn := axis.cross(ref).normalized()
		var flat := (ref * cos(roll) + bn * sin(roll)).normalized()
		var kf0 := float(k) / float(n - 1)
		var kf1 := float(k + 1) / float(n - 1)
		# Genişlik profili: tabana yakın dar, ortada en geniş, uçta sivri.
		var w0 := width * _spray_w(kf0)
		var w1 := width * _spray_w(kf1)
		var sag0 := Vector3.DOWN * w0 * 0.5
		var sag1 := Vector3.DOWN * w1 * 0.5
		var L0 := pts[k] - flat * w0 + sag0 * 0.3
		var R0 := pts[k] + flat * w0 + sag0 * 0.3
		var L1 := pts[k + 1] - flat * w1 + sag1 * 0.3
		var R1 := pts[k + 1] + flat * w1 + sag1 * 0.3
		var v0 := acc
		acc += seg_len / maxf(frond_size * 0.55, 0.1)
		var v1 := acc
		# AO: gövdeye yakın koyu, uca/dışa doğru aydınlık.
		var ao0: float = lerp(0.45, 1.0, kf0)
		var ao1: float = lerp(0.45, 1.0, kf1)
		var h0 := pts[k].y
		var h1 := pts[k + 1].y
		_leaf_vert(st, L0, Vector2(0, v0), ao0, h0)
		_leaf_vert(st, L1, Vector2(0, v1), ao1, h1)
		_leaf_vert(st, R1, Vector2(1, v1), ao1, h1)
		_leaf_vert(st, L0, Vector2(0, v0), ao0, h0)
		_leaf_vert(st, R1, Vector2(1, v1), ao1, h1)
		_leaf_vert(st, R0, Vector2(1, v0), ao0, h0)

func _spray_w(k: float) -> float:
	# 0..1 dal boyu -> normalize genişlik (yelpaze profili).
	return sin(clampf(k, 0.0, 1.0) * PI) * 0.7 + (1.0 - k) * 0.5 + 0.12

func _leaf_vert(st: SurfaceTool, p: Vector3, uv: Vector2, ao: float, world_y: float) -> void:
	var hf: float = clampf(world_y / maxf(total_height, 0.001), 0.0, 1.0)
	st.set_color(Color(ao, ao, ao, hf))
	st.set_uv(uv)
	st.add_vertex(p)

# --- Materyaller / dokular --------------------------------------------

func _bark_material() -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = bark_color
	m.albedo_texture = _bark_texture()
	m.roughness = 0.92
	m.metallic = 0.0
	m.specular = 0.12
	return m

func _needle_material() -> Material:
	var tex := _needle_texture()
	if enable_wind and ResourceLoader.exists("res://shaders/pine_wind.gdshader"):
		var sh := ResourceLoader.load("res://shaders/pine_wind.gdshader") as Shader
		if sh != null:
			var sm := ShaderMaterial.new()
			sm.shader = sh
			sm.set_shader_parameter("base_color", needle_base)
			sm.set_shader_parameter("tip_color", needle_tip)
			sm.set_shader_parameter("tree_height", total_height)
			sm.set_shader_parameter("wind_strength", 0.13)
			sm.set_shader_parameter("needle_tex", tex)
			return sm
	var m := StandardMaterial3D.new()
	m.albedo_texture = tex
	m.albedo_color = needle_tip
	m.vertex_color_use_as_albedo = true
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
	m.alpha_scissor_threshold = 0.45
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	m.roughness = 0.88
	return m

func _needle_texture() -> Texture2D:
	if _shared_needle_tex != null:
		return _shared_needle_tex
	# Dikeyde tilelenebilir yoğun iğne dalcığı (orta sap + iki yana iğneler).
	var w := 256
	var h := 256
	var img := Image.create(w, h, false, Image.FORMAT_RGBA8)
	img.fill(Color(0, 0, 0, 0))
	var rng := RandomNumberGenerator.new()
	rng.seed = 7331
	var cx := float(w) * 0.5
	var dark := Color(0.04, 0.13, 0.05)
	var lite := Color(0.30, 0.46, 0.20)
	# Sapın iki yanına, yukarı eğimli, uzunlukları değişen iğneler.
	var rows := 46
	var signs: Array[float] = [-1.0, 1.0]
	for r in range(rows):
		var y := float(r) / float(rows) * float(h)
		var sx := cx + sin(y * 0.05) * 10.0
		for sgn in signs:
			var count := 3
			for c in range(count):
				var jy := y + rng.randf_range(-2.0, 2.0)
				var nl := rng.randf_range(46.0, 92.0)
				var ang: float = deg_to_rad(rng.randf_range(42.0, 66.0)) * sgn
				var p0 := Vector2(sx + sgn * 2.0, jy)
				var p1 := p0 + Vector2(sin(ang), -cos(ang)) * nl
				var cc := dark.lerp(lite, rng.randf_range(0.0, 0.7))
				_draw_needle(img, p0, p1, rng.randf_range(1.1, 1.8), cc, lite, true)
	# Orta sap (ince koyu çizgi).
	for r in range(h):
		var sx2 := int(cx + sin(float(r) * 0.05) * 10.0)
		for ox in range(-1, 2):
			var px := sx2 + ox
			if px >= 0 and px < w:
				img.set_pixel(px, r, Color(0.07, 0.14, 0.06, 1.0))
	_shared_needle_tex = ImageTexture.create_from_image(img)
	return _shared_needle_tex

func _draw_needle(img: Image, p0: Vector2, p1: Vector2, w: float, c0: Color, c1: Color, wrap: bool) -> void:
	var steps := int(ceil(p0.distance_to(p1)))
	var H := img.get_height()
	var W := img.get_width()
	for s in range(steps + 1):
		var t := float(s) / float(maxi(steps, 1))
		var p := p0.lerp(p1, t)
		var col := c0.lerp(c1, t)
		col.a = lerp(1.0, 0.45, t)
		var rad := maxf(w * (1.0 - 0.5 * t), 0.55)
		var ri := int(ceil(rad))
		for oy in range(-ri, ri + 1):
			for ox in range(-ri, ri + 1):
				if Vector2(ox, oy).length() > rad:
					continue
				var px := int(round(p.x)) + ox
				var py := int(round(p.y)) + oy
				if wrap:
					py = ((py % H) + H) % H  # dikey tilelenebilirlik
				if px < 0 or px >= W or py < 0 or py >= H:
					continue
				var ex := img.get_pixel(px, py)
				if col.a > ex.a:
					img.set_pixel(px, py, col)

func _bark_texture() -> Texture2D:
	if _shared_bark_tex != null:
		return _shared_bark_tex
	var w := 128
	var h := 256
	var img := Image.create(w, h, false, Image.FORMAT_RGBA8)
	var n := FastNoiseLite.new()
	n.noise_type = FastNoiseLite.TYPE_SIMPLEX
	n.frequency = 0.05
	var plate := FastNoiseLite.new()
	plate.noise_type = FastNoiseLite.TYPE_CELLULAR
	plate.frequency = 0.018
	plate.cellular_return_type = FastNoiseLite.RETURN_DISTANCE2_SUB
	for y in range(h):
		for x in range(w):
			var fib := n.get_noise_2d(float(x) * 3.0, float(y) * 0.55)
			var pl := plate.get_noise_2d(float(x) * 1.6, float(y) * 1.0)
			var v: float = 0.62 + 0.30 * fib
			# Hücresel plaka sınırları -> derin kabuk çatlakları.
			if pl > 0.32:
				v *= 0.38
			elif pl > 0.18:
				v *= 0.7
			v = clampf(v, 0.12, 1.05)
			var warm := Color(0.40, 0.25, 0.16) * v + Color(0.05, 0.03, 0.02)
			img.set_pixel(x, y, Color(warm.r, warm.g, warm.b, 1.0))
	_shared_bark_tex = ImageTexture.create_from_image(img)
	return _shared_bark_tex

func _build_collision() -> void:
	var body := StaticBody3D.new()
	body.name = "TrunkBody"
	add_child(body)
	var col := CollisionShape3D.new()
	var shape := CylinderShape3D.new()
	shape.radius = maxf(trunk_radius * 1.4, 0.18)
	shape.height = total_height
	col.shape = shape
	col.position = Vector3(0.0, total_height * 0.5, 0.0)
	body.add_child(col)
