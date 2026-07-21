"use client";

import { useState, useEffect, useCallback } from "react";
import type { VillageState, AgentState } from "@/lib/types";
import { BUILDINGS, PATHS } from "@/lib/tilemap";
import { villageBridge } from "@/lib/websocket";
import { Building } from "./Building";
import { Agent } from "./Agent";
import { StatusPanel } from "./StatusPanel";
import { TimeIndicator } from "./TimeIndicator";

interface VillageMapProps {
  demoMode?: boolean;
}

export function VillageMap({ demoMode = false }: VillageMapProps) {
  const [state, setState] = useState<VillageState>({
    time_of_day: "day",
    agents: [],
    queue_depth: 0,
    active_jobs: 0,
    last_event: null,
    completed_count: 0,
    failed_count: 0,
  });

  const handleStateChange = useCallback((newState: VillageState) => {
    setState(newState);
  }, []);

  useEffect(() => {
    villageBridge.onStateChange(handleStateChange);
    villageBridge.connect();

    if (demoMode) {
      villageBridge.demoMode();
    }

    return () => {
      villageBridge.disconnect();
    };
  }, [handleStateChange, demoMode]);

  const getAgentCountForBuilding = (buildingId: string): number => {
    return state.agents.filter(
      (a) => a.current_building === buildingId && a.status !== "idle"
    ).length;
  };

  const getWorkersInStage = (stage: string): AgentState[] => {
    const stageBuilding = BUILDINGS.find((b) => b.stage === stage);
    if (!stageBuilding) return [];
    return state.agents.filter(
      (a) => a.current_building === stageBuilding.id && a.status === "working"
    );
  };

  const isNight = state.time_of_day === "night" || state.time_of_day === "dawn";

  return (
    <div className="relative w-full max-w-5xl mx-auto">
      {/* Village container */}
      <div
        className={`relative w-[900px] h-[650px] mx-auto rounded-xl overflow-hidden border-2 
          transition-colors duration-[3000ms] 
          ${isNight ? "border-indigo-700/50" : "border-amber-700/30"}`}
      >
        {/* Sky / background */}
        <TimeIndicator state={state} />

        {/* Grass ground */}
        <div
          className={`absolute inset-0 z-[1] transition-colors duration-[3000ms]
            ${isNight 
              ? "bg-gradient-to-b from-green-950/80 via-emerald-950/70 to-green-950/90" 
              : "bg-gradient-to-b from-green-300 via-green-400 to-green-500"}`}
        />

        {/* Paths between buildings */}
        <svg className="absolute inset-0 z-[2] pointer-events-none" width="900" height="650">
          {PATHS.map((path, i) => (
            <g key={i}>
              {/* Path line */}
              <line
                x1={path.waypoints[0][0]}
                y1={path.waypoints[0][1]}
                x2={path.waypoints[path.waypoints.length - 1][0]}
                y2={path.waypoints[path.waypoints.length - 1][1]}
                stroke={isNight ? "#8B7D3C" : "#C4A44A"}
                strokeWidth={6}
                strokeLinecap="round"
                strokeDasharray="4 4"
                opacity={0.5}
              />
              {/* Waypoint dots */}
              {path.waypoints.map((wp, j) => (
                <circle
                  key={j}
                  cx={wp[0]}
                  cy={wp[1]}
                  r={3}
                  fill={isNight ? "#6B5B2C" : "#A08430"}
                  opacity={0.4}
                />
              ))}
            </g>
          ))}
        </svg>

        {/* Grass details */}
        <div className="absolute inset-0 z-[1] pointer-events-none">
          {Array.from({ length: 30 }).map((_, i) => (
            <div
              key={i}
              className={`absolute text-xs transition-colors duration-1000
                ${isNight ? "text-green-800/30" : "text-green-600/40"}`}
              style={{
                left: `${5 + Math.random() * 90}%`,
                top: `${5 + Math.random() * 90}%`,
                transform: `rotate(${Math.random() * 360}deg)`,
              }}
            >
              🌿
            </div>
          ))}
        </div>

        {/* Buildings */}
        <div className="absolute inset-0 z-[10]">
          {BUILDINGS.map((building) => (
            <Building
              key={building.id}
              building={building}
              state={state}
              activeAgentCount={getAgentCountForBuilding(building.id)}
            />
          ))}
        </div>

        {/* Agents */}
        <div className="absolute inset-0 z-[20]">
          {state.agents.map((agent) => (
            <Agent key={agent.id} agent={agent} state={state} />
          ))}
        </div>

        {/* Title overlay */}
        <div className="absolute top-4 left-1/2 -translate-x-1/2 z-30 bg-black/50 backdrop-blur-sm rounded-full px-5 py-2 border border-gray-600/50">
          <h1 className="text-white text-sm font-bold tracking-wider flex items-center gap-2">
            <span>🏘️</span>
            Coloring Factory Village
            <span className="text-[10px] text-gray-400 font-normal">
              {getWorkersInStage("reasoning").length > 0 && " · Reasoning: " + getWorkersInStage("reasoning").length}
              {getWorkersInStage("generating").length > 0 && " · Generating: " + getWorkersInStage("generating").length}
            </span>
          </h1>
        </div>

        {/* Connection status */}
        <div className="absolute bottom-4 left-4 z-30 flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${state.last_event ? "bg-green-400" : "bg-yellow-400"} animate-pulse`} />
          <span className="text-[10px] text-gray-400 font-mono">
            {state.last_event ? "connected" : "listening"}
          </span>
        </div>
      </div>

      {/* Status panel */}
      <StatusPanel state={state} />
    </div>
  );
}
