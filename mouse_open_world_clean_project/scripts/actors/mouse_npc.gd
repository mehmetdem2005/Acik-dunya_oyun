extends Node3D
class_name MouseNPC

# NPC fare yapay zekası:
#  WANDER  : karada yakın hedeflere gezinir, suyu kaçınır.
#  CROSS   : (yalnız yüzücüler) dar suyu (nehir) karşıya geçer.
#  FLEE    : oyuncu saldırısından kaçar.
#
# Nehir geçişi MESAFE tabanlıdır: karşı kıyı max_cross_dist içinde bulunamazsa
# geçilmez -> deniz (çok geniş) asla geçilmez, yalnız dar nehirler geçilir.
# Ayrıca yalnız "swimmer" işaretli NPC'ler + rastgele istek + cooldown ->
# her nehir kenarındaki fare karşıya geçmez.

enum State { WANDER, CROSS, FLEE }

var terrain: Terrain
var visual: MouseVisual
var swimmer: bool = false
var model_scale: float = 0.9

var state: int = State.WANDER
var target: Vector3 = Vector3.ZERO
var velocity: Vector3 = Vector3.ZERO
var speed_walk: float = 2.0
var speed_swim: float = 1.8
var speed_flee: float = 5.5
var _cross_cooldown: float = 0.0
var _idle_timer: float = 0.0
var _in_water := false
var _y_smooth := 0.0

const MAX_CROSS_DIST := 38.0   # bundan geniş su (deniz) geçilmez

func setup(t: Terrain, is_swimmer: bool, scale: float) -> void:
	terrain = t
	swimmer = is_swimmer
	model_scale = scale
	speed_walk = randf_range(1.5, 2.6)
	_cross_cooldown = randf_range(4.0, 14.0)
	visual = MouseVisual.new()
	add_child(visual)
	visual.setup(scale, "res://assets/mouse/housemouse_npc.glb")
	add_to_group("npc_mouse")
	_y_smooth = global_position.y
	_pick_wander_target()

func _process(delta: float) -> void:
	if terrain == null or not terrain.built:
		return
	match state:
		State.WANDER:
			_update_wander(delta)
		State.CROSS:
			_update_cross(delta)
		State.FLEE:
			_update_flee(delta)

	_move_and_ground(delta)
	var planar := Vector2(velocity.x, velocity.z).length()
	visual.set_locomotion(planar, speed_walk * 1.4, _in_water)

# --- Hareket + araziye/su yüzeyine otur ---
func _move_and_ground(delta: float) -> void:
	global_position.x += velocity.x * delta
	global_position.z += velocity.z * delta
	var half := terrain.world_size * 0.5 - 2.0
	global_position.x = clampf(global_position.x, -half, half)
	global_position.z = clampf(global_position.z, -half, half)

	_in_water = terrain.is_water(global_position.x, global_position.z)
	var gy: float
	if _in_water:
		gy = terrain.water_surface_y - 0.12 * model_scale
	else:
		gy = terrain.height_at(global_position.x, global_position.z)
	_y_smooth = lerpf(_y_smooth, gy, clampf(8.0 * delta, 0.0, 1.0))
	global_position.y = _y_smooth

	# Yönelimi hıza çevir
	var planar := Vector2(velocity.x, velocity.z)
	if planar.length() > 0.15:
		var ty := atan2(-velocity.x, -velocity.z)
		rotation.y = lerp_angle(rotation.y, ty, clampf(6.0 * delta, 0.0, 1.0))

