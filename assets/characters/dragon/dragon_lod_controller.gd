class_name DragonLODController
extends Node

@export_node_path("Node3D") var asset_root_path: NodePath = NodePath("../VisualRoot/DragonAsset")
@export var force_mobile_profile := false
@export_range(0.02, 1.0, 0.01) var evaluation_interval_seconds := 0.12
@export_range(0.0, 10.0, 0.1) var hysteresis_meters := 1.5

const DESKTOP_LODS: Array[StringName] = [
    &"Dragon_LOD0", &"Dragon_LOD1", &"Dragon_LOD2", &"Dragon_LOD3", &"Dragon_LOD4"
]
const DESKTOP_THRESHOLDS: PackedFloat32Array = [9.0, 22.0, 48.0, 100.0]
const DETAIL_NODES: Array[StringName] = [
    &"Dragon_Eyes", &"Dragon_Teeth", &"Dragon_Tongue", &"Dragon_Horns"
]

var _asset_root: Node3D
var _lod_nodes: Dictionary[StringName, Node3D] = {}
var _detail_nodes: Array[Node3D] = []
var _current_lod: StringName = &""
var _elapsed := 0.0


func _ready() -> void:
    _asset_root = get_node_or_null(asset_root_path) as Node3D
    if _asset_root == null:
        push_error("DragonLODController: asset root was not found.")
        set_process(false)
        return
    _cache_nodes()
    _apply_lod(_initial_lod())


func _process(delta: float) -> void:
    _elapsed += delta
    if _elapsed < evaluation_interval_seconds:
        return
    _elapsed = 0.0
    var camera := get_viewport().get_camera_3d()
    if camera == null:
        return
    var distance := camera.global_position.distance_to(_asset_root.global_position)
    _apply_lod(_resolve_lod(distance))
    _set_details_visible(distance < 42.0 or force_mobile_profile)


func _cache_nodes() -> void:
    for lod_name in DESKTOP_LODS:
        var node := _asset_root.find_child(String(lod_name), true, false) as Node3D
        if node != null:
            _lod_nodes[lod_name] = node
    var mobile := _asset_root.find_child("Dragon_Mobile", true, false) as Node3D
    if mobile != null:
        _lod_nodes[&"Dragon_Mobile"] = mobile
    for detail_name in DETAIL_NODES:
        var detail := _asset_root.find_child(String(detail_name), true, false) as Node3D
        if detail != null:
            _detail_nodes.append(detail)


func _resolve_lod(distance: float) -> StringName:
    var mobile_profile := force_mobile_profile or OS.has_feature("mobile")
    if mobile_profile:
        if distance < 58.0 + _hysteresis_for(&"Dragon_Mobile"):
            return &"Dragon_Mobile"
        if distance < 115.0 + _hysteresis_for(&"Dragon_LOD3"):
            return &"Dragon_LOD3"
        return &"Dragon_LOD4"

    for index in DESKTOP_THRESHOLDS.size():
        var candidate := DESKTOP_LODS[index]
        if distance < DESKTOP_THRESHOLDS[index] + _hysteresis_for(candidate):
            return candidate
    return &"Dragon_LOD4"


func _hysteresis_for(candidate: StringName) -> float:
    return hysteresis_meters if candidate == _current_lod else -hysteresis_meters


func _initial_lod() -> StringName:
    return &"Dragon_Mobile" if (force_mobile_profile or OS.has_feature("mobile")) else &"Dragon_LOD1"


func _apply_lod(lod_name: StringName) -> void:
    if lod_name == _current_lod:
        return
    if not _lod_nodes.has(lod_name):
        push_warning("Dragon LOD node is missing: %s" % lod_name)
        return
    for name in _lod_nodes:
        _lod_nodes[name].visible = name == lod_name
    _current_lod = lod_name


func _set_details_visible(value: bool) -> void:
    for detail in _detail_nodes:
        detail.visible = value
