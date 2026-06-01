extends Node3D
class_name Terrain

# Açık Dünya Arazi Üreticisi
# ---------------------------
# yarimada_16bit.exr yükseklik haritasından çalışma anında:
#   * görsel arazi mesh'i (yükseklik + eğime göre vertex renkli)
#   * HeightMapShape3D çarpışması (CharacterBody3D'ler için)
#   * SU TESPİTİ: deniz / göl / nehir (flood-fill ile sınıflandırma)
#   * su yüzeyi mesh'i (water.gdshader)
# üretir ve aktörler için sorgu API'si sunar:
#   height_at(x,z), is_water(x,z), water_surface_y(), get_random_land_point()
#
# Tüm yüklemeler path ile yapılır (uid/import kırılganlığı yok).

const HEIGHTMAP_PATH := "res://assets/heightmap/yarimada_16bit.exr"
const WATER_SHADER_PATH := "res://shaders/water.gdshader"

@export var world_size: float = 1250.0      # X ve Z'de metre cinsinden genişlik
@export var height_scale: float = 120.0     # max yükselti (metre)
@export var grid_res: int = 256             # mesh/collision/analiz ızgara çözünürlüğü
@export_range(0.0, 0.5, 0.001) var water_level: float = 0.075  # normalize su eşiği (deniz + iç göller + dar nehir kanalları)
@export var slope_limit_deg: float = 38.0   # bu eğimden dik yerler "ekilemez"

# Su bölge türleri
enum WaterType { NONE, SEA, LAKE, RIVER }

# Dahili ızgara verisi (z*N + x indeksleme)
var _N: int = 0
var _h01: PackedFloat32Array = PackedFloat32Array()   # normalize yükseklik 0..1
var _hworld: PackedFloat32Array = PackedFloat32Array() # metre yükseklik
var _water_region: PackedInt32Array = PackedInt32Array() # -1 = kara, >=0 bölge id
var _region_type: Array[int] = []                       # bölge id -> WaterType
var _region_size: Array[int] = []
var water_surface_y: float = 0.0
var min_h: float = 0.0
var max_h: float = 0.0

var _rng := RandomNumberGenerator.new()
var built: bool = false

func build() -> void:
	_rng.randomize()
	_N = maxi(8, grid_res)
	water_surface_y = water_level * height_scale

	var img := _load_heightmap()
	if img == null:
		push_error("Terrain: yükseklik haritası yüklenemedi: %s" % HEIGHTMAP_PATH)
		return
	_sample_grid(img)
	_analyze_water()
	_build_terrain_mesh()
	_build_collision()
	_build_water_mesh()
	built = true
	print("[Terrain] hazır: ızgara=%d dünya=%.0fm yükselti=%.0fm su_y=%.2f bölgeler=%d" % [
		_N, world_size, height_scale, water_surface_y, _region_type.size()])

# --- Yükseklik haritası okuma (Image veya Texture2D olarak gelebilir) ---
func _load_heightmap() -> Image:
	var res := load(HEIGHTMAP_PATH)
	if res is Image:
		return res as Image
	if res is Texture2D:
		return (res as Texture2D).get_image()
	return null

func _sample_grid(img: Image) -> void:
	var iw := img.get_width()
	var ih := img.get_height()
	_h01.resize(_N * _N)
	_hworld.resize(_N * _N)
	min_h = INF
	max_h = -INF
	for z in _N:
		var v := float(z) / float(_N - 1)
		var py := clampf(v * float(ih - 1), 0.0, float(ih - 1))
		var py0 := int(py)
		var py1 := mini(py0 + 1, ih - 1)
		var fy := py - float(py0)
		for x in _N:
			var u := float(x) / float(_N - 1)
			var px := clampf(u * float(iw - 1), 0.0, float(iw - 1))
			var px0 := int(px)
			var px1 := mini(px0 + 1, iw - 1)
			var fx := px - float(px0)
			# bilineer örnekleme (R kanalı = gri yükseklik)
			var h00 := img.get_pixel(px0, py0).r
			var h10 := img.get_pixel(px1, py0).r
			var h01v := img.get_pixel(px0, py1).r
			var h11 := img.get_pixel(px1, py1).r
			var top := lerpf(h00, h10, fx)
			var bot := lerpf(h01v, h11, fx)
			var hn := lerpf(top, bot, fy)
			var idx := z * _N + x
			_h01[idx] = hn
			_hworld[idx] = hn * height_scale
			min_h = minf(min_h, hn)
			max_h = maxf(max_h, hn)

