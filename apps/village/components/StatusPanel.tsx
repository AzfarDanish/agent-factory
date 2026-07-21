"use client";

import type { VillageState } from "@/lib/types";

interface StatusPanelProps {
  state: VillageState;
}

export function StatusPanel({ state }: StatusPanelProps) {
  const getTimeColor = () => {
    switch (state.time_of_day) {
      case "day": return "text-yellow-300";
      case "dusk": return "text-orange-300";
      case "night": return "text-indigo-300";
      case "dawn": return "text-pink-300";
    }
  };

  const getTimeIcon = () => {
    switch (state.time_of_day) {
      case "day": return "☀️";
      case "dusk": return "🌆";
      case "night": return "🌙";
      case "dawn": return "🌅";
    }
  };

  return (
    <div className="absolute top-4 right-4 z-30 bg-black/70 backdrop-blur-sm rounded-lg border border-gray-700 p-4 min-w-[200px] text-white text-sm">
      <h3 className="font-bold text-xs uppercase tracking-wider text-gray-400 mb-3">
        Factory Status
      </h3>

      {/* Time of day */}
      <div className="flex items-center justify-between mb-2">
        <span className="text-gray-400 text-xs">Time</span>
        <span className={`flex items-center gap-1 ${getTimeColor()}`}>
          {getTimeIcon()} {state.time_of_day}
        </span>
      </div>

      {/* Queue depth */}
      <div className="flex items-center justify-between mb-2">
        <span className="text-gray-400 text-xs">Queue</span>
        <span className="font-mono">{state.queue_depth} pending</span>
      </div>

      {/* Active jobs */}
      <div className="flex items-center justify-between mb-2">
        <span className="text-gray-400 text-xs">Active</span>
        <span className="font-mono text-blue-300">{state.active_jobs} jobs</span>
      </div>

      {/* Completed */}
      <div className="flex items-center justify-between mb-2">
        <span className="text-gray-400 text-xs">Completed</span>
        <span className="font-mono text-green-300">{state.completed_count}</span>
      </div>

      {/* Failed */}
      <div className="flex items-center justify-between mb-3">
        <span className="text-gray-400 text-xs">Failed</span>
        <span className="font-mono text-red-300">{state.failed_count}</span>
      </div>

      {/* Live event indicator */}
      {state.last_event && (
        <div className="border-t border-gray-700 pt-2 mt-1">
          <span className="text-[10px] text-gray-500 uppercase tracking-wider">
            Last event
          </span>
          <p className="text-xs mt-1 text-gray-300 font-mono truncate">
            {state.last_event.event} — {state.last_event.stage || "—"}
          </p>
          {state.last_event.request && (
            <p className="text-[10px] text-gray-500 mt-0.5 truncate">
              "{state.last_event.request.prompt.slice(0, 30)}…"
            </p>
          )}
        </div>
      )}

      {/* Legend */}
      <div className="border-t border-gray-700 pt-2 mt-2">
        <span className="text-[10px] text-gray-500 uppercase tracking-wider">
          Legend
        </span>
        <div className="grid grid-cols-2 gap-x-2 gap-y-1 mt-1.5">
          <div className="flex items-center gap-1">
            <div className="w-3 h-2 bg-blue-400 rounded-sm" />
            <span className="text-[10px] text-gray-400">walking</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-2 bg-amber-400 rounded-sm" />
            <span className="text-[10px] text-gray-400">working</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-2 bg-green-400 rounded-sm" />
            <span className="text-[10px] text-gray-400">celebrating</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-2 bg-red-400 rounded-sm" />
            <span className="text-[10px] text-gray-400">failed</span>
          </div>
        </div>
      </div>
    </div>
  );
}
