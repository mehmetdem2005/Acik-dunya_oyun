shader_type spatial;
render_mode cull_disabled;

// Minimal, mobil-güvenli iğne yaprak shader'ı (opsiyonel rüzgar).
// Karmaşık render_mode / fragment matris / BACKLIGHT kullanmaz ->
// Mobile renderer'da güvenle derlenir, beyaz fallback olmaz.
// Renk dokudan + vertex AO'dan gelir; StandardMaterial ile aynı görünüm.

uniform sampler2D needle_tex : source_color, filter_linear_mipmap;
uniform vec3 tip_color : source_color = vec3(0.34, 0.50, 0.22);
uniform float tree_height = 7.0;
uniform float alpha_cut : hint_range(0.0, 1.0) = 0.5;
uniform float wind_strength : hint_range(0.0, 0.6) = 0.12;
uniform float wind_speed : hint_range(0.0, 4.0) = 1.0;

varying vec3 v_col;

void vertex() {
	v_col = COLOR.rgb;
	float h = clamp(VERTEX.y / max(tree_height, 0.001), 0.0, 1.0);
	float amp = wind_strength * pow(h, 1.5);
	vec3 wp = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	float t = TIME * wind_speed + wp.x * 0.15 + wp.z * 0.15;
	float s = sin(t) * 0.75 + sin(t * 2.6) * 0.25;
	VERTEX.x += s * amp;
	VERTEX.z += s * amp * 0.6;
}

void fragment() {
	vec4 tex = texture(needle_tex, UV);
	if (tex.a < alpha_cut) {
		discard;
	}
	ALBEDO = tex.rgb * v_col;
	ROUGHNESS = 0.86;
	SPECULAR = 0.16;
	EMISSION = tip_color * 0.04;
}
