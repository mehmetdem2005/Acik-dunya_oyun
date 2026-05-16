@tool
class_name PineTextures
extends RefCounted

# Önbellekli prosedürel doku fabrikası. Tüm ağaçlar aynı dokuları paylaşır
# (statik cache -> orman/çoklu ağaç ucuz). Mobil editör için boyutlar ölçülü.
#
# Kabuk: tek bir YÜKSEKLİK alanından hem albedo hem normal map türer
# (tutarlı kabartma). Kızıl-kahve derin çatlaklı olgun çam kabuğu.
# İğne: çam DEMETİ (fascicle) atlası, keskin ince alpha.

const BARK_W := 256
const BARK_H := 512
const NEEDLE_S := 512

static var _bark: Texture2D
static var _bark_n: Texture2D
static var _needle: Texture2D
static var _hfield: PackedFloat32Array
static var _hready := false

# --- Kabuk yükseklik alanı (albedo + normal paylaşır) -----------------

static func _height_field() -> PackedFloat32Array:
	if _hready:
		return _hfield
	var fib := FastNoiseLite.new()
	fib.noise_type = FastNoiseLite.TYPE_SIMPLEX
	fib.frequency = 0.05
	var deep := FastNoiseLite.new()
	deep.noise_type = FastNoiseLite.TYPE_SIMPLEX
	deep.frequency = 0.012
	var plate := FastNoiseLite.new()
	plate.noise_type = FastNoiseLite.TYPE_CELLULAR
	plate.frequency = 0.020
	plate.cellular_return_type = FastNoiseLite.RETURN_DISTANCE2_SUB
	var arr := PackedFloat32Array()
	arr.resize(BARK_W * BARK_H)
	for y in range(BARK_H):
		for x in range(BARK_W):
			var fx := float(x)
			var fy := float(y)
			# Dikey lifli yapı: x'te sık, y'de uzun.
			var f := fib.get_noise_2d(fx * 2.6, fy * 0.5)
			var d := deep.get_noise_2d(fx * 2.0, fy * 0.35)
			var pl := plate.get_noise_2d(fx * 1.5, fy * 0.95)
			var hgt: float = 0.60 + 0.22 * f + 0.18 * d
			# Hücresel plaka sınırları -> derin çatlak (yükseklik düşer).
			if pl > 0.30:
				hgt -= 0.52
			elif pl > 0.15:
				hgt -= 0.22
			arr[y * BARK_W + x] = clampf(hgt, 0.0, 1.0)
	_hfield = arr
	_hready = true
	return _hfield

static func bark() -> Texture2D:
	if _bark != null:
		return _bark
	var hf := _height_field()
	var img := Image.create(BARK_W, BARK_H, false, Image.FORMAT_RGBA8)
	var furrow := Color(0.090, 0.052, 0.034)
	var mid := Color(0.165, 0.100, 0.066)
	var plate := Color(0.250, 0.165, 0.120)
	for y in range(BARK_H):
		for x in range(BARK_W):
			var h: float = hf[y * BARK_W + x]
			var c := furrow.lerp(mid, smoothstep(0.18, 0.5, h))
			c = c.lerp(plate, smoothstep(0.5, 0.92, h))
			# İnce lif greni + büyük ölçekli hafif benek.
			var grain: float = 1.0 + (h - 0.6) * 0.18
			c = Color(clampf(c.r * grain, 0.0, 1.0),
				clampf(c.g * grain, 0.0, 1.0),
				clampf(c.b * grain, 0.0, 1.0), 1.0)
			img.set_pixel(x, y, c)
	img.generate_mipmaps()
	_bark = ImageTexture.create_from_image(img)
	return _bark

