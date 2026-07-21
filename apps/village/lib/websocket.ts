import type { PipelineEvent, VillageState, AgentState } from "./types";
import { BUILDINGS, getBuildingForStage, getPathBetween } from "./tilemap";

const WS_URL = process.env.NEXT_PUBLIC_BRIDGE_URL || "ws://localhost:3001";

type StateListener = (state: VillageState) => void;

export class VillageBridge {
  private ws: WebSocket | null = null;
  private listeners: Set<StateListener> = new Set();
  private state: VillageState = {
    time_of_day: "day",
    agents: [],
    queue_depth: 0,
    active_jobs: 0,
    last_event: null,
    completed_count: 0,
    failed_count: 0,
  };
  private agentCounter = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  connect() {
    if (this.ws?.readyState === WebSocket.OPEN) return;

    try {
      this.ws = new WebSocket(WS_URL);
    } catch {
      this.scheduleReconnect();
      return;
    }

    this.ws.onopen = () => {
      console.log("[VillageBridge] connected");
    };

    this.ws.onmessage = (msg) => {
      try {
        const event: PipelineEvent = JSON.parse(msg.data);
        this.handleEvent(event);
      } catch {
        // ignore malformed
      }
    };

    this.ws.onclose = () => {
      console.log("[VillageBridge] disconnected");
      this.scheduleReconnect();
    };

    this.ws.onerror = () => {
      this.ws?.close();
    };
  }

  disconnect() {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.ws?.close();
    this.ws = null;
  }

  onStateChange(listener: StateListener) {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  getState(): VillageState {
    return { ...this.state };
  }

  demoMode() {
    this.spawnDemoAgent();
    setInterval(() => this.spawnDemoAgent(), 15000);
  }

  private spawnDemoAgent() {
    if (this.state.agents.length >= 5) return;
    const id = `demo-${++this.agentCounter}`;
    const agent: AgentState = {
      id,
      trace_id: id,
      current_building: "gate",
      target_building: "church",
      progress: 0,
      status: "walking",
      prompt: "a friendly dragon",
      age_group: "child",
    };
    this.state.agents.push(agent);
    this.state.active_jobs = this.state.agents.length;
    this.state.queue_depth = Math.max(0, 5 - this.state.agents.length);
    this.notify();
    this.animateAgent(id);
  }

  private animateAgent(agentId: string) {
    const step = () => {
      const agent = this.state.agents.find((a) => a.id === agentId);
      if (!agent) return;

      agent.progress += 0.05;

      if (agent.progress >= 1.0) {
        agent.progress = 0;
        agent.status = "working";

        // Move to next stage
        if (agent.current_building === "gate" && agent.target_building === "church") {
          agent.current_building = "church";
          agent.target_building = "workshop";
          setTimeout(() => {
            agent.status = "walking";
            this.notify();
            step();
          }, 3000);
        } else if (agent.current_building === "church" && agent.target_building === "workshop") {
          agent.current_building = "workshop";
          agent.target_building = "town_hall";
          setTimeout(() => {
            agent.status = "walking";
            this.notify();
            step();
          }, 3000);
        } else if (agent.current_building === "workshop" && agent.target_building === "town_hall") {
          agent.current_building = "town_hall";
          agent.target_building = "exit";
          agent.status = "celebrating";
          this.state.completed_count++;
          this.state.active_jobs = Math.max(0, this.state.active_jobs - 1);
          this.notify();
          setTimeout(() => {
            this.state.agents = this.state.agents.filter((a) => a.id !== agentId);
            this.notify();
          }, 4000);
          return;
        }

        this.notify();
        setTimeout(step, 500);
      } else {
        this.notify();
        setTimeout(step, 400);
      }
    };

    step();
  }

  private handleEvent(event: PipelineEvent) {
    this.state.last_event = event;
    this.state.queue_depth = event.queue_depth;

    switch (event.stage) {
      case "reasoning":
        this.spawnAgentFromEvent(event, "gate", "church");
        break;
      case "generating":
        this.moveAgentsTo("church", "workshop");
        break;
      case "completed":
        this.moveAgentsTo("workshop", "town_hall");
        this.state.completed_count++;
        break;
      case "failed":
        this.moveAgentsTo("town_hall", "pit");
        this.state.failed_count++;
        break;
    }

    this.updateTimeOfDay();
    this.notify();
  }

  private spawnAgentFromEvent(event: PipelineEvent, from: string, to: string) {
    const agent: AgentState = {
      id: `job-${event.trace_id}`,
      trace_id: event.trace_id,
      current_building: from,
      target_building: to,
      progress: 0,
      status: "walking",
      prompt: event.request?.prompt || "unknown",
      age_group: event.request?.age_group || "child",
    };
    this.state.agents.push(agent);
    this.state.active_jobs = this.state.agents.length;
  }

  private moveAgentsTo(fromStage: string, toStage: string) {
    const agents = this.state.agents.filter(
      (a) => a.current_building === fromStage && a.status === "working"
    );
    for (const agent of agents) {
      agent.target_building = toStage;
      agent.progress = 0;
      agent.status = "walking";
    }
  }

  private updateTimeOfDay() {
    const active = this.state.active_jobs;
    if (active === 0) this.state.time_of_day = "day";
    else if (active <= 2) this.state.time_of_day = "dusk";
    else if (active <= 4) this.state.time_of_day = "night";
    else this.state.time_of_day = "dawn";
  }

  private notify() {
    // Deep copy agents so React detects reference changes
    const snapshot = {
      ...this.state,
      agents: this.state.agents.map((a) => ({ ...a })),
      last_event: this.state.last_event ? { ...this.state.last_event } : null,
    };
    this.listeners.forEach((fn) => fn(snapshot));
  }

  private scheduleReconnect() {
    this.reconnectTimer = setTimeout(() => this.connect(), 5000);
  }
}

export const villageBridge = new VillageBridge();
