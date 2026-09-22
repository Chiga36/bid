import { apiGet } from "./http";
import type { AgentPrompt } from "./types";

export function listAgentPrompts() {
  return apiGet<AgentPrompt[]>("/agent-prompts");
}
