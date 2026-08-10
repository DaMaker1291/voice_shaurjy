"use client";

import { useRef, useEffect, useState } from "react";

interface ExecutionOverlayProps {
  active: boolean;
  agent?: string;
  task?: string;
}

export default function ExecutionOverlay({ active, agent = "OS", task = "" }: ExecutionOverlayProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const frameRef = useRef<number>(0);

  useEffect(() => {
    if (!active) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const w = window.innerWidth;
    const h = window.innerHeight;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    ctx.scale(dpr, dpr);

    // Particles
    const particles: { x: number; y: number; vx: number; vy: number; life: number; maxLife: number; size: number; color: string }[] = [];
    const colors = ["#00FF66", "#FFB300", "#00FF66", "#667085"];

    // Grid lines
    const gridSpacing = 60;
    let gridOffset = 0;

    let time = 0;

    const spawnParticles = () => {
      for (let i = 0; i < 3; i++) {
        particles.push({
          x: Math.random() * w,
          y: h + 10,
          vx: (Math.random() - 0.5) * 2,
          vy: -(2 + Math.random() * 4),
          life: 0,
          maxLife: 80 + Math.random() * 60,
          size: 1 + Math.random() * 2,
          color: colors[Math.floor(Math.random() * colors.length)],
        });
      }
    };

    const draw = () => {
      time += 0.016;
      gridOffset = (gridOffset + 0.5) % gridSpacing;

      ctx.clearRect(0, 0, w, h);

      // Transparent mesh overlay
      ctx.fillStyle = "rgba(3,3,3,0.85)";
      ctx.fillRect(0, 0, w, h);

      // Perspective grid
      ctx.strokeStyle = "rgba(0,255,102,0.04)";
      ctx.lineWidth = 0.5;

      // Horizontal lines
      for (let y = gridOffset; y < h; y += gridSpacing) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(w, y);
        ctx.stroke();
      }

      // Vertical lines
      for (let x = gridOffset; x < w; x += gridSpacing) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, h);
        ctx.stroke();
      }

      // Hexagonal mesh pattern (subtle)
      ctx.strokeStyle = "rgba(0,255,102,0.02)";
      const hexR = 40;
      const hexH = hexR * Math.sqrt(3);
      for (let row = -1; row < h / hexH + 1; row++) {
        for (let col = -1; col < w / (hexR * 1.5) + 1; col++) {
          const cx = col * hexR * 1.5;
          const cy = row * hexH + (col % 2 ? hexH / 2 : 0);
          ctx.beginPath();
          for (let a = 0; a < 6; a++) {
            const angle = (Math.PI / 3) * a - Math.PI / 6;
            const px = cx + hexR * Math.cos(angle);
            const py = cy + hexR * Math.sin(angle);
            if (a === 0) ctx.moveTo(px, py);
            else ctx.lineTo(px, py);
          }
          ctx.closePath();
          ctx.stroke();
        }
      }

      // Data stream particles
      if (Math.random() < 0.3) spawnParticles();

      for (let i = particles.length - 1; i >= 0; i--) {
        const p = particles[i];
        p.x += p.vx;
        p.y += p.vy;
        p.life++;

        const alpha = 1 - p.life / p.maxLife;
        if (alpha <= 0 || p.y < -10) {
          particles.splice(i, 1);
          continue;
        }

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fillStyle = p.color;
        ctx.globalAlpha = alpha * 0.6;
        ctx.fill();

        // Trail
        ctx.beginPath();
        ctx.moveTo(p.x, p.y);
        ctx.lineTo(p.x - p.vx * 3, p.y - p.vy * 3);
        ctx.strokeStyle = p.color;
        ctx.globalAlpha = alpha * 0.3;
        ctx.lineWidth = p.size * 0.5;
        ctx.stroke();
      }
      ctx.globalAlpha = 1;

      // Scanning line
      const scanY = (time * 100) % h;
      const scanGrad = ctx.createLinearGradient(0, scanY - 20, 0, scanY + 20);
      scanGrad.addColorStop(0, "rgba(0,255,102,0)");
      scanGrad.addColorStop(0.5, "rgba(0,255,102,0.08)");
      scanGrad.addColorStop(1, "rgba(0,255,102,0)");
      ctx.fillStyle = scanGrad;
      ctx.fillRect(0, scanY - 20, w, 40);

      // Center info
      ctx.font = "600 11px monospace";
      ctx.fillStyle = "rgba(0,255,102,0.8)";
      ctx.textAlign = "center";
      ctx.fillText(`EXECUTING: ${agent}`, w / 2, h / 2 - 10);
      if (task) {
        ctx.font = "10px monospace";
        ctx.fillStyle = "rgba(255,255,255,0.3)";
        ctx.fillText(task.slice(0, 60), w / 2, h / 2 + 10);
      }

      // Corner brackets
      const bSize = 40;
      const bOff = 30;
      ctx.strokeStyle = "rgba(0,255,102,0.3)";
      ctx.lineWidth = 1.5;
      // Top-left
      ctx.beginPath(); ctx.moveTo(bOff, bOff + bSize); ctx.lineTo(bOff, bOff); ctx.lineTo(bOff + bSize, bOff); ctx.stroke();
      // Top-right
      ctx.beginPath(); ctx.moveTo(w - bOff - bSize, bOff); ctx.lineTo(w - bOff, bOff); ctx.lineTo(w - bOff, bOff + bSize); ctx.stroke();
      // Bottom-left
      ctx.beginPath(); ctx.moveTo(bOff, h - bOff - bSize); ctx.lineTo(bOff, h - bOff); ctx.lineTo(bOff + bSize, h - bOff); ctx.stroke();
      // Bottom-right
      ctx.beginPath(); ctx.moveTo(w - bOff - bSize, h - bOff); ctx.lineTo(w - bOff, h - bOff); ctx.lineTo(w - bOff, h - bOff - bSize); ctx.stroke();

      frameRef.current = requestAnimationFrame(draw);
    };

    draw();
    return () => cancelAnimationFrame(frameRef.current);
  }, [active, agent, task]);

  if (!active) return null;

  return (
    <div style={{
      position: "fixed", inset: 0, zIndex: 9999,
      pointerEvents: "none",
      animation: "fade-in 0.3s ease both",
    }}>
      <canvas
        ref={canvasRef}
        style={{ width: "100vw", height: "100vh", display: "block" }}
      />
    </div>
  );
}
