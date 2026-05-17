@tool
extends Node3D
class_name PineTree

# AAA prosedürel çam/ladin MODELİ — çok geçişli mimari:
#   PineSkeleton (özyinelemeli dal grafiği, RMF frame, tropizm)
#   -> PineMesh (odun tüpleri + katlı iğne şeritleri, yumuşak normal)
#   -> PineTextures (önbellekli prosedürel kabuk + iğne atlası)
# Doku: Inspector "Ultra Texture" yuvalarına foto PNG/JPG sürüklenirse
# gerçek PBR kabuk/dal kullanılır; boşsa prosedürel fallback (model dosyası
# yine GEREKMEZ — mesh tamamen prosedürel). .tscn export adları korunur.

@export_group("Boyut")
@export var total_height: float = 7.5
@export var trunk_radius: float = 0.18
@export_range(0.03, 0.4, 0.01) var trunk_top_ratio: float = 0.05
@export_range(0.0, 0.2, 0.005) var trunk_bend: float = 0.04

@export_group("Taç / Dallar")
@export var crown_start_ratio: float = 0.27
@export_range(1.5, 6.0, 0.1) var crown_radius: float = 2.7
@export_range(20, 110, 1) var branch_count: int = 58
@export_range(0.0, 1.0, 0.02) var branch_droop: float = 0.22
@export_range(3, 16, 1) var shoots_per_branch: int = 11
@export var fine_twigs: bool = true
@export_range(0, 4, 1) var twigs_per_shoot: int = 2

@export_group("Gerçekçi Dal / Kök")
@export_range(6, 16, 1) var dal_segment: int = 8          # dal kıvrım çözünürlüğü
@export_range(0.0, 0.4, 0.01) var dal_yay: float = 0.22    # S süpürme yayı
@export_range(0.06, 0.4, 0.01) var surgun_konik: float = 0.14  # sürgün uç incelmesi
@export var level2_wood: bool = true                       # alt-dallar odun olarak görünsün
@export_range(1, 4, 1) var catal_derinlik: int = 1         # V/Y çatallanma (1=sade, az ince-dal karmaşası)
@export_range(0.6, 1.4, 0.05) var tabaka_aralik: float = 1.0   # whorl katman aralığı
@export_range(0.0, 2.0, 0.05) var govde_kok: float = 0.35      # dip kabarma gücü (hafif)
@export_range(0.0, 1.0, 0.02) var kok_payanda: float = 0.0     # payanda lob (0 = düz, kapalı)
@export_range(0, 8, 1) var kok_sayisi: int = 0                 # zemine yayılan kök stem (0 = yok)

@export_group("İğne Yaprak")
@export_range(2, 5, 1) var blades_per_branch: int = 3
@export_range(0.4, 2.5, 0.05) var frond_size: float = 1.2

@export_group("Form / Kusur")
@export_enum("Genc Konik:0", "Olgun Orman:1", "Acikta Yetisen:2") var tree_form: int = 1
@export_range(0.08, 0.30, 0.01) var branch_taper_tip: float = 0.18
@export_range(0.0, 0.5, 0.01) var knot_strength: float = 0.22
@export_range(0.0, 1.0, 0.05) var light_bias: float = 0.0

@export_group("Detay / Performans")
@export_range(8, 20, 1) var trunk_sides: int = 14
@export var seed: int = 20260516
@export var generate_collision: bool = true
@export var enable_wind: bool = true

@export_group("Araçlar")
# Inspector'da bu butona bas -> degisiklikler uygulanir (rebuild).
@export_tool_button("Uygula / Yeniden Olustur") var _apply_action: Callable = rebuild
# Yeni rastgele seed: cam FORMUNU bozmadan boyut/yas/kalinlik degisir.
@export_tool_button("Rastgele Seed") var _seed_action: Callable = _new_seed
@export var seed_varies_form: bool = true

@export_group("Renk / Materyal")
@export var bark_color: Color = Color(0.85, 0.82, 0.80)
@export_range(0.2, 2.0, 0.05) var bark_normal_scale: float = 1.0
@export var needle_dark: Color = Color(0.045, 0.110, 0.050)
@export var needle_mid: Color = Color(0.110, 0.230, 0.105)
@export var needle_lite: Color = Color(0.300, 0.420, 0.170)

