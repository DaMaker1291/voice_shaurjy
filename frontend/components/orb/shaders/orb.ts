// JARVIS Orb — Volumetric Ray-Marching Shaders

export const orbVertexShader = /* glsl */ `
  varying vec3 vNormal;
  varying vec3 vPosition;
  varying vec2 vUv;
  uniform float uTime;
  uniform float uBreathe;

  // Simplex noise for vertex displacement
  vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
  vec4 mod289(vec4 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
  vec4 permute(vec4 x) { return mod289(((x*34.0)+1.0)*x); }
  vec4 taylorInvSqrt(vec4 r) { return 1.79284291400159 - 0.85373472095314 * r; }

  float snoise(vec3 v) {
    const vec2 C = vec2(1.0/6.0, 1.0/3.0);
    const vec4 D = vec4(0.0, 0.5, 1.0, 2.0);
    vec3 i = floor(v + dot(v, C.yyy));
    vec3 x0 = v - i + dot(i, C.xxx);
    vec3 g = step(x0.yzx, x0.xyz);
    vec3 l = 1.0 - g;
    vec3 i1 = min(g.xyz, l.zxy);
    vec3 i2 = max(g.xyz, l.zxy);
    vec3 x1 = x0 - i1 + C.xxx;
    vec3 x2 = x0 - i2 + C.yyy;
    vec3 x3 = x0 - D.yyy;
    i = mod289(i);
    vec4 p = permute(permute(permute(
      i.z + vec4(0.0, i1.z, i2.z, 1.0))
      + i.y + vec4(0.0, i1.y, i2.y, 1.0))
      + i.x + vec4(0.0, i1.x, i2.x, 1.0));
    float n_ = 0.142857142857;
    vec3 ns = n_ * D.wyz - D.xzx;
    vec4 j = p - 49.0 * floor(p * ns.z * ns.z);
    vec4 x_ = floor(j * ns.z);
    vec4 y_ = floor(j - 7.0 * x_);
    vec4 x = x_ * ns.x + ns.yyyy;
    vec4 y = y_ * ns.x + ns.yyyy;
    vec4 h = 1.0 - abs(x) - abs(y);
    vec4 b0 = vec4(x.xy, y.xy);
    vec4 b1 = vec4(x.zw, y.zw);
    vec4 s0 = floor(b0)*2.0 + 1.0;
    vec4 s1 = floor(b1)*2.0 + 1.0;
    vec4 sh = -step(h, vec4(0.0));
    vec4 a0 = b0.xzyw + s0.xzyw*sh.xxyy;
    vec4 a1 = b1.xzyw + s1.xzyw*sh.zzww;
    vec3 p0 = vec3(a0.xy, h.x);
    vec3 p1 = vec3(a0.zw, h.y);
    vec3 p2 = vec3(a1.xy, h.z);
    vec3 p3 = vec3(a1.zw, h.w);
    vec4 norm = taylorInvSqrt(vec4(dot(p0,p0), dot(p1,p1), dot(p2,p2), dot(p3,p3)));
    p0 *= norm.x; p1 *= norm.y; p2 *= norm.z; p3 *= norm.w;
    vec4 m = max(0.6 - vec4(dot(x0,x0), dot(x1,x1), dot(x2,x2), dot(x3,x3)), 0.0);
    m = m * m;
    return 42.0 * dot(m*m, vec4(dot(p0,x0), dot(p1,x1), dot(p2,x2), dot(p3,x3)));
  }

  void main() {
    vUv = uv;
    vNormal = normalize(normalMatrix * normal);

    // Breathing displacement
    float breathe = sin(uTime * 2.0) * uBreathe * 0.08;

    // Noise-driven surface turbulence
    float noise = snoise(normal * 3.0 + uTime * 0.5) * 0.06;

    // Vertex displacement along normal
    vec3 displaced = position + normal * (breathe + noise);

    vPosition = (modelViewMatrix * vec4(displaced, 1.0)).xyz;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(displaced, 1.0);
  }
`;