# --- Su sınıflandırması: flood-fill ile bağlı bileşenler ---
func _analyze_water() -> void:
	var n2 := _N * _N
	_water_region.resize(n2)
	for i in n2:
		_water_region[i] = -1
	_region_type.clear()
	_region_size.clear()

	var is_w := func(x: int, z: int) -> bool:
		return _h01[z * _N + x] < water_level

	var region_id := 0
	var stack: PackedInt32Array = PackedInt32Array()
	for sz in _N:
		for sx in _N:
			var sidx := sz * _N + sx
			if _water_region[sidx] != -1:
				continue
			if not is_w.call(sx, sz):
				continue
			# Yeni su bölgesi -> flood fill (BFS)
			stack.clear()
			stack.push_back(sidx)
			_water_region[sidx] = region_id
			var touches_border := false
			var count := 0
			var min_x := _N
			var max_x := 0
			var min_z := _N
			var max_z := 0
			while stack.size() > 0:
				var idx: int = stack[stack.size() - 1]
				stack.remove_at(stack.size() - 1)
				var cx := idx % _N
				var cz := idx / _N
				count += 1
				min_x = mini(min_x, cx); max_x = maxi(max_x, cx)
				min_z = mini(min_z, cz); max_z = maxi(max_z, cz)
				if cx == 0 or cz == 0 or cx == _N - 1 or cz == _N - 1:
					touches_border = true
				# 4 komşu
				var nbrs := [[cx - 1, cz], [cx + 1, cz], [cx, cz - 1], [cx, cz + 1]]
				for nb in nbrs:
					var nx: int = nb[0]
					var nz: int = nb[1]
					if nx < 0 or nz < 0 or nx >= _N or nz >= _N:
						continue
					var nidx := nz * _N + nx
					if _water_region[nidx] != -1:
						continue
					if is_w.call(nx, nz):
						_water_region[nidx] = region_id
						stack.push_back(nidx)
			# Türü belirle
			var bw := max_x - min_x + 1
			var bh := max_z - min_z + 1
			var bbox_area := float(maxi(1, bw * bh))
			var fill := float(count) / bbox_area
			var aspect := float(maxi(bw, bh)) / float(maxi(1, mini(bw, bh)))
			var t := WaterType.LAKE
			if touches_border and count > n2 / 40:
				t = WaterType.SEA
			elif aspect >= 3.0 or fill < 0.35:
				t = WaterType.RIVER   # uzun/ince ya da dolgusu düşük -> nehir
			else:
				t = WaterType.LAKE
			_region_type.append(t)
			_region_size.append(count)
			region_id += 1

# --- Görsel arazi mesh'i ---
func _build_terrain_mesh() -> void:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var half := world_size * 0.5
	var step := world_size / float(_N - 1)
	for z in _N:
		for x in _N:
			var idx := z * _N + x
			var wx := -half + float(x) * step
			var wz := -half + float(z) * step
			var wy := _hworld[idx]
			st.set_uv(Vector2(float(x) / float(_N - 1), float(z) / float(_N - 1)))
			st.set_color(_vertex_color(idx, x, z))
			st.add_vertex(Vector3(wx, wy, wz))
	for z in _N - 1:
		for x in _N - 1:
			var i0 := z * _N + x
			var i1 := z * _N + x + 1
			var i2 := (z + 1) * _N + x
			var i3 := (z + 1) * _N + x + 1
			st.add_index(i0); st.add_index(i2); st.add_index(i1)
			st.add_index(i1); st.add_index(i2); st.add_index(i3)
	st.generate_normals()
	st.generate_tangents()
	var mesh := st.commit()
	var mi := MeshInstance3D.new()
	mi.name = "TerrainMesh"
	mi.mesh = mesh
	mi.material_override = _terrain_material()
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
	add_child(mi)

