@tool
extends Node3D
class_name PineTree

# Prosedürel gerçekçi çam ağacı.
# - Kök payandalı, S-eğimli, kabuk dokulu gövde
# - Altın açı (phyllotaxis) ile spiral dizilen gerçek dallar; uçları sarkar
# - Dallar boyunca prosedürel iğne dokulu yaprak kartları (çapraz frond)
# - Rüzgar + alt-yüzey ışık shader'ı
# Dokular tüm ağaçlarda paylaşılır (static cache) -> orman ucuz kalır.

@export_group("Boyut")
@export var total_height: float = 6.5
@export var trunk_radius: float = 0.16
@export_range(0.04, 0.5, 0.01) var trunk_top_ratio: float = 0.10
@export_range(0.0, 0.5, 0.01) var trunk_bend: float = 0.10

@export_group("Dallar")
@export var crown_start_ratio: float = 0.28
@export_range(2.0, 8.0, 0.1) var crown_radius: float = 2.2
@export_range(20, 90, 1) var branch_count: int = 54
@export_range(0.2, 1.4, 0.02) var branch_droop: float = 0.7

@export_group("İğne Yaprak")
@export_range(2, 8, 1) var fronds_per_branch: int = 5
@export_range(0.25, 1.4, 0.05) var frond_size: float = 0.7

@export_group("Detay / Performans")
@export_range(5, 12, 1) var trunk_sides: int = 8
@export var seed: int = 0
@export var generate_collision: bool = true
@export var enable_wind: bool = true

@export_group("Renk")
@export var bark_color: Color = Color(0.26, 0.18, 0.12)
@export var needle_base: Color = Color(0.10, 0.21, 0.10)
@export var needle_tip: Color = Color(0.30, 0.45, 0.22)

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

	var bend_phase := _rng.randf() * TAU
	_build_trunk(bark, bend_phase)
	_build_branches(bark, leaf, bend_phase)

	bark.generate_normals()
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
	# Yükseklikle artan yumuşak S eğrisi (rüzgardan/yaştan eğilmiş ağaç).
	var amt := trunk_bend * total_height
	return Vector3(sin(h01 * 1.7 + phase) * amt * h01 * h01,
		0.0,
		cos(h01 * 1.3 + phase) * amt * 0.6 * h01 * h01)

func _trunk_point(h01: float, phase: float) -> Vector3:
	return Vector3(0.0, h01 * total_height, 0.0) + _bend_offset(h01, phase)

func _build_trunk(st: SurfaceTool, phase: float) -> void:
	var rings := 14
	var r_bottom := trunk_radius
	var r_top := trunk_radius * trunk_top_ratio
	var side_jit := PackedFloat32Array()
	for s in range(trunk_sides):
		side_jit.append(1.0 + _rng.randf_range(-0.07, 0.07))
	for ri in range(rings):
		var t0 := float(ri) / float(rings)
		var t1 := float(ri + 1) / float(rings)
		var c0 := _trunk_point(t0, phase)
		var c1 := _trunk_point(t1, phase)
		# Kök payandası: en alttaki halkalarda yarıçap şişer.
		var flare0: float = 1.0 + pow(1.0 - t0, 3.0) * 1.6
		var flare1: float = 1.0 + pow(1.0 - t1, 3.0) * 1.6
		var rr0: float = lerp(r_bottom, r_top, t0) * flare0
		var rr1: float = lerp(r_bottom, r_top, t1) * flare1
		for si in range(trunk_sides):
			var a0 := TAU * float(si) / float(trunk_sides)
			var a1 := TAU * float(si + 1) / float(trunk_sides)
			var j0: float = side_jit[si]
			var j1: float = side_jit[(si + 1) % trunk_sides]
			var uA := float(si) / float(trunk_sides) * 3.0
			var uB := float(si + 1) / float(trunk_sides) * 3.0
			var p00 := c0 + Vector3(cos(a0) * rr0 * j0, 0, sin(a0) * rr0 * j0)
			var p10 := c0 + Vector3(cos(a1) * rr0 * j1, 0, sin(a1) * rr0 * j1)
			var p01 := c1 + Vector3(cos(a0) * rr1 * j0, 0, sin(a0) * rr1 * j0)
			var p11 := c1 + Vector3(cos(a1) * rr1 * j1, 0, sin(a1) * rr1 * j1)
			st.set_uv(Vector2(uA, t0 * 4.0)); st.add_vertex(p00)
			st.set_uv(Vector2(uA, t1 * 4.0)); st.add_vertex(p01)
			st.set_uv(Vector2(uB, t1 * 4.0)); st.add_vertex(p11)
			st.set_uv(Vector2(uA, t0 * 4.0)); st.add_vertex(p00)
			st.set_uv(Vector2(uB, t1 * 4.0)); st.add_vertex(p11)
			st.set_uv(Vector2(uB, t0 * 4.0)); st.add_vertex(p10)

