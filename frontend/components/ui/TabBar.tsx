"use client";

interface TabBarProps {
  tabs: { id: string; label: string; icon?: string }[];
  active: string;
  onChange: (id: string) => void;
}

export default function TabBar({ tabs, active, onChange }: TabBarProps) {
  return (
    <div className="flex gap-1 border-b border-white/5 overflow-x-auto pb-0 scrollbar-none">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onChange(tab.id)}
          className={`
            px-4 py-2 text-xs font-mono whitespace-nowrap transition-all duration-200
            border-b-2 -mb-px
            ${
              active === tab.id
                ? "text-accent-purple border-accent-purple"
                : "text-gray-600 border-transparent hover:text-gray-400 hover:border-white/10"
            }
          `}
        >
          {tab.icon && <span className="mr-1.5">{tab.icon}</span>}
          {tab.label}
        </button>
      ))}
    </div>
  );
}