# Gerçek foto texture yuvaları. Godot editöründe ilgili PNG/JPG'yi bu
# yuvalara SÜRÜKLE-BIRAK. Yuva boşsa otomatik prosedürel doku kullanılır
# (eski davranış korunur). Import ayarlarını editör doğru yapar:
#   normal/detail_normal -> "Normal Map" olarak içe aktar,
#   ormc/tip_age -> sRGB kapalı (renk değil veri).
@export_group("Ultra Texture — Kabuk")
@export var bark_albedo_tex: Texture2D
@export var bark_normal_tex: Texture2D
@export var bark_ormc_tex: Texture2D          # R=AO  G=Roughness  B=Cavity
@export var bark_height_tex: Texture2D
@export var bark_detail_normal_tex: Texture2D
@export var bark_variation_tex: Texture2D

@export_group("Ultra Texture — Dal")
@export var branch_albedo_tex: Texture2D
@export var branch_normal_tex: Texture2D
@export var branch_ormc_tex: Texture2D        # R=AO  G=Roughness  B=Cavity
@export var branch_tip_age_tex: Texture2D     # R=tip G=age B=bend A=young
@export var branch_detail_normal_tex: Texture2D

@export_group("Ultra Texture — İğne (5x5 atlas)")
@export var needle_albedo_tex: Texture2D       # RGB renk (siyah zemin)
@export var needle_opacity_tex: Texture2D      # alpha kesimi
@export var needle_normal_tex: Texture2D       # normal map
@export var needle_orm_tex: Texture2D          # R=AO G=Rough B=Metal
@export var needle_variation_tex: Texture2D    # renk varyasyonu
@export var needle_windmask_tex: Texture2D
@export var needle_height_tex: Texture2D
@export var needle_bent_tex: Texture2D

@export_group("Ultra Texture — Ayar")
@export_enum("Low:0", "Balanced:1", "High:2") var texture_quality: int = 1
@export var bark_tiling: Vector2 = Vector2(2.5, 3.5)
@export var branch_tiling: Vector2 = Vector2(1.0, 4.0)
@export_range(0.0, 0.18, 0.005) var bark_parallax: float = 0.04

const _TEX_ROOT := "res://assets/trees/pine_ultra_mobile/textures/"

func _ready() -> void:
	# Godot 4.6: instance edilen sahnede _ready sırasında add_child
	# ("busy setting up children") yasak -> ilk yapımı bir kare ertele.
	rebuild.call_deferred()

