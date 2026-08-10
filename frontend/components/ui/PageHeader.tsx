"use client";

import { ReactNode } from "react";

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  icon?: string;
  actions?: ReactNode;
}

export default function PageHeader({
  title,
  subtitle,
  icon,
  actions,
}: PageHeaderProps) {
  return (
    <div className="flex items-center justify-between mb-6">
      <div className="flex items-center gap-3">
        {icon && (
          <div className="w-10 h-10 rounded-xl bg-jarvis-500/10 border border-jarvis-400/20 flex items-center justify-center text-lg">
            {icon}
          </div>
        )}
        <div>
          <h1 className="text-xl font-bold text-gray-100 tracking-tight">{title}</h1>
          {subtitle && (
            <p className="text-xs text-gray-500 font-mono mt-0.5">{subtitle}</p>
          )}
        </div>
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}
