import test from 'node:test';
import assert from 'node:assert/strict';
import { reduce, initialState, busy } from './state.ts';
import type { State, Event } from './state.ts';

test('changing the next configuration does not relabel a completed run or refund it', () => {
  const completed: State = { ...initialState, phase: 'ACCEPTED', attempts: 1, completed: 3 };
  const next = reduce(completed, { type: 'CONFIGURE', roles: 7, scenario: 'success' });
  assert.equal(next.phase, 'READY');
  assert.equal(next.completed, 0);
  assert.equal(next.attempts, 1);
  assert.equal(next.roles, 7);
});
const incoming = (s: State, kind: Extract<Event, {type: 'EVENT'}>['kind']): State => reduce(s, {
  type: 'EVENT', generation: s.generation, sequence: s.eventSequence + 1, kind,
});
test('double start consumes a single attempt', () => {
  const s = reduce(initialState, { type: 'START' });
  assert.deepEqual(reduce(s, { type: 'START' }), s);
  assert.equal(s.attempts, 1);
});
test('cancelling holds admission until termination and rejects late completion', () => {
  let s = incoming(reduce(initialState, {type: 'START'}), 'READY');
  s = reduce(s, {type: 'CANCEL'});
  assert.equal(busy(s), true);
  s = incoming(s, 'ROLE_COMPLETED');
  assert.equal(s.phase, 'STOPPING');
  assert.equal(s.completed, 0);
  assert.deepEqual(reduce(s, {type: 'START'}), s);
  s = incoming(s, 'TERMINATED');
  assert.equal(s.phase, 'CANCELLED'); assert.equal(s.attempts, 1);
  assert.equal(incoming(s, 'VERIFIED').phase, 'CANCELLED');
});
test('old generation, duplicate and skipped events cannot advance state', () => {
  const s = reduce(initialState, {type: 'START'});
  for (const [generation, sequence] of [[0, 1], [1, 0], [1, 2]]) {
    assert.deepEqual(reduce(s, {type: 'EVENT', kind: 'READY', generation, sequence}), s);
  }
});
test('three failed starts exhaust the demo budget', () => {
  let s: State = initialState;
  for (let n = 0; n < 3; n++) s = incoming(reduce(s, {type: 'START'}), 'FAILED');
  assert.equal(s.attempts, 3); assert.deepEqual(reduce(s, {type: 'START'}), s);
});
test('recovery preserves consumption and does not repeat work', () => {
  let s = incoming(incoming(reduce(initialState, {type: 'START'}), 'READY'), 'INTERRUPTED');
  assert.equal(s.phase, 'RECOVERY_REQUIRED');
  assert.deepEqual(reduce(s, {type: 'START'}), s);
  s = reduce(s, {type: 'RECOVER'});
  assert.equal(s.phase, 'CANCELLED'); assert.equal(s.attempts, 1);
});
test('roles are frozen during an attempt and success follows verification', () => {
  let s = incoming(reduce(initialState, {type: 'START'}), 'READY');
  assert.deepEqual(reduce(s, {type: 'CONFIGURE', roles: 7, scenario: 'interrupted'}), s);
  s = incoming(s, 'VERIFIED'); assert.equal(s.phase, 'RUNNING');
  for (let n = 0; n < 3; n++) s = incoming(s, 'ROLE_COMPLETED');
  assert.equal(s.phase, 'VERIFYING');
  s = incoming(s, 'VERIFIED'); assert.equal(s.phase, 'ACCEPTED');
});
