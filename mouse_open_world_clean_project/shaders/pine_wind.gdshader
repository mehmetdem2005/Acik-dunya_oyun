shader_type spatial;
render_mode cull_disabled;

// Mobil-GÜVENLİ iğne yaprak shader'ı: hiyerarşik rüzgâr + alpha kesme +
// foto-gerçekçi PBR iğne atlası (albedo / opacity / normal / ORM /
// variation) + arkadan ışık geçirgenliği. Karmaşık render_mode YOK,
// fragment'te matris/loop YOK -> Mobile renderer'da kesin derlenir.
//
// UV mesh'te 5x5 atlas hücresine eşlenir (her kart = bir gerçek demet).
// COLOR.rgb = dal-içi AO/tint gölgesi (atlas rengiyle çarpılır).
// Doku yoksa parametreler nötr kalır (prosedürel yoldan ayrı).

uniform sampler2D needle_albedo : source_color, filter_linear_mipmap;
uniform sampler2D needle_opacity : hint_default_white, filter_linear_mipmap;
uniform sampler2D needle_normal : hint_normal, filter_linear_mipmap;
uniform sampler2D needle_orm : hint_default_white, filter_linear_mipmap;
uniform sampler2D needle_variation : source_color, filter_linear_mipmap;

uniform vec3 backlight_col : source_color = vec3(0.05, 0.10, 0.045);
uniform float tree_height = 7.5;
uniform float alpha_cut : hint_range(0.0, 1.0) = 0.34;
uniform float normal_amt : hint_range(0.0, 1.0) = 1.0;
uniform float use_opacity_tex : hint_range(0.0, 1.0) = 1.0;
uniform float variation_amt : hint_range(0.0, 1.0) = 0.22;
uniform float wind_strength : hint_range(0.0, 0.5) = 0.12;
uniform float wind_speed : hint_range(0.0, 4.0) = 1.0;
uniform vec2 wind_dir = vec2(1.0, 0.35);

varying vec3 v_col;

void vertex() {
	v_col = COLOR.rgb;
	// Hiyerarşik rüzgâr: UV2.x = flex (gövde 0 -> iğne ucu ~1.25).
	float flex = UV2.x;
	float h = clamp(VERTEX.y / max(tree_height, 0.001), 0.0, 1.0);
	float amp = wind_strength * mix(pow(h, 1.5) * 0.25, 1.0, clamp(flex, 0.0, 1.0));
	vec3 wp = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	float t = TIME * wind_speed + wp.x * 0.15 + wp.z * 0.15;
	float gust = sin(t) * 0.7 + sin(t * 2.7) * 0.3;
	float flutter = sin(t * 6.1 + wp.y * 3.0) * 0.16 * (0.15 + flex);
	vec2 d = normalize(wind_dir);
	VERTEX.x += d.x * (gust + flutter) * amp;
	VERTEX.z += d.y * (gust + flutter) * amp;
	VERTEX.y -= abs(gust) * amp * 0.2;
}

void fragment() {
	// 5x5 atlas: UV2.y = hücre indeksi, UV = kart yerel (0..1).
	float cell = floor(UV2.y + 0.5);   // mediump varying -> hücreyi yuvarla
	vec2 cb = vec2(mod(cell, 5.0), floor(cell / 5.0));
	vec2 auv = (clamp(UV, 0.0, 1.0) * 0.92 + 0.04 + cb) / 5.0;
	vec4 alb = texture(needle_albedo, auv);
	float lum = max(alb.r, max(alb.g, alb.b));
	float key = smoothstep(0.035, 0.12, lum);
	float op = mix(key, texture(needle_opacity, auv).r, use_opacity_tex);
	if (op < alpha_cut) {
		discard;
	}
	vec3 col = alb.rgb * v_col;
	vec3 varc = texture(needle_variation, auv).rgb;
	col *= mix(vec3(1.0), varc * 1.15, variation_amt);
	vec3 orm = texture(needle_orm, auv).rgb;       // R=AO G=Rough B=Metal
	ALBEDO = col * mix(1.0, orm.r, 0.7);
	ALPHA = op;
	ALPHA_SCISSOR_THRESHOLD = alpha_cut;
	// İğne mat: yüksek roughness + çok düşük specular -> beyaz parlama yok.
	ROUGHNESS = clamp(mix(0.85, orm.g, 0.45), 0.7, 1.0);
	METALLIC = 0.0;
	SPECULAR = 0.06;
	NORMAL_MAP = mix(vec3(0.5, 0.5, 1.0), texture(needle_normal, auv).rgb, normal_amt);
	NORMAL_MAP_DEPTH = 0.6;
	BACKLIGHT = backlight_col * 0.5;
}
