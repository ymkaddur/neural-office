import test from 'node:test';
import assert from 'node:assert/strict';
import { attachmentApi } from './attachments.ts';
import type { Requester } from './client.ts';

test('opening a thread serializes metadata and a repeated read shares its result', async () => {
  const calls: string[] = [];
  let release!: () => void;
  const gate = new Promise<void>(done => { release = done; });
  const send: Requester = async <T>(method: string) => {
    calls.push(method);
    if (calls.length === 1) await gate;
    return [] as T;
  };
  const api = attachmentApi(send);
  const one = api.threads('Portal'), two = api.threads('Portal'), list = api.list('Portal', 'main');
  await Promise.resolve();
  assert.deepEqual(calls, ['attachments.threads']);
  release();
  assert.equal(await one, await two);
  await list;
  assert.deepEqual(calls, ['attachments.threads', 'attachments.list']);
});

test('capacity retries read operations and sends inspections and grants once', async () => {
  const calls: string[] = [];
  const send: Requester = async <T>(method: string) => {
    calls.push(method);
    if (method === 'attachments.report' && calls.length === 2) return {} as T;
    throw Error('HOST_BUSY');
  };
  const api = attachmentApi(send);
  await api.report('Portal', 'main', 'saved');
  await assert.rejects(api.inspect('Portal', 'main', ['capture'], ''), /HOST_BUSY/);
  await assert.rejects(api.preview('Portal', 'main', 'saved', 'digest', 'Compara los plazos.'), /HOST_BUSY/);
  assert.deepEqual(calls, ['attachments.report', 'attachments.report', 'attachments.inspect', 'attachments.preview']);
});

test('cancelling a preview suppresses deferred retries for the same thread', async () => {
  const calls: string[] = [];
  const send: Requester = async <T>(method: string) => {
    calls.push(method);
    if (method === 'attachments.view') throw Error('HOST_BUSY');
    return { cancelled: 0 } as T;
  };
  const api = attachmentApi(send);
  const view = api.view('Portal', 'main', 'capture');
  await Promise.resolve();
  await api.cancel('Portal', 'main');
  await assert.rejects(view, /ATTACHMENT_READ_CANCELLED/);
  assert.deepEqual(calls, ['attachments.view', 'attachments.cancel']);
});
