"use client";

import { useRef, useEffect } from "react";

interface KineticOrbProps {
  size?: number;
  speed?: number;
}

export default function KineticOrb({ size = 280, speed = 1 }: KineticOrbProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const mouseRef = useRef({ x: 0.5, y: 0.5, active: false });
  const frameRef = useRef<number>(0);

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
    const maxR = size * 0.42;

    // Particles
    const particles: {
      angle: number; radius: number; speed: number; size: number;
      phase: number; orbitSpeed: number; color: string; trail: { x: number; y: number }[];
    }[] = [];

    const colors = ["#00FF66", "#00FF66", "#00FF66", "#FFB300", "#00CC55", "#00FF88"];
    for (let i = 0; i < 120; i++) {
      const r = 20 + Math.random() * (maxR - 30);
      particles.push({
        angle: Math.random() * Math.PI * 2,
        radius: r,
        speed: 0.002 + Math.random() * 0.008,
        size: 0.5 + Math.random() * 2,
        phase: Math.random() * Math.PI * 2,
        orbitSpeed: (0.005 + Math.random() * 0.015) * (Math.random() > 0.5 ? 1 : -1),
        color: colors[Math.floor(Math.random() * colors.length)],
        trail: [],
      });
    }

    // Ring particles (tight orbiting clusters)
    const ringParticles: {
      angle: number; radius: number; speed: number; size: number; color: string;
    }[] = [];
    for (let i = 0; i < 60; i++) {
      ringParticles.push({
        angle: Math.random() * Math.PI * 2,
        radius: maxR * 0.7 + (Math.random() - 0.5) * 20,
        speed: 0.008 + Math.random() * 0.012,
        size: 0.3 + Math.random() * 1.2,
        color: Math.random() > 0.7 ? "#FFB300" : "#00FF66",
      });
    }

    let time = 0;

    const handleMouseMove = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      mouseRef.current.x = (e.clientX - rect.left) / rect.width;
      mouseRef.current.y = (e.clientY - rect.top) / rect.height;
      mouseRef.current.active = true;
    };
    const handleMouseLeave = () => { mouseRef.current.active = false; };
    canvas.addEventListener("mousemove", handleMouseMove);
    canvas.addEventListener("mouseleave", handleMouseLeave);

    const draw = () => {
      time += 0.016 * speed;
      ctx.clearRect(0, 0, size, size);

      // Background
      ctx.fillStyle = "#030303";
      ctx.fillRect(0, 0, size, size);

      const mx = (mouseRef.current.x - 0.5) * 2;
      const my = (mouseRef.current.y - 0.5) * 2;
      const mouseActive = mouseRef.current.active;

      // Outer glow
      const breathe = Math.sin(time * 0.8) * 0.15 + 0.85;
      const outerGlow = ctx.createRadialGradient(cx, cy, 0, cx, cy, maxR * 1.3);
      outerGlow.addColorStop(0, `rgba(0,255,102,${0.06 * breathe})`);
      outerGlow.addColorStop(0.5, `rgba(0,255,102,${0.02 * breathe})`);
      outerGlow.addColorStop(1, "rgba(0,255,102,0)");
      ctx.fillStyle = outerGlow;
      ctx.beginPath();
      ctx.arc(cx, cy, maxR * 1.3, 0, Math.PI * 2);
      ctx.fill();

      // Concentric rings
      for (let i = 1; i <= 4; i++) {
        const r = (i / 4) * maxR * 0.9;
        const pulse = Math.sin(time + i * 0.5) * 0.3 + 0.7;
        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(0,255,102,${0.06 * pulse})`;
        ctx.lineWidth = 0.5;
        ctx.stroke();
      }

      // Ring particles (tight orbit)
      ringParticles.forEach(p => {
        p.angle += p.speed;
        const wobble = Math.sin(time * 2 + p.angle * 3) * 3;
        const x = cx + Math.cos(p.angle) * (p.radius + wobble);
        const y = cy + Math.sin(p.angle) * (p.radius + wobble);

        ctx.beginPath();
        ctx.arc(x, y, p.size, 0, Math.PI * 2);
        ctx.fillStyle = p.color;
        ctx.globalAlpha = 0.5 + Math.sin(time * 3 + p.angle) * 0.3;
        ctx.fill();
        ctx.globalAlpha = 1;
      });

      // Main particles with trails
      particles.forEach(p => {
        // Mouse repulsion
        let targetRadius = p.radius;
        if (mouseActive) {
          const px = cx + Math.cos(p.angle) * p.radius;
          const py = cy + Math.sin(p.angle) * p.radius;
          const dx = px - (mx * maxR + cx);
          const dy = py - (my * maxR + cy);
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 80) {
            targetRadius = p.radius + (80 - dist) * 0.3;
          }
        }

        // Breathing
        const breatheR = Math.sin(time * 1.2 + p.phase) * 8;
        const currentRadius = targetRadius + breatheR;

        p.angle += p.orbitSpeed;
        const x = cx + Math.cos(p.angle) * currentRadius;
        const y = cy + Math.sin(p.angle) * currentRadius;

        // Trail
        p.trail.push({ x, y });
        if (p.trail.length > 6) p.trail.shift();

        // Draw trail
        if (p.trail.length > 1) {
          ctx.beginPath();
          ctx.moveTo(p.trail[0].x, p.trail[0].y);
          for (let i = 1; i < p.trail.length; i++) {
            ctx.lineTo(p.trail[i].x, p.trail[i].y);
          }
          ctx.strokeStyle = p.color;
          ctx.globalAlpha = 0.15;
          ctx.lineWidth = p.size * 0.4;
          ctx.stroke();
          ctx.globalAlpha = 1;
        }

        // Draw particle
        const alpha = 0.4 + Math.sin(time * 2 + p.phase) * 0.3;
        ctx.beginPath();
        ctx.arc(x, y, p.size, 0, Math.PI * 2);
        ctx.fillStyle = p.color;
        ctx.globalAlpha = alpha;
        ctx.fill();
        ctx.globalAlpha = 1;

        // Glow on mouse proximity
        if (mouseActive) {
          const dx = x - (mx * maxR + cx);
          const dy = y - (my * maxR + cy);
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 60) {
            const glow = ctx.createRadialGradient(x, y, 0, x, y, 12);
            glow.addColorStop(0, `${p.color}40`);
            glow.addColorStop(1, `${p.color}00`);
            ctx.fillStyle = glow;
            ctx.beginPath();
            ctx.arc(x, y, 12, 0, Math.PI * 2);
            ctx.fill();
          }
        }
      });

      // Center core
      const corePulse = Math.sin(time * 1.5) * 0.2 + 0.8;
      const coreGlow = ctx.createRadialGradient(cx, cy, 0, cx, cy, 30);
      coreGlow.addColorStop(0, `rgba(0,255,102,${0.3 * corePulse})`);
      coreGlow.addColorStop(0.5, `rgba(0,255,102,${0.08 * corePulse})`);
      coreGlow.addColorStop(1, "rgba(0,255,102,0)");
      ctx.fillStyle = coreGlow;
      ctx.beginPath();
      ctx.arc(cx, cy, 30, 0, Math.PI * 2);
      ctx.fill();

      // Core dot
      ctx.beginPath();
      ctx.arc(cx, cy, 3, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(0,255,102,${0.9 * corePulse})`;
      ctx.fill();

      // Mouse crosshair when active
      if (mouseActive) {
        const mpx = mx * maxR + cx;
        const mpy = my * maxR + cy;
        ctx.strokeStyle = "rgba(0,255,102,0.2)";
        ctx.lineWidth = 0.5;
        ctx.beginPath();
        ctx.moveTo(mpx - 12, mpy); ctx.lineTo(mpx + 12, mpy);
        ctx.moveTo(mpx, mpy - 12); ctx.lineTo(mpx, mpy + 12);
        ctx.stroke();
        ctx.beginPath();
        ctx.arc(mpx, mpy, 8, 0, Math.PI * 2);
        ctx.stroke();
      }

      frameRef.current = requestAnimationFrame(draw);
    };

    draw();

    return () => {
      cancelAnimationFrame(frameRef.current);
      canvas.removeEventListener("mousemove", handleMouseMove);
      canvas.removeEventListener("mouseleave", handleMouseLeave);
    };
  }, [size, speed]);

  return (
    <canvas
      ref={canvasRef}
      style={{
        width: size,
        height: size,
        cursor: "crosshair",
        borderRadius: "50%",
      }}
    />
  );
}
