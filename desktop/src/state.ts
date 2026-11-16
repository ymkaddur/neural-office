/** Session-only demo adapter. No filesystem, network, provider or real authority. */
export type Phase = 'READY' | 'BOOTING' | 'RUNNING' | 'VERIFYING' | 'STOPPING' | 'CANCELLED' | 'ACCEPTED' | 'FAILED' | 'RECOVERY_REQUIRED';
export type Scenario = 'success' | 'startup-timeout' | 'interrupted';
export type RoleCount = 1 | 3 | 7;
export type State = {
  phase: Phase; roles: RoleCount; scenario: Scenario; attempts: number;
  generation: number; completed: number; eventSequence: number; error: string | null;
};
export type Event =
  | { type: 'CONFIGURE'; roles: RoleCount; scenario: Scenario }
  | { type: 'START' }
  | { type: 'CANCEL' }
  | { type: 'RECOVER' }
  | { type: 'EVENT'; generation: number; sequence: number;
      kind: 'READY' | 'ROLE_COMPLETED' | 'VERIFIED' | 'TERMINATED' | 'FAILED' | 'INTERRUPTED' };
export const initialState: State = {
  phase: 'READY', roles: 3, scenario: 'success', attempts: 0,
  generation: 0, completed: 0, eventSequence: 0, error: null,
};
export const busy = (state: State) => ['BOOTING', 'RUNNING', 'VERIFYING', 'STOPPING', 'RECOVERY_REQUIRED'].includes(state.phase);
export function reduce(state: State, event: Event): State {
  if (event.type === 'CONFIGURE') {
    if (busy(state) || ![1, 3, 7].includes(event.roles) || !['success', 'startup-timeout', 'interrupted'].includes(event.scenario)) return state;
    return { ...state, roles: event.roles, scenario: event.scenario, phase: 'READY', completed: 0, error: null };
  }
  if (event.type === 'START') {
    if (busy(state) || state.attempts >= 3) return state;
    return { ...state, phase: 'BOOTING', generation: state.generation + 1,
      attempts: state.attempts + 1, completed: 0, eventSequence: 0, error: null };
  }
  if (event.type === 'CANCEL') {
    if (!['BOOTING', 'RUNNING', 'VERIFYING'].includes(state.phase)) return state;
    return { ...state, phase: 'STOPPING' };
  }
  if (event.type === 'RECOVER') {
    return state.phase === 'RECOVERY_REQUIRED' ? { ...state, phase: 'CANCELLED', error: null } : state;
  }
  if (event.generation !== state.generation || event.sequence !== state.eventSequence + 1) return state;
  let phase = state.phase;
  let completed = state.completed;
  let error = state.error;
  if (event.kind === 'READY' && phase === 'BOOTING') phase = 'RUNNING';
  else if (event.kind === 'ROLE_COMPLETED' && phase === 'RUNNING') {
    completed += 1;
    if (completed === state.roles) phase = 'VERIFYING';
  } else if (event.kind === 'VERIFIED' && phase === 'VERIFYING') phase = 'ACCEPTED';
  else if (event.kind === 'TERMINATED' && phase === 'STOPPING') phase = 'CANCELLED';
  else if (event.kind === 'FAILED' && phase === 'BOOTING') { phase = 'FAILED'; error = 'OWNED_BACKEND_START_TIMEOUT'; }
  else if (event.kind === 'INTERRUPTED' && phase === 'RUNNING') { phase = 'RECOVERY_REQUIRED'; error = 'TERMINATION_UNKNOWN'; }
  else return { ...state, eventSequence: event.sequence };
  return { ...state, phase, completed, error, eventSequence: event.sequence };
}
export const roleNames = (count: RoleCount) => count === 1 ? ['Director'] : count === 3
  ? ['Director', 'Revisor crítico', 'Integrador']
  : ['Director', 'Planificador', 'Investigador', 'Implementador', 'Revisor crítico', 'Verificador', 'Integrador'];
