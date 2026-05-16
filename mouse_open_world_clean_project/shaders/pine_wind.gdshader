shader_type spatial;
render_mode cull_disabled, diffuse_burley, specular_schlick_ggx, depth_prepass_alpha;

// İğne yaprak kartları: prosedürel iğne dokusu (alpha) + rüzgar salınımı
// + alt-yüzey ışık geçirgenliği. Mobil için ucuz: sadece vertex sapması.

uniform vec3 base_color : source_color = vec3(0.10, 0.21, 0.10);
uniform vec3 tip_color : source_color = vec3(0.30, 0.45, 0.22);
uniform float roughness_val : hint_range(0.0, 1.0) = 0.88;
uniform float wind_strength : hint_range(0.0, 1.0) = 0.14;
uniform float wind_speed : hint_range(0.0, 4.0) = 1.0;
uniform float tree_height = 6.0;
uniform vec2 wind_dir = vec2(1.0, 0.35);
uniform float alpha_cut : hint_range(0.0, 1.0) = 0.4;
uniform sampler2D needle_tex : source_color, filter_linear_mipmap, repeat_disable;

varying float v_height;

void vertex() {
	float h = clamp(VERTEX.y / max(tree_height, 0.001), 0.0, 1.0);
	v_height = h;
	float sway_factor = pow(h, 1.6);

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
	// Doku iğne şeklini/yerel varyasyonu verir; tonu ağaca göre kaydır.
	vec3 tint = mix(base_color, tip_color, h * 0.7 + 0.15);
	ALBEDO = tex.rgb * 0.55 + tint * 0.85;
	ALPHA = tex.a;
	ROUGHNESS = roughness_val;
	SPECULAR = 0.12;
	BACKLIGHT = tip_color * 0.4;
}
