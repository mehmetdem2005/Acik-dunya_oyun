extends CharacterBody3D

@export_group("Model")
@export var model_path: String = "res://assets/animals/mouse/mouse.glb"
@export var visual_scale: Vector3 = Vector3.ONE
@export var visual_rotation_degrees: Vector3 = Vector3(0.0, 180.0, 0.0)
@export var create_debug_mouse_if_model_missing: bool = true

@export_group("Movement")
@export var walk_speed: float = 2.4
@export var run_speed: float = 4.8
@export var acceleration: float = 16.0
@export var deceleration: float = 20.0
@export var air_control: float = 0.35
@export var jump_velocity: float = 2.9
@export var gravity: float = 16.0
@export var turn_speed: float = 14.0

@export_group("Camera")
@export var camera_sensitivity: float = 0.005
@export var camera_height: float = 0.65
@export var camera_distance: float = 2.8
@export var camera_pitch_min_deg: float = -45.0
@export var camera_pitch_max_deg: float = 25.0
@export var camera_start_pitch_deg: float = -12.0

@export_group("Stamina")
@export var max_stamina: float = 100.0
@export var sprint_drain_per_second: float = 24.0
@export var stamina_regen_per_second: float = 18.0
@export var stamina_regen_delay: float = 0.65

@onready var collision_shape: CollisionShape3D = $CollisionShape3D
@onready var camera_rig: Node3D = $CameraRig
@onready var camera_pivot: Node3D = $CameraRig/CameraPivot
@onready var camera_spring: SpringArm3D = $CameraRig/CameraPivot/CameraSpring
@onready var camera: Camera3D = $CameraRig/CameraPivot/CameraSpring/Camera3D
@onready var model_root: Node3D = $ModelRoot
@onready var mouse_visual: Node3D = $ModelRoot/MouseVisual

var stamina: float = 100.0
var stamina_regen_timer: float = 0.0
var is_sprinting: bool = false
var is_moving: bool = false
var last_move_direction: Vector3 = Vector3.FORWARD
var _mobile_ui: Node
var _camera_yaw: float = 0.0
var _camera_pitch: float = 0.0

func _ready() -> void:
	_apply_player_defaults()
	_setup_camera()
	_load_visual_model()
	stamina = max_stamina

func _physics_process(delta: float) -> void:
	if _mobile_ui == null or not is_instance_valid(_mobile_ui):
		_mobile_ui = _find_mobile_ui()
	_update_camera(delta)
	_handle_movement(delta)
	_update_mobile_ui_stamina()

func _apply_player_defaults() -> void:
	floor_snap_length = 0.25
	floor_max_angle = deg_to_rad(50.0)
	up_direction = Vector3.UP
	if collision_shape != null and collision_shape.shape is CapsuleShape3D:
		var capsule: CapsuleShape3D = collision_shape.shape as CapsuleShape3D
		capsule.radius = 0.16
		capsule.height = 0.42
		collision_shape.position = Vector3(0.0, 0.25, 0.0)

func _setup_camera() -> void:
	camera_pivot.position = Vector3(0.0, camera_height, 0.0)
	camera_spring.spring_length = camera_distance
	camera.fov = 65.0
	camera.current = true
	_camera_pitch = deg_to_rad(camera_start_pitch_deg)
	camera_pivot.rotation.x = _camera_pitch

func _load_visual_model() -> void:
	_clear_children(mouse_visual)
	if ResourceLoader.exists(model_path):
		var res: Resource = ResourceLoader.load(model_path, "", ResourceLoader.CACHE_MODE_REPLACE)
		var instance: Node = null
		if res is PackedScene:
			instance = (res as PackedScene).instantiate()
		elif res is Mesh:
			var mi: MeshInstance3D = MeshInstance3D.new()
			mi.mesh = res as Mesh
			instance = mi
		if instance != null:
			instance.name = "MouseModel"
			mouse_visual.add_child(instance)
			if instance is Node3D:
				var n3d: Node3D = instance as Node3D
				n3d.position = Vector3.ZERO
				n3d.rotation_degrees = Vector3.ZERO
				n3d.scale = Vector3.ONE
			mouse_visual.scale = visual_scale
			mouse_visual.rotation_degrees = visual_rotation_degrees
			return
	if create_debug_mouse_if_model_missing:
		_create_debug_mouse()

func _clear_children(parent: Node) -> void:
	for child: Node in parent.get_children():
		child.queue_free()

func _create_debug_mouse() -> void:
	var body: MeshInstance3D = MeshInstance3D.new()
	body.name = "DebugMouseBody"
	var mesh: CapsuleMesh = CapsuleMesh.new()
	mesh.radius = 0.18
	mesh.height = 0.55
	mesh.radial_segments = 12
	body.mesh = mesh
	body.rotation_degrees.z = 90.0
	body.position = Vector3(0, 0.25, 0)
	var mat: StandardMaterial3D = StandardMaterial3D.new()
	mat.albedo_color = Color(0.25, 0.18, 0.13, 1)
	body.material_override = mat
	mouse_visual.add_child(body)

func _find_mobile_ui() -> Node:
	var nodes: Array[Node] = get_tree().get_nodes_in_group("mobile_ui")
	for node: Node in nodes:
		if node.has_method("get_joystick_vector"):
			return node
	return null

