class_name DragonCharacter
extends CharacterBody3D

@onready var animation_controller: DragonAnimationController = $AnimationController


func _ready() -> void:
    animation_controller.play_clip(&"Idle_Ground", 0.0)


func play_action(action_name: StringName, blend_time: float = 0.18, speed: float = 1.0) -> bool:
    return animation_controller.play_clip(action_name, blend_time, speed, true)


func set_alert(value: bool) -> void:
    animation_controller.play_clip(&"Idle_Alert" if value else &"Idle_Ground")


func set_locomotion(local_velocity: Vector3, running: bool) -> void:
    if local_velocity.length_squared() < 0.01:
        animation_controller.play_clip(&"Idle_Ground")
        return
    animation_controller.play_clip(&"Run" if running else &"Walk")
