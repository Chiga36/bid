import { apiDelete, apiGet, apiPut } from "./http";
import type { AgentPrompt, TenderPrompt } from "./types";

export function listAgentPrompts() {
  return apiGet<AgentPrompt[]>("/agent-prompts");
}

export function getTenderPrompt(tenderId: number, promptFile: string) {
  return apiGet<TenderPrompt>(`/tenders/${tenderId}/prompt-overrides/${encodeURIComponent(promptFile)}`);
}

export function saveTenderPrompt(tenderId: number, promptFile: string, contentText: string) {
  return apiPut<TenderPrompt>(`/tenders/${tenderId}/prompt-overrides/${encodeURIComponent(promptFile)}`, {
    content_text: contentText,
  });
}

export function resetTenderPrompt(tenderId: number, promptFile: string) {
  return apiDelete<TenderPrompt>(`/tenders/${tenderId}/prompt-overrides/${encodeURIComponent(promptFile)}`);
}