func _update_camera(_delta: float) -> void:
	var delta_vec: Vector2 = Vector2.ZERO
	if _mobile_ui != null and _mobile_ui.has_method("consume_camera_delta"):
		delta_vec = _mobile_ui.call("consume_camera_delta")
	_camera_yaw -= delta_vec.x * camera_sensitivity
	_camera_pitch -= delta_vec.y * camera_sensitivity
	_camera_pitch = clampf(_camera_pitch, deg_to_rad(camera_pitch_min_deg), deg_to_rad(camera_pitch_max_deg))
	camera_rig.rotation.y = _camera_yaw
	camera_pivot.rotation.x = _camera_pitch

func _handle_movement(delta: float) -> void:
	var input_vec: Vector2 = _get_move_input()
	var wants_jump: bool = _get_jump_pressed()
	var wants_sprint: bool = _get_sprint_pressed()
	var move_direction: Vector3 = _input_to_world_direction(input_vec)
	is_moving = move_direction.length_squared() > 0.001
	is_sprinting = is_moving and wants_sprint and stamina > 1.0
	var target_speed: float = run_speed if is_sprinting else walk_speed
	if is_sprinting:
		_drain_stamina(delta)
	else:
		_regen_stamina(delta)
	var target_horizontal_velocity: Vector3 = Vector3.ZERO
	if is_moving:
		target_horizontal_velocity = move_direction * target_speed
		last_move_direction = move_direction
	var current_horizontal_velocity: Vector3 = Vector3(velocity.x, 0.0, velocity.z)
	var active_accel: float = acceleration if is_moving else deceleration
	if not is_on_floor():
		active_accel *= air_control
	current_horizontal_velocity = current_horizontal_velocity.move_toward(target_horizontal_velocity, active_accel * delta)
	velocity.x = current_horizontal_velocity.x
	velocity.z = current_horizontal_velocity.z
	if is_on_floor():
		if velocity.y < 0.0:
			velocity.y = -0.45
		if wants_jump:
			velocity.y = jump_velocity
	else:
		velocity.y -= gravity * delta
	move_and_slide()
	if is_moving:
		_rotate_model_to_direction(move_direction, delta)

func _get_move_input() -> Vector2:
	var input_vec: Vector2 = Vector2.ZERO
	if Input.is_key_pressed(KEY_A) or Input.is_key_pressed(KEY_LEFT):
		input_vec.x -= 1.0
	if Input.is_key_pressed(KEY_D) or Input.is_key_pressed(KEY_RIGHT):
		input_vec.x += 1.0
	if Input.is_key_pressed(KEY_W) or Input.is_key_pressed(KEY_UP):
		input_vec.y += 1.0
	if Input.is_key_pressed(KEY_S) or Input.is_key_pressed(KEY_DOWN):
		input_vec.y -= 1.0
	if _mobile_ui != null and _mobile_ui.has_method("get_joystick_vector"):
		var joystick: Vector2 = _mobile_ui.call("get_joystick_vector")
		if joystick.length_squared() > input_vec.length_squared():
			input_vec.x = joystick.x
			input_vec.y = -joystick.y
	if input_vec.length() > 1.0:
		input_vec = input_vec.normalized()
	return input_vec

func _get_jump_pressed() -> bool:
	if Input.is_key_pressed(KEY_SPACE):
		return true
	if _mobile_ui != null and _mobile_ui.has_method("consume_jump_pressed"):
		return bool(_mobile_ui.call("consume_jump_pressed"))
	return false

func _get_sprint_pressed() -> bool:
	if Input.is_key_pressed(KEY_SHIFT):
		return true
	if _mobile_ui != null and _mobile_ui.has_method("is_sprint_pressed"):
		return bool(_mobile_ui.call("is_sprint_pressed"))
	return false

func _input_to_world_direction(input_vec: Vector2) -> Vector3:
	if input_vec.length_squared() <= 0.001:
		return Vector3.ZERO
	var forward: Vector3 = -camera_rig.global_transform.basis.z
	var right: Vector3 = camera_rig.global_transform.basis.x
	forward.y = 0.0
	right.y = 0.0
	forward = forward.normalized()
	right = right.normalized()
	return (right * input_vec.x + forward * input_vec.y).normalized()

func _rotate_model_to_direction(direction: Vector3, delta: float) -> void:
	var target_yaw: float = atan2(-direction.x, -direction.z)
	model_root.rotation.y = lerp_angle(model_root.rotation.y, target_yaw, clampf(turn_speed * delta, 0.0, 1.0))

func _drain_stamina(delta: float) -> void:
	stamina -= sprint_drain_per_second * delta
	stamina = maxf(stamina, 0.0)
	stamina_regen_timer = stamina_regen_delay

func _regen_stamina(delta: float) -> void:
	if stamina_regen_timer > 0.0:
		stamina_regen_timer -= delta
		return
	stamina += stamina_regen_per_second * delta
	stamina = minf(stamina, max_stamina)

func _update_mobile_ui_stamina() -> void:
	if _mobile_ui == null or not _mobile_ui.has_method("set_stamina_ratio"):
		return
	_mobile_ui.call("set_stamina_ratio", clampf(stamina / max_stamina, 0.0, 1.0))
