"use client";

interface EmptyStateProps {
  icon: string;
  title: string;
  description?: string;
}

export default function EmptyState({ icon, title, description }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="text-5xl mb-4 opacity-30">{icon}</div>
      <h3 className="text-sm font-semibold text-gray-400 mb-1">{title}</h3>
      {description && (
        <p className="text-xs text-gray-600 max-w-sm">{description}</p>
      )}
    </div>
  );
}
