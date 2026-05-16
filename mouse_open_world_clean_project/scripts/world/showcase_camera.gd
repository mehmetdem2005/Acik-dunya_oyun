extends Camera3D

# Çam ağacı sahnesini yavaşça çevreleyen tanıtım kamerası.
@export var target := Vector3(0.0, 4.0, 0.0)
@export var distance: float = 34.0
@export var height: float = 14.0
@export var orbit_speed: float = 0.06

var _angle: float = 0.0

func _process(delta: float) -> void:
	_angle += orbit_speed * delta
	global_position = target + Vector3(cos(_angle) * distance, height, sin(_angle) * distance)
	look_at(target, Vector3.UP)