# --- Dallar + iğne kartları -------------------------------------------

func _build_branches(bark: SurfaceTool, leaf: SurfaceTool, phase: float) -> void:
	var crown_start := crown_start_ratio
	for i in range(branch_count):
		var f := float(i) / float(branch_count - 1)
		# Tabanda uzun ve yoğun, tepeye doğru kısalan dallar.
		var h01: float = lerp(crown_start, 0.985, f)
		var attach := _trunk_point(h01, phase)
		var az := i * GOLDEN_ANGLE + _rng.randf_range(-0.12, 0.12)
		var taper: float = 1.0 - smoothstep(0.0, 1.0, (h01 - crown_start) / (1.0 - crown_start))
		var length: float = crown_radius * (0.22 + 0.78 * taper) * _rng.randf_range(0.85, 1.12)
		if length < 0.25:
			continue
		var dir := Vector3(cos(az), 0.0, sin(az))
		# Kalkış hafif yukarı; gövdeden uzaklaştıkça yerçekimiyle sarkar.
		var up0: float = lerp(0.05, 0.45, taper)
		var segs := 4
		var pts: Array[Vector3] = [attach]
		var cur := attach
		var seg_dir := (dir + Vector3.UP * up0).normalized()
		for s in range(segs):
			var sl := length / float(segs)
			cur = cur + seg_dir * sl
			pts.append(cur)
			# Her segmentte aşağı bük (uçta belirgin sarkma).
			var droop := branch_droop * (0.18 + 0.55 * float(s) / float(segs))
			seg_dir = (seg_dir + Vector3.DOWN * droop).normalized()
		_emit_branch_wood(bark, pts, h01)
		_emit_fronds(leaf, pts, length, taper)

func _emit_branch_wood(st: SurfaceTool, pts: Array[Vector3], h01: float) -> void:
	var sides := 4
	var n := pts.size()
	for k in range(n - 1):
		var r0: float = lerp(trunk_radius * 0.30, 0.006, float(k) / float(n - 1))
		var r1: float = lerp(trunk_radius * 0.30, 0.006, float(k + 1) / float(n - 1))
		var axis := (pts[k + 1] - pts[k]).normalized()
		var up := Vector3.UP if abs(axis.y) < 0.95 else Vector3.RIGHT
		var nx := axis.cross(up).normalized()
		var nz := axis.cross(nx).normalized()
		for si in range(sides):
			var a0 := TAU * float(si) / float(sides)
			var a1 := TAU * float(si + 1) / float(sides)
			var o0a := (nx * cos(a0) + nz * sin(a0))
			var o1a := (nx * cos(a1) + nz * sin(a1))
			var p00 := pts[k] + o0a * r0
			var p10 := pts[k] + o1a * r0
			var p01 := pts[k + 1] + o0a * r1
			var p11 := pts[k + 1] + o1a * r1
			st.set_uv(Vector2(0.0, 0.0)); st.add_vertex(p00)
			st.set_uv(Vector2(0.0, 1.0)); st.add_vertex(p01)
			st.set_uv(Vector2(1.0, 1.0)); st.add_vertex(p11)
			st.set_uv(Vector2(0.0, 0.0)); st.add_vertex(p00)
			st.set_uv(Vector2(1.0, 1.0)); st.add_vertex(p11)
			st.set_uv(Vector2(1.0, 0.0)); st.add_vertex(p10)

func _emit_fronds(st: SurfaceTool, pts: Array[Vector3], length: float, taper: float) -> void:
	# Dal boyunca, ekseni saran çapraz iğne kartları.
	var count := fronds_per_branch
	for fi in range(count):
		var ft := (float(fi) + 0.5) / float(count)
		var seg_f := ft * float(pts.size() - 1)
		var idx: int = clampi(int(seg_f), 0, pts.size() - 2)
		var local := seg_f - float(idx)
		var center: Vector3 = pts[idx].lerp(pts[idx + 1], local)
		var axis := (pts[idx + 1] - pts[idx]).normalized()
		var size: float = frond_size * (0.45 + 0.85 * taper) * (1.05 - 0.55 * ft)
		size *= _rng.randf_range(0.82, 1.18)
		# Tepe ucundaki ana lider sürgün hariç, üç çapraz düzlem.
		var planes := 3
		var roll0 := _rng.randf() * PI
		for pi in range(planes):
			var roll := roll0 + PI * float(pi) / float(planes)
			var up := Vector3.UP if abs(axis.y) < 0.95 else Vector3.FORWARD
			var side := axis.cross(up).normalized()
			var bn := axis.cross(side).normalized()
			var spread := side * cos(roll) + bn * sin(roll)
			var along := axis * size * 1.25
			var wide := spread * size
			# Karta hafif aşağı yönelim (gerçek iğne demeti gibi).
			var sag := Vector3.DOWN * size * 0.18
			var a := center - along * 0.2 - wide
			var b := center + along
			var bb := center + along + sag
			var c := center - along * 0.2 + wide
			# Dörtgen: (a)-(c) tabanda, (bb) uçta -> üçgen yelpaze yaprak.
			st.set_uv(Vector2(0, 1)); st.add_vertex(a)
			st.set_uv(Vector2(1, 1)); st.add_vertex(c)
			st.set_uv(Vector2(1, 0)); st.add_vertex(bb)
			st.set_uv(Vector2(0, 1)); st.add_vertex(a)
			st.set_uv(Vector2(1, 0)); st.add_vertex(bb)
			st.set_uv(Vector2(0, 0)); st.add_vertex(b)

