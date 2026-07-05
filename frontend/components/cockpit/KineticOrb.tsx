"use client";

import { useRef, useEffect, useMemo } from "react";
import * as THREE from "three";

interface KineticOrbProps {
  size?: number;
  particleCount?: number;
  color?: string;
  accentColor?: string;
  speed?: number;
  className?: string;
  style?: React.CSSProperties;
}

export default function KineticOrb({
  size = 280,
  particleCount = 600,
  color = "#00FF66",
  accentColor = "#FFB300",
  speed = 0.4,
  className,
  style,
}: KineticOrbProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const frameRef = useRef<number>(0);
  const mouseRef = useRef({ x: 0, y: 0 });

  const uniforms = useMemo(
    () => ({
      uTime: { value: 0 },
      uMouse: { value: new THREE.Vector2(0, 0) },
      uColor1: { value: new THREE.Color(color) },
      uColor2: { value: new THREE.Color(accentColor) },
    }),
    [color, accentColor]
  );

  useEffect(() => {
    if (!containerRef.current) return;

    const container = containerRef.current;

    // Renderer
    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
      powerPreference: "high-performance",
    });
    renderer.setSize(size, size);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor(0x000000, 0);
    container.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // Scene
    const scene = new THREE.Scene();
    sceneRef.current = scene;

    // Camera
    const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
    camera.position.z = 3.5;
    cameraRef.current = camera;

    // Particles geometry
    const geometry = new THREE.BufferGeometry();
    const positions = new Float32Array(particleCount * 3);
    const velocities = new Float32Array(particleCount * 3);
    const phases = new Float32Array(particleCount);
    const sizes = new Float32Array(particleCount);

    for (let i = 0; i < particleCount; i++) {
      const i3 = i * 3;
      // Distribute on sphere surface
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      const r = 0.8 + Math.random() * 0.4;

      positions[i3] = r * Math.sin(phi) * Math.cos(theta);
      positions[i3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      positions[i3 + 2] = r * Math.cos(phi);

      velocities[i3] = (Math.random() - 0.5) * 0.01;
      velocities[i3 + 1] = (Math.random() - 0.5) * 0.01;
      velocities[i3 + 2] = (Math.random() - 0.5) * 0.01;

      phases[i] = Math.random() * Math.PI * 2;
      sizes[i] = 0.5 + Math.random() * 1.5;
    }

    geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute("aVelocity", new THREE.BufferAttribute(velocities, 3));
    geometry.setAttribute("aPhase", new THREE.BufferAttribute(phases, 1));
    geometry.setAttribute("aSize", new THREE.BufferAttribute(sizes, 1));

    // Shader material
    const vertexShader = `
      uniform float uTime;
      uniform vec2 uMouse;
      attribute vec3 aVelocity;
      attribute float aPhase;
      attribute float aSize;
      varying vec3 vPos;
      varying float vAlpha;
      
      void main() {
        vec3 pos = position;
        
        // Orbital motion
        float angle = uTime * 0.3 + aPhase;
        float cosA = cos(angle);
        float sinA = sin(angle);
        
        // Rotate around Y
        vec3 rotated = vec3(
          pos.x * cosA - pos.z * sinA,
          pos.y,
          pos.x * sinA + pos.z * cosA
        );
        
        // Breathing pulse
        float breathe = sin(uTime * 0.5 + aPhase) * 0.08;
        rotated *= 1.0 + breathe;
        
        // Mouse repulsion
        vec2 toMouse = uMouse - rotated.xy;
        float mouseDist = length(toMouse);
        if (mouseDist < 1.2) {
          float force = (1.2 - mouseDist) * 0.3;
          rotated.xy -= normalize(toMouse) * force;
        }
        
        // Velocity drift
        rotated += aVelocity * sin(uTime * 0.2 + aPhase * 3.0);
        
        vPos = rotated;
        vAlpha = 0.3 + 0.7 * abs(sin(uTime * 0.4 + aPhase));
        
        vec4 mvPosition = modelViewMatrix * vec4(rotated, 1.0);
        gl_PointSize = aSize * (200.0 / -mvPosition.z);
        gl_Position = projectionMatrix * mvPosition;
      }
    `;

    const fragmentShader = `
      uniform vec3 uColor1;
      uniform vec3 uColor2;
      uniform float uTime;
      varying vec3 vPos;
      varying float vAlpha;
      
      void main() {
        // Circular point
        vec2 center = gl_PointCoord - 0.5;
        float dist = length(center);
        if (dist > 0.5) discard;
        
        // Glow falloff
        float glow = 1.0 - smoothstep(0.0, 0.5, dist);
        glow = pow(glow, 1.5);
        
        // Color blend based on position
        float t = (vPos.y + 1.2) / 2.4;
        t = clamp(t + sin(uTime * 0.3) * 0.15, 0.0, 1.0);
        vec3 color = mix(uColor1, uColor2, t);
        
        // Inner core brightens
        float core = 1.0 - smoothstep(0.0, 0.15, dist);
        color += vec3(core * 0.3);
        
        gl_FragColor = vec4(color, glow * vAlpha * 0.85);
      }
    `;

    const material = new THREE.ShaderMaterial({
      vertexShader,
      fragmentShader,
      uniforms,
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });

    const points = new THREE.Points(geometry, material);
    scene.add(points);

    // Inner glow sphere
    const glowGeo = new THREE.SphereGeometry(0.6, 32, 32);
    const glowMat = new THREE.ShaderMaterial({
      vertexShader: `
        varying vec3 vNormal;
        varying vec3 vPosition;
        void main() {
          vNormal = normalize(normalMatrix * normal);
          vPosition = (modelViewMatrix * vec4(position, 1.0)).xyz;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
      `,
      fragmentShader: `
        uniform vec3 uColor;
        uniform float uTime;
        varying vec3 vNormal;
        varying vec3 vPosition;
        void main() {
          vec3 viewDir = normalize(-vPosition);
          float fresnel = pow(1.0 - max(dot(viewDir, vNormal), 0.0), 3.0);
          float pulse = 0.5 + 0.5 * sin(uTime * 0.6);
          vec3 col = uColor * (fresnel * 0.4 + 0.1) * (0.8 + pulse * 0.2);
          gl_FragColor = vec4(col, fresnel * 0.25);
        }
      `,
      uniforms: {
        uColor: uniforms.uColor1,
        uTime: uniforms.uTime,
      },
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      side: THREE.BackSide,
    });
    const glowMesh = new THREE.Mesh(glowGeo, glowMat);
    scene.add(glowMesh);

    // Animation loop
    let time = 0;
    const animate = () => {
      time += 0.008 * speed;
      uniforms.uTime.value = time;
      uniforms.uMouse.value.set(mouseRef.current.x, mouseRef.current.y);

      points.rotation.y = time * 0.15;
      points.rotation.x = Math.sin(time * 0.1) * 0.1;

      renderer.render(scene, camera);
      frameRef.current = requestAnimationFrame(animate);
    };
    animate();

    // Mouse tracking
    const handleMouseMove = (e: MouseEvent) => {
      const rect = container.getBoundingClientRect();
      mouseRef.current.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      mouseRef.current.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
    };
    container.addEventListener("mousemove", handleMouseMove);

    return () => {
      cancelAnimationFrame(frameRef.current);
      container.removeEventListener("mousemove", handleMouseMove);
      renderer.dispose();
      geometry.dispose();
      material.dispose();
      glowGeo.dispose();
      glowMat.dispose();
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
    };
  }, [size, particleCount, speed, uniforms]);

  return (
    <div
      ref={containerRef}
      className={className}
      style={{
        width: size,
        height: size,
        cursor: "crosshair",
        ...style,
      }}
    />
  );
}
