@tool
extends Node3D
class_name PineTree

# Prosedürel gerçekçi çam ağacı.
# - Konik, hafif eğri gövde + kabuk dokusu rengi
# - Aşağı doğru sarkan, üst üste binen birçok iğne katmanı
# - Rüzgarda salınan yaprak shader'ı
# - İsteğe bağlı çarpışma gövdesi
# Mobil renderer için düşük poligonlu ama katmanlı/derinlikli.

@export_group("Boyut")
@export var total_height: float = 6.5
@export var trunk_radius: float = 0.16
@export_range(0.05, 0.6, 0.01) var trunk_top_ratio: float = 0.18
@export_range(0.0, 0.4, 0.01) var trunk_lean: float = 0.06

@export_group("İğne Yaprak Katmanları")
@export_range(4, 14, 1) var foliage_layers: int = 9
@export var crown_start_ratio: float = 0.22
@export var crown_max_radius: float = 2.1
@export_range(0.3, 1.5, 0.05) var layer_droop: float = 0.7

@export_group("Detay / Performans")
@export_range(5, 14, 1) var trunk_sides: int = 8
@export_range(6, 16, 1) var foliage_sides: int = 10
@export var seed: int = 0
@export var generate_collision: bool = true
@export var enable_wind: bool = true

@export_group("Renk")
@export var bark_color: Color = Color(0.20, 0.13, 0.09)
@export var needle_base: Color = Color(0.07, 0.20, 0.09)
@export var needle_tip: Color = Color(0.22, 0.40, 0.18)

var _rng := RandomNumberGenerator.new()

func _ready() -> void:
	rebuild()

func rebuild() -> void:
	for c in get_children():
		c.queue_free()
	_rng.seed = seed if seed != 0 else hash(name)

	var trunk_mi := MeshInstance3D.new()
	trunk_mi.name = "Trunk"
	trunk_mi.mesh = _build_trunk()
	trunk_mi.material_override = _bark_material()
	trunk_mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
	add_child(trunk_mi)

	var foliage_mi := MeshInstance3D.new()
	foliage_mi.name = "Foliage"
	foliage_mi.mesh = _build_foliage()
	foliage_mi.material_override = _needle_material()
	foliage_mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
	add_child(foliage_mi)

	if generate_collision and not Engine.is_editor_hint():
		_build_collision()

func _build_trunk() -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var rings := 6
	var bottom_r := trunk_radius
	var top_r := trunk_radius * trunk_top_ratio
	# Kenar başına sabit düzensizlik -> halkalar arası su sızdırmaz birleşim.
	var side_jit: PackedFloat32Array = PackedFloat32Array()
	for si in range(trunk_sides):
		side_jit.append(1.0 + _rng.randf_range(-0.08, 0.08))
	for ri in range(rings):
		var t0 := float(ri) / float(rings)
		var t1 := float(ri + 1) / float(rings)
		var y0 := t0 * total_height
		var y1 := t1 * total_height
		var r0: float = lerp(bottom_r, top_r, t0)
		var r1: float = lerp(bottom_r, top_r, t1)
		# Eğri büyüme + ince düzensizlik (kabuk hissi).
		var lean0 := trunk_lean * total_height * t0 * t0
		var lean1 := trunk_lean * total_height * t1 * t1
		var u0 := t0
		var u1 := t1
		for si in range(trunk_sides):
			var a0 := TAU * float(si) / float(trunk_sides)
			var a1 := TAU * float(si + 1) / float(trunk_sides)
			var j0: float = side_jit[si]
			var j1: float = side_jit[(si + 1) % trunk_sides]
			var uv00 := Vector2(float(si) / float(trunk_sides), u0)
			var uv10 := Vector2(float(si + 1) / float(trunk_sides), u0)
			var uv01 := Vector2(float(si) / float(trunk_sides), u1)
			var uv11 := Vector2(float(si + 1) / float(trunk_sides), u1)
			var p00 := Vector3(cos(a0) * r0 * j0 + lean0, y0, sin(a0) * r0 * j0)
			var p10 := Vector3(cos(a1) * r0 * j1 + lean0, y0, sin(a1) * r0 * j1)
			var p01 := Vector3(cos(a0) * r1 * j0 + lean1, y1, sin(a0) * r1 * j0)
			var p11 := Vector3(cos(a1) * r1 * j1 + lean1, y1, sin(a1) * r1 * j1)
			st.set_uv(uv00); st.add_vertex(p00)
			st.set_uv(uv01); st.add_vertex(p01)
			st.set_uv(uv11); st.add_vertex(p11)
			st.set_uv(uv00); st.add_vertex(p00)
			st.set_uv(uv11); st.add_vertex(p11)
			st.set_uv(uv10); st.add_vertex(p10)
	st.generate_normals()
	return st.commit()

