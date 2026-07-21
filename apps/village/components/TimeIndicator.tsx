"use client";

import type { VillageState } from "@/lib/types";

interface TimeIndicatorProps {
  state: VillageState;
}

export function TimeIndicator({ state }: TimeIndicatorProps) {
  const getSkyGradient = () => {
    switch (state.time_of_day) {
      case "day": return "from-sky-400 to-blue-500";
      case "dusk": return "from-orange-400 via-purple-500 to-indigo-700";
      case "night": return "from-indigo-900 via-blue-950 to-black";
      case "dawn": return "from-pink-400 via-orange-300 to-sky-400";
    }
  };

  const getSunPosition = () => {
    switch (state.time_of_day) {
      case "day": return "left-1/2 top-8";
      case "dusk": return "left-3/4 top-12";
      case "night": return "right-4 -top-4";
      case "dawn": return "left-1/4 top-12";
    }
  };

  const getStars = () => {
    if (state.time_of_day !== "night") return null;
    // Render a few star positions
    const stars = [
      { x: "15%", y: "15%", size: 1, delay: "0s" },
      { x: "35%", y: "8%", size: 2, delay: "1s" },
      { x: "55%", y: "20%", size: 1, delay: "0.5s" },
      { x: "75%", y: "12%", size: 1.5, delay: "2s" },
      { x: "90%", y: "25%", size: 1, delay: "1.5s" },
      { x: "25%", y: "30%", size: 1.5, delay: "0.8s" },
      { x: "65%", y: "35%", size: 1, delay: "2.5s" },
    ];
    return stars.map((s, i) => (
      <div
        key={i}
        className="absolute w-1 h-1 bg-white rounded-full animate-pulse"
        style={{
          left: s.x,
          top: s.y,
          width: s.size * 3,
          height: s.size * 3,
          animationDelay: s.delay,
          opacity: 0.6,
        }}
      />
    ));
  };

  return (
    <div
      className={`absolute inset-0 z-0 transition-all duration-[3000ms] bg-gradient-to-b ${getSkyGradient()}`}
    >
      {/* Sun/Moon */}
      <div
        className={`absolute w-16 h-16 rounded-full transition-all duration-[3000ms] 
          ${state.time_of_day === "night" || state.time_of_day === "dawn" 
            ? "bg-gray-200 shadow-[0_0_30px_rgba(200,200,200,0.5)]" 
            : "bg-yellow-300 shadow-[0_0_40px_rgba(255,200,50,0.6)]"
          } ${getSunPosition()}`}
      />

      {/* Stars (night only) */}
      {getStars()}

      {/* Ground fog for dusk/dawn */}
      {(state.time_of_day === "dusk" || state.time_of_day === "dawn") && (
        <div className="absolute bottom-0 left-0 right-0 h-1/4 bg-gradient-to-t from-gray-800/30 to-transparent" />
      )}
    </div>
  );
}
