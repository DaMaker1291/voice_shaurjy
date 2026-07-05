"use client";

import { useRef, useEffect, useState } from "react";

interface Device {
  id: string;
  name: string;
  device_type: string;
  ip: string;
  is_online: boolean;
}

interface PulseMapProps {
  devices: Device[];
  size?: number;
}

const TYPE_COLORS: Record<string, string> = {
  ROUTER: "#667085",
  SWITCH: "#00FF66",
  PRINTER: "#FFB300",
  PHONE: "#00FF66",
  SENSOR: "#667085",
  HUB: "#667085",
  LIGHT: "#FFB300",
  THERMOSTAT: "#FF3333",
  LOCK: "#00FF66",
  CAMERA: "#FFB300",
  VACUUM: "#667085",
  MEDIA_PLAYER: "#00FF66",
  COVER: "#667085",
};

export default function PulseMap({ devices, size = 360 }: PulseMapProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const frameRef = useRef<number>(0);
  const [hoveredDevice, setHoveredDevice] = useState<Device | null>(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });

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
    const maxR = size / 2 - 20;

    let time = 0;
    let sweepAngle = 0;

    // Position devices in concentric rings by type
    const devicePositions = devices.map((d, i) => {
      const typeOrder = ["ROUTER", "SWITCH", "PRINTER", "PHONE", "SENSOR", "HUB", "LIGHT", "CAMERA", "VACUUM", "MEDIA_PLAYER"];
      const ring = typeOrder.indexOf(d.device_type) >= 0 ? typeOrder.indexOf(d.device_type) : 5;
      const r = 40 + (ring / 9) * (maxR - 50);
      const angle = (i / devices.length) * Math.PI * 2 - Math.PI / 2;
      return {
        ...d,
        x: cx + Math.cos(angle) * r,
        y: cy + Math.sin(angle) * r,
        angle,
        r,
        color: TYPE_COLORS[d.device_type] || "#667085",
      };
    });

    const draw = () => {
      time += 0.016;
      sweepAngle += 0.008;
      if (sweepAngle > Math.PI * 2) sweepAngle -= Math.PI * 2;

      ctx.clearRect(0, 0, size, size);

      // Background
      ctx.fillStyle = "#030303";
      ctx.fillRect(0, 0, size, size);

      // Concentric rings
      for (let i = 1; i <= 5; i++) {
        const r = (i / 5) * maxR;
        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(0,255,102,${0.04 + i * 0.01})`;
        ctx.lineWidth = 0.5;
        ctx.stroke();
      }

      // Cross lines
      ctx.strokeStyle = "rgba(0,255,102,0.04)";
      ctx.lineWidth = 0.5;
      for (let a = 0; a < 4; a++) {
        const angle = (a / 4) * Math.PI * 2;
        ctx.beginPath();
        ctx.moveTo(cx, cy);
        ctx.lineTo(cx + Math.cos(angle) * maxR, cy + Math.sin(angle) * maxR);
        ctx.stroke();
      }

      // Sweep arc
      const sweepGrad = ctx.createConicGradient(sweepAngle - 0.4, cx, cy);
      sweepGrad.addColorStop(0, "rgba(0,255,102,0)");
      sweepGrad.addColorStop(0.06, "rgba(0,255,102,0)");
      sweepGrad.addColorStop(0.08, "rgba(0,255,102,0.12)");
      sweepGrad.addColorStop(0.1, "rgba(0,255,102,0)");
      sweepGrad.addColorStop(1, "rgba(0,255,102,0)");

      ctx.fillStyle = sweepGrad;
      ctx.beginPath();
      ctx.arc(cx, cy, maxR, 0, Math.PI * 2);
      ctx.fill();

      // Sweep line
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.lineTo(cx + Math.cos(sweepAngle) * maxR, cy + Math.sin(sweepAngle) * maxR);
      ctx.strokeStyle = "rgba(0,255,102,0.25)";
      ctx.lineWidth = 1;
      ctx.stroke();

      // Connection lines from center to each device
      devicePositions.forEach((d) => {
        const alpha = d.is_online ? 0.08 + Math.sin(time * 2 + d.angle * 3) * 0.04 : 0.03;
        ctx.beginPath();
        ctx.moveTo(cx, cy);
        ctx.lineTo(d.x, d.y);
        ctx.strokeStyle = `${d.color}${Math.round(alpha * 255).toString(16).padStart(2, "0")}`;
        ctx.lineWidth = 0.5;
        ctx.setLineDash([2, 4]);
        ctx.stroke();
        ctx.setLineDash([]);
      });

      // Device nodes
      devicePositions.forEach((d) => {
        const pulse = Math.sin(time * 3 + d.angle * 2) * 0.5 + 0.5;
        const nodeSize = d.is_online ? 3 + pulse * 2 : 2;

        // Glow
        if (d.is_online) {
          const glow = ctx.createRadialGradient(d.x, d.y, 0, d.x, d.y, 12);
          glow.addColorStop(0, `${d.color}30`);
          glow.addColorStop(1, `${d.color}00`);
          ctx.fillStyle = glow;
          ctx.beginPath();
          ctx.arc(d.x, d.y, 12, 0, Math.PI * 2);
          ctx.fill();
        }

        // Node
        ctx.beginPath();
        ctx.arc(d.x, d.y, nodeSize, 0, Math.PI * 2);
        ctx.fillStyle = d.is_online ? d.color : "#667085";
        ctx.fill();

        // Label (only on hover proximity)
        const dx = mousePos.x - d.x;
        const dy = mousePos.y - d.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 40) {
          ctx.font = "9px monospace";
          ctx.fillStyle = "rgba(255,255,255,0.8)";
          ctx.textAlign = "center";
          ctx.fillText(d.name, d.x, d.y - 10);
          ctx.font = "7px monospace";
          ctx.fillStyle = "rgba(255,255,255,0.4)";
          ctx.fillText(d.ip, d.x, d.y - 2);
        }
      });

      // Center hub
      const hubPulse = Math.sin(time * 2) * 0.3 + 0.7;
      ctx.beginPath();
      ctx.arc(cx, cy, 4, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(0,255,102,${hubPulse})`;
      ctx.fill();
      const hubGlow = ctx.createRadialGradient(cx, cy, 0, cx, cy, 16);
      hubGlow.addColorStop(0, `rgba(0,255,102,${0.15 * hubPulse})`);
      hubGlow.addColorStop(1, "rgba(0,255,102,0)");
      ctx.fillStyle = hubGlow;
      ctx.beginPath();
      ctx.arc(cx, cy, 16, 0, Math.PI * 2);
      ctx.fill();

      // Ring count label
      ctx.font = "8px monospace";
      ctx.fillStyle = "rgba(102,112,133,0.5)";
      ctx.textAlign = "center";
      ctx.fillText(`NET Pulse: ${devices.length} nodes`, cx, size - 8);

      frameRef.current = requestAnimationFrame(draw);
    };

    draw();
    return () => cancelAnimationFrame(frameRef.current);
  }, [devices, size, mousePos]);

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    setMousePos({ x, y });

    const cx = size / 2;
    const cy = size / 2;
    const maxR = size / 2 - 20;

    const found = devices.find((d, i) => {
      const typeOrder = ["ROUTER", "SWITCH", "PRINTER", "PHONE", "SENSOR", "HUB", "LIGHT", "CAMERA", "VACUUM", "MEDIA_PLAYER"];
      const ring = typeOrder.indexOf(d.device_type) >= 0 ? typeOrder.indexOf(d.device_type) : 5;
      const r = 40 + (ring / 9) * (maxR - 50);
      const angle = (i / devices.length) * Math.PI * 2 - Math.PI / 2;
      const dx = x - (cx + Math.cos(angle) * r);
      const dy = y - (cy + Math.sin(angle) * r);
      return Math.sqrt(dx * dx + dy * dy) < 15;
    });
    setHoveredDevice(found || null);
  };

  return (
    <div style={{ position: "relative" }}>
      <canvas
        ref={canvasRef}
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setHoveredDevice(null)}
        style={{ width: size, height: size, cursor: "crosshair", borderRadius: 4, border: "1px solid var(--border)" }}
      />
      {hoveredDevice && (
        <div style={{
          position: "absolute", bottom: 30, left: "50%", transform: "translateX(-50%)",
          padding: "5px 10px", borderRadius: 3, fontSize: 9, fontFamily: "var(--font-mono)",
          background: "var(--surface)", border: "1px solid var(--border)", color: "var(--text-primary)",
          whiteSpace: "nowrap", pointerEvents: "none", zIndex: 10,
        }}>
          <span style={{ color: TYPE_COLORS[hoveredDevice.device_type] || "#667085" }}>{hoveredDevice.name}</span>
          <span style={{ color: "var(--text-muted)", marginLeft: 6 }}>{hoveredDevice.ip}</span>
          <span style={{ color: hoveredDevice.is_online ? "var(--neon-green)" : "var(--crimson)", marginLeft: 6 }}>{hoveredDevice.is_online ? "ONLINE" : "OFFLINE"}</span>
        </div>
      )}
    </div>
  );
}
