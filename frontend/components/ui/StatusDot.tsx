"use client";

interface StatusDotProps {
  status: "online" | "offline" | "warning" | "error";
  size?: "sm" | "md" | "lg";
  pulse?: boolean;
}

const statusColors = {
  online: "bg-accent-green shadow-[0_0_8px_rgba(52,211,153,0.5)]",
  offline: "bg-gray-600",
  warning: "bg-accent-amber shadow-[0_0_8px_rgba(245,158,11,0.5)]",
  error: "bg-accent-red shadow-[0_0_8px_rgba(239,68,68,0.5)]",
};

const sizes = {
  sm: "w-2 h-2",
  md: "w-2.5 h-2.5",
  lg: "w-3 h-3",
};

export default function StatusDot({ status, size = "md", pulse = false }: StatusDotProps) {
  return (
    <span className="relative inline-flex">
      <span className={`rounded-full ${sizes[size]} ${statusColors[status]}`} />
      {pulse && status === "online" && (
        <span className={`absolute inset-0 rounded-full ${sizes[size]} bg-accent-green animate-ping opacity-75`} />
      )}
    </span>
  );
}
