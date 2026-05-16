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
@export var crown_start_ratio: float = 0.12
@export_range(1.5, 6.0, 0.1) var crown_radius: float = 2.7
@export_range(20, 110, 1) var branch_count: int = 70
@export_range(0.15, 1.2, 0.02) var branch_droop: float = 0.5
@export_range(3, 12, 1) var shoots_per_branch: int = 8

@export_group("İğne Yaprak")
@export_range(2, 5, 1) var blades_per_branch: int = 3
@export_range(0.4, 2.0, 0.05) var frond_size: float = 0.8

@export_group("Detay / Performans")
@export_range(6, 14, 1) var trunk_sides: int = 10
@export var seed: int = 20260516
@export var generate_collision: bool = true
@export var enable_wind: bool = false

@export_group("Renk")
@export var bark_color: Color = Color(0.34, 0.22, 0.15)
@export var needle_dark: Color = Color(0.07, 0.15, 0.08)
@export var needle_mid: Color = Color(0.14, 0.26, 0.13)
@export var needle_lite: Color = Color(0.30, 0.42, 0.21)

func _ready() -> void:
	rebuild()

func rebuild() -> void:
	for c in get_children():
		c.queue_free()

	var cfg := {
		"seed": seed if seed != 0 else hash(name),
		"height": total_height,
		"trunk_radius": trunk_radius,
		"trunk_top": trunk_top_ratio,
		"trunk_bend": trunk_bend,
		"crown_start": crown_start_ratio,
		"crown_radius": crown_radius,
		"branch_count": branch_count,
		"branch_droop": branch_droop,
		"shoots_per_branch": shoots_per_branch,
		"trunk_sides": trunk_sides,
		"needle_planes": blades_per_branch,
		"needle_size": frond_size,
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
	m.uv1_scale = Vector3(1.0, 1.0, 1.0)
	m.roughness = 0.93
	m.specular = 0.12
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
			sm.set_shader_parameter("tip_color", needle_lite)
			return sm
	var m := StandardMaterial3D.new()
	m.albedo_texture = tex
	# Renk atlas (yeşil) * vertex AO'dan gelir; aşırı kararmayı önlemek
	# için albedo_color beyaza yakın tutulur.
	m.albedo_color = Color(1, 1, 1, 1)
	m.vertex_color_use_as_albedo = true
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
	m.alpha_scissor_threshold = 0.5
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	m.roughness = 0.9
	m.specular = 0.14
	m.emission_enabled = true
	m.emission = needle_dark
	m.emission_energy_multiplier = 0.04
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
