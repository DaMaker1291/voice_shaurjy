"use client";

import React, { useRef, useEffect, useState, useCallback } from "react";

interface Skill {
  name: string;
  used?: number;
  successRate: number;
  category: string;
  lastUsed?: string;
  description?: string;
}

interface CapabilityFieldProps {
  skills: Skill[];
  onSkillClick?: (skill: Skill) => void;
}

interface Node {
  x: number;
  y: number;
  label: string;
  category: string;
  radius: number;
  connections: number[];
  pulse: number;
  active: boolean;
}

export default function CapabilityField({ skills = [], onSkillClick }: CapabilityFieldProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animRef = useRef<number>(0);
  const timeRef = useRef(0);
  const [nodes, setNodes] = useState<Node[]>([]);
  const [hoveredNode, setHoveredNode] = useState<number | null>(null);
  const [selectedNode, setSelectedNode] = useState<number | null>(null);

  useEffect(() => {
    const baseNodes: Omit<Node, "x" | "y">[] = [
      { label: "JARVIS", category: "core", radius: 18, connections: [1, 2, 3, 4, 5, 6], pulse: 0, active: true },
      { label: "Design", category: "creative", radius: 10, connections: [0, 7, 8], pulse: 0, active: skills.some(s => s.category === "creative") },
      { label: "Code", category: "dev", radius: 10, connections: [0, 9, 10], pulse: 0, active: skills.some(s => s.category === "dev") },
      { label: "Research", category: "analysis", radius: 10, connections: [0, 11], pulse: 0, active: skills.some(s => s.category === "research") },
      { label: "Business", category: "analysis", radius: 10, connections: [0, 12, 13], pulse: 0, active: skills.some(s => s.category === "business") },
      { label: "Media", category: "creative", radius: 10, connections: [0, 14], pulse: 0, active: skills.some(s => s.category === "media") },
      { label: "Office", category: "productivity", radius: 10, connections: [0, 15], pulse: 0, active: skills.some(s => s.category === "office") },
      { label: "Photoshop", category: "creative", radius: 6, connections: [1], pulse: 0, active: false },
      { label: "Branding", category: "creative", radius: 6, connections: [1], pulse: 0, active: false },
      { label: "Frontend", category: "dev", radius: 6, connections: [2], pulse: 0, active: false },
      { label: "Backend", category: "dev", radius: 6, connections: [2], pulse: 0, active: false },
      { label: "Search", category: "research", radius: 6, connections: [3], pulse: 0, active: false },
      { label: "Finance", category: "business", radius: 6, connections: [4], pulse: 0, active: false },
      { label: "Planning", category: "business", radius: 6, connections: [4], pulse: 0, active: false },
      { label: "Blender", category: "media", radius: 6, connections: [5], pulse: 0, active: false },
      { label: "Docs", category: "productivity", radius: 6, connections: [6], pulse: 0, active: false },
    ];
    setNodes(baseNodes.map(n => ({ ...n, x: 0, y: 0 })));
  }, [skills]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const parent = canvas.parentElement;
    if (!parent) return;
    const w = parent.clientWidth;
    const h = parent.clientHeight;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = `${w}px`;
    canvas.style.height = `${h}px`;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.scale(dpr, dpr);
    const cx = w / 2;
    const cy = h / 2;
    const orbitRadius = Math.min(w, h) * 0.32;
    const positioned = nodes.map((n, i) => {
      if (i === 0) return { ...n, x: cx, y: cy };
      const groupIndex = Math.floor((i - 1) / 3);
      const posInGroup = (i - 1) % 3;
      const groupAngle = (Math.PI * 2 * groupIndex) / 6 - Math.PI / 2;
      const spreadAngle = (posInGroup - 1) * 0.25;
      const angle = groupAngle + spreadAngle;
      const r = orbitRadius + (posInGroup === 1 ? -15 : posInGroup === 0 ? 10 : 20);
      return { ...n, x: cx + Math.cos(angle) * r, y: cy + Math.sin(angle) * r };
    });
    setNodes(positioned);
  }, [nodes.length]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const animate = () => {
      timeRef.current += 0.016;
      const t = timeRef.current;
      const dpr = window.devicePixelRatio || 1;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const w = canvas.width / dpr;
      const h = canvas.height / dpr;
      ctx.clearRect(0, 0, w, h);
      for (const node of nodes) {
        for (const connIdx of node.connections) {
          if (connIdx >= nodes.length) continue;
          const target = nodes[connIdx];
          ctx.beginPath();
          ctx.moveTo(node.x, node.y);
          ctx.lineTo(target.x, target.y);
          ctx.strokeStyle = node.active && target.active
            ? `rgba(0,255,102,${0.08 + Math.sin(t + node.x * 0.01) * 0.04})`
            : "rgba(255,255,255,0.02)";
          ctx.lineWidth = node.active && target.active ? 1 : 0.5;
          ctx.stroke();
          if (node.active && target.active) {
            const progress = (t * 0.3 + node.x * 0.001) % 1;
            const px = node.x + (target.x - node.x) * progress;
            const py = node.y + (target.y - node.y) * progress;
            ctx.beginPath();
            ctx.arc(px, py, 1.5, 0, Math.PI * 2);
            ctx.fillStyle = "rgba(0,255,102,0.6)";
            ctx.fill();
          }
        }
      }
      for (let i = 0; i < nodes.length; i++) {
        const node = nodes[i];
        const isHovered = hoveredNode === i;
        const isSelected = selectedNode === i;
        const breathe = Math.sin(t * 2 + i) * 0.1 + 1;
        const r = (isHovered ? node.radius * 1.3 : node.radius) * breathe;
        const color = node.category === "core" ? "#00FF66"
          : node.active ? "#00B4D8"
          : "#333";
        ctx.beginPath();
        ctx.arc(node.x, node.y, r + 4, 0, Math.PI * 2);
        ctx.fillStyle = color + "15";
        ctx.fill();
        ctx.beginPath();
        ctx.arc(node.x, node.y, r, 0, Math.PI * 2);
        const grad = ctx.createRadialGradient(node.x, node.y, 0, node.x, node.y, r);
        grad.addColorStop(0, node.active ? color : "#222");
        grad.addColorStop(1, node.active ? color + "80" : "#111");
        ctx.fillStyle = grad;
        ctx.fill();
        if (isHovered || isSelected) {
          ctx.beginPath();
          ctx.arc(node.x, node.y, r + 3, 0, Math.PI * 2);
          ctx.strokeStyle = "rgba(0,255,102,0.4)";
          ctx.lineWidth = 1;
          ctx.stroke();
        }
        if (node.category === "core" || r > 8) {
          ctx.fillStyle = node.active ? "#000" : "#555";
          ctx.font = `${Math.max(6, Math.min(9, r * 0.6))}px "JetBrains Mono", monospace`;
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          ctx.fillText(node.label, node.x, node.y);
        }
      }
      animRef.current = requestAnimationFrame(animate);
    };
    animRef.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(animRef.current);
  }, [nodes, hoveredNode, selectedNode]);

  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    let found = null;
    for (let i = 0; i < nodes.length; i++) {
      const dx = nodes[i].x - mx;
      const dy = nodes[i].y - my;
      if (Math.sqrt(dx * dx + dy * dy) < nodes[i].radius + 5) {
        found = i;
        break;
      }
    }
    setHoveredNode(found);
  }, [nodes]);

  const handleClick = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    if (hoveredNode !== null) {
      setSelectedNode(hoveredNode === selectedNode ? null : hoveredNode);
      const skill = skills.find(s => s.name === nodes[hoveredNode]?.label);
      if (skill && onSkillClick) onSkillClick(skill);
    } else {
      setSelectedNode(null);
    }
  }, [hoveredNode, selectedNode, nodes, skills, onSkillClick]);

  return (
    <div style={{
      flex: 1,
      display: "flex",
      flexDirection: "column",
      overflow: "hidden",
    }}>
      <div style={{
        padding: "8px 12px",
        borderBottom: "1px solid rgba(255,255,255,0.04)",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
      }}>
        <div style={{
          fontSize: 8,
          color: "#555",
          fontFamily: "'JetBrains Mono', monospace",
          letterSpacing: "0.1em",
        }}>
          CAPABILITY FIELD
        </div>
        <div style={{
          fontSize: 7,
          color: "#00B4D8",
          fontFamily: "'JetBrains Mono', monospace",
        }}>
          {skills.length} procedures learned
        </div>
      </div>
      <div style={{ flex: 1, position: "relative" }}>
        <canvas
          ref={canvasRef}
          onMouseMove={handleMouseMove}
          onMouseLeave={() => setHoveredNode(null)}
          onClick={handleClick}
          style={{
            position: "absolute",
            inset: 0,
            cursor: hoveredNode !== null ? "pointer" : "default",
          }}
        />
      </div>
    </div>
  );
}