func rebuild() -> void:
	for c in get_children():
		c.queue_free()

	# Form ön ayarları (genç konik / olgun orman / açıkta yetişen).
	var f_crown := crown_start_ratio
	var f_pl := 0.12
	var f_ph := 0.02
	var f_dry := 0.05
	var f_brk := 0.03
	var f_droop := branch_droop
	var f_el := -0.18
	var f_eh := 0.55
	match tree_form:
		0:
			f_crown = 0.10
			f_pl = 0.05; f_ph = 0.02
			f_dry = 0.05; f_brk = 0.03
			f_droop = maxf(branch_droop * 0.6, 0.10)
			f_el = 0.05; f_eh = 0.75
		2:
			f_crown = 0.06
			f_pl = 0.04; f_ph = 0.03
			f_dry = 0.06; f_brk = 0.04
			f_droop = maxf(branch_droop * 1.1, 0.25)
			f_el = -0.10; f_eh = 0.45
		_:
			f_crown = 0.36

	# Seed cam FORMUNU bozmadan boyut/kalinlik/yas varyasyonu uretir
	# (ayni seed -> ayni agac; farkli seed -> farkli ama yine cam).
	var v_h := total_height
	var v_tr := trunk_radius
	var v_cr := crown_radius
	var v_bc := branch_count
	var v_dr := f_droop
	if seed_varies_form:
		var _fr := RandomNumberGenerator.new()
		_fr.seed = seed if seed != 0 else hash(name)
		v_h *= _fr.randf_range(0.78, 1.30)
		v_tr *= _fr.randf_range(0.80, 1.28)
		v_cr *= _fr.randf_range(0.85, 1.18)
		v_bc = int(round(branch_count * _fr.randf_range(0.85, 1.15)))
		v_dr *= _fr.randf_range(0.85, 1.20)

	var cfg := {
		"seed": seed if seed != 0 else hash(name),
		"height": v_h,
		"trunk_radius": v_tr,
		"trunk_top": trunk_top_ratio,
		"trunk_bend": trunk_bend,
		"crown_start": f_crown,
		"crown_radius": v_cr,
		"branch_count": v_bc,
		"branch_droop": v_dr,
		"shoots_per_branch": shoots_per_branch,
		"trunk_sides": trunk_sides,
		"needle_planes": blades_per_branch,
		"needle_size": frond_size,
		"fine_twigs": fine_twigs,
		"twigs_per_shoot": twigs_per_shoot,
		"prune_low": f_pl,
		"prune_high": f_ph,
		"dry_chance_low": f_dry,
		"broken_chance": f_brk,
		"elev_low": f_el,
		"elev_high": f_eh,
		"branch_taper_tip": branch_taper_tip,
		"knot_strength": knot_strength,
		"light_bias": light_bias,
		"dal_segment": dal_segment,
		"shoot_segment": 7,
		"twig_segment": 4,
		"dal_yay": dal_yay,
		"shoot_taper": surgun_konik,
		"level2_wood": level2_wood,
		"fork_depth": catal_derinlik,
		"whorl_gap": tabaka_aralik,
		"flare_strength": govde_kok,
		"flare_lobe": kok_payanda,
		"root_count": kok_sayisi,
	}

	var skel := PineSkeleton.new()
	var stems := skel.build(cfg)
	var meshes := PineMesh.build(stems, cfg)

	var bark_mi := MeshInstance3D.new()
	bark_mi.name = "Bark"
	bark_mi.mesh = meshes["bark"]
	bark_mi.material_override = _bark_material()
	add_child(bark_mi)

	var branch_mesh = meshes.get("branch")
	if branch_mesh != null:
		var branch_mi := MeshInstance3D.new()
		branch_mi.name = "Branches"
		branch_mi.mesh = branch_mesh
		branch_mi.material_override = _branch_material()
		add_child(branch_mi)

	var leaf_mi := MeshInstance3D.new()
	leaf_mi.name = "Foliage"
	leaf_mi.mesh = meshes["needle"]
	leaf_mi.material_override = _needle_material()
	add_child(leaf_mi)

	if generate_collision and not Engine.is_editor_hint():
		_build_collision()

# Yuva doluysa onu, değilse verilen res:// yolunu (içe aktarılmışsa),
# o da yoksa null döndürür -> çağıran prosedürel fallback'e düşer.
func _tex_or(slot: Texture2D, res_path: String) -> Texture2D:
	if slot != null:
		return slot
	if res_path != "" and ResourceLoader.exists(res_path):
		return ResourceLoader.load(res_path) as Texture2D
	return null

