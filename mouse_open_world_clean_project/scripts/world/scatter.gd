extends Node3D
class_name WorldScatter

# Araziye ağaç (çam + elma) ve toplanabilir ceviz/fıstık serpiştirir.
# Ağaçlar/fındıklar MultiMesh ile tek draw-call (mobil dostu). Çamlar prosedürel
# PineTree sahnesi olarak (sınırlı sayıda) eklenir.

const APPLE_GLB := "res://assets/trees/elma_agaci/elma_agaci.glb"
const PINE_SCENE := "res://scenes/world/pine_tree.tscn"
const CEVIZ_GLB := "res://assets/nuts/ceviz.glb"
const FISTIK_GLB := "res://assets/nuts/fistik.glb"

@export var pine_count: int = 22
@export var apple_count: int = 32
@export var ceviz_count: int = 220
@export var fistik_count: int = 220
@export var apple_scale: float = 1.0
@export var nut_scale: float = 0.13
@export var collect_radius: float = 0.7

var terrain: Terrain
var player: Node3D

var _nuts: Array = []          # {pos, kind, mm, idx, taken}
var _ceviz_mm: MultiMesh
var _fistik_mm: MultiMesh
var _frame := 0

func build() -> void:
	if terrain == null or not terrain.built:
		return
	_scatter_pines()
	_scatter_apples()
	_scatter_nuts()

# --- yardımcı: glb'den ilk mesh + materyal ---
func _mesh_from_glb(path: String) -> Mesh:
	if not ResourceLoader.exists(path):
		return null
	var packed := load(path) as PackedScene
	if packed == null:
		return null
	var inst := packed.instantiate()
	var found: Mesh = null
	for mi in inst.find_children("*", "MeshInstance3D", true, false):
		var m := mi as MeshInstance3D
		found = m.mesh
		# yüzey materyalini mesh'e göm (override) -> MultiMesh tek materyal
		if found != null and m.get_surface_override_material(0) != null:
			found = found.duplicate()
			found.surface_set_material(0, m.get_surface_override_material(0))
		break
	inst.queue_free()
	return found

func _scatter_pines() -> void:
	if not ResourceLoader.exists(PINE_SCENE):
		return
	var packed := load(PINE_SCENE) as PackedScene
	if packed == null:
		return
	var root := Node3D.new()
	root.name = "Pines"
	add_child(root)
	for i in pine_count:
		var p := terrain.get_random_land_point(25.0)
		if p.y <= terrain.water_surface_y + 0.5:
			continue
		var t := packed.instantiate()
		root.add_child(t)
		t.global_position = p
		t.rotation.y = randf() * TAU
		if t.has_method("set"):
			t.set("seed", randi())

func _scatter_apples() -> void:
	var mesh := _mesh_from_glb(APPLE_GLB)
	if mesh == null:
		return
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.mesh = mesh
	var xforms: Array = []
	for i in apple_count:
		var p := terrain.get_random_land_point(25.0)
		if p.y <= terrain.water_surface_y + 0.5:
			continue
		var b := Basis(Vector3.UP, randf() * TAU).scaled(Vector3.ONE * apple_scale * randf_range(0.85, 1.25))
		xforms.append(Transform3D(b, p))
	mm.instance_count = xforms.size()
	for i in xforms.size():
		mm.set_instance_transform(i, xforms[i])
	var mmi := MultiMeshInstance3D.new()
	mmi.name = "AppleTrees"
	mmi.multimesh = mm
	add_child(mmi)

func _scatter_nuts() -> void:
	var ceviz_mesh := _mesh_from_glb(CEVIZ_GLB)
	var fistik_mesh := _mesh_from_glb(FISTIK_GLB)
	_ceviz_mm = _make_nut_mm(ceviz_mesh, ceviz_count, "ceviz")
	_fistik_mm = _make_nut_mm(fistik_mesh, fistik_count, "fistik")

func _make_nut_mm(mesh: Mesh, count: int, kind: String) -> MultiMesh:
	if mesh == null:
		return null
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.mesh = mesh
	var placed: Array = []
	for i in count:
		var p := terrain.get_random_land_point(8.0)
		if p.y <= terrain.water_surface_y + 0.1:
			continue
		p.y += nut_scale * 0.5
		placed.append(p)
	mm.instance_count = placed.size()
	for i in placed.size():
		var b := Basis(Vector3.UP, randf() * TAU).scaled(Vector3.ONE * nut_scale)
		mm.set_instance_transform(i, Transform3D(b, placed[i]))
		_nuts.append({"pos": placed[i], "kind": kind, "mm": mm, "idx": i, "taken": false})
	var mmi := MultiMeshInstance3D.new()
	mmi.name = "Nuts_" + kind
	mmi.multimesh = mm
	add_child(mmi)
	return mm

func _process(_delta: float) -> void:
	_frame += 1
	if player == null or (_frame % 3) != 0:
		return
	var pp := player.global_position
	var r2 := collect_radius * collect_radius
	for nut in _nuts:
		if nut["taken"]:
			continue
		var d: Vector3 = nut["pos"] - pp
		d.y = 0
		if d.length_squared() <= r2:
			nut["taken"] = true
			# MultiMesh örneğini gizle (sıfır ölçek)
			var mm: MultiMesh = nut["mm"]
			mm.set_instance_transform(nut["idx"], Transform3D(Basis().scaled(Vector3.ZERO), nut["pos"]))
			if player.has_method("collect_nut"):
				player.collect_nut(nut["kind"])
