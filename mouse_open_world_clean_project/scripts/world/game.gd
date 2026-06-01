extends Node3D
class_name Game

# Oyun orkestratörü. HER ŞEYİ KODLA kurar (sahneye veri gömülmez):
# ortam/ışık -> arazi (heightmap + su) -> ağaç/fındık serpme -> oyuncu + HUD
# -> yoğun NPC fareler. Mobil renderer için ayarlanmıştır.

@export var world_size: float = 480.0
@export var height_scale: float = 60.0
@export var npc_count: int = 50
@export var player_scale: float = 1.15

var terrain: Terrain
var player: MousePlayer
var hud: GameHUD

func _ready() -> void:
	randomize()
	_setup_input()
	_setup_environment()

	terrain = Terrain.new()
	terrain.name = "Terrain"
	terrain.world_size = world_size
	terrain.height_scale = height_scale
	add_child(terrain)
	terrain.build()
	if not terrain.built:
		push_error("Game: arazi kurulamadı")
		return

	# HUD
	var canvas := CanvasLayer.new()
	canvas.name = "HUDLayer"
	add_child(canvas)
	hud = GameHUD.new()
	canvas.add_child(hud)

	# Oyuncu
	player = MousePlayer.new()
	player.name = "Player"
	player.terrain = terrain
	player.hud = hud
	player.model_scale = player_scale
	add_child(player)
	var sp := terrain.get_random_land_point(40.0)
	player.global_position = sp + Vector3(0, 1.0, 0)
	player.nut_changed.connect(func(c, f): hud.set_nuts(c, f))

	# Ağaç + ceviz/fıstık serpme
	var scat := WorldScatter.new()
	scat.name = "Scatter"
	scat.terrain = terrain
	scat.player = player
	add_child(scat)
	scat.build()

	# Yoğun NPC fareler (kareye yayılarak)
	var spawner := MouseSpawner.new()
	spawner.name = "Spawner"
	spawner.terrain = terrain
	spawner.count = npc_count
	add_child(spawner)
	spawner.build()

# Giriş haritasını kodla kur (klavye + gamepad). Dokunmatik HUD ayrı.
func _setup_input() -> void:
	var defs := {
		"move_forward": [KEY_W, KEY_UP],
		"move_back": [KEY_S, KEY_DOWN],
		"move_left": [KEY_A, KEY_LEFT],
		"move_right": [KEY_D, KEY_RIGHT],
		"jump": [KEY_SPACE],
		"attack": [KEY_J],
		"run": [KEY_SHIFT],
	}
	for action in defs:
		if not InputMap.has_action(action):
			InputMap.add_action(action)
		for kc in defs[action]:
			var ev := InputEventKey.new()
			ev.physical_keycode = kc
			InputMap.action_add_event(action, ev)
	# Gamepad
	var pad := {"jump": JOY_BUTTON_A, "run": JOY_BUTTON_B, "attack": JOY_BUTTON_X}
	for action in pad:
		var jb := InputEventJoypadButton.new()
		jb.button_index = pad[action]
		InputMap.action_add_event(action, jb)
	# Sol analog -> hareket eksenleri
	var axes := {
		"move_left": [JOY_AXIS_LEFT_X, -1.0], "move_right": [JOY_AXIS_LEFT_X, 1.0],
		"move_forward": [JOY_AXIS_LEFT_Y, -1.0], "move_back": [JOY_AXIS_LEFT_Y, 1.0],
	}
	for action in axes:
		var jm := InputEventJoypadMotion.new()
		jm.axis = axes[action][0]
		jm.axis_value = axes[action][1]
		InputMap.action_add_event(action, jm)

func _setup_environment() -> void:
	# Güneş
	var sun := DirectionalLight3D.new()
	sun.name = "Sun"
	sun.rotation = Vector3(deg_to_rad(-48.0), deg_to_rad(40.0), 0.0)
	sun.light_energy = 1.25
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 120.0
	add_child(sun)

	# Gökyüzü + ortam ışığı
	var env := Environment.new()
	var sky_mat := ProceduralSkyMaterial.new()
	sky_mat.sky_top_color = Color(0.36, 0.56, 0.86)
	sky_mat.sky_horizon_color = Color(0.72, 0.80, 0.88)
	sky_mat.ground_bottom_color = Color(0.32, 0.34, 0.30)
	sky_mat.ground_horizon_color = Color(0.62, 0.66, 0.62)
	sky_mat.sun_angle_max = 12.0
	var sky := Sky.new()
	sky.sky_material = sky_mat
	env.background_mode = Environment.BG_SKY
	env.sky = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.ambient_light_energy = 0.9
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	# Uzak mesafe sisi (ada hissi)
	env.fog_enabled = true
	env.fog_light_color = Color(0.72, 0.80, 0.88)
	env.fog_density = 0.0015
	env.fog_aerial_perspective = 0.4
	var we := WorldEnvironment.new()
	we.name = "WorldEnvironment"
	we.environment = env
	add_child(we)
