"use client";

import { useState } from "react";
import Link from "next/link";

interface Capability {
  category: string;
  icon: string;
  color: string;
  items: { name: string; desc: string; example: string; icon: string }[];
}

const CAPABILITIES: Capability[] = [
  {
    category: "Travel & Flights",
    icon: "✈️",
    color: "#00B4D8",
    items: [
      { name: "Search Flights", desc: "Find the cheapest flights anywhere", example: "Find flights from NYC to London", icon: "🔍" },
      { name: "Book Flights", desc: "Complete flight booking flow", example: "Book a flight to Paris for next Friday", icon: "🎫" },
      { name: "Online Check-in", desc: "Auto check-in with boarding pass", example: "Check in for my flight", icon: "✅" },
      { name: "Flight Tracking", desc: "Real-time flight status", example: "Where's my flight BA123?", icon: "📡" },
      { name: "Hotel Search", desc: "Find and book hotels", example: "Find hotels in Tokyo for Dec 15-20", icon: "🏨" },
      { name: "Car Rental", desc: "Rent a car at your destination", example: "Rent a car in Miami for 3 days", icon: "🚗" },
      { name: "Trip Planning", desc: "Full itinerary creation", example: "Plan a 7-day trip to Italy", icon: "🗺️" },
    ],
  },
  {
    category: "Immigration & Documents",
    icon: "📋",
    color: "#A855F7",
    items: [
      { name: "Visa Requirements", desc: "Check visa needs for any country", example: "Do I need a visa for Japan?", icon: "📄" },
      { name: "Visa Application", desc: "Start visa application process", example: "Apply for a UK tourist visa", icon: "📝" },
      { name: "OCI Application", desc: "Overseas Citizen of India card", example: "Start my OCI application", icon: "🇮🇳" },
      { name: "Passport Renewal", desc: "Renew passport online", example: "Help me renew my passport", icon: "📕" },
      { name: "ESTA/ETA", desc: "Travel authorization", example: "Apply for ESTA for US travel", icon: "🌐" },
    ],
  },
  {
    category: "Email & Communication",
    icon: "📧",
    color: "#FFB300",
    items: [
      { name: "Read Emails", desc: "Scan and summarize inbox", example: "Check my email", icon: "📥" },
      { name: "Send Emails", desc: "Compose and send emails", example: "Send email to John about the meeting", icon: "📤" },
      { name: "Reply to Emails", desc: "Draft replies to emails", example: "Reply to the last email", icon: "↩️" },
      { name: "Email Triage", desc: "Prioritize and organize", example: "Triage my inbox", icon: "📊" },
      { name: "Text Messages", desc: "Read and send texts", example: "Text Sarah I'll be late", icon: "💬" },
    ],
  },
  {
    category: "Forms & Documents",
    icon: "📝",
    color: "#00FF66",
    items: [
      { name: "Fill Forms", desc: "Auto-fill any web form", example: "Fill out this application form", icon: "📋" },
      { name: "PDF Forms", desc: "Complete fillable PDFs", example: "Fill this PDF with my info", icon: "📄" },
      { name: "Sign Documents", desc: "E-sign documents", example: "Sign this contract", icon: "✍️" },
      { name: "Scan Documents", desc: "OCR and digitize", example: "Scan this document", icon: "📷" },
      { name: "Tax Forms", desc: "Help with tax paperwork", example: "Help me with my tax return", icon: "💰" },
    ],
  },
  {
    category: "Education & Homework",
    icon: "📚",
    color: "#FF3333",
    items: [
      { name: "Homework Help", desc: "Solve any homework problem", example: "Help with this math problem", icon: "🧮" },
      { name: "Essay Writing", desc: "Write essays and reports", example: "Write an essay on climate change", icon: "✍️" },
      { name: "Research", desc: "Deep research on any topic", example: "Research quantum computing", icon: "🔬" },
      { name: "Study Materials", desc: "Create flashcards and notes", example: "Make flashcards for biology", icon: "🗂️" },
      { name: "Tutoring", desc: "Explain any concept", example: "Explain how photosynthesis works", icon: "🎓" },
    ],
  },
  {
    category: "Shopping & Deals",
    icon: "🛒",
    color: "#00B4D8",
    items: [
      { name: "Find Discounts", desc: "Coupons and promo codes", example: "Find discounts for Nike", icon: "🏷️" },
      { name: "Price Compare", desc: "Compare prices everywhere", example: "Compare iPhone 16 prices", icon: "💰" },
      { name: "Product Search", desc: "Find any product", example: "Find a good standing desk", icon: "🔍" },
      { name: "Deal Alerts", desc: "Monitor prices and alert", example: "Alert me when PS5 drops to $400", icon: "🔔" },
    ],
  },
  {
    category: "Device Control",
    icon: "📡",
    color: "#F97316",
    items: [
      { name: "Smart Plugs", desc: "Control Tapo/TP-Link plugs", example: "Turn off desk lamp", icon: "💡" },
      { name: "Alexa Control", desc: "Voice commands to Echo", example: "Alexa say good morning", icon: "🔊" },
      { name: "System Monitor", desc: "CPU, memory, disk usage", example: "What's my CPU usage?", icon: "📊" },
      { name: "Screenshots", desc: "Capture any screen", example: "Take a screenshot", icon: "📷" },
      { name: "App Control", desc: "Open and control apps", example: "Open VS Code", icon: "💻" },
    ],
  },
  {
    category: "Productivity",
    icon: "⚡",
    color: "#FFB300",
    items: [
      { name: "Calendar", desc: "View and manage schedule", example: "What's on my calendar today?", icon: "📅" },
      { name: "Reminders", desc: "Set timed reminders", example: "Remind me to call mom in 2 hours", icon: "⏰" },
      { name: "Todo Lists", desc: "Manage task lists", example: "Add buy groceries to my todo", icon: "✅" },
      { name: "Notes", desc: "Take and organize notes", example: "Take a note: meeting at 3pm", icon: "📝" },
      { name: "Summarize", desc: "Summarize any content", example: "Summarize this article", icon: "📋" },
    ],
  },
];

