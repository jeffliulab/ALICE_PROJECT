/** API client for the Generative Agents replay viewer. */

export interface StepMovement {
  movement: number[];
  pronunciatio: string;
  description: string;
  chat: string[][] | null;
}

export type StepMovements = Record<string, StepMovement>;

export interface ReplayMeta {
  name: string;
  sim_name: string;
  start_date: string;
  total_steps: number;
  sec_per_step: number;
  persona_names: string[];
  created_at: string;
}

const BASE = '';

export async function listReplays(): Promise<ReplayMeta[]> {
  const r = await fetch(`${BASE}/api/replays`);
  return r.json();
}

export async function getReplayMeta(name: string): Promise<ReplayMeta> {
  const r = await fetch(`${BASE}/api/replay/${encodeURIComponent(name)}/meta`);
  return r.json();
}

export async function getReplayMovements(name: string): Promise<Record<string, StepMovements>> {
  const r = await fetch(`${BASE}/api/replay/${encodeURIComponent(name)}/movements`);
  return r.json();
}

/** Start simulation (used to initialize map/persona positions) */
export async function startSimulation(simName = 'the_ville') {
  const r = await fetch(`${BASE}/api/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sim_name: simName }),
  });
  return r.json();
}

export async function getState() {
  const r = await fetch(`${BASE}/api/state`);
  return r.json();
}
