shader_type spatial;
render_mode cull_disabled;

// Mobil-GÜVENLİ iğne yaprak shader'ı: rüzgâr salınımı + alpha kesme +
// arkadan ışık geçirgenliği (backlight). Karmaşık render_mode YOK,
// fragment'te matris YOK, depth_prepass YOK -> Mobile renderer'da
// kesin derlenir (beyaz/magenta fallback olmaz).
//
// Renk dokudan (atlas) + vertex COLOR (AO/tint) çarpımından gelir.
// Yumuşak hacim normalleri mesh'te bakelidir (NORMAL'a dokunulmaz).

uniform sampler2D needle_tex : source_color, filter_linear_mipmap;
uniform vec3 backlight_col : source_color = vec3(0.05, 0.10, 0.045);
uniform float tree_height = 7.5;
uniform float alpha_cut : hint_range(0.0, 1.0) = 0.33;
uniform float wind_strength : hint_range(0.0, 0.5) = 0.12;
uniform float wind_speed : hint_range(0.0, 4.0) = 1.0;
uniform vec2 wind_dir = vec2(1.0, 0.35);

varying vec3 v_col;

void vertex() {
	v_col = COLOR.rgb;
	// Yüksekliğe göre artan salınım + uç çırpıntısı.
	float h = clamp(VERTEX.y / max(tree_height, 0.001), 0.0, 1.0);
	float amp = wind_strength * pow(h, 1.5);
	vec3 wp = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	float t = TIME * wind_speed + wp.x * 0.15 + wp.z * 0.15;
	float gust = sin(t) * 0.7 + sin(t * 2.7) * 0.3;
	float flutter = sin(t * 6.1 + wp.y * 3.0) * 0.18;
	vec2 d = normalize(wind_dir);
	VERTEX.x += d.x * (gust + flutter) * amp;
	VERTEX.z += d.y * (gust + flutter) * amp;
	VERTEX.y -= abs(gust) * amp * 0.2;
}

void fragment() {
	vec4 tex = texture(needle_tex, UV);
	float a = tex.a * COLOR.a;
	if (a < alpha_cut) {
		discard;
	}
	ALBEDO = tex.rgb * v_col;
	ALPHA = a;
	ALPHA_SCISSOR_THRESHOLD = alpha_cut;
	ROUGHNESS = 0.65;
	SPECULAR = 0.5;
	// Arkadan ışıkta translucent yeşil parıltı (iğne ince -> ışık geçer).
	BACKLIGHT = backlight_col;
}
