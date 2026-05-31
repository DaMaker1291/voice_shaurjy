"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";

interface Props {
  listening?: boolean;
  speaking?: boolean;
  onClick?: () => void;
}

export default function HolographicNeuron({ listening, speaking, onClick }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const w = container.clientWidth;
    const h = container.clientHeight;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(60, w / h, 0.1, 100);
    camera.position.z = 12;

    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    renderer.setSize(w, h);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);

    // ── Neural network nodes ──────────────────────────────────
    const nodeCount = 120;
    const nodes: THREE.Mesh[] = [];
    const nodePositions: THREE.Vector3[] = [];
    const nodeData: { phase: number; speed: number }[] = [];

    const sphereGeo = new THREE.SphereGeometry(0.08, 8, 8);
    const glowGeo = new THREE.SphereGeometry(0.15, 8, 8);

    for (let i = 0; i < nodeCount; i++) {
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      const r = 2 + Math.random() * 4;
      const pos = new THREE.Vector3(
        r * Math.sin(phi) * Math.cos(theta),
        r * Math.sin(phi) * Math.sin(theta),
        r * Math.cos(phi)
      );

      const mat = new THREE.MeshBasicMaterial({
        color: new THREE.Color().setHSL(0.75 + Math.random() * 0.1, 0.8, 0.5 + Math.random() * 0.3),
        transparent: true,
        opacity: 0.6 + Math.random() * 0.4,
      });
      const mesh = new THREE.Mesh(sphereGeo, mat);
      mesh.position.copy(pos);
      scene.add(mesh);
      nodes.push(mesh);
      nodePositions.push(pos);
      nodeData.push({ phase: Math.random() * Math.PI * 2, speed: 0.3 + Math.random() * 0.7 });

      // Glow
      const glowMat = new THREE.MeshBasicMaterial({
        color: new THREE.Color().setHSL(0.75, 0.9, 0.4),
        transparent: true,
        opacity: 0.15,
      });
      const glow = new THREE.Mesh(glowGeo, glowMat);
      glow.position.copy(pos);
      scene.add(glow);
    }

    // ── Connections ───────────────────────────────────────────
    const connectionPairs: { a: number; b: number; line: THREE.Line }[] = [];
    const connectionMat = new THREE.LineBasicMaterial({
      color: 0x8855dd,
      transparent: true,
      opacity: 0.08,
    });

    for (let i = 0; i < nodeCount; i++) {
      for (let j = i + 1; j < nodeCount; j++) {
        const dist = nodePositions[i].distanceTo(nodePositions[j]);
        if (dist < 2.5 && Math.random() < 0.15) {
          const geo = new THREE.BufferGeometry().setFromPoints([
            nodePositions[i],
            nodePositions[j],
          ]);
          const line = new THREE.Line(geo, connectionMat.clone());
          scene.add(line);
          connectionPairs.push({ a: i, b: j, line });
        }
      }
    }

    // ── Floating particles ────────────────────────────────────
    const particleCount = 600;
    const particleGeo = new THREE.BufferGeometry();
    const positions = new Float32Array(particleCount * 3);
    const particleSizes = new Float32Array(particleCount);
    for (let i = 0; i < particleCount; i++) {
      positions[i * 3] = (Math.random() - 0.5) * 20;
      positions[i * 3 + 1] = (Math.random() - 0.5) * 20;
      positions[i * 3 + 2] = (Math.random() - 0.5) * 20;
      particleSizes[i] = 0.01 + Math.random() * 0.03;
    }
    particleGeo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    particleGeo.setAttribute("size", new THREE.BufferAttribute(particleSizes, 1));

    const particleMat = new THREE.PointsMaterial({
      color: 0x9966ff,
      size: 0.035,
      transparent: true,
      opacity: 0.3,
      blending: THREE.AdditiveBlending,
    });
    const particles = new THREE.Points(particleGeo, particleMat);
    scene.add(particles);

    // ── Ring ──────────────────────────────────────────────────
    const ringGeo = new THREE.RingGeometry(3.8, 4.0, 64);
    const ringMat = new THREE.MeshBasicMaterial({
      color: 0x7744cc,
      transparent: true,
      opacity: 0.12,
      side: THREE.DoubleSide,
    });
    const ring = new THREE.Mesh(ringGeo, ringMat);
    ring.rotation.x = Math.PI / 3;
    ring.rotation.z = 0.2;
    scene.add(ring);

    const ring2 = new THREE.Mesh(
      new THREE.RingGeometry(4.2, 4.3, 64),
      new THREE.MeshBasicMaterial({ color: 0x9955ee, transparent: true, opacity: 0.06, side: THREE.DoubleSide })
    );
    ring2.rotation.x = -Math.PI / 4;
    ring2.rotation.z = 0.5;
    scene.add(ring2);

    // ── Center glow ───────────────────────────────────────────
    const centerGlow = new THREE.Mesh(
      new THREE.SphereGeometry(0.4, 16, 16),
      new THREE.MeshBasicMaterial({ color: 0x7733dd, transparent: true, opacity: 0.2 })
    );
    scene.add(centerGlow);

    // ── Animation ─────────────────────────────────────────────
    let time = 0;
    let pulseTarget = 0;
    let pulse = 0;
    let currentPulse = 0;

    const animate = () => {
      requestAnimationFrame(animate);
      time += 0.003;

      // Read pulse from container CSS variable
      const pulseVal = parseFloat(container.style.getPropertyValue("--pulse")) || 0;
      pulseTarget = pulseVal;
      pulse += (pulseTarget - pulse) * 0.08;
      currentPulse = pulse;

      // Pulse nodes
      nodes.forEach((mesh, i) => {
        const d = nodeData[i];
        const offset = Math.sin(time * d.speed + d.phase) * 0.15;
        const base = 1;
        mesh.scale.setScalar(base + offset + pulse * 0.3);
        (mesh.material as THREE.MeshBasicMaterial).opacity = 0.5 + offset * 0.8 + pulse * 0.4;
      });

      // Pulse connections
      connectionPairs.forEach(({ line }) => {
        (line.material as THREE.LineBasicMaterial).opacity = 0.04 + pulse * 0.15;
      });

      // Rotate network
      nodes.forEach((mesh, i) => {
        mesh.position.copy(nodePositions[i]);
        mesh.position.applyAxisAngle(new THREE.Vector3(0, 1, 0), time * 0.1);
        mesh.position.applyAxisAngle(new THREE.Vector3(1, 0, 0), time * 0.05);
      });
      connectionPairs.forEach(({ a, b, line }) => {
        const pa = nodes[a].position;
        const pb = nodes[b].position;
        line.geometry.dispose();
        line.geometry = new THREE.BufferGeometry().setFromPoints([pa, pb]);
      });

      // Rotate particles
      particles.rotation.y = time * 0.02;
      particles.rotation.x = time * 0.01;

      // Rotate rings
      ring.rotation.z += 0.002;
      ring2.rotation.x += 0.001;

      // Center glow pulse
      centerGlow.scale.setScalar(1 + Math.sin(time * 2) * 0.2 + pulse * 0.5);
      (centerGlow.material as THREE.MeshBasicMaterial).opacity = 0.15 + Math.sin(time * 2) * 0.08 + pulse * 0.2;

      // Camera sway
      camera.position.x = Math.sin(time * 0.05) * 0.5;
      camera.position.y = Math.cos(time * 0.07) * 0.3;
      camera.lookAt(0, 0, 0);

      renderer.render(scene, camera);
    };

    animate();

    // ── Resize ────────────────────────────────────────────────
    const resize = () => {
      const w2 = container.clientWidth;
      const h2 = container.clientHeight;
      renderer.setSize(w2, h2);
      camera.aspect = w2 / h2;
      camera.updateProjectionMatrix();
    };
    window.addEventListener("resize", resize);

    return () => {
      window.removeEventListener("resize", resize);
      container.removeChild(renderer.domElement);
      renderer.dispose();
    };
  }, []);

  // ── Pulse on state change ───────────────────────────────────
  useEffect(() => {
    if (listening || speaking) {
      // Trigger pulse via CSS variable hack — the Three.js scene reads it
      containerRef.current?.style.setProperty("--pulse", listening ? "1" : "0.5");
    }
  }, [listening, speaking]);

  return (
    <div
      ref={containerRef}
      onClick={onClick}
      className="relative w-72 h-72 cursor-pointer group"
      style={{ filter: "drop-shadow(0 0 40px rgba(120, 60, 220, 0.3))" }}
    >
      {/* Holographic ring overlay */}
      <div className="absolute inset-0 rounded-full pointer-events-none"
        style={{
          background: "radial-gradient(circle, transparent 40%, rgba(120, 60, 220, 0.08) 60%, transparent 70%)",
          animation: "spin-slow 8s linear infinite",
        }}
      />
      {/* Label */}
      <div className="absolute bottom-0 left-1/2 -translate-x-1/2 text-center pointer-events-none">
        <p className="text-[10px] font-mono text-purple-400/50 tracking-[0.3em] uppercase">
          {listening ? "listening" : speaking ? "processing" : "idle"}
        </p>
      </div>
    </div>
  );
}
