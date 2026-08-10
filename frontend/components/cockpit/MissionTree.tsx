"use client";

import React, { useState } from "react";

interface MissionNode {
  id: string;
  label: string;
  description?: string;
  status: "done" | "active" | "pending" | "error";
  progress?: number;
  children?: MissionNode[];
  evidence?: { check: string; passed: boolean; detail?: string }[];
  expanded?: boolean;
}

interface MissionTreeProps {
  mission?: string;
  objective?: string;
  tree?: MissionNode[];
  onNodeClick?: (node: MissionNode) => void;
}

function MissionNodeComponent({
  node,
  depth = 0,
  onNodeClick,
  onToggle,
}: {
  node: MissionNode;
  depth?: number;
  onNodeClick?: (node: MissionNode) => void;
  onToggle?: (id: string) => void;
}) {
  const [expanded, setExpanded] = useState(node.status === "active" || depth < 1);
  const hasChildren = node.children && node.children.length > 0;

  const getStatusColor = (status: string) => {
    switch (status) {
      case "done": return "#00FF66";
      case "active": return "#FFB300";
      case "error": return "#EF4444";
      default: return "#333";
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "done": return "✓";
      case "active": return "●";
      case "error": return "✗";
      default: return "○";
    }
  };

  return (
    <div style={{ paddingLeft: depth > 0 ? 12 : 0 }}>
      <div
        onClick={() => {
          if (hasChildren) {
            setExpanded(!expanded);
            onToggle?.(node.id);
          }
          onNodeClick?.(node);
        }}
        style={{
          display: "flex",
          alignItems: "flex-start",
          gap: 6,
          padding: "4px 8px",
          cursor: hasChildren ? "pointer" : "default",
          borderRadius: 3,
          background: node.status === "active" ? "rgba(255,179,0,0.02)" : "transparent",
          transition: "background 0.15s",
          borderLeft: depth > 0 ? "1px solid rgba(255,255,255,0.03)" : "none",
        }}
      >
        {hasChildren && (
          <span style={{
            fontSize: 6,
            color: "#444",
            marginTop: 3,
            width: 8,
            textAlign: "center",
            transition: "transform 0.2s",
            transform: expanded ? "rotate(90deg)" : "rotate(0deg)",
          }}>
            ▶
          </span>
        )}
        {!hasChildren && <span style={{ width: 8 }} />}
        <span style={{
          fontSize: 8,
          color: getStatusColor(node.status),
          width: 10,
          textAlign: "center",
          marginTop: 1,
        }}>
          {getStatusIcon(node.status)}
        </span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            fontSize: 8,
            color: node.status === "active" ? "#ccc" : node.status === "done" ? "#444" : "#333",
            fontWeight: node.status === "active" ? 500 : 400,
            lineHeight: 1.3,
          }}>
            {node.label}
          </div>
          {node.progress !== undefined && node.status === "active" && (
            <div style={{
              width: "100%",
              height: 2,
              background: "#111",
              borderRadius: 1,
              marginTop: 3,
              overflow: "hidden",
            }}>
              <div style={{
                width: `${Math.round(node.progress)}%`,
                height: "100%",
                background: "linear-gradient(90deg, #00FF66, #00B4D8)",
                borderRadius: 1,
                transition: "width 0.3s ease",
              }} />
            </div>
          )}
          {node.evidence && node.evidence.length > 0 && expanded && (
            <div style={{
              marginTop: 4,
              paddingLeft: 6,
              borderLeft: "1px solid rgba(255,255,255,0.03)",
            }}>
              {node.evidence.map((ev, i) => (
                <div key={i} style={{
                  fontSize: 6,
                  color: ev.passed ? "#00FF6660" : "#EF444480",
                  padding: "1px 0",
                  display: "flex",
                  alignItems: "center",
                  gap: 3,
                }}>
                  <span>{ev.passed ? "✓" : "✗"}</span>
                  <span>{ev.check}</span>
                  {ev.detail && <span style={{ color: "#333" }}>({ev.detail})</span>}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
      {expanded && hasChildren && (
        <div>
          {node.children!.map((child) => (
            <MissionNodeComponent
              key={child.id}
              node={child}
              depth={depth + 1}
              onNodeClick={onNodeClick}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default function MissionTree({
  mission = "",
  objective = "",
  tree = [],
  onNodeClick,
}: MissionTreeProps) {
  return (
    <div style={{
      width: 240,
      display: "flex",
      flexDirection: "column",
      overflow: "hidden",
      position: "relative",
    }}>
      <div style={{
        padding: "10px 12px",
        borderBottom: "1px solid rgba(255,255,255,0.03)",
      }}>
        <div style={{
          fontSize: 6, color: "#444", letterSpacing: "0.12em",
          marginBottom: 4, textTransform: "uppercase",
        }}>
          Mission
        </div>
        <div style={{ fontSize: 10, color: "#ccc", fontWeight: 500, lineHeight: 1.4 }}>
          {mission || "No active mission"}
        </div>
        {objective && mission && (
          <div style={{ fontSize: 7, color: "#555", marginTop: 4, lineHeight: 1.3 }}>
            {objective}
          </div>
        )}
      </div>
      <div style={{ flex: 1, overflowY: "auto", padding: "6px 0" }}>
        {tree.length === 0 && (
          <div style={{
            padding: "12px 12px",
            fontSize: 7, color: "#333", lineHeight: 1.4,
          }}>
            Define a mission to see the execution tree.
          </div>
        )}
        {tree.map((node) => (
          <MissionNodeComponent
            key={node.id}
            node={node}
            onNodeClick={onNodeClick}
          />
        ))}
      </div>
    </div>
  );
}

export type { MissionNode };