# --- WANDER ---
func _update_wander(delta: float) -> void:
	_cross_cooldown -= delta
	var to := target - global_position
	to.y = 0
	var d := to.length()
	if d < 1.2:
		_idle_timer -= delta
		velocity.x = move_toward(velocity.x, 0.0, speed_walk * 4.0 * delta)
		velocity.z = move_toward(velocity.z, 0.0, speed_walk * 4.0 * delta)
		if _idle_timer <= 0.0:
			_pick_wander_target()
		return

	var dir := to / d
	# Önümüz su mu? (yüzücü değilse kaçın)
	var ahead := global_position + dir * 1.5
	if terrain.is_water(ahead.x, ahead.z):
		# yüzücü ve cooldown bittiyse karşıya geçmeyi DENE
		if swimmer and _cross_cooldown <= 0.0 and randf() < 0.5:
			if _try_start_cross(dir):
				return
		# geçmiyorsa: yeni kara hedefi seç (sudan kaç)
		_pick_wander_target()
		return

	velocity.x = dir.x * speed_walk
	velocity.z = dir.z * speed_walk

func _pick_wander_target() -> void:
	for _i in 8:
		var ang := randf() * TAU
		var dist := randf_range(6.0, 22.0)
		var cand := global_position + Vector3(cos(ang) * dist, 0, sin(ang) * dist)
		var half := terrain.world_size * 0.5 - 4.0
		cand.x = clampf(cand.x, -half, half)
		cand.z = clampf(cand.z, -half, half)
		if not terrain.is_water(cand.x, cand.z):
			target = cand
			_idle_timer = randf_range(0.5, 2.5)
			return
	target = global_position

# --- CROSS (nehir geçişi) ---
# dir yönünde 1m adımlarla suyu tara: ilk su -> sonra ilk kara. Kara
# MAX_CROSS_DIST içindeyse hedefle, değilse geçme (deniz çok geniş).
func _try_start_cross(dir: Vector3) -> bool:
	var entered_water := false
	var step := 1.0
	var d := 1.0
	while d <= MAX_CROSS_DIST:
		var p := global_position + dir * d
		if not terrain.in_bounds(p.x, p.z):
			return false
		var w := terrain.is_water(p.x, p.z)
		if w:
			entered_water = true
		elif entered_water:
			# karşı kıyı bulundu
			target = Vector3(p.x + dir.x * 1.5, 0, p.z + dir.z * 1.5)
			state = State.CROSS
			return true
		d += step
	return false   # MAX_CROSS_DIST içinde karşı kıyı yok -> deniz, geçme

func _update_cross(delta: float) -> void:
	var to := target - global_position
	to.y = 0
	var d := to.length()
	if d < 1.0 or not _in_water and not terrain.is_water(target.x, target.z):
		# karşıya ulaştı (artık karadayız)
		if not terrain.is_water(global_position.x, global_position.z):
			state = State.WANDER
			_cross_cooldown = randf_range(8.0, 20.0)
			_pick_wander_target()
			return
	if d < 1.0:
		state = State.WANDER
		_cross_cooldown = randf_range(8.0, 20.0)
		_pick_wander_target()
		return
	var dir := to / d
	velocity.x = dir.x * speed_swim
	velocity.z = dir.z * speed_swim

# --- FLEE ---
func scare(from: Vector3) -> void:
	state = State.FLEE
	var away := (global_position - from)
	away.y = 0
	if away.length() < 0.1:
		away = Vector3(randf() - 0.5, 0, randf() - 0.5)
	target = global_position + away.normalized() * 12.0
	_idle_timer = randf_range(1.5, 3.0)

func _update_flee(delta: float) -> void:
	_idle_timer -= delta
	var to := target - global_position
	to.y = 0
	var d := to.length()
	if _idle_timer <= 0.0 or d < 1.0:
		state = State.WANDER
		_pick_wander_target()
		return
	var dir := to / maxf(d, 0.001)
	var ahead := global_position + dir * 1.5
	if terrain.is_water(ahead.x, ahead.z) and not swimmer:
		# panikle ama suya girme: kıyı boyunca yön değiştir
		dir = dir.rotated(Vector3.UP, PI * 0.5)
		target = global_position + dir * 8.0
	velocity.x = dir.x * speed_flee
	velocity.z = dir.z * speed_flee
