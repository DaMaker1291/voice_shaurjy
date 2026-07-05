"use client";

import React from "react";

interface MarkdownProps {
  content: string;
  style?: React.CSSProperties;
}

function parseInline(text: string): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  let remaining = text;
  let key = 0;

  while (remaining.length > 0) {
    // Bold: **text** or __text__
    const boldMatch = remaining.match(/^(.*?)\*\*(.+?)\*\*(.*)$/) || remaining.match(/^(.*?)__(.+?)__(.*)$/);
    if (boldMatch) {
      if (boldMatch[1]) parts.push(<span key={key++}>{boldMatch[1]}</span>);
      parts.push(<strong key={key++} style={{ color: "var(--text-primary)", fontWeight: 600 }}>{boldMatch[2]}</strong>);
      remaining = boldMatch[3];
      continue;
    }

    // Italic: *text* or _text_
    const italicMatch = remaining.match(/^(.*?)\*(.+?)\*(.*)$/) || remaining.match(/^(.*?)_(.+?)_(.*)$/);
    if (italicMatch) {
      if (italicMatch[1]) parts.push(<span key={key++}>{italicMatch[1]}</span>);
      parts.push(<em key={key++} style={{ color: "var(--text-secondary)", fontStyle: "italic" }}>{italicMatch[2]}</em>);
      remaining = italicMatch[3];
      continue;
    }

    // Inline code: `text`
    const codeMatch = remaining.match(/^(.*?)`(.+?)`(.*)$/);
    if (codeMatch) {
      if (codeMatch[1]) parts.push(<span key={key++}>{codeMatch[1]}</span>);
      parts.push(
        <code key={key++} style={{
          padding: "1px 5px", borderRadius: 3, fontSize: "0.9em",
          background: "var(--surface-raised)", border: "1px solid var(--border)",
          color: "var(--neon-green)", fontFamily: "var(--font-mono)",
        }}>{codeMatch[2]}</code>
      );
      remaining = codeMatch[3];
      continue;
    }

    // Link: [text](url)
    const linkMatch = remaining.match(/^(.*?)\[(.+?)\]\((.+?)\)(.*)$/);
    if (linkMatch) {
      if (linkMatch[1]) parts.push(<span key={key++}>{linkMatch[1]}</span>);
      parts.push(
        <a key={key++} href={linkMatch[3]} target="_blank" rel="noopener noreferrer" style={{
          color: "var(--neon-green)", textDecoration: "none",
          borderBottom: "1px solid rgba(0,255,102,0.3)",
        }}>{linkMatch[2]}</a>
      );
      remaining = linkMatch[4];
      continue;
    }

    // No more matches, push rest
    parts.push(<span key={key++}>{remaining}</span>);
    break;
  }

  return parts;
}

export default function Markdown({ content, style }: MarkdownProps) {
  const lines = content.split("\n");
  const elements: React.ReactNode[] = [];
  let i = 0;
  let key = 0;

  while (i < lines.length) {
    const line = lines[i];

    // Code block: ```lang\n...\n```
    if (line.trimStart().startsWith("```")) {
      const lang = line.trimStart().slice(3).trim();
      const codeLines: string[] = [];
      i++;
      while (i < lines.length && !lines[i].trimStart().startsWith("```")) {
        codeLines.push(lines[i]);
        i++;
      }
      i++; // skip closing ```
      elements.push(
        <div key={key++} style={{
          margin: "8px 0", borderRadius: 4, overflow: "hidden",
          border: "1px solid var(--border)", background: "#080a0d",
        }}>
          {lang && (
            <div style={{
              padding: "4px 10px", fontSize: 8, fontFamily: "var(--font-mono)",
              color: "var(--steel)", borderBottom: "1px solid var(--border)",
              letterSpacing: "0.08em", textTransform: "uppercase",
            }}>{lang}</div>
          )}
          <pre style={{
            margin: 0, padding: "10px 12px", fontSize: 11, lineHeight: 1.5,
            fontFamily: "var(--font-mono)", color: "var(--text-secondary)",
            overflowX: "auto", whiteSpace: "pre",
          }}>{codeLines.join("\n")}</pre>
        </div>
      );
      continue;
    }

    // Header: ### text
    const headerMatch = line.match(/^(#{1,3})\s+(.+)$/);
    if (headerMatch) {
      const level = headerMatch[1].length;
      elements.push(
        <div key={key++} style={{
          fontSize: level === 1 ? 14 : level === 2 ? 12 : 11,
          fontWeight: 700, color: "var(--text-primary)",
          marginTop: level === 1 ? 12 : 8, marginBottom: 4,
          fontFamily: "var(--font-mono)", letterSpacing: "0.02em",
        }}>{parseInline(headerMatch[2])}</div>
      );
      i++;
      continue;
    }

    // List item: - text or * text or 1. text
    const listMatch = line.match(/^(\s*)([-*]|\d+\.)\s+(.+)$/);
    if (listMatch) {
      const items: string[] = [];
      while (i < lines.length) {
        const m = lines[i].match(/^(\s*)([-*]|\d+\.)\s+(.+)$/);
        if (!m) break;
        items.push(m[3]);
        i++;
      }
      elements.push(
        <div key={key++} style={{ margin: "6px 0", paddingLeft: 8 }}>
          {items.map((item, j) => (
            <div key={j} style={{
              fontSize: 12, lineHeight: 1.6, color: "var(--text-secondary)",
              display: "flex", gap: 6, fontFamily: "var(--font-mono)",
            }}>
              <span style={{ color: "var(--neon-green)", opacity: 0.5, flexShrink: 0 }}>›</span>
              <span>{parseInline(item)}</span>
            </div>
          ))}
        </div>
      );
      continue;
    }

    // Horizontal rule
    if (/^[-*_]{3,}$/.test(line.trim())) {
      elements.push(
        <hr key={key++} style={{
          border: "none", borderTop: "1px solid var(--border)",
          margin: "10px 0",
        }} />
      );
      i++;
      continue;
    }

    // Empty line
    if (line.trim() === "") {
      i++;
      continue;
    }

    // Regular paragraph
    const paraLines: string[] = [];
    while (i < lines.length && lines[i].trim() !== "" && !lines[i].trimStart().startsWith("```") && !lines[i].match(/^#{1,3}\s/) && !lines[i].match(/^(\s*)([-*]|\d+\.)\s+/) && !/^[-*_]{3,}$/.test(lines[i].trim())) {
      paraLines.push(lines[i]);
      i++;
    }
    if (paraLines.length > 0) {
      elements.push(
        <div key={key++} style={{
          fontSize: 12, lineHeight: 1.7, color: "var(--text-secondary)",
          margin: "4px 0", fontFamily: "var(--font-mono)",
        }}>{parseInline(paraLines.join(" "))}</div>
      );
    }
  }

  return <div style={style}>{elements}</div>;
}
