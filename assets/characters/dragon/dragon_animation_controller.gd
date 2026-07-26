class_name DragonAnimationController
extends Node

@export_node_path("Node") var asset_root_path: NodePath = NodePath("../VisualRoot/DragonAsset")

const LOOPING_CLIPS: Dictionary[StringName, bool] = {
    &"Idle_Ground": true,
    &"Idle_Alert": true,
    &"Walk": true,
    &"Run": true,
    &"Flight_Forward": true,
    &"Flight_Glide": true,
    &"Flight_Hover": true,
}

var _animation_player: AnimationPlayer
var _active_clip: StringName = &""


func _ready() -> void:
    _animation_player = _find_animation_player(get_node_or_null(asset_root_path))
    if _animation_player == null:
        push_error("DragonAnimationController: imported dragon AnimationPlayer was not found.")
        return
    _configure_clip_loop_modes()


func play_clip(clip: StringName, blend_time: float = 0.18, speed: float = 1.0, restart: bool = false) -> bool:
    if _animation_player == null:
        return false
    var resolved_clip := _resolve_clip_name(clip)
    if resolved_clip == &"":
        push_warning("Dragon animation is missing: %s" % clip)
        return false
    if not restart and _active_clip == resolved_clip and _animation_player.is_playing():
        return true
    _animation_player.speed_scale = speed
    _animation_player.play(resolved_clip, blend_time)
    _active_clip = resolved_clip
    return true


func stop(keep_pose: bool = true) -> void:
    if _animation_player == null:
        return
    _animation_player.stop(keep_pose)
    _active_clip = &""


func get_active_clip() -> StringName:
    return _active_clip


func _configure_clip_loop_modes() -> void:
    for requested_clip in LOOPING_CLIPS:
        var resolved_clip := _resolve_clip_name(requested_clip)
        if resolved_clip == &"":
            continue
        var animation := _animation_player.get_animation(resolved_clip)
        if animation != null:
            animation.loop_mode = Animation.LOOP_LINEAR


func _resolve_clip_name(requested: StringName) -> StringName:
    if _animation_player.has_animation(requested):
        return requested
    var suffix := "/%s" % String(requested)
    for candidate in _animation_player.get_animation_list():
        if String(candidate).ends_with(suffix):
            return candidate
    return &""


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
