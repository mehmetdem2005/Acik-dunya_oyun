// Mobil dostu su yüzeyi shader'ı.
// Ekran dokusu / SSR KULLANMAZ (mobile renderer + performans). Animasyonlu
// normaller TIME ile prosedürel sinüs dalgalarından üretilir; sığ/derin renk
// karışımı ve Fresnel kenar parlaması ile ucuz ama inandırıcı su verir.
shader_type spatial;
render_mode blend_mix, cull_back, diffuse_burley, specular_schlick_ggx, depth_draw_opaque;

uniform vec4 shallow_color : source_color = vec4(0.18, 0.52, 0.58, 0.72);
uniform vec4 deep_color : source_color = vec4(0.03, 0.13, 0.22, 0.92);
uniform float wave_speed : hint_range(0.0, 3.0) = 0.6;
uniform float wave_scale : hint_range(0.5, 30.0) = 6.0;
uniform float wave_height : hint_range(0.0, 0.6) = 0.10;
uniform float normal_strength : hint_range(0.0, 2.0) = 0.55;
uniform float fresnel_power : hint_range(0.5, 8.0) = 4.0;
uniform float roughness_val : hint_range(0.0, 1.0) = 0.06;

// Birden çok yöne kayan ucuz dalga toplamı (gerstner benzeri yükseklik).
float wave_h(vec2 p, float t) {
	float h = 0.0;
	h += sin(p.x * 0.7 + t * 1.1) * 0.5;
	h += sin(p.y * 0.9 - t * 0.9) * 0.4;
	h += sin((p.x + p.y) * 0.5 + t * 1.7) * 0.3;
	h += sin((p.x - p.y) * 1.3 - t * 1.3) * 0.2;
	return h;
}

varying vec3 world_pos;

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	float t = TIME * wave_speed;
	vec2 wp = world_pos.xz / wave_scale;
	VERTEX.y += wave_h(wp, t) * wave_height;
}

void fragment() {
	float t = TIME * wave_speed;
	vec2 wp = world_pos.xz / wave_scale;
	// Yükseklik alanından sonlu fark ile normal türet.
	float e = 0.35;
	float hl = wave_h(wp - vec2(e, 0.0), t);
	float hr = wave_h(wp + vec2(e, 0.0), t);
	float hd = wave_h(wp - vec2(0.0, e), t);
	float hu = wave_h(wp + vec2(0.0, e), t);
	vec3 n = normalize(vec3((hl - hr) * normal_strength, 2.0, (hd - hu) * normal_strength));
	NORMAL = normalize((VIEW_MATRIX * vec4(n, 0.0)).xyz);

	float fres = pow(1.0 - clamp(dot(normalize(VIEW), NORMAL), 0.0, 1.0), fresnel_power);
	vec3 col = mix(deep_color.rgb, shallow_color.rgb, clamp(fres + 0.25, 0.0, 1.0));
	ALBEDO = col;
	ALPHA = mix(deep_color.a, shallow_color.a, fres);
	ROUGHNESS = roughness_val;
	METALLIC = 0.0;
	SPECULAR = 0.5;
}
