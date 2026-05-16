@tool
class_name PineTextures
extends RefCounted

# Önbellekli prosedürel doku fabrikası. Tüm ağaçlar aynı dokuları paylaşır.
# İğne atlası nötr-yeşil luminans olarak bakelidir; tür/mevsim tonu
# materyalin albedo_color'ı + vertex AO ile verilir (doku-renk ayrışması).

static var _needle: Texture2D
static var _bark: Texture2D

# Tilelenebilir (dikey) yoğun iğne dalcığı. Orta sap + iki yana ince
# iğneler; uçlar şeffaflaşır. Güçlü alpha -> keskin scissor silüeti.
static func needle_atlas() -> Texture2D:
	if _needle != null:
		return _needle
	var w := 512
	var h := 512
	var img := Image.create(w, h, false, Image.FORMAT_RGBA8)
	img.fill(Color(0, 0, 0, 0))
	var rng := RandomNumberGenerator.new()
	rng.seed = 7331
	var cx := float(w) * 0.5
	var dark := Color(0.07, 0.16, 0.07)
	var lite := Color(0.42, 0.58, 0.30)
	var signs: Array[float] = [-1.0, 1.0]
	var rows := 170
	for ri in range(rows):
		var y := float(ri) / float(rows) * float(h)
		var stem_x := cx + sin(y * 0.045) * 16.0
		for sgn in signs:
			for c in range(2):
				var jy := y + rng.randf_range(-3.0, 3.0)
				var nl := rng.randf_range(85.0, 175.0)
				var ang: float = deg_to_rad(rng.randf_range(36.0, 62.0)) * sgn
				var p0 := Vector2(stem_x + sgn * 3.0, jy)
				var p1 := p0 + Vector2(sin(ang), -cos(ang)) * nl
				var k: float = rng.randf()
				var base := dark.lerp(lite, k * k)
				_stroke(img, p0, p1, rng.randf_range(1.5, 2.6), base, lite)
	# Orta sap (koyu).
	for r2 in range(h):
		var sx := int(round(cx + sin(float(r2) * 0.045) * 16.0))
		for ox in range(-2, 3):
			var px := sx + ox
			if px >= 0 and px < w:
				img.set_pixel(px, r2, Color(0.05, 0.12, 0.05, 1.0))
	img.generate_mipmaps()
	_needle = ImageTexture.create_from_image(img)
	return _needle

static func _stroke(img: Image, p0: Vector2, p1: Vector2, w: float, c0: Color, c1: Color) -> void:
	var steps := int(ceil(p0.distance_to(p1)))
	var H := img.get_height()
	var W := img.get_width()
	for s in range(steps + 1):
		var t := float(s) / float(maxi(steps, 1))
		var p := p0.lerp(p1, t)
		var col := c0.lerp(c1, t * 0.55)
		col.a = lerp(1.0, 0.45, t)
		var rad := maxf(w * (1.0 - 0.55 * t), 0.6)
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

# Lifli + hücresel plakalı sıcak kabuk.
static func bark() -> Texture2D:
	if _bark != null:
		return _bark
	var w := 128
	var h := 256
	var img := Image.create(w, h, false, Image.FORMAT_RGBA8)
	var fib := FastNoiseLite.new()
	fib.noise_type = FastNoiseLite.TYPE_SIMPLEX
	fib.frequency = 0.05
	var plate := FastNoiseLite.new()
	plate.noise_type = FastNoiseLite.TYPE_CELLULAR
	plate.frequency = 0.018
	plate.cellular_return_type = FastNoiseLite.RETURN_DISTANCE2_SUB
	for y in range(h):
		for x in range(w):
			var f := fib.get_noise_2d(float(x) * 3.0, float(y) * 0.55)
			var pl := plate.get_noise_2d(float(x) * 1.6, float(y))
			var v: float = 0.62 + 0.30 * f
			if pl > 0.32:
				v *= 0.38
			elif pl > 0.18:
				v *= 0.70
			v = clampf(v, 0.12, 1.05)
			var warm := Color(0.42, 0.27, 0.17) * v + Color(0.05, 0.03, 0.02)
			img.set_pixel(x, y, Color(warm.r, warm.g, warm.b, 1.0))
	img.generate_mipmaps()
	_bark = ImageTexture.create_from_image(img)
	return _bark
