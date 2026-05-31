"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";

interface SceneData {
  devices?: number;
  connections?: number;
  status?: string;
}

interface DeviceNode {
  mesh: THREE.Mesh;
  label: THREE.Sprite;
}

export default function NetworkSimulation({ data, progress }: { data?: SceneData; progress?: number }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const devCount = Math.max(3, data?.devices || 6);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const w = container.clientWidth || 400;
    const h = container.clientHeight || 400;
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(50, w / h, 0.1, 100);
    camera.position.z = 8;

    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    renderer.setSize(w, h);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);

    // ── Device nodes ────────────────────────────────────────
    const nodes: DeviceNode[] = [];
    const deviceNames = ["Router", "Desktop", "Laptop", "Server", "Phone", "Tablet", "Printer", "NAS", "Switch", "Camera", "TV", "Speaker"];
    const deviceIps = ["192.168.1.1", "192.168.1.2", "192.168.1.3", "192.168.1.4", "192.168.1.5", "192.168.1.6",
                       "192.168.1.7", "192.168.1.8", "192.168.1.9", "192.168.1.10", "192.168.1.11", "192.168.1.12"];

    for (let i = 0; i < Math.min(devCount, 12); i++) {
      const angle = (i / devCount) * Math.PI * 2 - Math.PI / 2;
      const radius = 2.5 + Math.random() * 0.5;
      const x = Math.cos(angle) * radius;
      const z = Math.sin(angle) * radius;
      const y = (Math.random() - 0.5) * 0.8;

      const isRouter = i === 0;
      const size = isRouter ? 0.35 : 0.18 + Math.random() * 0.08;
      const hue = isRouter ? 0.6 : 0.55 + Math.random() * 0.15;
      const color = new THREE.Color().setHSL(hue, 0.8, 0.5);

      const mat = new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.7 });
      const geo = isRouter ? new THREE.IcosahedronGeometry(size, 1) : new THREE.SphereGeometry(size, 10, 10);
      const mesh = new THREE.Mesh(geo, mat);
      mesh.position.set(x, y, z);
      scene.add(mesh);

      // Label
      const canvas = document.createElement("canvas");
      canvas.width = 128;
      canvas.height = 24;
      const ctx = canvas.getContext("2d")!;
      ctx.fillStyle = "rgba(0,0,0,0)";
      ctx.fillRect(0, 0, 128, 24);
      ctx.fillStyle = isRouter ? "#6688ff" : "#ffffff";
      ctx.font = "10px monospace";
      ctx.textAlign = "center";
      ctx.fillText(deviceNames[i] || `Device ${i+1}`, 64, 12);
      ctx.fillStyle = "rgba(255,255,255,0.3)";
      ctx.font = "7px monospace";
      ctx.fillText(deviceIps[i], 64, 22);
      const tex = new THREE.CanvasTexture(canvas);
      const spriteMat = new THREE.SpriteMaterial({ map: tex, transparent: true, opacity: 0.6, depthTest: false });
      const sprite = new THREE.Sprite(spriteMat);
      sprite.position.set(x, y - 0.5, z);
      sprite.scale.set(1.5, 0.3, 1);
      scene.add(sprite);

      nodes.push({ mesh, label: sprite });
    }

    // ── Connections ─────────────────────────────────────────
    const lines: THREE.Line[] = [];
    for (let i = 1; i < nodes.length; i++) {
      const from = nodes[0].mesh.position;
      const to = nodes[i].mesh.position;
      const pts = [from.clone(), to.clone()];
      const mat = new THREE.LineBasicMaterial({
        color: new THREE.Color().setHSL(0.65, 0.6, 0.3 + Math.random() * 0.2),
        transparent: true,
        opacity: 0.15 + Math.random() * 0.1,
      });
      const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), mat);
      scene.add(line);
      lines.push(line);
    }

    // ── Data packets ────────────────────────────────────────
    const packets: THREE.Mesh[] = [];
    for (let i = 0; i < 6; i++) {
      const pMat = new THREE.MeshBasicMaterial({ color: 0x44ddff, transparent: true, opacity: 0.6 });
      const p = new THREE.Mesh(new THREE.SphereGeometry(0.04, 6, 6), pMat);
      p.position.set(0, 0, 0);
      scene.add(p);
      packets.push(p);
    }

    // ── Center glow ─────────────────────────────────────────
    const glowMat = new THREE.MeshBasicMaterial({
      color: 0x4466aa,
      transparent: true,
      opacity: 0.06,
    });
    const glow = new THREE.Mesh(new THREE.SphereGeometry(0.8, 16, 16), glowMat);
    scene.add(glow);

    // ── Floating particles ──────────────────────────────────
    const pCount = 100;
    const pg = new THREE.BufferGeometry();
    const pp = new Float32Array(pCount * 3);
    for (let i = 0; i < pCount * 3; i++) pp[i] = (Math.random() - 0.5) * 10;
    pg.setAttribute("position", new THREE.BufferAttribute(pp, 3));
    const pm = new THREE.PointsMaterial({ color: 0x6688cc, size: 0.01, transparent: true, opacity: 0.1, blending: THREE.AdditiveBlending });
    const pts = new THREE.Points(pg, pm);
    scene.add(pts);

    // ── Animation ───────────────────────────────────────────
    let time = 0;
    let packetIdx = 0;

    const animate = () => {
      requestAnimationFrame(animate);
      time += 0.005;

      // Pulse nodes
      nodes.forEach((n, i) => {
        const s = 1 + Math.sin(time * 0.8 + i * 1.2) * 0.08;
        n.mesh.scale.setScalar(s);
        (n.mesh.material as THREE.MeshBasicMaterial).opacity = 0.5 + Math.sin(time + i) * 0.15;
      });

      // Pulse connections
      lines.forEach((l, i) => {
        (l.material as THREE.LineBasicMaterial).opacity = 0.1 + Math.sin(time * 0.5 + i * 0.7) * 0.1;
      });

      // Animate packets along random routes
      packets.forEach((p, i) => {
        const t = (time * 0.3 + i * 1.2) % nodes.length;
        const fromIdx = Math.floor(t);
        const toIdx = (fromIdx + 1) % nodes.length;
        const frac = t - fromIdx;
        const from = nodes[fromIdx % nodes.length]?.mesh.position || new THREE.Vector3();
        const to = nodes[toIdx % nodes.length]?.mesh.position || new THREE.Vector3();
        p.position.lerpVectors(from, to, frac);
        (p.material as THREE.MeshBasicMaterial).opacity = Math.sin(frac * Math.PI) * 0.6;
      });

      glow.rotation.x = time * 0.1;
      glow.rotation.z = time * 0.05;
      pts.rotation.y = time * 0.02;

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
  }, [devCount]);

  return (
    <div ref={containerRef} className="w-full h-full min-h-[300px]" />
  );
}
