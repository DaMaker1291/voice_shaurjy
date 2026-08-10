// JARVIS Neural Network Visualization Shaders
// Renders agent nodes and synapse connections inside the orb

export const nodeVertexShader = /* glsl */ `
  attribute float aSize;
  attribute float aActivity;
  attribute vec3 aColor;
  varying float vActivity;
  varying vec3 vColor;
  uniform float uTime;

  void main() {
    vActivity = aActivity;
    vColor = aColor;

    vec3 pos = position;
    // Subtle float animation
    pos += sin(uTime * 2.0 + position.x * 3.0) * 0.02;

    vec4 mvPosition = modelViewMatrix * vec4(pos, 1.0);
    gl_PointSize = aSize * (300.0 / -mvPosition.z);
    gl_Position = projectionMatrix * mvPosition;
  }
`;

export const nodeFragmentShader = /* glsl */ `
  varying float vActivity;
  varying vec3 vColor;
  uniform float uTime;

  void main() {
    // Soft circle
    float dist = length(gl_PointCoord - vec2(0.5));
    if (dist > 0.5) discard;

    float softEdge = 1.0 - smoothstep(0.2, 0.5, dist);
    float glow = exp(-dist * 4.0) * vActivity;

    vec3 color = vColor * (0.5 + glow * 0.5);
    float alpha = softEdge * (0.4 + vActivity * 0.6);

    // Pulse when active
    float pulse = sin(uTime * 4.0 + vActivity * 6.28) * 0.5 + 0.5;
    color += vColor * pulse * vActivity * 0.3;

    gl_FragColor = vec4(color, alpha);
  }
`;

export const synapseVertexShader = /* glsl */ `
  attribute float aActivity;
  attribute float aAlpha;
  varying float vActivity;
  varying float vAlpha;
  uniform float uTime;

  void main() {
    vActivity = aActivity;
    vAlpha = aAlpha;

    vec3 pos = position;
    pos += sin(uTime * 1.5 + position.x * 2.0) * 0.01;

    gl_Position = projectionMatrix * modelViewMatrix * vec4(pos, 1.0);
  }
`;

export const synapseFragmentShader = /* glsl */ `
  varying float vActivity;
  varying float vAlpha;
  uniform float uTime;
  uniform vec3 uColor;

  void main() {
    float pulse = sin(uTime * 3.0 + vActivity * 6.28) * 0.5 + 0.5;
    vec3 color = uColor * (0.3 + pulse * 0.7 * vActivity);
    float alpha = vAlpha * (0.1 + vActivity * 0.4);

    gl_FragColor = vec4(color, alpha);
  }
`;
