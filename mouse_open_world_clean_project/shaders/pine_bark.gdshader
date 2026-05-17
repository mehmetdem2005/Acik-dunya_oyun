shader_type spatial;
render_mode cull_disabled;

// Mobil-GÜVENLİ kabuk/dal shader'ı: foto-gerçekçi PBR kabuk
// (albedo / normal / ORMc / detail-normal / height) + StandardMaterial3D'de
// karşılığı OLMAYAN iki ultra harita:
//   * bark_variation -> düşük-frekanslı renk varyasyonu (tile tekrarını kırar)
//   * tip_age         -> yalnız DAL materyalinde set edilir (gövdede beyaz =
//                        nötr); genç-uç/yaş ince ton, dal gövdeyle uyumlu kalır
// Fragment'te loop/matris YOK -> Mobile renderer'da kesin derlenir.
// use_*/amt = 0 ise davranış nötr (texture atanmazsa eski görünüm korunur).

uniform sampler2D bark_albedo : source_color, filter_linear_mipmap;
uniform sampler2D bark_normal : hint_normal, filter_linear_mipmap;
uniform sampler2D bark_ormc : hint_default_white, filter_linear_mipmap; // R=AO G=Rough
uniform sampler2D bark_detail_normal : hint_normal, filter_linear_mipmap;
uniform sampler2D bark_height : hint_default_white, filter_linear_mipmap;
uniform sampler2D bark_variation : source_color, filter_linear_mipmap;
uniform sampler2D tip_age : hint_default_white, filter_linear_mipmap;

uniform vec2 uv_scale = vec2(1.0, 1.0);
uniform float parallax : hint_range(0.0, 0.12) = 0.04;
uniform float detail_scale : hint_range(1.0, 8.0) = 4.0;
uniform float variation_scale : hint_range(0.01, 0.5) = 0.05;
uniform float variation_amt : hint_range(0.0, 1.0) = 0.30;
uniform float tip_age_amt : hint_range(0.0, 1.0) = 0.0;
uniform float normal_depth : hint_range(0.0, 2.0) = 1.0;
uniform float use_detail : hint_range(0.0, 1.0) = 0.0;
uniform float use_height : hint_range(0.0, 1.0) = 0.0;

varying vec3 v_wpos;

void vertex() {
	UV *= uv_scale;
	v_wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	// Tek-adım parallax (loopsuz, mobil güvenli). use_height=0 -> etkisiz.
	vec2 voff = vec2(dot(VIEW, TANGENT), dot(VIEW, BINORMAL));
	float h0 = texture(bark_height, UV).r;
	vec2 uv = UV + voff * (h0 - 0.5) * parallax * use_height;

	vec3 alb = texture(bark_albedo, uv).rgb;

	// Düşük-frekanslı varyasyon: dünya XZ'den örneklenir -> bitişik
	// kareler arası tile tekrarı görsel olarak kırılır (asıl "ultra" etki).
	vec3 varc = texture(bark_variation, v_wpos.xz * variation_scale).rgb;
	alb *= mix(vec3(1.0), varc * 1.15, variation_amt);

	// tip_age: gövdede beyaz doku + amt=0 -> nötr; dalda ince yaş tonu.
	vec3 ta = texture(tip_age, uv).rgb;
	alb *= mix(1.0, 0.85 + 0.15 * ta.g, tip_age_amt);

	ALBEDO = alb;

	vec3 orm = texture(bark_ormc, uv).rgb;   // R=AO  G=Roughness
	AO = orm.r;
	AO_LIGHT_AFFECT = 1.0;
	ROUGHNESS = clamp(orm.g, 0.04, 1.0);
	METALLIC = 0.0;
	SPECULAR = 0.4;

	vec3 nb = texture(bark_normal, uv).rgb;
	vec3 nd = texture(bark_detail_normal, uv * detail_scale).rgb;
	NORMAL_MAP = mix(nb, nd, 0.5 * use_detail);
	NORMAL_MAP_DEPTH = normal_depth;
}
