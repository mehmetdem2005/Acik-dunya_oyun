shader_type spatial;
render_mode cull_disabled, diffuse_burley, specular_schlick_ggx;

// Çam iğnelerinin rüzgarda salınımı + hafif alt-yüzey ışık geçirgenliği.
// Mobil renderer için optimize: sadece vertex sapması, ucuz aydınlatma.

uniform vec3 base_color : source_color = vec3(0.09, 0.22, 0.10);
uniform vec3 tip_color : source_color = vec3(0.22, 0.40, 0.18);
uniform float roughness_val : hint_range(0.0, 1.0) = 0.85;
uniform float wind_strength : hint_range(0.0, 1.0) = 0.18;
uniform float wind_speed : hint_range(0.0, 4.0) = 1.1;
uniform float tree_height = 6.0;
uniform vec2 wind_dir = vec2(1.0, 0.35);
uniform sampler2D noise_tex : hint_default_white, filter_linear, repeat_enable;

varying float v_height;

void vertex() {
	// Yerel y = tabandan yükseklik. Tepeye gidildikçe salınım artar (gerçek ağaç gibi).
	float h = clamp(VERTEX.y / max(tree_height, 0.001), 0.0, 1.0);
	v_height = h;
	float sway_factor = pow(h, 2.0);

	vec3 wp = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	float phase = wp.x * 0.15 + wp.z * 0.15;
	float t = TIME * wind_speed;

	// Ana esinti + yüksek frekanslı titreşim (yaprak çırpıntısı).
	float gust = sin(t + phase) * 0.7 + sin(t * 2.7 + phase * 1.9) * 0.3;
	float flutter = sin(t * 6.3 + wp.y * 3.0) * 0.15;

	vec2 dir = normalize(wind_dir);
	float amp = wind_strength * sway_factor;
	VERTEX.x += dir.x * (gust + flutter) * amp;
	VERTEX.z += dir.y * (gust + flutter) * amp;
	VERTEX.y -= abs(gust) * amp * 0.25; // esnerken hafif çökme
}

void fragment() {
	float h = clamp(v_height, 0.0, 1.0);
	float n = texture(noise_tex, UV * 4.0).r;
	vec3 col = mix(base_color, tip_color, h * 0.85 + n * 0.25);
	ALBEDO = col;
	ROUGHNESS = roughness_val;
	SPECULAR = 0.15;
	// İğne yapraklarda alt-yüzey ışık geçişi hissi.
	BACKLIGHT = tip_color * 0.35;
}
