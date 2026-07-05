"use client";

import { useRef, useEffect } from "react";

export default function KineticOrb({ size = 300 }: { size?: number }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const frameRef = useRef<number>(0);
  const mouseRef = useRef({ x: 0.5, y: 0.5, active: false });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = size * dpr;
    canvas.height = size * dpr;
    ctx.scale(dpr, dpr);

    const cx = size / 2;
    const cy = size / 2;
    const maxR = size * 0.44;

    // Geodesic vertices (inner wireframe sphere)
    const geoVertices: { x: number; y: number; z: number }[] = [];
    const geoEdges: [number, number][] = [];
    const icosahedron = (() => {
      const t = (1 + Math.sqrt(5)) / 2;
      return [
        [-1, t, 0], [1, t, 0], [-1, -t, 0], [1, -t, 0],
        [0, -1, t], [0, 1, t], [0, -1, -t], [0, 1, -t],
        [t, 0, -1], [t, 0, 1], [-t, 0, -1], [-t, 0, 1],
      ].map(v => {
        const l = Math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2);
        return { x: v[0] / l, y: v[1] / l, z: v[2] / l };
      });
    })();

    // Create geodesic subdivisions
    for (let i = 0; i < icosahedron.length; i++) {
      geoVertices.push(icosahedron[i]);
      for (let j = i + 1; j < icosahedron.length; j++) {
        const d = Math.sqrt(
          (icosahedron[i].x - icosahedron[j].x) ** 2 +
          (icosahedron[i].y - icosahedron[j].y) ** 2 +
          (icosahedron[i].z - icosahedron[j].z) ** 2
        );
        if (d < 1.2) geoEdges.push([i, j]);
      }
    }

    // Add midpoints for more detail
    const midVertices: { x: number; y: number; z: number }[] = [];
    for (const [a, b] of geoEdges.slice(0, 30)) {
      const va = geoVertices[a];
      const vb = geoVertices[b];
      const mx = (va.x + vb.x) / 2;
      const my = (va.y + vb.y) / 2;
      const mz = (va.z + vb.z) / 2;
      const l = Math.sqrt(mx ** 2 + my ** 2 + mz ** 2);
      midVertices.push({ x: mx / l, y: my / l, z: mz / l });
    }

    // Ring segments (middle tech ring)
    const ringSegments = 36;
    const ringRadius = maxR * 0.65;
    const ringWidth = 12;

    // Outer wave particles
    const waveParticles: {
      angle: number; radius: number; speed: number;
      size: number; phase: number; color: string;
    }[] = [];
    for (let i = 0; i < 200; i++) {
      waveParticles.push({
        angle: Math.random() * Math.PI * 2,
        radius: maxR * (0.85 + Math.random() * 0.3),
        speed: (0.001 + Math.random() * 0.004) * (Math.random() > 0.5 ? 1 : -1),
        size: 0.3 + Math.random() * 1.5,
        phase: Math.random() * Math.PI * 2,
        color: Math.random() > 0.6 ? "#1a8a7a" : Math.random() > 0.3 ? "#0d5c52" : "#0a4a40",
      });
    }

    // Dust particles
    const dust: {
      x: number; y: number; vx: number; vy: number;
      size: number; alpha: number; life: number;
    }[] = [];
    for (let i = 0; i < 60; i++) {
      dust.push({
        x: cx + (Math.random() - 0.5) * size * 0.8,
        y: cy + (Math.random() - 0.5) * size * 0.8,
        vx: (Math.random() - 0.5) * 0.3,
        vy: (Math.random() - 0.5) * 0.3,
        size: 0.5 + Math.random() * 1,
        alpha: 0.1 + Math.random() * 0.3,
        life: Math.random() * 200,
      });
    }

    let time = 0;
    let rotY = 0;
    let rotX = 0.3;

    const handleMouseMove = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      mouseRef.current.x = (e.clientX - rect.left) / rect.width;
      mouseRef.current.y = (e.clientY - rect.top) / rect.height;
      mouseRef.current.active = true;
    };
    const handleMouseLeave = () => { mouseRef.current.active = false; };
    canvas.addEventListener("mousemove", handleMouseMove);
    canvas.addEventListener("mouseleave", handleMouseLeave);

    const project = (x: number, y: number, z: number, rY: number, rX: number) => {
      // Rotate Y
      let x1 = x * Math.cos(rY) - z * Math.sin(rY);
      let z1 = x * Math.sin(rY) + z * Math.cos(rY);
      // Rotate X
      let y1 = y * Math.cos(rX) - z1 * Math.sin(rX);
      let z2 = y * Math.sin(rX) + z1 * Math.cos(rX);
      const scale = 1 / (1 + z2 * 0.3);
      return { px: x1 * scale, py: y1 * scale, depth: z2, scale };
    };

    const draw = () => {
      time += 0.008;
      rotY += 0.003;

      // Mouse influence on rotation
      if (mouseRef.current.active) {
        const mx = (mouseRef.current.x - 0.5) * 2;
        const my = (mouseRef.current.y - 0.5) * 2;
        rotY += mx * 0.01;
        rotX = 0.3 + my * 0.2;
      }

      ctx.clearRect(0, 0, size, size);

      // Background
      ctx.fillStyle = "#020808";
      ctx.fillRect(0, 0, size, size);

      // Outer glow
      const breathe = Math.sin(time * 0.6) * 0.15 + 0.85;
      const outerGlow = ctx.createRadialGradient(cx, cy, 0, cx, cy, maxR * 1.5);
      outerGlow.addColorStop(0, `rgba(10,74,64,${0.15 * breathe})`);
      outerGlow.addColorStop(0.4, `rgba(13,92,82,${0.06 * breathe})`);
      outerGlow.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = outerGlow;
      ctx.beginPath();
      ctx.arc(cx, cy, maxR * 1.5, 0, Math.PI * 2);
      ctx.fill();

      // ── Outer organic ring (wavy) ──
      ctx.beginPath();
      for (let a = 0; a <= Math.PI * 2; a += 0.02) {
        const wave = Math.sin(a * 8 + time * 2) * 6 + Math.sin(a * 3 + time * 1.5) * 4;
        const r = maxR * 0.92 + wave;
        const x = cx + Math.cos(a) * r;
        const y = cy + Math.sin(a) * r;
        if (a === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.closePath();
      ctx.strokeStyle = `rgba(20,140,120,${0.25 * breathe})`;
      ctx.lineWidth = 1.5;
      ctx.stroke();

      // Second organic ring
      ctx.beginPath();
      for (let a = 0; a <= Math.PI * 2; a += 0.02) {
        const wave = Math.sin(a * 6 + time * 1.8 + 1) * 5 + Math.cos(a * 4 + time * 2.2) * 3;
        const r = maxR * 0.97 + wave;
        const x = cx + Math.cos(a) * r;
        const y = cy + Math.sin(a) * r;
        if (a === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.closePath();
      ctx.strokeStyle = `rgba(15,110,100,${0.15 * breathe})`;
      ctx.lineWidth = 1;
      ctx.stroke();

      // ── Wave particles (outer cloud) ──
      waveParticles.forEach(p => {
        p.angle += p.speed;
        const wobble = Math.sin(time * 1.5 + p.phase) * 8;
        const x = cx + Math.cos(p.angle) * (p.radius + wobble);
        const y = cy + Math.sin(p.angle) * (p.radius + wobble);
        const alpha = 0.15 + Math.sin(time * 2 + p.phase) * 0.1;
        ctx.beginPath();
        ctx.arc(x, y, p.size, 0, Math.PI * 2);
        ctx.fillStyle = p.color;
        ctx.globalAlpha = alpha;
        ctx.fill();
        ctx.globalAlpha = 1;
      });

      // ── Middle tech ring (segments) ──
      for (let i = 0; i < ringSegments; i++) {
        const a = (i / ringSegments) * Math.PI * 2 + time * 0.5;
        const segAlpha = 0.15 + Math.sin(time * 2 + i * 0.3) * 0.1;
        const x1 = cx + Math.cos(a) * (ringRadius - ringWidth / 2);
        const y1 = cy + Math.sin(a) * (ringRadius - ringWidth / 2);
        const x2 = cx + Math.cos(a) * (ringRadius + ringWidth / 2);
        const y2 = cy + Math.sin(a) * (ringRadius + ringWidth / 2);

        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.strokeStyle = `rgba(10,80,70,${segAlpha})`;
        ctx.lineWidth = 3;
        ctx.stroke();

        // Segment end caps
        if (i % 3 === 0) {
          ctx.beginPath();
          ctx.arc(x2, y2, 1.5, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(20,160,140,${segAlpha * 1.5})`;
          ctx.fill();
        }
      }

      // Ring glow
      ctx.beginPath();
      ctx.arc(cx, cy, ringRadius, 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(10,90,80,${0.12 * breathe})`;
      ctx.lineWidth = 0.5;
      ctx.stroke();

      // ── Inner wireframe geodesic sphere ──
      const innerR = maxR * 0.38;

      // Project all vertices
      const projected = geoVertices.map(v => project(v.x, v.y, v.z, rotY, rotX));
      const midProjected = midVertices.map(v => project(v.x, v.y, v.z, rotY, rotX));

      // Draw edges
      ctx.lineWidth = 0.4;
      for (const [a, b] of geoEdges) {
        const pa = projected[a];
        const pb = projected[b];
        const avgDepth = (pa.depth + pb.depth) / 2;
        const alpha = 0.08 + (1 - avgDepth) * 0.12;
        ctx.beginPath();
        ctx.moveTo(cx + pa.px * innerR, cy + pa.py * innerR);
        ctx.lineTo(cx + pb.px * innerR, cy + pb.py * innerR);
        ctx.strokeStyle = `rgba(20,150,130,${alpha})`;
        ctx.stroke();
      }

      // Draw vertices (bright nodes)
      projected.forEach((p, i) => {
        const alpha = 0.3 + (1 - p.depth) * 0.5;
        const r = 1 + (1 - p.depth) * 1.5;
        ctx.beginPath();
        ctx.arc(cx + p.px * innerR, cy + p.py * innerR, r * p.scale, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(30,180,160,${alpha})`;
        ctx.fill();

        // Glow on front-facing vertices
        if (p.depth < 0) {
          ctx.beginPath();
          ctx.arc(cx + p.px * innerR, cy + p.py * innerR, r * 3 * p.scale, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(20,140,120,${alpha * 0.15})`;
          ctx.fill();
        }
      });

      // Midpoint vertices (smaller, dimmer)
      midProjected.forEach(p => {
        const alpha = 0.1 + (1 - p.depth) * 0.15;
        ctx.beginPath();
        ctx.arc(cx + p.px * innerR, cy + p.py * innerR, 0.8 * p.scale, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(15,100,90,${alpha})`;
        ctx.fill();
      });

      // Inner sphere glow
      const innerGlow = ctx.createRadialGradient(cx, cy, 0, cx, cy, innerR * 0.8);
      innerGlow.addColorStop(0, `rgba(10,80,70,${0.08 * breathe})`);
      innerGlow.addColorStop(0.5, `rgba(8,60,55,${0.04 * breathe})`);
      innerGlow.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = innerGlow;
      ctx.beginPath();
      ctx.arc(cx, cy, innerR * 0.8, 0, Math.PI * 2);
      ctx.fill();

      // ── Dust particles ──
      dust.forEach(d => {
        d.x += d.vx;
        d.y += d.vy;
        d.life++;
        if (d.life > 200) {
          d.x = cx + (Math.random() - 0.5) * size * 0.8;
          d.y = cy + (Math.random() - 0.5) * size * 0.8;
          d.life = 0;
        }
        const dx = d.x - cx;
        const dy = d.y - cy;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist > maxR * 1.4) return;
        const alpha = d.alpha * (1 - dist / (maxR * 1.4));
        ctx.beginPath();
        ctx.arc(d.x, d.y, d.size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(20,120,100,${alpha})`;
        ctx.fill();
      });

      // ── Center core ──
      const corePulse = Math.sin(time * 1.2) * 0.2 + 0.8;
      const coreGlow = ctx.createRadialGradient(cx, cy, 0, cx, cy, 20);
      coreGlow.addColorStop(0, `rgba(30,200,180,${0.25 * corePulse})`);
      coreGlow.addColorStop(0.5, `rgba(15,120,110,${0.08 * corePulse})`);
      coreGlow.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = coreGlow;
      ctx.beginPath();
      ctx.arc(cx, cy, 20, 0, Math.PI * 2);
      ctx.fill();

      ctx.beginPath();
      ctx.arc(cx, cy, 2, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(40,220,200,${0.9 * corePulse})`;
      ctx.fill();

      frameRef.current = requestAnimationFrame(draw);
    };

    draw();
    return () => {
      cancelAnimationFrame(frameRef.current);
      canvas.removeEventListener("mousemove", handleMouseMove);
      canvas.removeEventListener("mouseleave", handleMouseLeave);
    };
  }, [size]);

  return (
    <canvas
      ref={canvasRef}
      style={{ width: size, height: size, cursor: "crosshair" }}
    />
  );
}
