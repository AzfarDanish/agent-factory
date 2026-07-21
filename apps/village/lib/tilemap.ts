import type { BuildingDef, PipelineStage } from "./types";

export const BUILDINGS: BuildingDef[] = [
  {
    id: "gate",
    label: "Village Gate",
    stage: "gate",
    x: 400,
    y: 80,
    width: 120,
    height: 60,
    description: "Requests enter here",
    icon: "🚪",
  },
  {
    id: "church",
    label: "Library",
    stage: "reasoning",
    x: 160,
    y: 200,
    width: 140,
    height: 120,
    description: "DeepSeek reasons here",
    icon: "🏛️",
  },
  {
    id: "workshop",
    label: "Artisan Workshop",
    stage: "generating",
    x: 640,
    y: 200,
    width: 140,
    height: 120,
    description: "GPT draws here",
    icon: "🎨",
  },
  {
    id: "town_hall",
    label: "Town Hall",
    stage: "completed",
    x: 400,
    y: 360,
    width: 160,
    height: 100,
    description: "Completed pages arrive here",
    icon: "🏆",
  },
  {
    id: "pit",
    label: "The Pit",
    stage: "failed",
    x: 400,
    y: 520,
    width: 100,
    height: 60,
    description: "Failed requests fall here",
    icon: "⚠️",
  },
];

export const PATHS: { from: string; to: string; waypoints: [number, number][] }[] = [
  {
    from: "gate",
    to: "church",
    waypoints: [
      [400, 140],
      [280, 140],
      [230, 200],
    ],
  },
  {
    from: "gate",
    to: "workshop",
    waypoints: [
      [400, 140],
      [520, 140],
      [710, 200],
    ],
  },
  {
    from: "church",
    to: "workshop",
    waypoints: [
      [300, 260],
      [400, 300],
      [540, 260],
    ],
  },
  {
    from: "church",
    to: "town_hall",
    waypoints: [
      [230, 320],
      [400, 380],
    ],
  },
  {
    from: "workshop",
    to: "town_hall",
    waypoints: [
      [710, 320],
      [480, 380],
    ],
  },
  {
    from: "town_hall",
    to: "pit",
    waypoints: [
      [400, 460],
      [450, 520],
    ],
  },
  {
    from: "gate",
    to: "town_hall",
    waypoints: [
      [400, 140],
      [400, 360],
    ],
  },
];

export const STAGE_ORDER: Record<string, PipelineStage[]> = {
  normal: ["idle", "reasoning", "generating", "completed"],
  failure: ["reasoning", "failed"],
  image_failure: ["generating", "failed"],
};

export function getBuildingForStage(stage: PipelineStage): BuildingDef | undefined {
  return BUILDINGS.find((b) => b.stage === stage);
}

export function getPathBetween(fromId: string, toId: string) {
  return PATHS.find(
    (p) =>
      (p.from === fromId && p.to === toId) ||
      (p.from === toId && p.to === fromId)
  );
}
