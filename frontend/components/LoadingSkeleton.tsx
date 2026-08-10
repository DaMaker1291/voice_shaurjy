"use client";
export function SkeletonLine({ className = "", width = "100%", height = "16px" }: { className?: string; width?: string; height?: string }) {
  return <div className={`animate-pulse bg-gray-800/50 rounded ${className}`} style={{ width, height }} />;
}
export function SkeletonCard({ lines = 3 }: { lines?: number }) {
  return (
    <div className="bg-gray-900/50 border border-gray-800 rounded-xl p-4 space-y-3">
      <SkeletonLine width="60%" height="20px" />
      {Array.from({ length: lines }).map((_, i) => (
        <SkeletonLine key={i} width={`${70 + Math.random() * 30}%`} />
      ))}
    </div>
  );
}
export function PageSkeleton() {
  return (
    <div className="space-y-6 p-6">
      <SkeletonLine width="200px" height="28px" className="mb-6" />
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <SkeletonCard lines={2} /><SkeletonCard lines={2} /><SkeletonCard lines={2} />
      </div>
      <SkeletonCard lines={5} />
    </div>
  );
}
