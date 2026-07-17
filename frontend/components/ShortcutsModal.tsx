"use client";

import { useEffect, useState } from "react";

interface Props { onClose: () => void; }

const shortcuts = [
  { category: "Navigation", items: [
    { keys: ["⌘", "K"], desc: "Open command palette" },
    { keys: ["⌘", "1"], desc: "Go to Chat" },
    { keys: ["⌘", "2"], desc: "Go to Agents" },
    { keys: ["⌘", "3"], desc: "Go to Devices" },
    { keys: ["⌘", "4"], desc: "Go to Feed" },
  ]},
  { category: "Chat", items: [
    { keys: ["⌘", "/"], desc: "Focus chat input" },
    { keys: ["Enter"], desc: "Send message" },
    { keys: ["Shift", "Enter"], desc: "New line in input" },
    { keys: ["⌘", "Esc"], desc: "Clear chat / New chat" },
    { keys: ["Esc"], desc: "Close modal/palette" },
  ]},
  { category: "Device Control", items: [
    { keys: ["scan"], desc: "Discover all network devices" },
    { keys: ["alexa discover"], desc: "Find Echo devices" },
    { keys: ["turn on/off"], desc: "Control smart plugs" },
    { keys: ["set credentials"], desc: "Store Tapo login" },
  ]},
  { category: "Autonomous Agents", items: [
    { keys: ["check email"], desc: "Run email agent" },
    { keys: ["check flights"], desc: "Run flight agent" },
    { keys: ["summarize day"], desc: "Run summary agent" },
    { keys: ["stop"], desc: "Stop running agent" },
  ]},
];

export default function ShortcutsModal({ onClose }: Props) {
  const [visible, setVisible] = useState(false);
  const [isMac, setIsMac] = useState(true);

  useEffect(() => {
    setIsMac(/mac/i.test(navigator.userAgent));
    setTimeout(() => setVisible(true), 10);
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  const mod = isMac ? "⌘" : "Ctrl";

  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed", inset: 0, zIndex: 10000,
        background: "rgba(3,3,3,0.85)", backdropFilter: "blur(8px)",
        display: "flex", alignItems: "center", justifyContent: "center",
        opacity: visible ? 1 : 0, transition: "opacity 0.2s",
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        className="modal-container"
        style={{
          width: 520, maxHeight: "80vh", overflow: "auto",
          background: "#0d0f12", border: "1px solid rgba(0,255,102,0.15)",
          borderRadius: 12, padding: 24,
          transform: visible ? "translateY(0) scale(1)" : "translateY(12px) scale(0.97)",
          transition: "transform 0.25s cubic-bezier(0.16,1,0.3,1)",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
          <div>
            <div style={{ fontSize: 14, fontWeight: 600, color: "#e5e5e5" }}>Keyboard Shortcuts</div>
            <div style={{ fontSize: 9, color: "#667085", marginTop: 2 }}>Master every shortcut</div>
          </div>
          <button onClick={onClose} style={{
            padding: "4px 10px", borderRadius: 4, fontSize: 10, fontFamily: "inherit",
            background: "#1a1d23", color: "#667085", border: "1px solid #252830", cursor: "pointer",
          }}>
            ESC
          </button>
        </div>

        {shortcuts.map(section => (
          <div key={section.category} style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 9, fontWeight: 600, color: "#00FF66", letterSpacing: "0.1em", marginBottom: 8 }}>
              {section.category.toUpperCase()}
            </div>
            {section.items.map((item, i) => (
              <div key={i} style={{
                display: "flex", alignItems: "center", justifyContent: "space-between",
                padding: "6px 0", borderBottom: i < section.items.length - 1 ? "1px solid #1a1d23" : "none",
              }}>
                <span style={{ fontSize: 11, color: "#9ca3af" }}>{item.desc}</span>
                <div style={{ display: "flex", gap: 3 }}>
                  {item.keys.map(k => (
                    <span key={k} style={{
                      padding: "2px 6px", borderRadius: 3, fontSize: 9,
                      background: "#1a1d23", border: "1px solid #252830", color: "#e5e5e5",
                      fontFamily: "inherit", minWidth: 20, textAlign: "center",
                    }}>
                      {k === "⌘" ? mod : k}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
