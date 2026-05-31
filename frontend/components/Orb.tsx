"use client";

interface Props {
  listening: boolean;
  speaking: boolean;
  onClick: () => void;
}

export default function Orb({ listening, speaking, onClick }: Props) {
  const active = listening || speaking;

  return (
    <button onClick={onClick} className="relative w-64 h-64 md:w-80 md:h-80 group cursor-pointer">
      {/* Outer glow rings */}
      <div
        className={`absolute inset-0 rounded-full transition-all duration-1000 ${
          active ? "opacity-100 scale-110" : "opacity-40 scale-95"
        }`}
        style={{
          background:
            "radial-gradient(circle, rgba(168,85,247,0.15) 0%, rgba(6,182,212,0.08) 40%, transparent 70%)",
          animation: active ? "pulse-ring 2s ease-in-out infinite" : "none",
        }}
      />

      {/* Second ring */}
      <div
        className={`absolute inset-4 rounded-full transition-all duration-1000 ${
          active ? "opacity-80" : "opacity-20"
        }`}
        style={{
          background:
            "radial-gradient(circle, rgba(236,72,153,0.1) 0%, rgba(168,85,247,0.06) 50%, transparent 70%)",
          animation: active ? "pulse-ring 2.5s ease-in-out infinite 0.3s" : "none",
        }}
      />

      {/* Main orb */}
      <div
        className={`absolute inset-8 rounded-full transition-all duration-700 ${
          listening
            ? "scale-110"
            : speaking
            ? "scale-105"
            : "scale-100"
        }`}
        style={{
          background:
            "radial-gradient(circle at 35% 30%, #a855f7 0%, #6366f1 30%, #06b6d4 60%, #0f172a 100%)",
          boxShadow: active
            ? "0 0 80px rgba(168,85,247,0.4), 0 0 160px rgba(6,182,212,0.2), inset 0 0 60px rgba(168,85,247,0.1)"
            : "0 0 30px rgba(168,85,247,0.1), inset 0 0 30px rgba(168,85,247,0.05)",
          animation: active
            ? "orb-breath 3s ease-in-out infinite"
            : "orb-idle 6s ease-in-out infinite",
        }}
      >
        {/* Inner highlight */}
        <div
          className="absolute inset-4 rounded-full opacity-60"
          style={{
            background:
              "radial-gradient(circle at 30% 25%, rgba(255,255,255,0.25) 0%, transparent 60%)",
          }}
        />
      </div>

      {/* Status text */}
      <div className="absolute -bottom-10 left-1/2 -translate-x-1/2 w-max">
        <span
          className={`text-xs font-mono transition-all duration-500 ${
            active ? "text-purple-300" : "text-gray-600"
          }`}
        >
          {listening
            ? "> LISTENING_"
            : speaking
            ? "> SPEAKING_"
            : "> IDLE_"}
        </span>
      </div>
    </button>
  );
}
