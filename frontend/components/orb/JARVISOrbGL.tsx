"use client";

import React, { useRef, useEffect, useCallback, useState, useMemo } from "react";
import * as THREE from "three";
import { orbVertexShader, orbFragmentShader } from "./shaders/orb";
import {
  nodeVertexShader,
  nodeFragmentShader,
  synapseVertexShader,
  synapseFragmentShader,
} from "./shaders/neural";

type OrbState =
  | "idle"
  | "listening"
  | "planning"
  | "working"
  | "waiting"
  | "needs_approval"
  | "error"
  | "recovering"
  | "complete";

interface OrbProps {
  state?: OrbState;
  size?: number;
  progress?: number;
  mission?: string;
  agentCount?: number;
  toolActive?: boolean;
  onClick?: () => void;
  onContextMenu?: (e: React.MouseEvent) => void;
  showLabel?: boolean;
  interactive?: boolean;
}

interface AgentNode {
  position: THREE.Vector3;
  velocity: THREE.Vector3;
  activity: number;
  color: THREE.Color;
  size: number;
}

const STATE_COLORS: Record<OrbState, { primary: string; alt: string }> = {
  idle: { primary: "#00FF66", alt: "#00CC55" },
  listening: { primary: "#00FF66", alt: "#33FFaa" },
  planning: { primary: "#00B4D8", alt: "#0090B0" },
  working: { primary: "#00FF66", alt: "#00DDFF" },
  waiting: { primary: "#FFB300", alt: "#CC9000" },
  needs_approval: { primary: "#EF4444", alt: "#FF6666" },
  error: { primary: "#EF4444", alt: "#CC0000" },
  recovering: { primary: "#FFB300", alt: "#FFD060" },
  complete: { primary: "#00FF66", alt: "#88FFBB" },
};

const STATE_BEHAVIORS: Record<
  OrbState,
  {
    breathe: number;
    glow: number;
    speed: number;
    errorAmount: number;
    recoveryAmount: number;
  }
> = {
  idle: { breathe: 1.0, glow: 0.4, speed: 0.3, errorAmount: 0, recoveryAmount: 0 },
  listening: { breathe: 1.5, glow: 0.7, speed: 0.8, errorAmount: 0, recoveryAmount: 0 },
  planning: { breathe: 1.2, glow: 0.6, speed: 0.6, errorAmount: 0, recoveryAmount: 0 },
  working: { breathe: 0.8, glow: 0.8, speed: 1.2, errorAmount: 0, recoveryAmount: 0 },
  waiting: { breathe: 0.6, glow: 0.3, speed: 0.15, errorAmount: 0, recoveryAmount: 0 },
  needs_approval: { breathe: 2.0, glow: 1.0, speed: 1.5, errorAmount: 0, recoveryAmount: 0 },
  error: { breathe: 2.5, glow: 0.9, speed: 2.0, errorAmount: 1.0, recoveryAmount: 0 },
  recovering: { breathe: 1.5, glow: 0.6, speed: 1.0, errorAmount: 0.3, recoveryAmount: 1.0 },
  complete: { breathe: 0.5, glow: 1.0, speed: 0.4, errorAmount: 0, recoveryAmount: 0 },
};

function hexToRGB(hex: string): THREE.Color {
  return new THREE.Color(hex);
}

