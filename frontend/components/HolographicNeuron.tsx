"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";

interface Props {
  listening?: boolean;
  speaking?: boolean;
  thinking?: boolean;
  onClick?: () => void;
}

const LAYERS = [6, 10, 12, 8, 4]; // neurons per layer: input -> hidden1 -> hidden2 -> hidden3 -> output

export default function HolographicNeuron({ listening, thinking, speaking, onClick }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const w = container.clientWidth;
    const h = container.clientHeight;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(50, w / h, 0.1, 100);
    camera.position.z = 14;

    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    renderer.setSize(w, h);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);

    // ── Build neural network layers ──────────────────────────
    const allNodes: { mesh: THREE.Mesh; glow: THREE.Mesh; basePos: THREE.Vector3 }[] = [];
    const connections: { line: THREE.Line; opacity: number }[] = [];
    const signals: { start: number; end: number; progress: number; speed: number; mesh: THREE.Mesh }[] = [];

    const layerSpacing = 3.2;
    const maxNeurons = Math.max(...LAYERS);
    const startX = -((LAYERS.length - 1) * layerSpacing) / 2;

    LAYERS.forEach((numNeurons, layerIdx) => {
      const x = startX + layerIdx * layerSpacing;
      const verticalSpacing = 1.8;
      const startY = -((numNeurons - 1) * verticalSpacing) / 2;

      for (let n = 0; n < numNeurons; n++) {
        const y = startY + n * verticalSpacing;
        const z = (Math.random() - 0.5) * 1.5;
        const pos = new THREE.Vector3(x, y, z);

        // Neuron sphere
        const size = 0.15 + Math.random() * 0.08;
        const hue = 0.72 + (layerIdx / LAYERS.length) * 0.12;
        const color = new THREE.Color().setHSL(hue, 0.8, 0.5 + Math.random() * 0.2);
        const mat = new THREE.MeshBasicMaterial({
          color,
          transparent: true,
          opacity: 0.7,
        });
        const mesh = new THREE.Mesh(new THREE.SphereGeometry(size, 12, 12), mat);
        mesh.position.copy(pos);
        scene.add(mesh);

        // Glow
        const glowMat = new THREE.MeshBasicMaterial({
          color: new THREE.Color().setHSL(hue, 0.9, 0.3),
          transparent: true,
          opacity: 0.12,
        });
        const glow = new THREE.Mesh(new THREE.SphereGeometry(size * 2.2, 8, 8), glowMat);
        glow.position.copy(pos);
        scene.add(glow);

        allNodes.push({ mesh, glow, basePos: pos.clone() });
      }
    });

    // ── Connect layers ───────────────────────────────────────
    for (let l = 0; l < LAYERS.length - 1; l++) {
      const layerStart = LAYERS.slice(0, l).reduce((a, b) => a + b, 0);
      const layerEnd = LAYERS.slice(0, l + 1).reduce((a, b) => a + b, 0);
      const nextStart = LAYERS.slice(0, l + 1).reduce((a, b) => a + b, 0);
      const nextEnd = LAYERS.slice(0, l + 2).reduce((a, b) => a + b, 0);

      // Connect each neuron in this layer to a subset in the next
      for (let i = layerStart; i < layerEnd; i++) {
        const from = allNodes[i];
        const targets = [];
        for (let j = nextStart; j < nextEnd; j++) {
          if (Math.random() < 0.35) {
            targets.push(j);
          }
        }
        // Ensure at least 1 connection
        if (targets.length === 0) {
          targets.push(nextStart + Math.floor(Math.random() * (nextEnd - nextStart)));
        }
        for (const j of targets) {
          const to = allNodes[j];
          const points = [];
          points.push(from.basePos.clone());
          // Curved connection
          const mid = from.basePos.clone().lerp(to.basePos, 0.5);
          mid.y += 0.3 + Math.random() * 0.6;
          points.push(mid);
          points.push(to.basePos.clone());
          const curve = new THREE.QuadraticBezierCurve3(from.basePos, mid, to.basePos);
          const curvePoints = curve.getPoints(12);
          const geo = new THREE.BufferGeometry().setFromPoints(curvePoints);
          const opacity = 0.03 + Math.random() * 0.07;
          const line = new THREE.Line(
            geo,
            new THREE.LineBasicMaterial({
              color: new THREE.Color().setHSL(0.74, 0.7, 0.4 + Math.random() * 0.2),
              transparent: true,
              opacity,
            })
          );
          scene.add(line);
          connections.push({ line, opacity });
        }
      }
    }

    // ── Floating particles ────────────────────────────────────
    const particleCount = 400;
    const particleGeo = new THREE.BufferGeometry();
    const positions = new Float32Array(particleCount * 3);
    const sizes = new Float32Array(particleCount);
    for (let i = 0; i < particleCount; i++) {
      positions[i * 3] = (Math.random() - 0.5) * 18;
      positions[i * 3 + 1] = (Math.random() - 0.5) * 14;
      positions[i * 3 + 2] = (Math.random() - 0.5) * 8 - 2;
      sizes[i] = 0.01 + Math.random() * 0.03;
    }
    particleGeo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    const particleMat = new THREE.PointsMaterial({
      color: 0x8855dd,
      size: 0.025,
      transparent: true,
      opacity: 0.2,
      blending: THREE.AdditiveBlending,
    });
    const particles = new THREE.Points(particleGeo, particleMat);
    scene.add(particles);

    // ── Label layers ──────────────────────────────────────────
    const layerLabels = ["INPUT", "HIDDEN 1", "HIDDEN 2", "HIDDEN 3", "OUTPUT"];
    // Use sprites for labels
    layerLabels.forEach((label, i) => {
      const canvas = document.createElement("canvas");
      canvas.width = 128;
      canvas.height = 32;
      const ctx = canvas.getContext("2d")!;
      ctx.fillStyle = "rgba(120,60,220,0.3)";
      ctx.font = "10px monospace";
      ctx.textAlign = "center";
      ctx.fillText(label, 64, 18);
      const texture = new THREE.CanvasTexture(canvas);
      const spriteMat = new THREE.SpriteMaterial({ map: texture, transparent: true, opacity: 0.4 });
      const sprite = new THREE.Sprite(spriteMat);
      sprite.position.set(startX + i * layerSpacing, -4.5, 0);
      sprite.scale.set(2, 0.5, 1);
      scene.add(sprite);
    });

    // ── Signal propagation ────────────────────────────────────
    function fireSignal() {
      const fromLayer = Math.floor(Math.random() * (LAYERS.length - 1));
      const layerStart = LAYERS.slice(0, fromLayer).reduce((a, b) => a + b, 0);
      const layerEnd = LAYERS.slice(0, fromLayer + 1).reduce((a, b) => a + b, 0);
      const nextStart = LAYERS.slice(0, fromLayer + 1).reduce((a, b) => a + b, 0);
      const nextEnd = LAYERS.slice(0, fromLayer + 2).reduce((a, b) => a + b, 0);

      const from = allNodes[layerStart + Math.floor(Math.random() * (layerEnd - layerStart))];
      const to = allNodes[nextStart + Math.floor(Math.random() * (nextEnd - nextStart))];

      const sigMat = new THREE.MeshBasicMaterial({
        color: 0xcc88ff,
        transparent: true,
        opacity: 0.8,
      });
      const sigMesh = new THREE.Mesh(new THREE.SphereGeometry(0.06, 6, 6), sigMat);
      scene.add(sigMesh);
      signals.push({
        start: 0,
        end: 1,
        progress: 0,
        speed: 0.02 + Math.random() * 0.03,
        mesh: sigMesh,
      });
      // Store from/to positions on the object
      (sigMesh as any)._fromPos = from.basePos.clone();
      (sigMesh as any)._toPos = to.basePos.clone();
    }

    // Fire initial signals
    for (let i = 0; i < 8; i++) {
      setTimeout(() => fireSignal(), i * 400);
    }

    // ── Rings ─────────────────────────────────────────────────
    const rings: THREE.Mesh[] = [];
    for (let i = 0; i < 2; i++) {
      const r = new THREE.Mesh(
        new THREE.RingGeometry(4.5 + i * 0.5, 4.7 + i * 0.5, 48),
        new THREE.MeshBasicMaterial({
          color: 0x6633cc,
          transparent: true,
          opacity: 0.06 + i * 0.03,
          side: THREE.DoubleSide,
        })
      );
      r.rotation.x = Math.PI / 3 + i * 0.3;
      r.rotation.z = i * 0.5;
      scene.add(r);
      rings.push(r);
    }

    // ── Animation ─────────────────────────────────────────────
    let time = 0;
    let pulseState = 0;

    const animate = () => {
      requestAnimationFrame(animate);
      time += 0.005;

      // Read pulse
      const pulseVal = parseFloat(container.style.getPropertyValue("--pulse") || "0");
      pulseState += (pulseVal - pulseState) * 0.06;

      // Animate nodes (gentle floating)
      allNodes.forEach((node, i) => {
        const offset = Math.sin(time * 0.5 + i * 0.3) * 0.04;
        const pulseOffset = pulseState * 0.15;
        node.mesh.position.y = node.basePos.y + offset + pulseOffset;
        node.mesh.position.x = node.basePos.x + Math.sin(time * 0.3 + i * 0.5) * 0.03;
        (node.mesh.material as THREE.MeshBasicMaterial).opacity = 0.5 + offset * 2 + pulseState * 0.3;
        node.glow.position.copy(node.mesh.position);
        node.glow.scale.setScalar(1 + pulseState * 0.3);
      });

      // Animate connections
      connections.forEach((conn) => {
        (conn.line.material as THREE.LineBasicMaterial).opacity = conn.opacity + pulseState * 0.08;
      });

      // Animate signals
      for (let i = signals.length - 1; i >= 0; i--) {
        const sig = signals[i];
        sig.progress += sig.speed;
        if (sig.progress >= 1) {
          scene.remove(sig.mesh);
          signals.splice(i, 1);
          continue;
        }
        const from = (sig.mesh as any)._fromPos as THREE.Vector3;
        const to = (sig.mesh as any)._toPos as THREE.Vector3;
        const mid = from.clone().lerp(to, 0.5);
        mid.y += 0.5;
        const t = sig.progress;
        const x = (1 - t) * (1 - t) * from.x + 2 * (1 - t) * t * mid.x + t * t * to.x;
        const y = (1 - t) * (1 - t) * from.y + 2 * (1 - t) * t * mid.y + t * t * to.y;
        const z = (1 - t) * (1 - t) * from.z + 2 * (1 - t) * t * mid.z + t * t * to.z;
        sig.mesh.position.set(x, y, z);
        (sig.mesh.material as THREE.MeshBasicMaterial).opacity = Math.sin(sig.progress * Math.PI) * 0.8;
      }

      // Spawn new signals periodically
      if (Math.random() < 0.03 || pulseState > 0.3) {
        fireSignal();
      }

      // Rotate rings
      rings.forEach((r, i) => {
        r.rotation.z += 0.003 * (i + 1);
        r.rotation.x += 0.001 * (i + 1);
      });

      // Particles
      particles.rotation.y = time * 0.02;
      particles.rotation.x = time * 0.01;

      // Camera sway
      camera.position.x = Math.sin(time * 0.04) * 0.4;
      camera.position.y = Math.cos(time * 0.06) * 0.3;
      camera.lookAt(0, 0, 0);

      renderer.render(scene, camera);
    };

    animate();

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
    const pulse = listening ? "1" : thinking ? "0.7" : speaking ? "0.4" : "0";
    containerRef.current?.style.setProperty("--pulse", pulse);
  }, [listening, speaking, thinking]);

  const label = listening ? "listening" : thinking ? "thinking" : speaking ? "speaking" : "standby";
  const labelColor = listening ? "rgba(34,197,94,0.5)" : thinking ? "rgba(168,85,247,0.5)" : speaking ? "rgba(6,182,212,0.5)" : "rgba(168,85,247,0.3)";

  return (
    <div
      ref={containerRef}
      onClick={onClick}
      className="relative w-80 h-80 cursor-pointer group"
      style={{ filter: "drop-shadow(0 0 60px rgba(120, 60, 220, 0.25))" }}
    >
      <div
        className="absolute inset-0 rounded-full pointer-events-none"
        style={{
          background: "radial-gradient(circle, transparent 35%, rgba(120, 60, 220, 0.06) 55%, transparent 70%)",
          animation: "spin-slow 10s linear infinite",
        }}
      />
      <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 text-center pointer-events-none">
        <p className="text-[9px] font-mono tracking-[0.3em] uppercase" style={{ color: labelColor }}>
          {label}
        </p>
      </div>
    </div>
  );
}
