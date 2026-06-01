extends CharacterBody3D
class_name MousePlayer

# Oyuncu fare: joystick/klavye ile hareket, zıplama, yüzme (suda yüzgeç),
# saldırı, araziye oturan üçüncü-şahıs takip kamerası.

@export var walk_speed: float = 3.5
@export var run_speed: float = 7.5
@export var swim_speed: float = 2.6
@export var jump_velocity: float = 5.2
@export var gravity: float = 18.0
@export var turn_speed: float = 9.0
@export var model_scale: float = 1.15
@export var cam_distance: float = 4.5
@export var cam_height: float = 1.4

var terrain: Terrain
var hud: Node            # HUD (get_move_vector / get_look_delta / consume_jump / consume_attack)

var visual: MouseVisual
var cam_pivot: Node3D
var spring: SpringArm3D
var camera: Camera3D
var cam_yaw: float = 0.0
var cam_pitch: float = -0.32
var in_water: bool = false
var nuts := {"ceviz": 0, "fistik": 0}

signal nut_changed(ceviz: int, fistik: int)

func _ready() -> void:
	# Çarpışma kapsülü (kök = ayaklar, y=0 zeminde)
	var col := CollisionShape3D.new()
	var cap := CapsuleShape3D.new()
	cap.radius = 0.24 * model_scale
	cap.height = 0.8 * model_scale
	col.shape = cap
	col.position.y = cap.height * 0.5
	add_child(col)

	# Görsel + animasyon
	visual = MouseVisual.new()
	visual.name = "Visual"
	add_child(visual)
	visual.setup(model_scale)

	# Kamera direği
	cam_pivot = Node3D.new()
	cam_pivot.name = "CamPivot"
	add_child(cam_pivot)
	cam_pivot.position.y = cam_height
	spring = SpringArm3D.new()
	cam_pivot.add_child(spring)
	spring.spring_length = cam_distance
	spring.margin = 0.3
	camera = Camera3D.new()
	spring.add_child(camera)
	camera.current = true
	camera.fov = 70.0

	add_to_group("player")

func _physics_process(delta: float) -> void:
	if terrain == null or not terrain.built:
		return

	# Kamera yönelimi (HUD sağ-sürükleme veya fare/sağ çubuk)
	var look := _get_look_delta()
	cam_yaw -= look.x * 0.005
	cam_pitch = clampf(cam_pitch - look.y * 0.005, -1.2, 0.2)
	cam_pivot.rotation.y = cam_yaw
	spring.rotation.x = cam_pitch

	# Su durumu
	in_water = terrain.is_water(global_position.x, global_position.z)
	var on_floor := is_on_floor()

	# Hareket girişi (kamera-göreli)
	var inp := _get_move_input()
	var dir := Vector3.ZERO
	if inp.length() > 0.05:
		var fwd := Vector3(-sin(cam_yaw), 0, -cos(cam_yaw))
		var right := Vector3(cos(cam_yaw), 0, -sin(cam_yaw))
		dir = (fwd * inp.y + right * inp.x)
		dir.y = 0
		dir = dir.normalized()

	var running := Input.is_action_pressed("run") or inp.length() > 0.92
	var speed := swim_speed if in_water else (run_speed if running else walk_speed)

	# Yatay hız
	if dir.length() > 0.1:
		velocity.x = dir.x * speed
		velocity.z = dir.z * speed
		var target_yaw := atan2(-dir.x, -dir.z)
		rotation.y = lerp_angle(rotation.y, target_yaw, clampf(turn_speed * delta, 0.0, 1.0))
	else:
		velocity.x = move_toward(velocity.x, 0.0, speed * 6.0 * delta)
		velocity.z = move_toward(velocity.z, 0.0, speed * 6.0 * delta)

	# Dikey: yerçekimi veya suda kaldırma kuvveti
	if in_water:
		var ws := terrain.water_surface_y
		var target_y := ws - 0.12 * model_scale     # gövde yüzeyin hemen altında
		var diff := target_y - global_position.y
		velocity.y = lerpf(velocity.y, clampf(diff * 5.0, -2.0, 2.5), 0.25)
	else:
		if not on_floor:
			velocity.y -= gravity * delta
		elif velocity.y < 0.0:
			velocity.y = -0.5
		if _consume_jump() and on_floor:
			velocity.y = jump_velocity

	# Saldırı
	if _consume_attack():
		if visual.attack():
			_do_attack_hit()

	move_and_slide()

	# Sınır içinde tut
	var half := terrain.world_size * 0.5 - 2.0
	global_position.x = clampf(global_position.x, -half, half)
	global_position.z = clampf(global_position.z, -half, half)

	# Animasyon durumunu güncelle
	var planar := Vector2(velocity.x, velocity.z).length()
	visual.set_locomotion(planar, run_speed * 0.65, in_water)

func _do_attack_hit() -> void:
	# Yakındaki NPC fareleri korkut/kaçır.
	for n in get_tree().get_nodes_in_group("npc_mouse"):
		if n is Node3D and global_position.distance_to((n as Node3D).global_position) < 2.5 * model_scale:
			if n.has_method("scare"):
				n.scare(global_position)

func collect_nut(kind: String) -> void:
	if nuts.has(kind):
		nuts[kind] += 1
		nut_changed.emit(nuts["ceviz"], nuts["fistik"])

# ---- Giriş yardımcıları (HUD + klavye/gamepad fallback) ----
func _get_move_input() -> Vector2:
	var v := Vector2.ZERO
	if hud != null and hud.has_method("get_move_vector"):
		v = hud.get_move_vector()
	if v.length() < 0.05:
		v.x = Input.get_axis("move_left", "move_right")
		v.y = -Input.get_axis("move_back", "move_forward")  # ileri = +y
	return Vector2(v.x, v.y).limit_length(1.0)

func _get_look_delta() -> Vector2:
	if hud != null and hud.has_method("get_look_delta"):
		return hud.get_look_delta()
	return Vector2.ZERO

func _consume_jump() -> bool:
	if hud != null and hud.has_method("consume_jump") and hud.consume_jump():
		return true
	return Input.is_action_just_pressed("jump")

func _consume_attack() -> bool:
	if hud != null and hud.has_method("consume_attack") and hud.consume_attack():
		return true
	return Input.is_action_just_pressed("attack")