export default function CapabilitiesPage() {
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const filtered = CAPABILITIES.filter(c =>
    !selectedCategory || c.category === selectedCategory
  ).filter(c =>
    !search || c.items.some(i => i.name.toLowerCase().includes(search.toLowerCase()) || i.desc.toLowerCase().includes(search.toLowerCase()))
  );

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column", background: "#030303", color: "#e5e5e5", fontFamily: "'JetBrains Mono', monospace" }}>
      <style jsx global>{`
        @keyframes fade-in { from { opacity:0; transform:translateY(4px); } to { opacity:1; transform:translateY(0); } }
        @keyframes card-hover { from { transform:translateY(0); } to { transform:translateY(-2px); } }
        .cf { animation: fade-in 0.2s cubic-bezier(0.16,1,0.3,1) both; }
      `}</style>

      {/* Header */}
      <header style={{ height: 40, background: "#0d0f12", borderBottom: "1px solid #1a1d23", display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 16px", flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <Link href="/" style={{ fontSize: 10, color: "#667085", textDecoration: "none" }}>← CHAT</Link>
          <div style={{ width: 1, height: 16, background: "#1a1d23" }} />
          <span style={{ fontSize: 11, color: "#00FF66", fontWeight: 600, letterSpacing: "0.08em" }}>CAPABILITIES</span>
          <span style={{ fontSize: 9, color: "#667085" }}>{CAPABILITIES.reduce((a, c) => a + c.items.length, 0)} actions</span>
        </div>
        <div style={{
          padding: "4px 10px", borderRadius: 4, fontSize: 9, fontFamily: "inherit",
          background: "rgba(0,255,102,0.1)", color: "#00FF66", border: "1px solid rgba(0,255,102,0.2)",
        }}>
          BILLION-DOLLAR AI
        </div>
      </header>

      {/* Search */}
      <div style={{ padding: "12px 16px", borderBottom: "1px solid #1a1d23" }}>
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search capabilities..."
          style={{
            width: "100%", padding: "8px 12px", borderRadius: 6, fontSize: 12,
            background: "#0d0f12", color: "#e5e5e5", fontFamily: "inherit",
            border: "1px solid #1a1d23", outline: "none",
          }}
        />
      </div>

      {/* Category Tabs */}
      <div style={{ display: "flex", gap: 4, padding: "8px 16px", borderBottom: "1px solid #1a1d23", overflow: "auto" }}>
        <button onClick={() => setSelectedCategory(null)} style={{
          padding: "4px 10px", borderRadius: 4, fontSize: 9, fontFamily: "inherit", cursor: "pointer",
          background: !selectedCategory ? "rgba(0,255,102,0.15)" : "transparent",
          color: !selectedCategory ? "#00FF66" : "#667085", border: `1px solid ${!selectedCategory ? "rgba(0,255,102,0.3)" : "#1a1d23"}`,
        }}>
          ALL
        </button>
        {CAPABILITIES.map(c => (
          <button key={c.category} onClick={() => setSelectedCategory(c.category)} style={{
            padding: "4px 10px", borderRadius: 4, fontSize: 9, fontFamily: "inherit", cursor: "pointer",
            background: selectedCategory === c.category ? `${c.color}15` : "transparent",
            color: selectedCategory === c.category ? c.color : "#667085",
            border: `1px solid ${selectedCategory === c.category ? `${c.color}40` : "#1a1d23"}`,
          }}>
            {c.icon} {c.category.toUpperCase()}
          </button>
        ))}
      </div>

      {/* Capabilities Grid */}
      <div style={{ flex: 1, overflow: "auto", padding: 16 }}>
        {filtered.map(category => (
          <div key={category.category} className="cf" style={{ marginBottom: 24 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
              <span style={{ fontSize: 18 }}>{category.icon}</span>
              <span style={{ fontSize: 13, fontWeight: 600, color: category.color }}>{category.category}</span>
              <span style={{ fontSize: 9, color: "#667085" }}>{category.items.length} actions</span>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 8 }}>
              {category.items.map(item => (
                <div key={item.name} style={{
                  padding: "12px 14px", borderRadius: 8, background: "#0d0f12",
                  border: "1px solid #1a1d23", cursor: "pointer", transition: "all 0.15s",
                  borderLeft: `3px solid ${category.color}`,
                }}
                  onMouseEnter={e => {
                    (e.currentTarget as HTMLElement).style.borderColor = `${category.color}40`;
                    (e.currentTarget as HTMLElement).style.background = "#12151a";
                  }}
                  onMouseLeave={e => {
                    (e.currentTarget as HTMLElement).style.borderColor = "#1a1d23";
                    (e.currentTarget as HTMLElement).style.background = "#0d0f12";
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                    <span style={{ fontSize: 14 }}>{item.icon}</span>
                    <span style={{ fontSize: 11, fontWeight: 500, color: "#e5e5e5" }}>{item.name}</span>
                  </div>
                  <div style={{ fontSize: 9, color: "#9ca3af", marginBottom: 6 }}>{item.desc}</div>
                  <div style={{
                    fontSize: 9, color: category.color, opacity: 0.7, fontStyle: "italic",
                    padding: "4px 8px", borderRadius: 4, background: `${category.color}08`,
                  }}>
                    "{item.example}"
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
