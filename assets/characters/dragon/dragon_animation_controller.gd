class_name DragonAnimationController
extends Node

@export_node_path("Node") var asset_root_path: NodePath = NodePath("../VisualRoot/DragonAsset")

var _animation_player: AnimationPlayer
var _active_clip: StringName = &""


func _ready() -> void:
    _animation_player = _find_animation_player(get_node_or_null(asset_root_path))
    if _animation_player == null:
        push_error("DragonAnimationController: imported dragon AnimationPlayer was not found.")


func play_clip(clip: StringName, blend_time: float = 0.18, speed: float = 1.0, restart: bool = false) -> bool:
    if _animation_player == null:
        return false
    if not _animation_player.has_animation(clip):
        push_warning("Dragon animation is missing: %s" % clip)
        return false
    if not restart and _active_clip == clip and _animation_player.is_playing():
        return true
    _animation_player.speed_scale = speed
    _animation_player.play(clip, blend_time)
    _active_clip = clip
    return true


func stop(blend_time: float = 0.15) -> void:
    if _animation_player == null:
        return
    _animation_player.stop(false)
    _active_clip = &""


func get_active_clip() -> StringName:
    return _active_clip


func _find_animation_player(root: Node) -> AnimationPlayer:
    if root == null:
        return null
    if root is AnimationPlayer:
        return root as AnimationPlayer
    for child in root.get_children():
        var result := _find_animation_player(child)
        if result != null:
            return result
    return null
