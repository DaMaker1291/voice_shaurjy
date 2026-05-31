"use client";

import { useState, useEffect } from "react";

export default function UsageMeter() {
  const [used, setUsed] = useState(0);
  const limit = 15;

  useEffect(() => {
    const stored = localStorage.getItem("voice_mins_used");
    if (stored) setUsed(parseFloat(stored));
    const interval = setInterval(() => {
      const mins = parseFloat(localStorage.getItem("voice_mins_used") || "0");
      setUsed(mins);
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  const pct = Math.min((used / limit) * 100, 100);

  return (
    <div className="bg-gray-900 rounded-xl p-4">
      <h2 className="text-lg font-semibold mb-2">Daily Usage</h2>
      <div className="w-full bg-gray-700 rounded-full h-3">
        <div
          className="bg-purple-500 h-3 rounded-full transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="text-sm text-gray-400 mt-1">
        {used.toFixed(1)} / {limit} min used
        {pct >= 100 && (
          <span className="text-red-400 block mt-1">
            Limit reached. Upgrade to Premium for unlimited access.
          </span>
        )}
      </p>
    </div>
  );
}