export const orbFragmentShader = /* glsl */ `
  varying vec3 vNormal;
  varying vec3 vPosition;
  varying vec2 vUv;
  uniform float uTime;
  uniform float uBreathe;
  uniform float uGlowIntensity;
  uniform vec3 uColor;
  uniform vec3 uColorAlt;
  uniform float uErrorAmount;    // 0 = normal, 1 = full error destabilization
  uniform float uRecoveryAmount; // 0 = normal, 1 = full recovery
  uniform float uCompletionPulse;

  // Simplex noise
  vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
  vec4 mod289(vec4 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
  vec4 permute(vec4 x) { return mod289(((x*34.0)+1.0)*x); }
  vec4 taylorInvSqrt(vec4 r) { return 1.79284291400159 - 0.85373472095314 * r; }

  float snoise(vec3 v) {
    const vec2 C = vec2(1.0/6.0, 1.0/3.0);
    const vec4 D = vec4(0.0, 0.5, 1.0, 2.0);
    vec3 i = floor(v + dot(v, C.yyy));
    vec3 x0 = v - i + dot(i, C.xxx);
    vec3 g = step(x0.yzx, x0.xyz);
    vec3 l = 1.0 - g;
    vec3 i1 = min(g.xyz, l.zxy);
    vec3 i2 = max(g.xyz, l.zxy);
    vec3 x1 = x0 - i1 + C.xxx;
    vec3 x2 = x0 - i2 + C.yyy;
    vec3 x3 = x0 - D.yyy;
    i = mod289(i);
    vec4 p = permute(permute(permute(
      i.z + vec4(0.0, i1.z, i2.z, 1.0))
      + i.y + vec4(0.0, i1.y, i2.y, 1.0))
      + i.x + vec4(0.0, i1.x, i2.x, 1.0));
    float n_ = 0.142857142857;
    vec3 ns = n_ * D.wyz - D.xzx;
    vec4 j = p - 49.0 * floor(p * ns.z * ns.z);
    vec4 x_ = floor(j * ns.z);
    vec4 y_ = floor(j - 7.0 * x_);
    vec4 x = x_ * ns.x + ns.yyyy;
    vec4 y = y_ * ns.x + ns.yyyy;
    vec4 h = 1.0 - abs(x) - abs(y);
    vec4 b0 = vec4(x.xy, y.xy);
    vec4 b1 = vec4(x.zw, y.zw);
    vec4 s0 = floor(b0)*2.0 + 1.0;
    vec4 s1 = floor(b1)*2.0 + 1.0;
    vec4 sh = -step(h, vec4(0.0));
    vec4 a0 = b0.xzyw + s0.xzyw*sh.xxyy;
    vec4 a1 = b1.xzyw + s1.xzyw*sh.zzww;
    vec3 p0 = vec3(a0.xy, h.x);
    vec3 p1 = vec3(a0.zw, h.y);
    vec3 p2 = vec3(a1.xy, h.z);
    vec3 p3 = vec3(a1.zw, h.w);
    vec4 norm = taylorInvSqrt(vec4(dot(p0,p0), dot(p1,p1), dot(p2,p2), dot(p3,p3)));
    p0 *= norm.x; p1 *= norm.y; p2 *= norm.z; p3 *= norm.w;
    vec4 m = max(0.6 - vec4(dot(x0,x0), dot(x1,x1), dot(x2,x2), dot(x3,x3)), 0.0);
    m = m * m;
    return 42.0 * dot(m*m, vec4(dot(p0,x0), dot(p1,x1), dot(p2,x2), dot(p3,x3)));
  }

  void main() {
    vec3 viewDir = normalize(-vPosition);
    vec3 normal = normalize(vNormal);

    // Fresnel (edge glow)
    float fresnel = pow(1.0 - max(dot(viewDir, normal), 0.0), 3.0);

    // Internal noise turbulence
    float noise1 = snoise(vPosition * 2.0 + uTime * 0.3) * 0.5 + 0.5;
    float noise2 = snoise(vPosition * 4.0 - uTime * 0.5) * 0.5 + 0.5;
    float noise3 = snoise(vPosition * 8.0 + uTime * 0.7) * 0.5 + 0.5;

    // Layered turbulence
    float turbulence = noise1 * 0.5 + noise2 * 0.3 + noise3 * 0.2;

    // Color mixing based on turbulence
    vec3 baseColor = mix(uColor, uColorAlt, turbulence * 0.4);

    // Error destabilization effect
    if (uErrorAmount > 0.0) {
      float errorNoise = snoise(vPosition * 5.0 + uTime * 3.0);
      baseColor = mix(baseColor, vec3(0.94, 0.27, 0.27), uErrorAmount * 0.6);
      turbulence += errorNoise * uErrorAmount * 0.3;
      fresnel += uErrorAmount * 0.3;
    }

    // Recovery rebuild effect
    if (uRecoveryAmount > 0.0) {
      float rebuildNoise = snoise(vPosition * 3.0 + uTime * 1.5);
      float rebuildPattern = step(0.5, rebuildNoise);
      baseColor = mix(baseColor, uColor, rebuildPattern * uRecoveryAmount);
    }

    // Completion pulse wave
    float pulse = 0.0;
    if (uCompletionPulse > 0.0) {
      float dist = length(vPosition);
      pulse = sin(dist * 10.0 - uTime * 5.0) * 0.5 + 0.5;
      pulse *= uCompletionPulse;
      baseColor += vec3(0.0, 1.0, 0.4) * pulse * 0.3;
    }

    // Core glow
    float coreGlow = exp(-length(vPosition) * 2.0) * uGlowIntensity;

    // Combine
    vec3 color = baseColor * (0.3 + turbulence * 0.4);
    color += baseColor * fresnel * 0.6;
    color += baseColor * coreGlow * 0.8;
    color += baseColor * pulse * 0.2;

    // Chromatic aberration at edges
    float chromR = fresnel * 0.15;
    color.r += chromR * sin(uTime * 2.0) * 0.5;

    // Energy intensity
    float alpha = 0.6 + fresnel * 0.3 + coreGlow * 0.2 + turbulence * 0.1;
    alpha = clamp(alpha, 0.0, 1.0);

    gl_FragColor = vec4(color, alpha);
  }
`;
