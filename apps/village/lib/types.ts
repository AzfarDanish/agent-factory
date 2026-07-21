export type PipelineStage = "idle" | "reasoning" | "generating" | "completed" | "failed";

export type AgeGroup = "toddler" | "child" | "teen" | "adult";
export type Style = "simple" | "detailed" | "mandala" | "cartoon" | "realistic";

export interface PipelineEvent {
  event: "stage_change" | "queue_update" | "heartbeat";
  trace_id: string;
  stage?: PipelineStage;
  request?: {
    prompt: string;
    age_group: AgeGroup;
    style: Style;
  };
  queue_depth: number;
  timestamp: string;
  error?: string;
}

export interface BuildingDef {
  id: string;
  label: string;
  stage: PipelineStage | "gate" | "town_hall";
  x: number;
  y: number;
  width: number;
  height: number;
  description: string;
  icon: string;
}

export interface AgentState {
  id: string;
  trace_id: string;
  current_building: string;
  target_building: string;
  progress: number;
  status: "walking" | "working" | "idle" | "celebrating" | "failed";
  prompt: string;
  age_group: AgeGroup;
}

export interface VillageState {
  time_of_day: "day" | "dusk" | "night" | "dawn";
  agents: AgentState[];
  queue_depth: number;
  active_jobs: number;
  last_event: PipelineEvent | null;
  completed_count: number;
  failed_count: number;
}