static func bark_normal() -> Texture2D:
	if _bark_n != null:
		return _bark_n
	var hf := _height_field()
	var img := Image.create(BARK_W, BARK_H, false, Image.FORMAT_RGBA8)
	var strength := 3.2
	for y in range(BARK_H):
		var ym := (y - 1 + BARK_H) % BARK_H
		var yp := (y + 1) % BARK_H
		for x in range(BARK_W):
			var xm := (x - 1 + BARK_W) % BARK_W
			var xp := (x + 1) % BARK_W
			var dx: float = (hf[y * BARK_W + xp] - hf[y * BARK_W + xm]) * strength
			var dy: float = (hf[yp * BARK_W + x] - hf[ym * BARK_W + x]) * strength
			var nrm := Vector3(-dx, -dy, 1.0).normalized()
			img.set_pixel(x, y, Color(nrm.x * 0.5 + 0.5,
				nrm.y * 0.5 + 0.5, nrm.z * 0.5 + 0.5, 1.0))
	img.generate_mipmaps()
	_bark_n = ImageTexture.create_from_image(img)
	return _bark_n

# --- İğne atlası: çam demeti (fascicle) -------------------------------

static func needle_atlas() -> Texture2D:
	if _needle != null:
		return _needle
	var s := NEEDLE_S
	var img := Image.create(s, s, false, Image.FORMAT_RGBA8)
	img.fill(Color(0, 0, 0, 0))
	var rng := RandomNumberGenerator.new()
	rng.seed = 7331
	var cx := float(s) * 0.5
	var dark := Color(0.130, 0.235, 0.105)
	var lite := Color(0.440, 0.560, 0.255)
	var signs: Array[float] = [-1.0, 1.0]
	# Sap boyunca ~110 çıkış noktası; her noktada 3-5'li iğne demeti.
	var pts := 110
	for ri in range(pts):
		var y: float = float(ri) / float(pts) * float(s)
		var stem_x := cx + sin(y * 0.04) * 14.0
		for sgn in signs:
			var base_ang: float = deg_to_rad(rng.randf_range(40.0, 65.0)) * sgn
			var needles_per := rng.randi_range(3, 5)
			for ni in range(needles_per):
				var jy := y + rng.randf_range(-2.0, 2.0)
				var nl := rng.randf_range(120.0, 200.0)
				var ang: float = base_ang + deg_to_rad(rng.randf_range(-6.0, 6.0))
				var p0 := Vector2(stem_x + sgn * 2.0, jy)
				var p1 := p0 + Vector2(sin(ang), -cos(ang)) * nl
				var k: float = rng.randf()
				_stroke(img, p0, p1, rng.randf_range(0.7, 1.3),
					dark.lerp(lite, k * k), lite)
	# İnce koyu merkez sap.
	for r2 in range(s):
		var sx := int(round(cx + sin(float(r2) * 0.04) * 14.0))
		if sx >= 0 and sx < s:
			img.set_pixel(sx, r2, Color(0.105, 0.160, 0.080, 1.0))
	img.generate_mipmaps()
	_needle = ImageTexture.create_from_image(img)
	return _needle

static func _stroke(img: Image, p0: Vector2, p1: Vector2, w: float, c0: Color, c1: Color) -> void:
	var steps := int(ceil(p0.distance_to(p1)))
	var H := img.get_height()
	var W := img.get_width()
	for st in range(steps + 1):
		var t := float(st) / float(maxi(steps, 1))
		var p := p0.lerp(p1, t)
		var col := c0.lerp(c1, t * 0.5)
		# Güçlü alpha kontrastı: sap boyunca opak, yalnız son %15 sıfıra.
		col.a = 1.0 if t < 0.85 else (1.0 - (t - 0.85) / 0.15)
		var rad := maxf(w * (1.0 - 0.45 * t), 0.5)
		var ir := int(ceil(rad))
		for oy in range(-ir, ir + 1):
			for ox in range(-ir, ir + 1):
				if Vector2(ox, oy).length() > rad:
					continue
				var px := int(round(p.x)) + ox
				var py := ((int(round(p.y)) + oy) % H + H) % H
				if px < 0 or px >= W:
					continue
				if col.a > img.get_pixel(px, py).a:
					img.set_pixel(px, py, col)
	return
