"use client";

import { ReactNode } from "react";

interface GlassCardProps {
  children: ReactNode;
  className?: string;
  hover?: boolean;
  onClick?: () => void;
}

export default function GlassCard({
  children,
  className = "",
  hover = false,
  onClick,
}: GlassCardProps) {
  return (
    <div
      onClick={onClick}
      className={`
        relative rounded-2xl overflow-hidden
        bg-cyber-600/60 backdrop-blur-xl
        border border-jarvis-400/10
        shadow-lg shadow-black/30
        transition-all duration-300 ease-out
        ${hover ? "hover:border-jarvis-400/25 hover:shadow-jarvis-500/10 hover:shadow-xl hover:-translate-y-0.5 cursor-pointer" : ""}
        ${className}
      `}
    >
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-jarvis-400/20 to-transparent" />
      {children}
    </div>
  );
}
