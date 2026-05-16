extends CanvasLayer

# Runtime UI. Sahnede texture gömmez, her şeyi oyun çalışınca üretir.

@onready var root_control: Control = $Control
@onready var base: TextureRect = $Control/JoystickBase
@onready var knob: TextureRect = $Control/JoystickKnob
@onready var jump_button: TouchScreenButton = $Control/JumpButton
@onready var sprint_button: TouchScreenButton = $Control/SprintButton
@onready var stamina_root: Control = $Control/StaminaRoot
@onready var stamina_bg: ColorRect = $Control/StaminaRoot/StaminaBg
@onready var stamina_fill: ColorRect = $Control/StaminaRoot/StaminaFill
@onready var stamina_label: Label = $Control/StaminaRoot/StaminaLabel
@onready var jump_label: Label = $Control/JumpLabel
@onready var sprint_label: Label = $Control/SprintLabel
@onready var joystick_hint: Label = $Control/JoystickHint

var joystick_vector: Vector2 = Vector2.ZERO
var camera_delta: Vector2 = Vector2.ZERO
var radius: float = 90.0
var dragging: bool = false
var camera_dragging: bool = false
var touch_id: int = -1
var camera_touch_id: int = -1
var center: Vector2 = Vector2.ZERO
var jump_pressed_once: bool = false
var stamina_ratio: float = 1.0

const JOYSTICK_BASE_SIZE: float = 220.0
const JOYSTICK_KNOB_SIZE: float = 110.0
const JUMP_SIZE: float = 150.0
const SPRINT_SIZE: float = 120.0

func _ready() -> void:
	add_to_group("mobile_ui")
	_setup_layout()
	_setup_generated_visuals()
	_setup_labels()
	center = base.position + base.size * 0.5
	_reset_knob()

func _process(_delta: float) -> void:
	_update_label_positions()
	_update_stamina_bar()

func get_joystick_vector() -> Vector2:
	return joystick_vector

func consume_camera_delta() -> Vector2:
	var out: Vector2 = camera_delta
	camera_delta = Vector2.ZERO
	return out

func is_jump_pressed() -> bool:
	return jump_button.is_pressed()

func consume_jump_pressed() -> bool:
	if jump_pressed_once:
		jump_pressed_once = false
		return true
	return false

func is_sprint_pressed() -> bool:
	return sprint_button.is_pressed()

func set_stamina_ratio(value: float) -> void:
	stamina_ratio = clampf(value, 0.0, 1.0)

func _setup_layout() -> void:
	var vp: Vector2 = get_viewport().get_visible_rect().size
	root_control.set_anchors_preset(Control.PRESET_FULL_RECT)
	root_control.offset_left = 0.0
	root_control.offset_top = 0.0
	root_control.offset_right = 0.0
	root_control.offset_bottom = 0.0
	base.position = Vector2(60.0, vp.y - 60.0 - JOYSTICK_BASE_SIZE)
	base.size = Vector2(JOYSTICK_BASE_SIZE, JOYSTICK_BASE_SIZE)
	knob.size = Vector2(JOYSTICK_KNOB_SIZE, JOYSTICK_KNOB_SIZE)
	jump_button.position = Vector2(vp.x - 60.0 - JUMP_SIZE, vp.y - 90.0 - JUMP_SIZE)
	sprint_button.position = Vector2(vp.x - 240.0 - SPRINT_SIZE, vp.y - 120.0 - SPRINT_SIZE)
	stamina_root.position = Vector2(40.0, 40.0)
	stamina_root.size = Vector2(260.0, 28.0)
	stamina_bg.position = Vector2.ZERO
	stamina_bg.size = stamina_root.size
	stamina_fill.position = Vector2.ZERO
	stamina_fill.size = stamina_root.size
	stamina_label.position = Vector2.ZERO
	stamina_label.size = stamina_root.size

func _setup_generated_visuals() -> void:
	base.texture = _make_circle_texture(int(JOYSTICK_BASE_SIZE), Color(0.08, 0.08, 0.08, 0.35), Color(1, 1, 1, 0.35), 6)
	knob.texture = _make_circle_texture(int(JOYSTICK_KNOB_SIZE), Color(0.92, 0.92, 0.92, 0.90), Color(1, 1, 1, 0.95), 4)
	base.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	base.stretch_mode = TextureRect.STRETCH_SCALE
	knob.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	knob.stretch_mode = TextureRect.STRETCH_SCALE
	jump_button.texture_normal = _make_circle_texture(int(JUMP_SIZE), Color(0.10, 0.55, 1.00, 0.78), Color(1, 1, 1, 0.9), 6)
	jump_button.texture_pressed = _make_circle_texture(int(JUMP_SIZE), Color(0.06, 0.35, 0.85, 0.95), Color(1, 1, 1, 1), 6)
	sprint_button.texture_normal = _make_circle_texture(int(SPRINT_SIZE), Color(1.00, 0.55, 0.12, 0.78), Color(1, 1, 1, 0.9), 6)
	sprint_button.texture_pressed = _make_circle_texture(int(SPRINT_SIZE), Color(0.90, 0.32, 0.06, 0.95), Color(1, 1, 1, 1), 6)
	stamina_bg.color = Color(0, 0, 0, 0.45)
	stamina_fill.color = Color(0.1, 0.85, 0.25, 0.95)

