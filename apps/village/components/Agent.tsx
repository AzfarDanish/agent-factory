"use client";

import { type AgentState, type VillageState } from "@/lib/types";
import { BUILDINGS } from "@/lib/tilemap";
import { SpriteCharacter, getRandomHair } from "./SpriteCharacter";
import { useMemo } from "react";

interface AgentProps {
  agent: AgentState;
  state: VillageState;
}

export function Agent({ agent, state }: AgentProps) {
  const current = BUILDINGS.find((b) => b.id === agent.current_building);
  const target = BUILDINGS.find((b) => b.id === agent.target_building);

  // Assign a random hair style per agent (stable across renders)
  const hairStyle = useMemo(() => getRandomHair(), [agent.id]);

  const getPosition = () => {
    if (!current || !target) return { x: 400, y: 300 };

    const cx = current.x + current.width / 2;
    const cy = current.y + current.height / 2;
    const tx = target.x + target.width / 2;
    const ty = target.y + target.height / 2;

    return {
      x: cx + (tx - cx) * agent.progress,
      y: cy + (ty - cy) * agent.progress,
    };
  };

  const getAnimType = () => {
    switch (agent.status) {
      case "walking": return "walk";
      case "working": return "work";
      case "celebrating": return "celebrate";
      case "failed": return "fail";
      default: return "idle";
    }
  };

  const pos = getPosition();
  const animType = getAnimType();

  return (
    <div
      className="absolute z-20 transition-all duration-500 ease-linear flex flex-col items-center"
      style={{
        left: pos.x - 48,  // center 96px wide sprite
        top: pos.y - 32,   // 64px tall, offset so feet are at the position
      }}
    >
      {/* Shadow */}
      <div
        className="rounded-full bg-black/20 mx-auto"
        style={{ width: 40, height: 8, marginBottom: -8 }}
      />

      {/* Sprite character with animations */}
      <div className={`
        ${agent.status === "walking" ? (agent.progress % 0.2 < 0.1 ? "-translate-y-[2px]" : "translate-y-[1px]") : ""}
        ${agent.status === "celebrating" ? "animate-bounce-gentle" : ""}
        ${agent.status === "working" ? "animate-bounce-gentle" : ""}
        transition-transform duration-200
      `}>
        <SpriteCharacter
          anim={animType}
          hair={hairStyle}
        />
      </div>

      {/* Agent name / prompt tag */}
      <div className="mt-0.5 px-1.5 py-0.5 bg-black/60 rounded text-[8px] text-white whitespace-nowrap pointer-events-none">
        {agent.prompt.slice(0, 20)}{agent.prompt.length > 20 ? "…" : ""}
      </div>

      {/* Walking trail */}
      {agent.status === "walking" && (
        <div className="absolute top-2 -right-1 w-2 h-2 bg-blue-300/60 rounded-full animate-ping" />
      )}

      {/* Working sparkle */}
      {agent.status === "working" && (
        <div className="absolute -top-2 left-1/2 -translate-x-1/2 text-xs animate-bounce-gentle">
          ⚡
        </div>
      )}

      {/* Celebration sparkles */}
      {agent.status === "celebrating" && (
        <div className="absolute -top-4 left-1/2 -translate-x-1/2 flex gap-1 text-xs">
          <span className="text-yellow-300">✦</span>
          <span className="text-pink-300">✦</span>
          <span className="text-yellow-300">✦</span>
        </div>
      )}

      {/* Failed indicator */}
      {agent.status === "failed" && (
        <div className="absolute -top-1 left-1/2 -translate-x-1/2 text-xs text-red-400">
          ✕
        </div>
      )}
    </div>
  );
}
