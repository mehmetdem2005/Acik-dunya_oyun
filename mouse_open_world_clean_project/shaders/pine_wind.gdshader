shader_type spatial;
render_mode cull_disabled, diffuse_burley, specular_schlick_ggx, depth_prepass_alpha;

// AAA iğne yaprak shader'ı:
// - Tilelenen prosedürel iğne dokusu (keskin alpha)
// - COLOR.rgb = AO (gövdeye/içe doğru koyu), COLOR.a = yükseklik
// - Hacimsel foliage normali (gövdeden dışa doğru) -> karton görünüm yok
// - Rüzgar salınımı + alt-yüzey ışık geçirgenliği

uniform vec3 base_color : source_color = vec3(0.06, 0.16, 0.08);
uniform vec3 tip_color : source_color = vec3(0.28, 0.44, 0.20);
uniform float roughness_val : hint_range(0.0, 1.0) = 0.9;
uniform float wind_strength : hint_range(0.0, 1.0) = 0.13;
uniform float wind_speed : hint_range(0.0, 4.0) = 1.0;
uniform float tree_height = 7.0;
uniform vec2 wind_dir = vec2(1.0, 0.35);
uniform float alpha_cut : hint_range(0.0, 1.0) = 0.45;
uniform float normal_round : hint_range(0.0, 1.0) = 0.75;
uniform sampler2D needle_tex : source_color, filter_linear_mipmap, repeat_enable;

varying float v_height;
varying float v_ao;
varying vec3 v_round_n;

void vertex() {
	v_height = clamp(VERTEX.y / max(tree_height, 0.001), 0.0, 1.0);
	v_ao = COLOR.r;

	// Hacimsel normal: nesne merkez ekseninden dışa + hafif yukarı.
	vec3 outward = normalize(vec3(VERTEX.x, 0.0, VERTEX.z) + vec3(0.0001));
	v_round_n = normalize(mix(NORMAL, normalize(outward + vec3(0.0, 0.6, 0.0)), normal_round));

	float sway_factor = pow(v_height, 1.6);
	vec3 wp = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	float phase = wp.x * 0.15 + wp.z * 0.15;
	float t = TIME * wind_speed;
	float gust = sin(t + phase) * 0.7 + sin(t * 2.7 + phase * 1.9) * 0.3;
	float flutter = sin(t * 6.3 + wp.y * 3.0) * 0.18;

	vec2 dir = normalize(wind_dir);
	float amp = wind_strength * sway_factor;
	VERTEX.x += dir.x * (gust + flutter) * amp;
	VERTEX.z += dir.y * (gust + flutter) * amp;
	VERTEX.y -= abs(gust) * amp * 0.22;
}

void fragment() {
	vec4 tex = texture(needle_tex, UV);
	if (tex.a < alpha_cut) {
		discard;
	}
	float h = clamp(v_height, 0.0, 1.0);
	float ao = clamp(v_ao, 0.0, 1.0);

	// Ton: tabanda koyu iç, tepede/dışta güneşli uç.
	vec3 tint = mix(base_color, tip_color, h * 0.55 + ao * 0.45);
	// Doku iğne deseni/yerel varyasyon; aşırı parlamadan harmanla.
	vec3 col = tint * (0.55 + 0.45 * tex.g) * (0.45 + 0.55 * ao);

	ALBEDO = col;
	ALPHA = tex.a;
	ROUGHNESS = roughness_val;
	SPECULAR = 0.15;
	NORMAL = normalize((MODELVIEW_MATRIX * vec4(v_round_n, 0.0)).xyz);
	// İnce iğnelerde arkadan ışık geçişi (terleme/translucency hissi).
	BACKLIGHT = tip_color * (0.35 + 0.3 * h);
}