func _setup_labels() -> void:
	jump_label.text = "JUMP"
	sprint_label.text = "RUN"
	joystick_hint.text = "MOVE"
	stamina_label.text = "STAMINA 100%"
	_style_label(jump_label, 30)
	_style_label(sprint_label, 24)
	_style_label(joystick_hint, 22)
	_style_label(stamina_label, 16)

func _style_label(lbl: Label, size: int) -> void:
	lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	lbl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	lbl.add_theme_color_override("font_color", Color(1, 1, 1, 0.95))
	lbl.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0.7))
	lbl.add_theme_constant_override("shadow_offset_x", 2)
	lbl.add_theme_constant_override("shadow_offset_y", 2)
	lbl.add_theme_font_size_override("font_size", size)

func _update_label_positions() -> void:
	jump_label.position = jump_button.position + Vector2(18.0, 48.0)
	jump_label.size = Vector2(JUMP_SIZE - 36.0, 50.0)
	sprint_label.position = sprint_button.position + Vector2(10.0, 35.0)
	sprint_label.size = Vector2(SPRINT_SIZE - 20.0, 40.0)
	joystick_hint.position = base.position + Vector2(50.0, 88.0)
	joystick_hint.size = Vector2(JOYSTICK_BASE_SIZE - 100.0, 40.0)

func _update_stamina_bar() -> void:
	stamina_fill.size = Vector2(stamina_root.size.x * stamina_ratio, stamina_root.size.y)
	stamina_label.text = "STAMINA " + str(int(round(stamina_ratio * 100.0))) + "%"

func _input(event: InputEvent) -> void:
	if event is InputEventScreenTouch:
		var touch: InputEventScreenTouch = event
		if touch.pressed:
			if _is_inside_joystick(touch.position):
				dragging = true
				touch_id = touch.index
			elif _is_inside_jump(touch.position):
				jump_pressed_once = true
			elif not is_pointer_over_action_buttons(touch.position) and touch.position.x > get_viewport().get_visible_rect().size.x * 0.45:
				camera_dragging = true
				camera_touch_id = touch.index
		else:
			if touch.index == touch_id:
				dragging = false
				touch_id = -1
				joystick_vector = Vector2.ZERO
				_reset_knob()
			if touch.index == camera_touch_id:
				camera_dragging = false
				camera_touch_id = -1

	if event is InputEventScreenDrag:
		var drag: InputEventScreenDrag = event
		if dragging and drag.index == touch_id:
			var dir: Vector2 = drag.position - center
			if dir.length() > radius:
				dir = dir.normalized() * radius
			knob.position = center + dir - knob.size * 0.5
			joystick_vector = dir / radius
		elif camera_dragging and drag.index == camera_touch_id:
			camera_delta += drag.relative

func is_pointer_over_action_buttons(screen_pos: Vector2) -> bool:
	return _is_inside_jump(screen_pos) or _is_inside_sprint(screen_pos)

func _is_inside_joystick(pos: Vector2) -> bool:
	return Rect2(base.position, base.size).has_point(pos)

func _is_inside_jump(pos: Vector2) -> bool:
	return Rect2(jump_button.position, Vector2(JUMP_SIZE, JUMP_SIZE)).has_point(pos)

func _is_inside_sprint(pos: Vector2) -> bool:
	return Rect2(sprint_button.position, Vector2(SPRINT_SIZE, SPRINT_SIZE)).has_point(pos)

func _reset_knob() -> void:
	knob.position = base.position + (base.size - knob.size) * 0.5
	center = base.position + base.size * 0.5

func _make_circle_texture(size: int, fill: Color, border: Color, border_width: int = 4) -> Texture2D:
	var img: Image = Image.create(size, size, false, Image.FORMAT_RGBA8)
	img.fill(Color(0, 0, 0, 0))
	var r: float = float(size) * 0.5
	var inner_r: float = r - float(border_width)
	var c: Vector2 = Vector2(r, r)
	for y: int in range(size):
		for x: int in range(size):
			var p: Vector2 = Vector2(float(x) + 0.5, float(y) + 0.5)
			var d: float = p.distance_to(c)
			if d <= r:
				if d >= inner_r:
					img.set_pixel(x, y, border)
				else:
					img.set_pixel(x, y, fill)
	return ImageTexture.create_from_image(img)