# --- Materyaller / dokular --------------------------------------------

func _bark_material() -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = bark_color
	m.albedo_texture = _bark_texture()
	m.roughness = 0.95
	m.metallic = 0.0
	m.specular = 0.08
	m.uv1_scale = Vector3(1, 1, 1)
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
			sm.set_shader_parameter("wind_strength", 0.14)
			sm.set_shader_parameter("needle_tex", tex)
			return sm
	var m := StandardMaterial3D.new()
	m.albedo_texture = tex
	m.albedo_color = needle_tip
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
	m.alpha_scissor_threshold = 0.4
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	m.roughness = 0.9
	return m

func _needle_texture() -> Texture2D:
	if _shared_needle_tex != null:
		return _shared_needle_tex
	var s := 256
	var img := Image.create(s, s, false, Image.FORMAT_RGBA8)
	img.fill(Color(0, 0, 0, 0))
	var rng := RandomNumberGenerator.new()
	rng.seed = 9001
	# Birkaç dalcık + üzerinde yana açılı iğneler.
	var sprigs := 5
	for sp in range(sprigs):
		var bx: float = lerp(40.0, 216.0, (float(sp) + 0.5) / float(sprigs))
		var stem_top := Vector2(bx + rng.randf_range(-12, 12), 18.0)
		var stem_bot := Vector2(bx + rng.randf_range(-10, 10), 244.0)
		var nstep := 26
		for i in range(nstep):
			var u := float(i) / float(nstep - 1)
			var on_stem := stem_bot.lerp(stem_top, u)
			var nl: float = lerp(46.0, 14.0, u) * rng.randf_range(0.8, 1.15)
			for sgn in [-1.0, 1.0]:
				var ang := deg_to_rad(58.0) * sgn
				var d := Vector2(sin(ang), -cos(ang)) * nl
				var dark := Color(0.05, 0.16, 0.06)
				var lite := Color(0.26, 0.42, 0.18)
				_draw_needle(img, on_stem, on_stem + d, 1.7,
					dark.lerp(lite, rng.randf_range(0.1, 0.6)),
					lite, rng)
	_shared_needle_tex = ImageTexture.create_from_image(img)
	return _shared_needle_tex

func _draw_needle(img: Image, p0: Vector2, p1: Vector2, w: float, c0: Color, c1: Color, rng: RandomNumberGenerator) -> void:
	var steps := int(ceil(p0.distance_to(p1)))
	for s in range(steps + 1):
		var t := float(s) / float(maxi(steps, 1))
		var p := p0.lerp(p1, t)
		var col := c0.lerp(c1, t)
		col.a = lerp(1.0, 0.55, t)  # uçlar daha şeffaf
		var rad := maxf(w * (1.0 - 0.4 * t), 0.6)
		var ri := int(ceil(rad))
		for oy in range(-ri, ri + 1):
			for ox in range(-ri, ri + 1):
				if Vector2(ox, oy).length() > rad:
					continue
				var px := int(p.x) + ox
				var py := int(p.y) + oy
				if px < 0 or py < 0 or px >= img.get_width() or py >= img.get_height():
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
	n.frequency = 0.06
	var n2 := FastNoiseLite.new()
	n2.noise_type = FastNoiseLite.TYPE_SIMPLEX
	n2.frequency = 0.015
	for y in range(h):
		for x in range(w):
			# Dikey lifli kabuk: yatayda sık, dikeyde uzun çatlaklar.
			var fib := n.get_noise_2d(float(x) * 3.0, float(y) * 0.5)
			var crack := n2.get_noise_2d(float(x) * 2.0, float(y) * 0.4)
			var v: float = 0.5 + 0.35 * fib + 0.2 * crack
			v = clampf(v, 0.18, 1.0)
			if crack < -0.35:
				v *= 0.45  # derin çatlak gölgesi
			var col := Color(0.30, 0.21, 0.14) * v + Color(0.04, 0.03, 0.02)
			img.set_pixel(x, y, Color(col.r, col.g, col.b, 1.0))
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