export default function JARVISOrbGL({
  state = "idle",
  size = 64,
  progress = 0,
  mission = "",
  agentCount = 0,
  toolActive = false,
  onClick,
  onContextMenu,
  showLabel = false,
  interactive = true,
}: OrbProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const orbMaterialRef = useRef<THREE.ShaderMaterial | null>(null);
  const nodesRef = useRef<AgentNode[]>([]);
  const nodePointsRef = useRef<THREE.Points | null>(null);
  const synapsesRef = useRef<THREE.LineSegments | null>(null);
  const clockRef = useRef(new THREE.Clock());
  const animRef = useRef<number>(0);
  const [hovered, setHovered] = useState(false);
  const prevAgentCountRef = useRef(0);

  const behavior = useMemo(() => STATE_BEHAVIORS[state], [state]);
  const colors = useMemo(() => STATE_COLORS[state], [state]);

  // Initialize Three.js scene
  useEffect(() => {
    if (!containerRef.current) return;

    const container = containerRef.current;
    const w = size;
    const h = size;

    // Renderer
    const renderer = new THREE.WebGLRenderer({
      alpha: true,
      antialias: true,
      powerPreference: "high-performance",
    });
    renderer.setSize(w, h);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor(0x000000, 0);
    container.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // Scene
    const scene = new THREE.Scene();
    sceneRef.current = scene;

    // Camera
    const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
    camera.position.z = 3;
    cameraRef.current = camera;

    // Orb geometry (icosahedron for smooth sphere)
    const orbGeo = new THREE.IcosahedronGeometry(1, 6);

    // Orb shader material
    const orbMat = new THREE.ShaderMaterial({
      vertexShader: orbVertexShader,
      fragmentShader: orbFragmentShader,
      uniforms: {
        uTime: { value: 0 },
        uBreathe: { value: 1.0 },
        uGlowIntensity: { value: 0.4 },
        uColor: { value: hexToRGB("#00FF66") },
        uColorAlt: { value: hexToRGB("#00CC55") },
        uErrorAmount: { value: 0 },
        uRecoveryAmount: { value: 0 },
        uCompletionPulse: { value: 0 },
      },
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      side: THREE.DoubleSide,
    });
    orbMaterialRef.current = orbMat;

    const orbMesh = new THREE.Mesh(orbGeo, orbMat);
    scene.add(orbMesh);

    // Inner glow sphere
    const glowGeo = new THREE.SphereGeometry(0.6, 32, 32);
    const glowMat = new THREE.ShaderMaterial({
      vertexShader: `
        varying vec3 vNormal;
        void main() {
          vNormal = normalize(normalMatrix * normal);
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
      `,
      fragmentShader: `
        varying vec3 vNormal;
        uniform vec3 uColor;
        uniform float uIntensity;
        void main() {
          float intensity = pow(0.7 - dot(vNormal, vec3(0.0, 0.0, 1.0)), 2.0);
          gl_FragColor = vec4(uColor, intensity * uIntensity);
        }
      `,
      uniforms: {
        uColor: { value: hexToRGB("#00FF66") },
        uIntensity: { value: 0.6 },
      },
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      side: THREE.BackSide,
    });
    const glowMesh = new THREE.Mesh(glowGeo, glowMat);
    glowMesh.scale.setScalar(1.4);
    scene.add(glowMesh);

    // Agent node points
    const nodeGeo = new THREE.BufferGeometry();
    const maxNodes = 64;
    const positions = new Float32Array(maxNodes * 3);
    const sizes = new Float32Array(maxNodes);
    const activities = new Float32Array(maxNodes);
    const nodeColors = new Float32Array(maxNodes * 3);

    nodeGeo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    nodeGeo.setAttribute("aSize", new THREE.BufferAttribute(sizes, 1));
    nodeGeo.setAttribute("aActivity", new THREE.BufferAttribute(activities, 1));
    nodeGeo.setAttribute("aColor", new THREE.BufferAttribute(nodeColors, 3));

    const nodeMat = new THREE.ShaderMaterial({
      vertexShader: nodeVertexShader,
      fragmentShader: nodeFragmentShader,
      uniforms: {
        uTime: { value: 0 },
      },
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });

    const nodePoints = new THREE.Points(nodeGeo, nodeMat);
    scene.add(nodePoints);
    nodePointsRef.current = nodePoints;

    // Synapse lines
    const synapseGeo = new THREE.BufferGeometry();
    const maxSynapses = maxNodes * 3;
    const synapsePositions = new Float32Array(maxSynapses * 6);
    const synapseActivities = new Float32Array(maxSynapses * 2);
    const synapseAlphas = new Float32Array(maxSynapses * 2);

    synapseGeo.setAttribute("position", new THREE.BufferAttribute(synapsePositions, 3));
    synapseGeo.setAttribute("aActivity", new THREE.BufferAttribute(synapseActivities, 1));
    synapseGeo.setAttribute("aAlpha", new THREE.BufferAttribute(synapseAlphas, 1));

    const synapseMat = new THREE.ShaderMaterial({
      vertexShader: synapseVertexShader,
      fragmentShader: synapseFragmentShader,
      uniforms: {
        uTime: { value: 0 },
        uColor: { value: hexToRGB("#00FF66") },
      },
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });

    const synapses = new THREE.LineSegments(synapseGeo, synapseMat);
    scene.add(synapses);
    synapsesRef.current = synapses;

    return () => {
      cancelAnimationFrame(animRef.current);
      renderer.dispose();
      orbGeo.dispose();
      orbMat.dispose();
      glowGeo.dispose();
      glowMat.dispose();
      nodeGeo.dispose();
      nodeMat.dispose();
      synapseGeo.dispose();
      synapseMat.dispose();
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
    };
  }, [size]);

  // Spawn/despawn agent nodes
  useEffect(() => {
    const nodes = nodesRef.current;
    const targetCount = Math.min(agentCount, 64);

    // Spawn new nodes
    while (nodes.length < targetCount) {
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      const r = 0.5 + Math.random() * 0.5;

      nodes.push({
        position: new THREE.Vector3(
          r * Math.sin(phi) * Math.cos(theta),
          r * Math.sin(phi) * Math.sin(theta),
          r * Math.cos(phi)
        ),
        velocity: new THREE.Vector3(
          (Math.random() - 0.5) * 0.01,
          (Math.random() - 0.5) * 0.01,
          (Math.random() - 0.5) * 0.01
        ),
        activity: 0.3 + Math.random() * 0.7,
        color: new THREE.Color().setHSL(0.35 + Math.random() * 0.15, 0.8, 0.6),
        size: 3 + Math.random() * 5,
      });
    }

    // Remove excess nodes
    while (nodes.length > targetCount) {
      nodes.pop();
    }

    prevAgentCountRef.current = agentCount;
  }, [agentCount]);

  // Animation loop
  useEffect(() => {
    const animate = () => {
      const renderer = rendererRef.current;
      const scene = sceneRef.current;
      const camera = cameraRef.current;
      const orbMat = orbMaterialRef.current;
      const nodePoints = nodePointsRef.current;
      const synapses = synapsesRef.current;

      if (!renderer || !scene || !camera || !orbMat) {
        animRef.current = requestAnimationFrame(animate);
        return;
      }

      const elapsed = clockRef.current.getElapsedTime();

      // Update orb material uniforms
      orbMat.uniforms.uTime.value = elapsed;
      orbMat.uniforms.uBreathe.value = behavior.breathe;
      orbMat.uniforms.uGlowIntensity.value = behavior.glow;
      orbMat.uniforms.uColor.value = hexToRGB(colors.primary);
      orbMat.uniforms.uColorAlt.value = hexToRGB(colors.alt);
      orbMat.uniforms.uErrorAmount.value = behavior.errorAmount;

      // Recovery amount transitions smoothly
      const targetRecovery = behavior.recoveryAmount;
      orbMat.uniforms.uRecoveryAmount.value +=
        (targetRecovery - orbMat.uniforms.uRecoveryAmount.value) * 0.05;

      // Completion pulse
      if (state === "complete") {
        orbMat.uniforms.uCompletionPulse.value =
          Math.min(orbMat.uniforms.uCompletionPulse.value + 0.02, 1.0);
      } else {
        orbMat.uniforms.uCompletionPulse.value *= 0.95;
      }

      // Update inner glow
      const glowMesh = scene.children[1] as THREE.Mesh<THREE.SphereGeometry, THREE.ShaderMaterial>;
      if (glowMesh?.material?.uniforms) {
        glowMesh.material.uniforms.uColor.value = hexToRGB(colors.primary);
        glowMesh.material.uniforms.uIntensity.value = behavior.glow;
      }

      // Update agent nodes
      if (nodePoints) {
        const geo = nodePoints.geometry;
        const posAttr = geo.getAttribute("position") as THREE.BufferAttribute;
        const sizeAttr = geo.getAttribute("aSize") as THREE.BufferAttribute;
        const actAttr = geo.getAttribute("aActivity") as THREE.BufferAttribute;
        const colorAttr = geo.getAttribute("aColor") as THREE.BufferAttribute;
        const nodeMat = nodePoints.material as THREE.ShaderMaterial;
        nodeMat.uniforms.uTime.value = elapsed;

        const nodes = nodesRef.current;
        for (let i = 0; i < nodes.length; i++) {
          const node = nodes[i];

          // Orbital motion
          node.position.add(node.velocity);

          // Gently pull toward orbital shell
          const dist = node.position.length();
          const targetDist = 0.7;
          const pull = (targetDist - dist) * 0.02;
          node.position.normalize().multiplyScalar(dist + pull);

          // Add subtle turbulence
          node.velocity.x += (Math.random() - 0.5) * 0.001;
          node.velocity.y += (Math.random() - 0.5) * 0.001;
          node.velocity.z += (Math.random() - 0.5) * 0.001;
          node.velocity.multiplyScalar(0.98);

          // Tool activity pulse
          if (toolActive) {
            node.activity = Math.min(1.0, node.activity + 0.05);
          } else {
            node.activity = Math.max(0.3, node.activity - 0.02);
          }

          posAttr.setXYZ(i, node.position.x, node.position.y, node.position.z);
          sizeAttr.setX(i, node.size * (0.8 + Math.sin(elapsed * 2 + i) * 0.2));
          actAttr.setX(i, node.activity);
          colorAttr.setXYZ(i, node.color.r, node.color.g, node.color.b);
        }

        posAttr.needsUpdate = true;
        sizeAttr.needsUpdate = true;
        actAttr.needsUpdate = true;
        colorAttr.needsUpdate = true;
        geo.setDrawRange(0, nodes.length);
      }

      // Update synapses
      if (synapses) {
        const geo = synapses.geometry;
        const posAttr = geo.getAttribute("position") as THREE.BufferAttribute;
        const actAttr = geo.getAttribute("aActivity") as THREE.BufferAttribute;
        const alphaAttr = geo.getAttribute("aAlpha") as THREE.BufferAttribute;
        const synMat = synapses.material as THREE.ShaderMaterial;
        synMat.uniforms.uTime.value = elapsed;
        synMat.uniforms.uColor.value = hexToRGB(colors.primary);

        const nodes = nodesRef.current;
        let lineIdx = 0;
        const maxLines = posAttr.count / 2;

        // Connect nearby nodes
        for (let i = 0; i < nodes.length && lineIdx < maxLines; i++) {
          for (let j = i + 1; j < nodes.length && lineIdx < maxLines; j++) {
            const dist = nodes[i].position.distanceTo(nodes[j].position);
            if (dist < 1.2) {
              const alpha = (1.0 - dist / 1.2) * 0.5;
              const activity = (nodes[i].activity + nodes[j].activity) * 0.5;

              posAttr.setXYZ(lineIdx * 2, nodes[i].position.x, nodes[i].position.y, nodes[i].position.z);
              posAttr.setXYZ(lineIdx * 2 + 1, nodes[j].position.x, nodes[j].position.y, nodes[j].position.z);
              actAttr.setX(lineIdx * 2, activity);
              actAttr.setX(lineIdx * 2 + 1, activity);
              alphaAttr.setX(lineIdx * 2, alpha);
              alphaAttr.setX(lineIdx * 2 + 1, alpha);

              lineIdx++;
            }
          }
        }

        posAttr.needsUpdate = true;
        actAttr.needsUpdate = true;
        alphaAttr.needsUpdate = true;
        geo.setDrawRange(0, lineIdx * 2);
      }

      // Subtle rotation
      const orbMesh = scene.children[0] as THREE.Mesh;
      if (orbMesh) {
        orbMesh.rotation.y = elapsed * 0.1 * behavior.speed;
        orbMesh.rotation.x = Math.sin(elapsed * 0.15) * 0.1;
      }

      renderer.render(scene, camera);
      animRef.current = requestAnimationFrame(animate);
    };

    animRef.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(animRef.current);
  }, [behavior, colors, state, toolActive]);

  const stateLabels: Record<OrbState, string> = {
    idle: "Available",
    listening: "Listening",
    planning: "Planning",
    working: "Working",
    waiting: "Waiting",
    needs_approval: "YOUR APPROVAL",
    error: "Error",
    recovering: "Recovering",
    complete: "Complete",
  };

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 6,
        cursor: interactive ? "pointer" : "default",
      }}
      onClick={onClick}
      onContextMenu={onContextMenu}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <div
        style={{
          width: size,
          height: size,
          position: "relative",
          transform: hovered && interactive ? "scale(1.1)" : "scale(1)",
          transition: "transform 0.2s ease",
        }}
      >
        <div ref={containerRef} style={{ width: size, height: size }} />
        {(state === "needs_approval" || state === "error") && (
          <div
            style={{
              position: "absolute",
              inset: -4,
              borderRadius: "50%",
              border: `2px solid ${state === "needs_approval" ? "#EF444460" : "#EF444480"}`,
              animation: "pulse-border 1.5s ease-in-out infinite",
              pointerEvents: "none",
            }}
          />
        )}
      </div>
      {showLabel && (
        <div
          style={{
            fontSize: 9,
            fontFamily: "'JetBrains Mono', 'SF Mono', monospace",
            color: colors.primary,
            letterSpacing: "0.1em",
            textAlign: "center",
            lineHeight: 1.3,
            opacity: 0.9,
          }}
        >
          JARVIS
          <br />
          {stateLabels[state]}
          {state === "working" && progress > 0 && <br />}
          {state === "working" && progress > 0 && (
            <span style={{ fontSize: 8, opacity: 0.7 }}>{Math.round(progress)}%</span>
          )}
          {mission && state === "working" && (
            <span
              style={{
                fontSize: 7,
                opacity: 0.5,
                display: "block",
                maxWidth: size + 20,
              }}
            >
              {mission.length > 20 ? mission.slice(0, 20) + "…" : mission}
            </span>
          )}
          {agentCount > 0 && (
            <span style={{ fontSize: 7, opacity: 0.4, display: "block" }}>
              {agentCount} agent{agentCount !== 1 ? "s" : ""}
            </span>
          )}
        </div>
      )}
      <style>{`
        @keyframes pulse-border {
          0%, 100% { opacity: 0.4; transform: scale(1); }
          50% { opacity: 0.8; transform: scale(1.05); }
        }
      `}</style>
    </div>
  );
}