# Ortak PBR kabuk/dal materyali. albedo yoksa eski prosedürel kabuğa düşer.
func _pbr_wood_material(albedo: Texture2D, nrm: Texture2D, ormc: Texture2D,
		detail_n: Texture2D, height: Texture2D, tiling: Vector2,
		use_height: bool) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	# Gövde girintili/oluklu -> tek-yüzlü cull'da yakın çekimde silüette
	# arka plan sızan ince çizgi olur. Çift yüzlü: hairline imkansız.
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	if albedo == null:
		# Prosedürel fallback (eski davranış).
		m.albedo_color = bark_color
		m.albedo_texture = PineTextures.bark()
		m.normal_enabled = true
		m.normal_texture = PineTextures.bark_normal()
		m.normal_scale = bark_normal_scale
		m.uv1_scale = Vector3(1.0, 1.5, 1.0)
		m.roughness = 0.88
		return m
	m.albedo_color = Color(1, 1, 1, 1)
	m.albedo_texture = albedo
	m.metallic = 0.0
	m.roughness = 1.0
	# UV.V mesh'te yay-uzunluğundan fiziksel üretiliyor (kare hücre);
	# .tscn'deki eski tiling override'ı sonucu BOZMASIN diye (1,1,1).
	m.uv1_scale = Vector3.ONE
	if nrm != null:
		m.normal_enabled = true
		m.normal_texture = nrm
		m.normal_scale = bark_normal_scale
	if ormc != null:
		# Kanal paketi: R=AO, G=Roughness (B=Cavity kullanılmıyor).
		m.ao_enabled = true
		m.ao_texture = ormc
		m.ao_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_RED
		m.roughness_texture = ormc
		m.roughness_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_GREEN
	if detail_n != null and texture_quality >= 2:
		m.detail_enabled = true
		m.detail_normal = detail_n
		m.detail_blend_mode = BaseMaterial3D.BLEND_MODE_MIX
		m.detail_uv = BaseMaterial3D.DETAIL_UV_1
	if use_height and height != null and texture_quality >= 2:
		m.heightmap_enabled = true
		m.heightmap_texture = height
		m.heightmap_scale = bark_parallax * 16.0
	return m

# Kabuk: özel shader (variation + tip_age StandardMaterial3D'de YOK).
# texture_quality<1 / shader yok / albedo yok -> eski StandardMaterial3D
# yoluna düşer (mevcut kabul edilen görünüm, sıfır regresyon).
func _bark_shader_material(extra_tip_age: Texture2D) -> Material:
	var albedo := _tex_or(bark_albedo_tex, _TEX_ROOT + "bark/pine_bark_albedo_2k.jpg")
	var nrm := _tex_or(bark_normal_tex, _TEX_ROOT + "bark/pine_bark_normal_2k.jpg")
	var ormc := _tex_or(bark_ormc_tex, _TEX_ROOT + "bark/pine_bark_ormc_2k.jpg")
	var det := _tex_or(bark_detail_normal_tex, _TEX_ROOT + "bark/pine_bark_detail_normal_1k.jpg")
	var hgt := _tex_or(bark_height_tex, _TEX_ROOT + "bark/pine_bark_height_1k.jpg")
	var shader_path := "res://shaders/pine_bark.gdshader"
	var sh: Shader = null
	if albedo != null and texture_quality >= 1 and ResourceLoader.exists(shader_path):
		sh = ResourceLoader.load(shader_path) as Shader
	if sh == null:
		return _pbr_wood_material(albedo, nrm, ormc, det, hgt, bark_tiling, true)
	var sm := ShaderMaterial.new()
	sm.shader = sh
	sm.set_shader_parameter("bark_albedo", albedo)
	if nrm != null:
		sm.set_shader_parameter("bark_normal", nrm)
	if ormc != null:
		sm.set_shader_parameter("bark_ormc", ormc)
	sm.set_shader_parameter("uv_scale", bark_tiling)
	sm.set_shader_parameter("use_detail",
		1.0 if (det != null and texture_quality >= 2) else 0.0)
	if det != null:
		sm.set_shader_parameter("bark_detail_normal", det)
	var vart := _tex_or(bark_variation_tex, _TEX_ROOT + "bark/pine_bark_variation_1k.jpg")
	sm.set_shader_parameter("variation_amt", 0.30 if vart != null else 0.0)
	if vart != null:
		sm.set_shader_parameter("bark_variation", vart)
	if extra_tip_age != null:
		sm.set_shader_parameter("tip_age", extra_tip_age)
		sm.set_shader_parameter("tip_age_amt", 0.25)
	else:
		sm.set_shader_parameter("tip_age_amt", 0.0)
	return sm

func _bark_material() -> Material:
	return _bark_shader_material(null)

func _branch_material() -> Material:
	# Dal kabuğu = GÖVDE kabuğu (gerçek çamda aynı): albedo/normal/ormc
	# gövdeyle AYNI -> tutarlı geçiş. Yalnız tip_age ince yaş tonu ekler.
	return _bark_shader_material(
		_tex_or(branch_tip_age_tex, _TEX_ROOT + "branches/pine_branch_tip_age_1k.png"))

