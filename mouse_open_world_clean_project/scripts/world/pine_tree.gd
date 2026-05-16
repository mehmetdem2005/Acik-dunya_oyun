@tool
extends Node3D
class_name PineTree

# AAA prosedürel çam/ladin MODELİ — çok geçişli mimari:
#   PineSkeleton (özyinelemeli dal grafiği, RMF frame, tropizm)
#   -> PineMesh (odun tüpleri + katlı iğne şeritleri, yumuşak normal)
#   -> PineTextures (önbellekli prosedürel kabuk + iğne atlası)
# Harici model/doku dosyası GEREKMEZ. .tscn export adları korunur.

@export_group("Boyut")
@export var total_height: float = 7.5
@export var trunk_radius: float = 0.18
@export_range(0.03, 0.4, 0.01) var trunk_top_ratio: float = 0.05
@export_range(0.0, 0.2, 0.005) var trunk_bend: float = 0.04

@export_group("Taç / Dallar")
@export var crown_start_ratio: float = 0.27
@export_range(1.5, 6.0, 0.1) var crown_radius: float = 2.7
@export_range(20, 110, 1) var branch_count: int = 58
@export_range(0.0, 1.0, 0.02) var branch_droop: float = 0.22
@export_range(3, 12, 1) var shoots_per_branch: int = 8
@export var fine_twigs: bool = true
@export_range(0, 4, 1) var twigs_per_shoot: int = 2

@export_group("İğne Yaprak")
@export_range(2, 5, 1) var blades_per_branch: int = 3
@export_range(0.4, 2.5, 0.05) var frond_size: float = 1.2

@export_group("Form / Kusur")
@export_enum("Genc Konik:0", "Olgun Orman:1", "Acikta Yetisen:2") var tree_form: int = 1
@export_range(0.08, 0.30, 0.01) var branch_taper_tip: float = 0.18
@export_range(0.0, 0.5, 0.01) var knot_strength: float = 0.22
@export_range(0.0, 1.0, 0.05) var light_bias: float = 0.0

@export_group("Detay / Performans")
@export_range(8, 20, 1) var trunk_sides: int = 14
@export var seed: int = 20260516
@export var generate_collision: bool = true
@export var enable_wind: bool = true

@export_group("Renk / Materyal")
@export var bark_color: Color = Color(0.85, 0.82, 0.80)
@export_range(0.2, 2.0, 0.05) var bark_normal_scale: float = 1.0
@export var needle_dark: Color = Color(0.045, 0.110, 0.050)
@export var needle_mid: Color = Color(0.110, 0.230, 0.105)
@export var needle_lite: Color = Color(0.300, 0.420, 0.170)

func _ready() -> void:
	rebuild()

func rebuild() -> void:
	for c in get_children():
		c.queue_free()

	# Form ön ayarları (genç konik / olgun orman / açıkta yetişen).
	var f_crown := crown_start_ratio
	var f_pl := 0.30
	var f_ph := 0.04
	var f_dry := 0.16
	var f_brk := 0.08
	var f_droop := branch_droop
	var f_el := -0.18
	var f_eh := 0.55
	match tree_form:
		0:
			f_crown = 0.10
			f_pl = 0.05; f_ph = 0.02
			f_dry = 0.05; f_brk = 0.03
			f_droop = maxf(branch_droop * 0.6, 0.10)
			f_el = 0.05; f_eh = 0.75
		2:
			f_crown = 0.06
			f_pl = 0.04; f_ph = 0.03
			f_dry = 0.06; f_brk = 0.04
			f_droop = maxf(branch_droop * 1.1, 0.25)
			f_el = -0.10; f_eh = 0.45
		_:
			f_crown = 0.32

	var cfg := {
		"seed": seed if seed != 0 else hash(name),
		"height": total_height,
		"trunk_radius": trunk_radius,
		"trunk_top": trunk_top_ratio,
		"trunk_bend": trunk_bend,
		"crown_start": f_crown,
		"crown_radius": crown_radius,
		"branch_count": branch_count,
		"branch_droop": f_droop,
		"shoots_per_branch": shoots_per_branch,
		"trunk_sides": trunk_sides,
		"needle_planes": blades_per_branch,
		"needle_size": frond_size,
		"fine_twigs": fine_twigs,
		"twigs_per_shoot": twigs_per_shoot,
		"prune_low": f_pl,
		"prune_high": f_ph,
		"dry_chance_low": f_dry,
		"broken_chance": f_brk,
		"elev_low": f_el,
		"elev_high": f_eh,
		"branch_taper_tip": branch_taper_tip,
		"knot_strength": knot_strength,
		"light_bias": light_bias,
	}

	var skel := PineSkeleton.new()
	var stems := skel.build(cfg)
	var meshes := PineMesh.build(stems, cfg)

	var wood_mi := MeshInstance3D.new()
	wood_mi.name = "Wood"
	wood_mi.mesh = meshes["wood"]
	wood_mi.material_override = _wood_material()
	add_child(wood_mi)

	var leaf_mi := MeshInstance3D.new()
	leaf_mi.name = "Foliage"
	leaf_mi.mesh = meshes["needle"]
	leaf_mi.material_override = _needle_material()
	add_child(leaf_mi)

	if generate_collision and not Engine.is_editor_hint():
		_build_collision()

func _wood_material() -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = bark_color
	m.albedo_texture = PineTextures.bark()
	m.normal_enabled = true
	m.normal_texture = PineTextures.bark_normal()
	m.normal_scale = bark_normal_scale
	# Uzun gövdede plaka esnemesin (V'de yoğunlaştır).
	m.uv1_scale = Vector3(1.0, 1.5, 1.0)
	m.roughness = 0.88
	m.specular = 0.5
	return m

func _needle_material() -> Material:
	var tex := PineTextures.needle_atlas()
	if enable_wind and ResourceLoader.exists("res://shaders/pine_wind.gdshader"):
		var sh := ResourceLoader.load("res://shaders/pine_wind.gdshader") as Shader
		if sh != null:
			var sm := ShaderMaterial.new()
			sm.shader = sh
			sm.set_shader_parameter("needle_tex", tex)
			sm.set_shader_parameter("tree_height", total_height)
			sm.set_shader_parameter("backlight_col", needle_mid * 0.45)
			return sm
	# Güvenli fallback (rüzgârsız ama doğru): native backlight.
	var m := StandardMaterial3D.new()
	m.albedo_texture = tex
	m.albedo_color = Color(1, 1, 1, 1)
	m.vertex_color_use_as_albedo = true
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
	m.alpha_scissor_threshold = 0.33
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	m.roughness = 0.65
	m.specular = 0.5
	m.backlight_enabled = true
	m.backlight = needle_mid * 0.45
	m.emission_enabled = true
	m.emission = needle_dark
	m.emission_energy_multiplier = 0.02
	return m

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
