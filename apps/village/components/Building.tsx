"use client";

import { type BuildingDef, type VillageState } from "@/lib/types";

interface BuildingProps {
  building: BuildingDef;
  state: VillageState;
  activeAgentCount: number;
}

export function Building({ building, state, activeAgentCount }: BuildingProps) {
  const isDay = state.time_of_day === "day";
  const isNight = state.time_of_day === "night" || state.time_of_day === "dawn";
  const hasActivity = activeAgentCount > 0;
  const isFailed = building.stage === "failed";

  const getBuildingColors = () => {
    if (isFailed && hasActivity) return "bg-red-900 border-red-500 text-red-200";
    if (isNight) return "bg-gray-800 border-yellow-600 text-yellow-200";
    if (hasActivity) return "bg-emerald-800 border-emerald-400 text-emerald-100";
    return "bg-gray-700 border-gray-500 text-gray-200";
  };

  const getActivityIndicator = () => {
    if (building.stage === "failed" && activeAgentCount > 0) return "animate-pulse";
    if (hasActivity) return "animate-pulse-glow";
    return "";
  };

  return (
    <div
      className={`absolute flex flex-col items-center justify-center rounded-lg border-2 
        transition-all duration-1000 ${getBuildingColors()} ${getActivityIndicator()}`}
      style={{
        left: building.x,
        top: building.y,
        width: building.width,
        height: building.height,
      }}
      title={`${building.label} — ${building.description}`}
    >
      {/* Chimney smoke for workshop when active */}
      {building.stage === "generating" && hasActivity && (
        <div className="absolute -top-6 left-1/2 -translate-x-1/2">
          <div className="w-3 h-3 bg-gray-300 rounded-full opacity-60 animate-chimney-smoke" />
        </div>
      )}

      {/* Roof line */}
      {!isFailed && (
        <div
          className={`absolute -top-3 left-0 right-0 h-3 rounded-t-md
            ${isNight ? "bg-yellow-800" : "bg-amber-700"}`}
          style={{
            clipPath: "polygon(10% 100%, 50% 0%, 90% 100%)",
          }}
        />
      )}

      {/* Icon */}
      <span className="text-2xl mb-1">{building.icon}</span>

      {/* Label */}
      <span className="text-[10px] font-semibold uppercase tracking-wide leading-tight text-center px-1">
        {building.label}
      </span>

      {/* Activity count */}
      {activeAgentCount > 0 && building.stage !== "failed" && building.stage !== "gate" && building.stage !== "town_hall" && (
        <span className="absolute -top-2 -right-2 w-5 h-5 bg-white text-black 
          rounded-full text-[10px] font-bold flex items-center justify-center">
          {activeAgentCount}
        </span>
      )}

      {/* Stage label */}
      {building.stage !== "gate" && building.stage !== "town_hall" && (
        <span className={`text-[8px] opacity-70 mt-0.5 ${
          isNight ? "text-yellow-300" : "text-gray-400"
        }`}>
          {building.stage}
        </span>
      )}
    </div>
  );
}