func _needle_material() -> Material:
	var n_alb := _tex_or(needle_albedo_tex, _TEX_ROOT + "needles/pine_needles_albedo_alpha_2k.png")
	if n_alb != null and enable_wind and ResourceLoader.exists("res://shaders/pine_wind.gdshader"):
		var sh := ResourceLoader.load("res://shaders/pine_wind.gdshader") as Shader
		if sh != null:
			var sm := ShaderMaterial.new()
			sm.shader = sh
			sm.set_shader_parameter("needle_albedo", n_alb)
			var n_op := _tex_or(needle_opacity_tex, _TEX_ROOT + "needles/pine_needles_opacity_1k.png")
			sm.set_shader_parameter("use_opacity_tex", 1.0 if n_op != null else 0.0)
			if n_op != null:
				sm.set_shader_parameter("needle_opacity", n_op)
			var n_nrm := _tex_or(needle_normal_tex, _TEX_ROOT + "needles/pine_needles_normal_2k.png")
			sm.set_shader_parameter("normal_amt", 1.0 if n_nrm != null else 0.0)
			if n_nrm != null:
				sm.set_shader_parameter("needle_normal", n_nrm)
			var n_orm := _tex_or(needle_orm_tex, _TEX_ROOT + "needles/pine_needles_orm_2k.png")
			if n_orm != null:
				sm.set_shader_parameter("needle_orm", n_orm)
			var n_var := _tex_or(needle_variation_tex, _TEX_ROOT + "needles/pine_needles_variation_1k.png")
			if n_var != null:
				sm.set_shader_parameter("needle_variation", n_var)
				sm.set_shader_parameter("variation_amt", 0.35)
			else:
				sm.set_shader_parameter("variation_amt", 0.0)
			# needle_windmask bilerek bağlanmıyor: atlas-kart iğne sisteminde
			# kart-yerel UV kartı çarpıtıp titremeye yol açıyor (sertlik
			# zaten flex/yükseklik ile yapılıyor).
			var n_hg := _tex_or(needle_height_tex, _TEX_ROOT + "needles/pine_needles_height_1k.png")
			sm.set_shader_parameter("use_height_tex", 1.0 if n_hg != null else 0.0)
			if n_hg != null:
				sm.set_shader_parameter("needle_height", n_hg)
			var n_bn := _tex_or(needle_bent_tex, _TEX_ROOT + "needles/pine_needles_bent_normal_1k.png")
			sm.set_shader_parameter("bent_amt", 0.4 if n_bn != null else 0.0)
			if n_bn != null:
				sm.set_shader_parameter("needle_bent", n_bn)
			sm.set_shader_parameter("tree_height", total_height)
			sm.set_shader_parameter("backlight_col", needle_mid * 0.28)
			return sm
	# Albedo yoksa: prosedürel atlas + güvenli StandardMaterial3D fallback.
	var tex := PineTextures.needle_atlas()
	var m := StandardMaterial3D.new()
	m.albedo_texture = tex
	m.albedo_color = Color(1, 1, 1, 1)
	m.vertex_color_use_as_albedo = true
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
	m.alpha_scissor_threshold = 0.33
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	# Mat iğne: düşük specular + yüksek roughness -> beyaz parlama yok
	# (shader yolu çalışmasa bile fallback'te de garanti).
	m.roughness = 0.9
	m.backlight_enabled = true
	m.backlight = needle_mid * 0.28
	m.emission_enabled = true
	m.emission = needle_dark
	m.emission_energy_multiplier = 0.02
	return m

func _build_collision() -> void:
	var body := StaticBody3D.new()
	body.name = "TrunkBody"
	add_child(body)
	var col := CollisionShape3D.new()
	var shape := CylinderShape3D.new()
	shape.radius = maxf(trunk_radius * 1.4, 0.18)
	shape.height = total_height
	col.shape = shape
	col.position = Vector3(0.0, total_height * 0.5, 0.0)
	body.add_child(col)

func _new_seed() -> void:
	seed = randi()
	rebuild()
	notify_property_list_changed()