func _build_foliage() -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var crown_start := total_height * crown_start_ratio
	var crown_h := total_height - crown_start
	for li in range(foliage_layers):
		var lt := float(li) / float(foliage_layers - 1)
		# Tepeye gidildikçe daralan koni katmanları, alttan üste binen.
		var radius: float = lerp(crown_max_radius, crown_max_radius * 0.12, pow(lt, 0.85))
		radius *= _rng.randf_range(0.92, 1.08)
		var base_y: float = crown_start + lt * crown_h
		var layer_h: float = lerp(crown_h * 0.42, crown_h * 0.16, lt)
		var tip_y := base_y + layer_h
		var droop := layer_h * layer_droop
		var sides := foliage_sides
		var ang_off := _rng.randf() * TAU
		for si in range(sides):
			var a0 := ang_off + TAU * float(si) / float(sides)
			var a1 := ang_off + TAU * float(si + 1) / float(sides)
			# Dış uçları aşağı sarkan dal görünümü.
			var r_jit0 := radius * _rng.randf_range(0.85, 1.0)
			var r_jit1 := radius * _rng.randf_range(0.85, 1.0)
			var e0 := Vector3(cos(a0) * r_jit0, base_y - droop, sin(a0) * r_jit0)
			var e1 := Vector3(cos(a1) * r_jit1, base_y - droop, sin(a1) * r_jit1)
			var tip := Vector3(0.0, tip_y, 0.0)
			var mid0 := Vector3(cos(a0) * r_jit0 * 0.45, base_y + layer_h * 0.35, sin(a0) * r_jit0 * 0.45)
			var mid1 := Vector3(cos(a1) * r_jit1 * 0.45, base_y + layer_h * 0.35, sin(a1) * r_jit1 * 0.45)
			var uo := float(si) / float(sides)
			var u1v := float(si + 1) / float(sides)
			var uv_e0 := Vector2(uo, lt)
			var uv_e1 := Vector2(u1v, lt)
			var uv_m0 := Vector2(uo, lt + 0.1)
			var uv_m1 := Vector2(u1v, lt + 0.1)
			var uv_tip := Vector2((uo + u1v) * 0.5, 1.0)
			# İki segmentli yan yüzey -> daha hacimli silüet.
			st.set_uv(uv_e0); st.add_vertex(e0)
			st.set_uv(uv_m0); st.add_vertex(mid0)
			st.set_uv(uv_m1); st.add_vertex(mid1)
			st.set_uv(uv_e0); st.add_vertex(e0)
			st.set_uv(uv_m1); st.add_vertex(mid1)
			st.set_uv(uv_e1); st.add_vertex(e1)
			st.set_uv(uv_m0); st.add_vertex(mid0)
			st.set_uv(uv_tip); st.add_vertex(tip)
			st.set_uv(uv_m1); st.add_vertex(mid1)
	st.generate_normals()
	return st.commit()

func _bark_material() -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = bark_color
	m.roughness = 0.95
	m.metallic = 0.0
	m.specular = 0.1
	return m

func _needle_material() -> Material:
	if enable_wind and ResourceLoader.exists("res://shaders/pine_wind.gdshader"):
		var sh := ResourceLoader.load("res://shaders/pine_wind.gdshader") as Shader
		if sh != null:
			var sm := ShaderMaterial.new()
			sm.shader = sh
			sm.set_shader_parameter("base_color", needle_base)
			sm.set_shader_parameter("tip_color", needle_tip)
			sm.set_shader_parameter("tree_height", total_height)
			sm.set_shader_parameter("wind_strength", 0.16)
			sm.set_shader_parameter("noise_tex", _make_noise_texture())
			return sm
	var m := StandardMaterial3D.new()
	m.albedo_color = needle_base
	m.roughness = 0.9
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	return m

func _make_noise_texture() -> NoiseTexture2D:
	var n := FastNoiseLite.new()
	n.noise_type = FastNoiseLite.TYPE_SIMPLEX
	n.frequency = 0.05
	var tex := NoiseTexture2D.new()
	tex.noise = n
	tex.width = 128
	tex.height = 128
	return tex

func _build_collision() -> void:
	var body := StaticBody3D.new()
	body.name = "TrunkBody"
	add_child(body)
	var col := CollisionShape3D.new()
	var shape := CylinderShape3D.new()
	shape.radius = maxf(trunk_radius * 1.3, 0.18)
	shape.height = total_height
	col.shape = shape
	col.position = Vector3(0.0, total_height * 0.5, 0.0)
	body.add_child(col)
