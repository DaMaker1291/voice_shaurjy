"use client";

import { useState, useEffect, useRef, useCallback } from "react";

interface Command {
  id: string;
  label: string;
  category: string;
  icon: string;
  action: () => void;
  shortcut?: string;
}

interface Props {
  open: boolean;
  onClose: () => void;
  onCommand: (cmd: string) => void;
}

export function CommandPalette({ open, onClose, onCommand }: Props) {
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const commands: Command[] = [
    // Navigation
    { id: "nav:chat", label: "Go to Chat", category: "Navigation", icon: "💬", action: () => { window.location.href = "/"; onClose(); } },
    { id: "nav:agents", label: "Go to Agents", category: "Navigation", icon: "🤖", action: () => { window.location.href = "/agents"; onClose(); } },
    { id: "nav:devices", label: "Go to Devices", category: "Navigation", icon: "📡", action: () => { window.location.href = "/sovereign"; onClose(); } },
    { id: "nav:feed", label: "Go to Data Feed", category: "Navigation", icon: "📋", action: () => { window.location.href = "/feed"; onClose(); } },
    { id: "nav:workspace", label: "Go to Workspace", category: "Navigation", icon: "📂", action: () => { window.location.href = "/workspace"; onClose(); } },
    { id: "nav:capabilities", label: "View All Capabilities", category: "Navigation", icon: "⚡", action: () => { window.location.href = "/capabilities"; onClose(); } },
    { id: "nav:settings", label: "Go to Settings", category: "Navigation", icon: "⚙️", action: () => { window.location.href = "/settings"; onClose(); } },

    // Device Control
    { id: "device:scan", label: "Scan All Devices", category: "Devices", icon: "🔍", action: () => { onCommand("scan everything"); onClose(); } },
    { id: "device:alexa", label: "Discover Echo Devices", category: "Devices", icon: "🔊", action: () => { onCommand("alexa discover"); onClose(); } },
    { id: "device:lights_on", label: "Turn On All Lights", category: "Devices", icon: "💡", action: () => { onCommand("turn on all lights"); onClose(); } },
    { id: "device:lights_off", label: "Turn Off All Lights", category: "Devices", icon: "💡", action: () => { onCommand("turn off all lights"); onClose(); } },

    // Alexa
    { id: "alexa:speak", label: "Alexa: Say Something", category: "Alexa", icon: "🗣", action: () => { const t = prompt("What should Alexa say?"); if (t) onCommand(`alexa say ${t}`); onClose(); } },
    { id: "alexa:play", label: "Alexa: Play Music", category: "Alexa", icon: "▶", action: () => { onCommand("alexa play"); onClose(); } },
    { id: "alexa:pause", label: "Alexa: Pause", category: "Alexa", icon: "⏸", action: () => { onCommand("alexa pause"); onClose(); } },
    { id: "alexa:volume", label: "Alexa: Set Volume", category: "Alexa", icon: "🔊", action: () => { const v = prompt("Volume (0-100):"); if (v) onCommand(`alexa volume ${v}`); onClose(); } },
    { id: "alexa:timer", label: "Alexa: Set Timer", category: "Alexa", icon: "⏰", action: () => { const t = prompt("Timer duration (e.g. 5 minutes):"); if (t) onCommand(`alexa timer ${t}`); onClose(); } },
    { id: "alexa:dnd", label: "Alexa: Do Not Disturb", category: "Alexa", icon: "🌙", action: () => { onCommand("alexa dnd on"); onClose(); } },

    // Tasks
    { id: "task:email", label: "Scan Email for Flights", category: "Tasks", icon: "📧", action: () => { onCommand("check email for flights"); onClose(); } },
    { id: "task:checkin", label: "Check In for Flight", category: "Tasks", icon: "✈️", action: () => { onCommand("check in for my flight"); onClose(); } },
    { id: "task:passport", label: "Find Passport Photos", category: "Tasks", icon: "📷", action: () => { onCommand("do I have passport photos"); onClose(); } },
    { id: "task:time", label: "What Time Is It?", category: "Tasks", icon: "🕐", action: () => { onCommand("what time is it"); onClose(); } },

    // Universal Actions
    { id: "univ:flights", label: "Search Flights", category: "Universal", icon: "✈️", action: () => { onCommand("find flights"); onClose(); } },
    { id: "univ:checkin", label: "Check-in for Flight", category: "Universal", icon: "✅", action: () => { onCommand("check in for my flight"); onClose(); } },
    { id: "univ:visa", label: "Check Visa Requirements", category: "Universal", icon: "📋", action: () => { onCommand("visa requirements for Japan"); onClose(); } },
    { id: "univ:email", label: "Check Email", category: "Universal", icon: "📧", action: () => { onCommand("check my email"); onClose(); } },
    { id: "univ:hotel", label: "Search Hotels", category: "Universal", icon: "🏨", action: () => { onCommand("find hotels"); onClose(); } },
    { id: "univ:discount", label: "Find Discounts", category: "Universal", icon: "🏷️", action: () => { onCommand("find discounts for products"); onClose(); } },
    { id: "univ:homework", label: "Homework Help", category: "Universal", icon: "📚", action: () => { onCommand("help with homework"); onClose(); } },
    { id: "univ:form", label: "Fill Form", category: "Universal", icon: "📝", action: () => { onCommand("fill out this form"); onClose(); } },
    { id: "univ:trip", label: "Plan Trip", category: "Universal", icon: "🗺️", action: () => { onCommand("plan a trip"); onClose(); } },
    { id: "univ:news", label: "Read News", category: "Universal", icon: "📰", action: () => { onCommand("what's the news today"); onClose(); } },
    { id: "univ:essay", label: "Write Essay", category: "Universal", icon: "✍️", action: () => { onCommand("write an essay"); onClose(); } },
    { id: "univ:calendar", label: "Check Calendar", category: "Universal", icon: "📅", action: () => { onCommand("what's on my calendar"); onClose(); } },

    // System
    { id: "sys:screenshot", label: "Take Screenshot", category: "System", icon: "📸", action: () => { onCommand("screenshot"); onClose(); } },
    { id: "sys:open_vscode", label: "Open VS Code", category: "System", icon: "💻", action: () => { onCommand("open VS Code"); onClose(); } },
    { id: "sys:open_terminal", label: "Open Terminal", category: "System", icon: "🖥", action: () => { onCommand("open terminal"); onClose(); } },
  ];

  const filtered = commands.filter(cmd =>
    cmd.label.toLowerCase().includes(query.toLowerCase()) ||
    cmd.category.toLowerCase().includes(query.toLowerCase())
  );

  useEffect(() => {
    if (open) {
      setQuery("");
      setSelected(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  useEffect(() => {
    setSelected(0);
  }, [query]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelected(s => Math.min(s + 1, filtered.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelected(s => Math.max(s - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (filtered[selected]) {
        filtered[selected].action();
      }
    } else if (e.key === "Escape") {
      onClose();
    }
  }, [filtered, selected, onClose]);

  if (!open) return null;

  const categories = Array.from(new Set(filtered.map(c => c.category)));

  return (
    <div
      style={{
        position: "fixed", inset: 0, zIndex: 1000,
        background: "rgba(3,3,3,0.8)", backdropFilter: "blur(8px)",
        display: "flex", alignItems: "flex-start", justifyContent: "center",
        paddingTop: "15vh",
      }}
      onClick={onClose}
    >
      <div
        onClick={e => e.stopPropagation()}
        className="modal-container"
        style={{
          width: 560, maxHeight: 420, borderRadius: 12, overflow: "hidden",
          background: "#0d0f12", border: "1px solid #1a1d23",
          boxShadow: "0 24px 80px rgba(0,0,0,0.6), 0 0 1px rgba(0,255,102,0.2)",
        }}
      >
        {/* Input */}
        <div style={{ display: "flex", alignItems: "center", padding: "12px 16px", borderBottom: "1px solid #1a1d23" }}>
          <span style={{ color: "#00FF66", marginRight: 10, fontSize: 14 }}>⌘</span>
          <input
            ref={inputRef}
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type a command..."
            style={{
              flex: 1, background: "none", border: "none", outline: "none",
              color: "#e5e5e5", fontSize: 14, fontFamily: "'JetBrains Mono', monospace",
            }}
          />
          <span style={{ fontSize: 10, color: "#667085", padding: "2px 6px", borderRadius: 3, background: "#1a1d23" }}>
            ESC
          </span>
        </div>

        {/* Results */}
        <div style={{ overflow: "auto", maxHeight: 360, padding: "8px 0" }}>
          {categories.map(cat => (
            <div key={cat}>
              <div style={{ padding: "6px 16px", fontSize: 9, color: "#667085", letterSpacing: "0.1em", fontWeight: 600 }}>
                {cat.toUpperCase()}
              </div>
              {filtered.filter(c => c.category === cat).map((cmd, i) => {
                const idx = filtered.indexOf(cmd);
                return (
                  <div
                    key={cmd.id}
                    onClick={cmd.action}
                    style={{
                      padding: "8px 16px", display: "flex", alignItems: "center", gap: 10,
                      cursor: "pointer", transition: "all 0.1s",
                      background: idx === selected ? "rgba(0,255,102,0.08)" : "transparent",
                      borderLeft: idx === selected ? "2px solid #00FF66" : "2px solid transparent",
                    }}
                    onMouseEnter={() => setSelected(idx)}
                  >
                    <span style={{ fontSize: 14, width: 24, textAlign: "center" }}>{cmd.icon}</span>
                    <span style={{ fontSize: 13, color: idx === selected ? "#00FF66" : "#e5e5e5" }}>{cmd.label}</span>
                    {cmd.shortcut && (
                      <span style={{ marginLeft: "auto", fontSize: 10, color: "#667085", padding: "2px 6px", borderRadius: 3, background: "#1a1d23" }}>
                        {cmd.shortcut}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          ))}
          {filtered.length === 0 && (
            <div style={{ padding: 24, textAlign: "center", color: "#667085", fontSize: 12 }}>
              No commands found
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
