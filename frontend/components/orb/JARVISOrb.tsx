"use client";

import React, { useRef, useEffect, useCallback, useState } from "react";

type OrbState =
  | "idle"
  | "listening"
  | "planning"
  | "working"
  | "multi_agent"
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
  onClick?: () => void;
  onContextMenu?: (e: React.MouseEvent) => void;
  showLabel?: boolean;
  interactive?: boolean;
}

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
  opacity: number;
  targetOpacity: number;
  angle: number;
  orbitRadius: number;
  orbitSpeed: number;
  phase: number;
  connected: boolean;
}

export default function JARVISOrb({
  state = "idle",
  size = 64,
  progress = 0,
  mission = "",
  onClick,
  onContextMenu,
  showLabel = false,
  interactive = true,
}: OrbProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animRef = useRef<number>(0);
  const particlesRef = useRef<Particle[]>([]);
  const timeRef = useRef(0);
  const [hovered, setHovered] = useState(false);

  const getStateConfig = useCallback((s: OrbState) => {
    switch (s) {
      case "idle":
        return { particleCount: 8, speed: 0.3, breathe: 0.02, color: "#00FF66", glowIntensity: 0.4 };
      case "listening":
        return { particleCount: 12, speed: 0.8, breathe: 0.05, color: "#00FF66", glowIntensity: 0.7 };
      case "planning":
        return { particleCount: 16, speed: 0.6, breathe: 0.04, color: "#00B4D8", glowIntensity: 0.6 };
      case "working":
        return { particleCount: 20, speed: 1.2, breathe: 0.03, color: "#00FF66", glowIntensity: 0.8 };
      case "multi_agent":
        return { particleCount: 30, speed: 0.8, breathe: 0.04, color: "#A855F7", glowIntensity: 0.9 };
      case "waiting":
        return { particleCount: 8, speed: 0.15, breathe: 0.06, color: "#FFB300", glowIntensity: 0.3 };
      case "needs_approval":
        return { particleCount: 12, speed: 1.5, breathe: 0.1, color: "#EF4444", glowIntensity: 1.0 };
      case "error":
        return { particleCount: 14, speed: 2.0, breathe: 0.15, color: "#EF4444", glowIntensity: 0.9 };
      case "recovering":
        return { particleCount: 14, speed: 1.0, breathe: 0.08, color: "#FFB300", glowIntensity: 0.6 };
      case "complete":
        return { particleCount: 24, speed: 0.4, breathe: 0.2, color: "#00FF66", glowIntensity: 1.0 };
      default:
        return { particleCount: 8, speed: 0.3, breathe: 0.02, color: "#00FF66", glowIntensity: 0.4 };
    }
  }, []);

  const initParticles = useCallback(
    (count: number, s: OrbState) => {
      const particles: Particle[] = [];
      const cx = size / 2;
      const cy = size / 2;
      for (let i = 0; i < count; i++) {
        const angle = (Math.PI * 2 * i) / count + Math.random() * 0.3;
        const orbitRadius = size * 0.25 + Math.random() * size * 0.15;
        particles.push({
          x: cx + Math.cos(angle) * orbitRadius,
          y: cy + Math.sin(angle) * orbitRadius,
          vx: 0,
          vy: 0,
          radius: s === "complete" ? 2.5 : 1.5 + Math.random() * 1.5,
          opacity: 0,
          targetOpacity: 0.6 + Math.random() * 0.4,
          angle,
          orbitRadius,
          orbitSpeed: (0.002 + Math.random() * 0.004) * (Math.random() > 0.5 ? 1 : -1),
          phase: Math.random() * Math.PI * 2,
          connected: i % 2 === 0,
        });
      }
      return particles;
    },
    [size]
  );

  useEffect(() => {
    const config = getStateConfig(state);
    particlesRef.current = initParticles(config.particleCount, state);
  }, [state, initParticles, getStateConfig]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = size * dpr;
    canvas.height = size * dpr;
    ctx.scale(dpr, dpr);

    const animate = () => {
      timeRef.current += 0.016;
      const t = timeRef.current;
      const config = getStateConfig(state);
      const particles = particlesRef.current;
      const cx = size / 2;
      const cy = size / 2;

      ctx.clearRect(0, 0, size, size);

      const breathe = Math.sin(t * 60 * config.breathe) * 0.15 + 1;
      const coreRadius = size * 0.12 * breathe;

      const glowGrad = ctx.createRadialGradient(cx, cy, coreRadius * 0.5, cx, cy, size * 0.45);
      glowGrad.addColorStop(0, config.color + Math.round(config.glowIntensity * 80).toString(16).padStart(2, "0"));
      glowGrad.addColorStop(1, config.color + "00");
      ctx.fillStyle = glowGrad;
      ctx.beginPath();
      ctx.arc(cx, cy, size * 0.45, 0, Math.PI * 2);
      ctx.fill();

      if (
        state === "working" ||
        state === "planning" ||
        state === "recovering" ||
        state === "multi_agent"
      ) {
        for (let i = 0; i < particles.length; i++) {
          const p1 = particles[i];
          for (let j = i + 1; j < particles.length; j++) {
            const p2 = particles[j];
            const dx = p1.x - p2.x;
            const dy = p1.y - p2.y;
            const dist = Math.sqrt(dx * dx + dy * dy);
            if (dist < size * 0.35) {
              const alpha = (1 - dist / (size * 0.35)) * 0.3;
              ctx.strokeStyle = config.color + Math.round(alpha * 255).toString(16).padStart(2, "0");
              ctx.lineWidth = 0.5;
              ctx.beginPath();
              ctx.moveTo(p1.x, p1.y);
              ctx.lineTo(p2.x, p2.y);
              ctx.stroke();
            }
          }
        }
      }

      if (state === "needs_approval") {
        const pulseR = size * 0.3 + Math.sin(t * 8) * size * 0.05;
        ctx.strokeStyle = config.color + "60";
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(cx, cy, pulseR, 0, Math.PI * 2);
        ctx.stroke();
      }

      // Multi-agent: draw orbiting satellite nodes
      if (state === "multi_agent") {
        const satelliteCount = 6;
        const orbitRadius = size * 0.38;
        for (let i = 0; i < satelliteCount; i++) {
          const angle = (Math.PI * 2 * i) / satelliteCount + t * 0.5;
          const sx = cx + Math.cos(angle) * orbitRadius;
          const sy = cy + Math.sin(angle) * orbitRadius;
          const satelliteRadius = 3 + Math.sin(t * 3 + i) * 1;

          // Draw connection line to core
          ctx.strokeStyle = config.color + "40";
          ctx.lineWidth = 0.8;
          ctx.beginPath();
          ctx.moveTo(cx, cy);
          ctx.lineTo(sx, sy);
          ctx.stroke();

          // Draw satellite node
          const satGrad = ctx.createRadialGradient(sx, sy, 0, sx, sy, satelliteRadius * 2);
          satGrad.addColorStop(0, config.color);
          satGrad.addColorStop(1, config.color + "00");
          ctx.fillStyle = satGrad;
          ctx.beginPath();
          ctx.arc(sx, sy, satelliteRadius * 2, 0, Math.PI * 2);
          ctx.fill();

          ctx.fillStyle = config.color;
          ctx.beginPath();
          ctx.arc(sx, sy, satelliteRadius, 0, Math.PI * 2);
          ctx.fill();
        }
      }

      for (const p of particles) {
        p.angle += p.orbitSpeed * config.speed * 60;
        const targetX = cx + Math.cos(p.angle) * p.orbitRadius * breathe;
        const targetY = cy + Math.sin(p.angle) * p.orbitRadius * breathe;

        if (state === "listening") {
          const toCenter = 0.02 * config.speed;
          p.vx += (cx - p.x) * toCenter;
          p.vy += (cy - p.y) * toCenter;
        } else if (state === "working") {
          p.vx += (targetX - p.x) * 0.03;
          p.vy += (targetY - p.y) * 0.03;
        } else if (state === "needs_approval" || state === "error") {
          const jitter = state === "error" ? 3 : 1.5;
          p.vx += (Math.random() - 0.5) * jitter;
          p.vy += (Math.random() - 0.5) * jitter;
          p.vx += (targetX - p.x) * 0.02;
          p.vy += (targetY - p.y) * 0.02;
        } else if (state === "complete") {
          const spiral = Math.sin(t * 3 + p.phase) * 0.01;
          p.vx += (targetX - p.x) * 0.05 + spiral;
          p.vy += (targetY - p.y) * 0.05 + spiral;
        } else {
          p.vx += (targetX - p.x) * 0.04;
          p.vy += (targetY - p.y) * 0.04;
        }

        p.vx *= 0.92;
        p.vy *= 0.92;
        p.x += p.vx;
        p.y += p.vy;

        const opacityTarget =
          state === "complete"
            ? 0.8 + Math.sin(t * 2 + p.phase) * 0.2
            : p.targetOpacity;
        p.opacity += (opacityTarget - p.opacity) * 0.05;

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
        ctx.fillStyle = config.color + Math.round(p.opacity * 255).toString(16).padStart(2, "0");
        ctx.fill();
      }

      const coreGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, coreRadius);
      coreGrad.addColorStop(0, config.color);
      coreGrad.addColorStop(0.7, config.color + "CC");
      coreGrad.addColorStop(1, config.color + "40");
      ctx.fillStyle = coreGrad;
      ctx.beginPath();
      ctx.arc(cx, cy, coreRadius, 0, Math.PI * 2);
      ctx.fill();

      if (state === "working" && progress > 0) {
        ctx.strokeStyle = config.color + "80";
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(cx, cy, coreRadius + 4, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * (progress / 100));
        ctx.stroke();
      }

      if (state === "complete") {
        ctx.strokeStyle = "#00FF6660";
        ctx.lineWidth = 1.5;
        const checkSize = coreRadius * 0.5;
        ctx.beginPath();
        ctx.moveTo(cx - checkSize * 0.5, cy);
        ctx.lineTo(cx - checkSize * 0.1, cy + checkSize * 0.4);
        ctx.lineTo(cx + checkSize * 0.6, cy - checkSize * 0.4);
        ctx.stroke();
      }

      animRef.current = requestAnimationFrame(animate);
    };

    animRef.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(animRef.current);
  }, [state, size, getStateConfig, progress]);

  const stateLabels: Record<OrbState, string> = {
    idle: "Available",
    listening: "Listening",
    planning: "Planning",
    working: "Working",
    multi_agent: "Multi-Agent",
    waiting: "Waiting",
    needs_approval: "YOUR APPROVAL",
    error: "Error",
    recovering: "Recovering",
    complete: "Complete",
  };

  return (
    <div
      style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6, cursor: interactive ? "pointer" : "default" }}
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
        <canvas
          ref={canvasRef}
          style={{ width: size, height: size, display: "block" }}
        />
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
            color: getStateConfig(state).color,
            letterSpacing: "0.1em",
            textAlign: "center",
            lineHeight: 1.3,
            opacity: 0.9,
          }}
        >
          JARVIS
          <br />
          {stateLabels[state]}
          {state === "working" && progress > 0 && (
            <br />
          )}
          {state === "working" && progress > 0 && (
            <span style={{ fontSize: 8, opacity: 0.7 }}>{Math.round(progress)}%</span>
          )}
          {mission && state === "working" && (
            <span style={{ fontSize: 7, opacity: 0.5, display: "block", maxWidth: size + 20 }}>
              {mission.length > 20 ? mission.slice(0, 20) + "…" : mission}
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
