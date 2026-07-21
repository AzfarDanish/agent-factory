"use client";

import { useMemo } from "react";

const HAIR_STYLES = ["shorthair", "bowlhair", "curlyhair", "longhair", "mophair", "spikeyhair"] as const;
type HairStyle = (typeof HAIR_STYLES)[number];

type AnimType = "idle" | "walk" | "work" | "celebrate" | "fail";

interface AnimConfig {
  frames: number;
  totalWidth: number; // px
}

const ANIM_CONFIGS: Record<AnimType, AnimConfig> = {
  idle: { frames: 9, totalWidth: 864 },
  walk: { frames: 8, totalWidth: 768 },
  work: { frames: 8, totalWidth: 768 },
  celebrate: { frames: 9, totalWidth: 864 },
  fail: { frames: 8, totalWidth: 768 },
};

function getRandomHair(): HairStyle {
  return HAIR_STYLES[Math.floor(Math.random() * HAIR_STYLES.length)];
}

interface SpriteCharacterProps {
  anim: AnimType;
  hair?: HairStyle;
  className?: string;
}

export function SpriteCharacter({ anim, hair, className = "" }: SpriteCharacterProps) {
  const hairStyle = useMemo(() => hair || getRandomHair(), [hair]);
  const config = ANIM_CONFIGS[anim];

  const baseStyle: React.CSSProperties = {
    width: 96,
    height: 64,
    position: "absolute",
    top: 0,
    left: 0,
    imageRendering: "pixelated",
    backgroundSize: `${config.totalWidth}px 64px`,
  };

  return (
    <div className={`relative inline-block ${className}`} style={{ width: 96, height: 64 }}>
      <div
        className={`sprite-${anim}`}
        style={{
          ...baseStyle,
          backgroundImage: `url(/characters/${anim}/base_${anim}_strip${config.frames}.png)`,
        }}
      />
      <div
        className={`sprite-${anim} z-10`}
        style={{
          ...baseStyle,
          backgroundImage: `url(/characters/${anim}/${hairStyle}_${anim}_strip${config.frames}.png)`,
        }}
      />
    </div>
  );
}

export { HAIR_STYLES, getRandomHair };
export type { HairStyle, AnimType };
