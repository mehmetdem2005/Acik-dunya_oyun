extends Control
class_name GameHUD

# Mobil dokunmatik HUD:
#  - Sol yarı: sanal joystick (hareket)
#  - Sağ yarı: kamera sürükleme + ZIPLA / SALDIR butonları
#  - Üst sol: ceviz / fıstık sayaçları
# Çoklu dokunmayı parmak index'i ile yönetir; masaüstünde fare ile de çalışır.

var _move_idx: int = -100
var _move_origin: Vector2 = Vector2.ZERO
var _move_pos: Vector2 = Vector2.ZERO
var _look_idx: int = -100
var _look_last: Vector2 = Vector2.ZERO
var _look_delta: Vector2 = Vector2.ZERO

var _jump_latch := false
var _attack_latch := false

const JOY_RADIUS := 110.0
const BTN := 120.0
const BTN_MARGIN := 36.0

var _ceviz_label: Label
var _fistik_label: Label

func _ready() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	_ceviz_label = Label.new()
	_fistik_label = Label.new()
	for l in [_ceviz_label, _fistik_label]:
		l.add_theme_font_size_override("font_size", 28)
		add_child(l)
	_ceviz_label.position = Vector2(24, 18)
	_fistik_label.position = Vector2(24, 54)
	set_nuts(0, 0)
	# CanvasLayer altındaki Control anchor ile otomatik boyutlanmaz (size=0 kalır).
	# Bu yüzden tüm geometriyi _vp() = görünüm boyutundan hesaplarız ve pencere
	# yeniden boyutlanınca yeniden çizeriz.
	get_viewport().size_changed.connect(queue_redraw)
	queue_redraw.call_deferred()

# Gerçek çizilebilir alan (Control.size'a güvenmeden).
func _vp() -> Vector2:
	return get_viewport_rect().size

func set_nuts(ceviz: int, fistik: int) -> void:
	_ceviz_label.text = "🌰 Ceviz: %d" % ceviz
	_fistik_label.text = "🥜 Fıstık: %d" % fistik

# --- Buton dikdörtgenleri (sağ alt) ---
func _jump_rect() -> Rect2:
	var v := _vp()
	return Rect2(v.x - BTN - BTN_MARGIN, v.y - BTN - BTN_MARGIN, BTN, BTN)

func _attack_rect() -> Rect2:
	var v := _vp()
	return Rect2(v.x - BTN * 2 - BTN_MARGIN * 1.6, v.y - BTN - BTN_MARGIN, BTN, BTN)

# --- Giriş ---
func _input(event: InputEvent) -> void:
	if event is InputEventScreenTouch:
		_handle_press(event.index, event.position, event.pressed)
	elif event is InputEventScreenDrag:
		_handle_drag(event.index, event.position)
	elif event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
		_handle_press(-1, event.position, event.pressed)
	elif event is InputEventMouseMotion and (event.button_mask & MOUSE_BUTTON_MASK_LEFT):
		_handle_drag(-1, event.position)

func _handle_press(idx: int, pos: Vector2, pressed: bool) -> void:
	if pressed:
		if _jump_rect().has_point(pos):
			_jump_latch = true
			return
		if _attack_rect().has_point(pos):
			_attack_latch = true
			return
		if pos.x < _vp().x * 0.5 and _move_idx == -100:
			_move_idx = idx
			_move_origin = pos
			_move_pos = pos
			queue_redraw()
		elif _look_idx == -100:
			_look_idx = idx
			_look_last = pos
	else:
		if idx == _move_idx:
			_move_idx = -100
			queue_redraw()
		elif idx == _look_idx:
			_look_idx = -100

func _handle_drag(idx: int, pos: Vector2) -> void:
	if idx == _move_idx:
		_move_pos = pos
		var off := _move_pos - _move_origin
		if off.length() > JOY_RADIUS:
			_move_pos = _move_origin + off.normalized() * JOY_RADIUS
		queue_redraw()
	elif idx == _look_idx:
		_look_delta += pos - _look_last
		_look_last = pos

# --- API (oyuncu kullanır) ---
func get_move_vector() -> Vector2:
	if _move_idx == -100:
		return Vector2.ZERO
	var off := (_move_pos - _move_origin) / JOY_RADIUS
	return Vector2(off.x, -off.y).limit_length(1.0)  # yukarı = ileri

func get_look_delta() -> Vector2:
	var d := _look_delta
	_look_delta = Vector2.ZERO
	return d

func consume_jump() -> bool:
	var j := _jump_latch
	_jump_latch = false
	return j

func consume_attack() -> bool:
	var a := _attack_latch
	_attack_latch = false
	return a

# --- Çizim ---
func _draw() -> void:
	# joystick
	if _move_idx != -100:
		draw_circle(_move_origin, JOY_RADIUS, Color(1, 1, 1, 0.12))
		draw_arc(_move_origin, JOY_RADIUS, 0, TAU, 48, Color(1, 1, 1, 0.35), 3.0)
		draw_circle(_move_pos, JOY_RADIUS * 0.42, Color(1, 1, 1, 0.35))
	# butonlar
	var jr := _jump_rect()
	draw_circle(jr.position + jr.size * 0.5, BTN * 0.5, Color(0.3, 0.7, 1.0, 0.35))
	_draw_btn_label(jr, "ZIPLA")
	var ar := _attack_rect()
	draw_circle(ar.position + ar.size * 0.5, BTN * 0.5, Color(1.0, 0.4, 0.3, 0.35))
	_draw_btn_label(ar, "SALDIR")

func _draw_btn_label(r: Rect2, txt: String) -> void:
	var f := get_theme_default_font()
	var fs := 24
	var w := f.get_string_size(txt, HORIZONTAL_ALIGNMENT_CENTER, -1, fs).x
	draw_string(f, r.position + r.size * 0.5 + Vector2(-w * 0.5, fs * 0.35), txt,
		HORIZONTAL_ALIGNMENT_LEFT, -1, fs, Color(1, 1, 1, 0.9))
