extends Node3D
class_name MouseVisual

# Rig'lenmiş fare modelini (housemouse_rigged.glb) yükler ve Blender'da üretilen
# skeletal animasyonları (idle/walk/run/attack/swim) bir durum makinesiyle oynatır.
# AnimationPlayer bulunamazsa (import sorunu) prosedürel bob'a düşer.

const MODEL_PATH := "res://assets/mouse/housemouse_rigged.glb"

var model_scale: float = 1.0
var _model: Node3D
var _anim: AnimationPlayer
var _has_anim := false
var _cur := ""
var _attacking := false
var _t := 0.0          # prosedürel fallback fazı
var _proc_speed := 0.0
var _proc_water := false

func setup(scale: float = 1.0, model_path: String = MODEL_PATH) -> void:
	model_scale = scale
	var packed := load(model_path)
	if packed == null:
		push_error("MouseVisual: model yüklenemedi %s" % model_path)
		return
	_model = (packed as PackedScene).instantiate()
	add_child(_model)
	_model.scale = Vector3.ONE * model_scale
	# Model başı +Z'ye bakar; Godot ileri yönü -Z -> 180° çevir.
	_model.rotation.y = PI
	# Ayakları y=0'a getir (model yükseklik ekseni Y, min ≈ -0.228).
	_model.position.y = 0.228 * model_scale
	_anim = _find_anim(_model)
	if _anim != null:
		_has_anim = true
		_config_loops()
		if not _anim.animation_finished.is_connected(_on_anim_finished):
			_anim.animation_finished.connect(_on_anim_finished)
		_play("idle", 0.0)

func _find_anim(n: Node) -> AnimationPlayer:
	if n is AnimationPlayer:
		return n
	for c in n.get_children():
		var r := _find_anim(c)
		if r != null:
			return r
	return null

func _config_loops() -> void:
	for nm in ["idle", "walk", "run", "swim"]:
		if _anim.has_animation(nm):
			var a := _anim.get_animation(nm)
			a.loop_mode = Animation.LOOP_LINEAR

func _play(name: String, blend: float = 0.15, speed: float = 1.0) -> void:
	if not _has_anim or not _anim.has_animation(name):
		return
	if _cur == name:
		_anim.speed_scale = speed
		return
	_cur = name
	_anim.play(name, blend, speed)
	_anim.speed_scale = speed

func _on_anim_finished(name: String) -> void:
	if name == "attack":
		_attacking = false
		_cur = ""   # bir sonraki set_locomotion yeniden seçsin

# Aktör her karede çağırır.
func set_locomotion(planar_speed: float, run_threshold: float, in_water: bool) -> void:
	_proc_speed = planar_speed
	_proc_water = in_water
	if not _has_anim:
		return
	if _attacking:
		return
	if in_water:
		_play("swim", 0.2, clampf(0.6 + planar_speed * 0.18, 0.6, 1.6))
	elif planar_speed < 0.25:
		_play("idle", 0.2, 1.0)
	elif planar_speed < run_threshold:
		_play("walk", 0.15, clampf(planar_speed / 2.5, 0.6, 1.7))
	else:
		_play("run", 0.15, clampf(planar_speed / 6.0, 0.8, 1.6))

func attack() -> bool:
	if _attacking:
		return false
	_attacking = true
	if _has_anim and _anim.has_animation("attack"):
		_cur = "attack"
		_anim.play("attack", 0.05, 1.3)
		_anim.speed_scale = 1.3
	else:
		# fallback: kısa süreli işaret
		_attacking = true
		get_tree().create_timer(0.4).timeout.connect(func(): _attacking = false)
	return true

func is_attacking() -> bool:
	return _attacking

# AnimationPlayer yoksa prosedürel hareket (bob/tilt/squash).
func _process(delta: float) -> void:
	if _has_anim or _model == null:
		return
	_t += delta * (4.0 + _proc_speed * 2.0)
	var bob := absf(sin(_t)) * (0.03 + _proc_speed * 0.01) * model_scale
	var pitch := sin(_t * 2.0) * 0.04 * clampf(_proc_speed, 0.0, 2.0)
	var base_y := 0.228 * model_scale
	if _proc_water:
		_model.rotation.x = lerp(_model.rotation.x, 0.3, 0.1)
		_model.position.y = base_y - 0.05 * model_scale + sin(_t) * 0.02
	else:
		_model.rotation.x = lerp(_model.rotation.x, pitch, 0.2)
		_model.position.y = base_y + bob
	if _attacking:
		_model.position.z = lerp(_model.position.z, -0.15 * model_scale, 0.3)
	else:
		_model.position.z = lerp(_model.position.z, 0.0, 0.2)
