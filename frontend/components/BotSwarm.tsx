"use client";

import { useEffect, useRef } from "react";

interface Props {
  listening?: boolean;
  thinking?: boolean;
  speaking?: boolean;
  activity?: number;
  botEvents?: { type: string; label: string; timestamp: number }[];
  centered?: boolean;
}

const BOT_COLORS = {
  idle: { h: 260, s: 80, l: 50 },
  listening: { h: 140, s: 80, l: 55 },
  thinking: { h: 270, s: 90, l: 65 },
  action: { h: 190, s: 85, l: 60 },
  error: { h: 0, s: 85, l: 55 },
  planning: { h: 40, s: 90, l: 60 },
  vision: { h: 320, s: 80, l: 55 },
  workflow: { h: 220, s: 85, l: 60 },
};

interface Bot {
  x: number; y: number;
  vx: number; vy: number;
  targetX: number; targetY: number;
  size: number;
  hue: number; sat: number; light: number;
  trail: { x: number; y: number; life: number }[];
  role: string;
  glow: number;
  phase: number;
}

interface Particle {
  x: number; y: number;
  vx: number; vy: number;
  life: number; maxLife: number;
  size: number;
  hue: number;
}

interface ConnectionLine {
  from: number; to: number;
  life: number; maxLife: number;
}

