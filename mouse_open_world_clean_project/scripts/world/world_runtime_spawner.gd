extends Node

# World editörde boş kalır. Player ve UI sadece oyun çalışınca eklenir.

@export_group("Player")
@export var player_scene_path: String = "res://scenes/player/player.tscn"
@export var player_spawn_position: Vector3 = Vector3(0.0, 8.0, 0.0)

@export_group("Mobile UI")
@export var create_mobile_ui_at_runtime: bool = true
@export var mobile_ui_script_path: String = "res://scripts/ui/mobile_ui.gd"

@export_group("Terrain")
@export var terrain_runtime_path: NodePath = NodePath("../TerrainRuntime")

var player: Node3D
var mobile_ui: CanvasLayer

func _ready() -> void:
	_spawn_player()
	_spawn_mobile_ui()
	_bind_terrain_to_player()

func _spawn_player() -> void:
	if get_parent().get_node_or_null("Player") != null:
		player = get_parent().get_node_or_null("Player") as Node3D
		return
	if not ResourceLoader.exists(player_scene_path):
		push_error("Player sahnesi bulunamadı: " + player_scene_path)
		return
	var packed: PackedScene = ResourceLoader.load(player_scene_path, "", ResourceLoader.CACHE_MODE_REPLACE) as PackedScene
	if packed == null:
		return
	var instance: Node = packed.instantiate()
	instance.name = "Player"
	get_parent().add_child(instance)
	if instance is Node3D:
		player = instance as Node3D
		player.global_position = player_spawn_position

func _spawn_mobile_ui() -> void:
	if not create_mobile_ui_at_runtime:
		return
	if get_parent().get_node_or_null("MobileUI") != null:
		return
	mobile_ui = CanvasLayer.new()
	mobile_ui.name = "MobileUI"
	mobile_ui.layer = 20
	mobile_ui.add_to_group("mobile_ui", true)
	if ResourceLoader.exists(mobile_ui_script_path):
		var script: Script = ResourceLoader.load(mobile_ui_script_path, "", ResourceLoader.CACHE_MODE_REPLACE) as Script
		if script != null:
			mobile_ui.set_script(script)

	var control: Control = Control.new()
	control.name = "Control"
	mobile_ui.add_child(control)
	_add_texture_rect(control, "JoystickBase")
	_add_texture_rect(control, "JoystickKnob")
	_add_touch_button(control, "JumpButton")
	_add_touch_button(control, "SprintButton")
	var stamina_root: Control = Control.new()
	stamina_root.name = "StaminaRoot"
	control.add_child(stamina_root)
	_add_color_rect(stamina_root, "StaminaBg")
	_add_color_rect(stamina_root, "StaminaFill")
	_add_label(stamina_root, "StaminaLabel")
	_add_label(control, "JumpLabel")
	_add_label(control, "SprintLabel")
	_add_label(control, "JoystickHint")
	get_parent().add_child(mobile_ui)

func _add_texture_rect(parent: Node, node_name: String) -> TextureRect:
	var node: TextureRect = TextureRect.new()
	node.name = node_name
	parent.add_child(node)
	return node

func _add_touch_button(parent: Node, node_name: String) -> TouchScreenButton:
	var node: TouchScreenButton = TouchScreenButton.new()
	node.name = node_name
	parent.add_child(node)
	return node

func _add_color_rect(parent: Node, node_name: String) -> ColorRect:
	var node: ColorRect = ColorRect.new()
	node.name = node_name
	parent.add_child(node)
	return node

func _add_label(parent: Node, node_name: String) -> Label:
	var node: Label = Label.new()
	node.name = node_name
	parent.add_child(node)
	return node

func _bind_terrain_to_player() -> void:
	var terrain_runtime: Node = get_node_or_null(terrain_runtime_path)
	if terrain_runtime == null:
		return
	terrain_runtime.set("player_path", NodePath("../Player"))