# yükseklik + eğime göre vertex rengi (kum/çim/kaya/kar) -> shader gerekmez
func _vertex_color(idx: int, x: int, z: int) -> Color:
	var h01 := _h01[idx]
	var slope := _slope01(x, z)
	var sand := Color(0.78, 0.71, 0.50)
	var grass := Color(0.22, 0.42, 0.16)
	var grass_dry := Color(0.42, 0.46, 0.20)
	var rock := Color(0.34, 0.31, 0.28)
	var snow := Color(0.90, 0.92, 0.95)
	var c: Color
	var above := (h01 - water_level) / maxf(0.001, (1.0 - water_level))
	if above < 0.04:
		c = sand
	elif above < 0.35:
		c = sand.lerp(grass, smoothstep(0.04, 0.18, above))
	elif above < 0.65:
		c = grass.lerp(grass_dry, smoothstep(0.35, 0.65, above))
	elif above < 0.85:
		c = grass_dry.lerp(rock, smoothstep(0.65, 0.85, above))
	else:
		c = rock.lerp(snow, smoothstep(0.85, 1.0, above))
	# dik yamaçlar kayalık
	c = c.lerp(rock, smoothstep(0.55, 0.85, slope))
	return c

# 0=düz, 1=dik normalize eğim
func _slope01(x: int, z: int) -> float:
	var xa := maxi(0, x - 1)
	var xb := mini(_N - 1, x + 1)
	var za := maxi(0, z - 1)
	var zb := mini(_N - 1, z + 1)
	var step := world_size / float(_N - 1)
	var dx := (_hworld[z * _N + xb] - _hworld[z * _N + xa]) / (float(xb - xa) * step)
	var dz := (_hworld[zb * _N + x] - _hworld[za * _N + x]) / (float(zb - za) * step)
	var grad := sqrt(dx * dx + dz * dz)
	return clampf(atan(grad) / (PI * 0.5), 0.0, 1.0)

func _terrain_material() -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.vertex_color_use_as_albedo = true
	m.roughness = 0.95
	m.metallic = 0.0
	return m

# --- Çarpışma: HeightMapShape3D ---
func _build_collision() -> void:
	var body := StaticBody3D.new()
	body.name = "TerrainBody"
	add_child(body)
	var shape := HeightMapShape3D.new()
	shape.map_width = _N
	shape.map_depth = _N
	shape.map_data = _hworld   # metre yükseklikleri doğrudan
	var col := CollisionShape3D.new()
	col.shape = shape
	# HeightMapShape ızgarası (N-1) birim genişler; dünya boyutuna ölçekle.
	var s := world_size / float(_N - 1)
	col.scale = Vector3(s, 1.0, s)
	body.add_child(col)

# --- Su yüzeyi mesh'i (tüm su hücreleri tek mesh, su seviyesinde) ---
func _build_water_mesh() -> void:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var half := world_size * 0.5
	var step := world_size / float(_N - 1)
	var vcount := 0
	var any := false
	for z in _N - 1:
		for x in _N - 1:
			# hücre dört köşesinden en az biri su ise su karosu üret
			if not (_is_water_idx(z * _N + x) or _is_water_idx(z * _N + x + 1) \
					or _is_water_idx((z + 1) * _N + x) or _is_water_idx((z + 1) * _N + x + 1)):
				continue
			any = true
			var x0 := -half + float(x) * step
			var x1 := -half + float(x + 1) * step
			var z0 := -half + float(z) * step
			var z1 := -half + float(z + 1) * step
			var y := water_surface_y
			st.set_uv(Vector2(float(x) / float(_N), float(z) / float(_N)))
			st.add_vertex(Vector3(x0, y, z0))
			st.set_uv(Vector2(float(x + 1) / float(_N), float(z) / float(_N)))
			st.add_vertex(Vector3(x1, y, z0))
			st.set_uv(Vector2(float(x) / float(_N), float(z + 1) / float(_N)))
			st.add_vertex(Vector3(x0, y, z1))
			st.set_uv(Vector2(float(x + 1) / float(_N), float(z + 1) / float(_N)))
			st.add_vertex(Vector3(x1, y, z1))
			st.add_index(vcount); st.add_index(vcount + 2); st.add_index(vcount + 1)
			st.add_index(vcount + 1); st.add_index(vcount + 2); st.add_index(vcount + 3)
			vcount += 4
	if not any:
		return
	st.generate_normals()
	var mi := MeshInstance3D.new()
	mi.name = "WaterMesh"
	mi.mesh = st.commit()
	mi.material_override = _water_material()
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(mi)