export default function BotSwarm({ listening, thinking, speaking, activity = 0.5, botEvents = [], centered = false }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const botsRef = useRef<Bot[]>([]);
  const particlesRef = useRef<Particle[]>([]);
  const connectionsRef = useRef<ConnectionLine[]>([]);
  const eventLogRef = useRef<{ type: string; label: string; timestamp: number }[]>([]);
  const mouseRef = useRef({ x: 0.5, y: 0.5 });
  const timeRef = useRef(0);
  const sizeRef = useRef({ w: 500, h: 500 });

  useEffect(() => {
    eventLogRef.current = botEvents;
  }, [botEvents]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d")!;

    const resize = () => {
      if (centered) {
        const parent = canvas.parentElement;
        sizeRef.current = { w: parent?.clientWidth || 500, h: parent?.clientHeight || 500 };
        canvas.width = sizeRef.current.w;
        canvas.height = sizeRef.current.h;
      } else {
        sizeRef.current = { w: window.innerWidth, h: window.innerHeight };
        canvas.width = sizeRef.current.w;
        canvas.height = sizeRef.current.h;
      }
    };
    resize();
    window.addEventListener("resize", resize);
    window.addEventListener("mousemove", (e) => {
      mouseRef.current = { x: e.clientX / canvas.width, y: e.clientY / canvas.height };
    });

    // Initialize bots
    const roles = ["vision", "workflow", "planning", "action", "memory", "search", "automation", "monitor"];
    const bots: Bot[] = [];
    for (let i = 0; i < 24; i++) {
      const role = roles[i % roles.length];
      const color = BOT_COLORS[role as keyof typeof BOT_COLORS] || BOT_COLORS.idle;
      bots.push({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        vx: (Math.random() - 0.5) * 0.5,
        vy: (Math.random() - 0.5) * 0.5,
        targetX: Math.random() * canvas.width,
        targetY: Math.random() * canvas.height,
        size: 2 + Math.random() * 3,
        hue: color.h + Math.random() * 20 - 10,
        sat: color.s,
        light: color.l,
        trail: [],
        role,
        glow: 0,
        phase: Math.random() * Math.PI * 2,
      });
    }
    botsRef.current = bots;

    // Init particles
    const particles: Particle[] = [];
    for (let i = 0; i < 100; i++) {
      particles.push({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        vx: (Math.random() - 0.5) * 0.3,
        vy: (Math.random() - 0.5) * 0.3,
        life: Math.random(),
        maxLife: 1 + Math.random() * 2,
        size: 0.5 + Math.random() * 1.5,
        hue: 260 + Math.random() * 60,
      });
    }
    particlesRef.current = particles;

    let animId: number;

    const animate = () => {
      const w = canvas.width;
      const h = canvas.height;
      timeRef.current += 0.016;

      ctx.clearRect(0, 0, w, h);

      // ── Dark background with subtle radial glow ──
      const grad = ctx.createRadialGradient(
        w * 0.5, h * 0.5, 0,
        w * 0.5, h * 0.5, w * 0.6
      );
      const intensity = listening ? 0.08 : thinking ? 0.12 : 0.04;
      grad.addColorStop(0, `rgba(120, 60, 220, ${intensity})`);
      grad.addColorStop(0.5, `rgba(6, 182, 212, ${intensity * 0.5})`);
      grad.addColorStop(1, "transparent");
      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, w, h);

      // ── Draw grid lines ──
      ctx.strokeStyle = "rgba(120, 60, 220, 0.03)";
      ctx.lineWidth = 1;
      const gridSize = 60;
      for (let x = 0; x < w; x += gridSize) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, h);
        ctx.stroke();
      }
      for (let y = 0; y < h; y += gridSize) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(w, y);
        ctx.stroke();
      }

      const cx = w * 0.35;
      const cy = h * 0.5;
      const mx = mouseRef.current.x * w;
      const my = mouseRef.current.y * h;

      // ── Bots find targets ──
      const activeMode = listening ? "listening" : thinking ? "thinking" : speaking ? "action" : "idle";

      bots.forEach((bot, i) => {
        const phase = bot.phase + timeRef.current;
        const spread = activeMode === "thinking" ? 120 : activeMode === "listening" ? 80 : 200;

        // Swarm around center + mouse influence
        const baseX = cx + Math.sin(phase * 0.3 + i * 0.5) * spread;
        const baseY = cy + Math.cos(phase * 0.4 + i * 0.7) * spread * 0.7;

        // Mouse repulsion (bots flee mouse)
        const dx = bot.x - mx;
        const dy = bot.y - my;
        const dist = Math.sqrt(dx * dx + dy * dy);
        let mouseInfluence = 0;
        if (dist < 150) {
          mouseInfluence = (150 - dist) / 150 * 3;
        }

        bot.targetX = baseX + dx * mouseInfluence * 0.1;
        bot.targetY = baseY + dy * mouseInfluence * 0.1;

        // Move toward target
        bot.vx += (bot.targetX - bot.x) * 0.005;
        bot.vy += (bot.targetY - bot.y) * 0.005;

        // Damping
        bot.vx *= 0.97;
        bot.vy *= 0.97;

        bot.x += bot.vx;
        bot.y += bot.vy;

        // Trail
        bot.trail.push({ x: bot.x, y: bot.y, life: 1 });
        if (bot.trail.length > 15) bot.trail.shift();
        bot.trail.forEach(t => t.life -= 0.06);

        // Glow pulsing
        bot.glow = 0.3 + Math.sin(phase * 2 + i) * 0.2;
        if (activeMode !== "idle") bot.glow += 0.2;

        // ── Draw trail ──
        for (let t = 0; t < bot.trail.length - 1; t++) {
          const pt = bot.trail[t];
          const alpha = pt.life * 0.3;
          if (alpha <= 0) continue;
          ctx.beginPath();
          ctx.moveTo(bot.trail[t + 1].x, bot.trail[t + 1].y);
          ctx.lineTo(pt.x, pt.y);
          ctx.strokeStyle = `hsla(${bot.hue}, ${bot.sat}%, ${bot.light}%, ${alpha})`;
          ctx.lineWidth = bot.size * pt.life * 0.5;
          ctx.stroke();
        }

        // ── Draw glow ──
        const glowSize = bot.size * 6 + bot.glow * 4;
        const grad2 = ctx.createRadialGradient(bot.x, bot.y, 0, bot.x, bot.y, glowSize);
        grad2.addColorStop(0, `hsla(${bot.hue}, ${bot.sat}%, ${bot.light}%, ${0.15 + bot.glow * 0.1})`);
        grad2.addColorStop(1, "transparent");
        ctx.fillStyle = grad2;
        ctx.beginPath();
        ctx.arc(bot.x, bot.y, glowSize, 0, Math.PI * 2);
        ctx.fill();

        // ── Draw bot ──
        const isActive = activeMode !== "idle";
        const botAlpha = isActive ? 0.9 : 0.4;
        ctx.beginPath();
        // Diamonds for bots
        const s = bot.size * (isActive ? 1.2 : 0.8);
        ctx.moveTo(bot.x, bot.y - s);
        ctx.lineTo(bot.x + s * 0.7, bot.y);
        ctx.lineTo(bot.x, bot.y + s);
        ctx.lineTo(bot.x - s * 0.7, bot.y);
        ctx.closePath();
        ctx.fillStyle = `hsla(${bot.hue}, ${bot.sat}%, ${bot.light}%, ${botAlpha})`;
        ctx.fill();
        ctx.strokeStyle = `hsla(${bot.hue}, ${bot.sat}%}, ${bot.light + 20}%, ${botAlpha * 0.5})`;
        ctx.lineWidth = 0.5;
        ctx.stroke();
      });

      // ── Draw connections between nearby bots ──
      connectionsRef.current = connectionsRef.current.filter(c => c.life > 0);
      for (let i = 0; i < bots.length; i++) {
        for (let j = i + 1; j < bots.length; j++) {
          const dx = bots[i].x - bots[j].x;
          const dy = bots[i].y - bots[j].y;
          const d = Math.sqrt(dx * dx + dy * dy);
          const connectDist = activeMode === "thinking" ? 180 : 100;
          if (d < connectDist && Math.random() < 0.005) {
            connectionsRef.current.push({ from: i, to: j, life: 0.5, maxLife: 0.5 });
          }
        }
      }

      connectionsRef.current.forEach((conn, idx) => {
        conn.life -= 0.01;
        const b1 = bots[conn.from];
        const b2 = bots[conn.to];
        if (!b1 || !b2) return;
        const alpha = (conn.life / conn.maxLife) * 0.15;
        ctx.beginPath();
        ctx.moveTo(b1.x, b1.y);
        ctx.lineTo(b2.x, b2.y);
        ctx.strokeStyle = `hsla(270, 80%, 60%, ${alpha})`;
        ctx.lineWidth = 0.5;
        ctx.stroke();
      });

      // ── Particles ──
      const particleCount = activeMode === "thinking" ? 150 : 80;
      while (particlesRef.current.length < particleCount) {
        particlesRef.current.push({
          x: Math.random() * w,
          y: Math.random() * h,
          vx: (Math.random() - 0.5) * 0.5,
          vy: (Math.random() - 0.5) * 0.5 - 0.2,
          life: 0,
          maxLife: 1 + Math.random() * 3,
          size: 0.3 + Math.random() * 1.2,
          hue: 260 + Math.random() * 60,
        });
      }

      particlesRef.current.forEach((p, i) => {
        p.life += 0.016;
        p.x += p.vx;
        p.y += p.vy;
        p.vx *= 0.99;

        const alpha = Math.sin((p.life / p.maxLife) * Math.PI) * 0.5;
        const pulse = Math.sin(timeRef.current * 2 + i) * 0.3 + 0.7;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size * pulse, 0, Math.PI * 2);
        ctx.fillStyle = `hsla(${p.hue}, 80%, 60%, ${alpha})`;
        ctx.fill();

        // Glow
        if (p.size > 0.8) {
          const glowGrad = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.size * 4);
          glowGrad.addColorStop(0, `hsla(${p.hue}, 80%, 60%, ${alpha * 0.2})`);
          glowGrad.addColorStop(1, "transparent");
          ctx.fillStyle = glowGrad;
          ctx.beginPath();
          ctx.arc(p.x, p.y, p.size * 4, 0, Math.PI * 2);
          ctx.fill();
        }

        // Reset dead particles
        if (p.life >= p.maxLife) {
          particlesRef.current[i] = {
            x: Math.random() * w,
            y: h + 10,
            vx: (Math.random() - 0.5) * 0.5,
            vy: -Math.random() * 0.8 - 0.2,
            life: 0,
            maxLife: 1 + Math.random() * 3,
            size: 0.3 + Math.random() * 1.2,
            hue: 260 + Math.random() * 60,
          };
        }
      });

      // ── Orbital ring at center ──
      const ringCount = listening ? 4 : thinking ? 3 : 2;
      for (let r = 0; r < ringCount; r++) {
        const radius = 60 + r * 40 + Math.sin(timeRef.current * 0.5 + r) * 10;
        const rotSpeed = 0.3 + r * 0.1;
        const alpha = (listening ? 0.15 : thinking ? 0.12 : 0.06) * (1 - r / ringCount);
        ctx.beginPath();
        ctx.ellipse(cx, cy, radius, radius * 0.4, timeRef.current * rotSpeed, 0, Math.PI * 2);
        ctx.strokeStyle = `hsla(${260 + r * 20}, 80%, 60%, ${alpha})`;
        ctx.lineWidth = 0.5;
        ctx.stroke();
      }

      // ── Label bots with roles (very subtle) ──
      if (activeMode !== "idle") {
        const labelBots = bots.slice(0, 8);
        labelBots.forEach((bot, i) => {
          ctx.fillStyle = `hsla(${bot.hue}, ${bot.sat}%, ${bot.light + 20}%, 0.15)`;
          ctx.font = "7px monospace";
          ctx.textAlign = "center";
          ctx.fillText(bot.role.toUpperCase(), bot.x, bot.y - bot.size - 6);
        });
      }

      // ── Event log overlay ──
      const events = eventLogRef.current.slice(-4);
      events.forEach((evt, i) => {
        const alpha = Math.max(0, 1 - (Date.now() - evt.timestamp) / 5000);
        if (alpha <= 0) return;
        const colorMap: Record<string, string> = {
          action: "rgba(6, 182, 212",
          thinking: "rgba(168, 85, 247",
          vision: "rgba(236, 72, 153",
          workflow: "rgba(59, 130, 246",
          error: "rgba(239, 68, 68",
        };
        const base = colorMap[evt.type] || "rgba(168, 85, 247";
        ctx.fillStyle = `${base}, ${alpha * 0.3})`;
        ctx.font = "10px monospace";
        ctx.textAlign = "right";
        ctx.fillText(`▸ ${evt.label}`, w - 20, h - 20 - i * 18);
      });

      // ── Center glow pulse ──
      const pulseIntensity = listening ? 1 : thinking ? 0.7 : 0.3;
      const pulseSize = 30 + Math.sin(timeRef.current * 3) * 10;
      const centerGlow = ctx.createRadialGradient(cx, cy, 0, cx, cy, pulseSize * (1 + activity * 0.5));
      centerGlow.addColorStop(0, `rgba(168, 85, 247, ${0.1 * pulseIntensity})`);
      centerGlow.addColorStop(0.5, `rgba(6, 182, 212, ${0.05 * pulseIntensity})`);
      centerGlow.addColorStop(1, "transparent");
      ctx.fillStyle = centerGlow;
      ctx.beginPath();
      ctx.arc(cx, cy, pulseSize * (1 + activity * 0.5), 0, Math.PI * 2);
      ctx.fill();

      animId = requestAnimationFrame(animate);
    };

    animate();

    return () => {
      window.removeEventListener("resize", resize);
      cancelAnimationFrame(animId);
    };
  }, [listening, thinking, speaking, activity]);

  return (
    <canvas
      ref={canvasRef}
      className={centered ? "w-full h-full pointer-events-none" : "fixed inset-0 z-0 pointer-events-none"}
      style={{ opacity: centered ? 1 : 0.8 }}
    />
  );
}