func _water_material() -> Material:
	if ResourceLoader.exists(WATER_SHADER_PATH):
		var sh := load(WATER_SHADER_PATH) as Shader
		if sh != null:
			var sm := ShaderMaterial.new()
			sm.shader = sh
			return sm
	var m := StandardMaterial3D.new()
	m.albedo_color = Color(0.1, 0.35, 0.5, 0.7)
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	return m

func _is_water_idx(i: int) -> bool:
	return _water_region[i] >= 0

# ======================= SORGU API'si (aktörler için) =======================

# Dünya (x,z) -> grid kayan koordinat
func _to_grid(wx: float, wz: float) -> Vector2:
	var half := world_size * 0.5
	var gx := (wx + half) / world_size * float(_N - 1)
	var gz := (wz + half) / world_size * float(_N - 1)
	return Vector2(gx, gz)

func in_bounds(wx: float, wz: float) -> bool:
	var half := world_size * 0.5 - 1.0
	return wx > -half and wx < half and wz > -half and wz < half

# Bilineer arazi yüksekliği (metre)
func height_at(wx: float, wz: float) -> float:
	if not built:
		return 0.0
	var g := _to_grid(wx, wz)
	var gx := clampf(g.x, 0.0, float(_N - 1))
	var gz := clampf(g.y, 0.0, float(_N - 1))
	var x0 := int(gx); var x1 := mini(x0 + 1, _N - 1)
	var z0 := int(gz); var z1 := mini(z0 + 1, _N - 1)
	var fx := gx - float(x0); var fz := gz - float(z0)
	var h00 := _hworld[z0 * _N + x0]
	var h10 := _hworld[z0 * _N + x1]
	var h01v := _hworld[z1 * _N + x0]
	var h11 := _hworld[z1 * _N + x1]
	return lerpf(lerpf(h00, h10, fx), lerpf(h01v, h11, fx), fz)

func _nearest_idx(wx: float, wz: float) -> int:
	var g := _to_grid(wx, wz)
	var x := clampi(int(round(g.x)), 0, _N - 1)
	var z := clampi(int(round(g.y)), 0, _N - 1)
	return z * _N + x

func is_water(wx: float, wz: float) -> bool:
	if not built:
		return false
	return _water_region[_nearest_idx(wx, wz)] >= 0

func water_type_at(wx: float, wz: float) -> int:
	if not built:
		return WaterType.NONE
	var r := _water_region[_nearest_idx(wx, wz)]
	if r < 0:
		return WaterType.NONE
	return _region_type[r]

func slope_at(wx: float, wz: float) -> float:
	var g := _to_grid(wx, wz)
	return _slope01(clampi(int(round(g.x)), 0, _N - 1), clampi(int(round(g.y)), 0, _N - 1))

# Karada (su değil + eğim uygun) rastgele bir nokta döndür. Bulamazsa y çok düşük.
func get_random_land_point(margin: float = 20.0) -> Vector3:
	var half := world_size * 0.5 - margin
	var slope_max := deg_to_rad(slope_limit_deg) / (PI * 0.5)
	for _i in 40:
		var wx := _rng.randf_range(-half, half)
		var wz := _rng.randf_range(-half, half)
		if is_water(wx, wz):
			continue
		var idx := _nearest_idx(wx, wz)
		if _h01[idx] <= water_level + 0.005:
			continue
		var cx := idx % _N; var cz := idx / _N
		if _slope01(cx, cz) > slope_max:
			continue
		return Vector3(wx, height_at(wx, wz), wz)
	# yedek: merkeze yakın
	return Vector3(0, height_at(0, 0), 0)
