import test from 'node:test';
import assert from 'node:assert/strict';
import { attachmentApi, consultationQuestion } from './attachments.ts';
import type { Inspection } from './attachments.ts';
import type {Inspection, InspectionFinding} from './attachments.ts';
import {exportVersion, receiptMarkdown, sourceLabel} from '../office/team.ts';
import type {Receipt} from '../office/team.ts';
import type { Requester } from './client.ts';

test('follow-ups use the same captured evidence and text-only turns bind their saved question', () => {
  const question = '¿Qué dice la fuente?';
  const file = {id:'captura',source_id:'captura',name:'plazo.txt',sha256:'a'.repeat(64),kind:'text',bytes:20,created_at:1,origin:'snapshot'};
  const citation = {attachment_id:file.id,name:file.name,sha256:file.sha256,quote:'Primera respuesta en 24 h.'};
  const finding: Inspection['findings'][number] = {rule:'literal_search',status:'observed',title:'Plazo',detail:'Lectura local',sources:[citation]};
  const report: Inspection = {id:'inspeccion',project_id:'prueba',thread_id:'main',created_at:1,objective:'Localiza el plazo.',attachments:[file],findings:[finding],steps:[],model_calls:0,reservations:0};
  assert.equal(consultationQuestion(report,true,question),question);
  assert.equal(consultationQuestion(report,true,'  '),report.objective);
  assert.equal(consultationQuestion(report,false,question),null);
  assert.equal(consultationQuestion({...report,findings:[{...finding,sources:[]}]},true,question),null);
  assert.equal(consultationQuestion({...report,findings:Array(9).fill(finding)},true,question),question);
  const text = {...report,attachments:[],findings:[{...finding,rule:'text_brief',sources:[]}]};
  assert.equal(consultationQuestion(text,true,''),text.objective);
  assert.equal(consultationQuestion(text,true,question),null);
  assert.equal(consultationQuestion({...text,findings:[]},true,''),null);
});

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

test('exported receipts bind homonymous captures to their version and visible findings', () => {
  const file = {id:'first', name:'acta.txt', kind:'text', bytes:42, sha256:'hash-1', source_id:'s1', created_at:2, origin:'local'};
  const files = [file, {...file, id:'second', sha256:'hash-2', source_id:'s2'}];
  const cite = {attachment_id:'second', name:'acta.txt', sha256:'hash-2', line:3, quote:'Contenido literal'};
  const finding:InspectionFinding = {sources:[cite], rule:'literal', title:'Coincidencia', detail:'Frase localizada', status:'observed'};
  const report:Inspection = {id:'entrega', project_id:'proyecto', thread_id:'hilo', created_at:2, objective:'Objetivo original',
    attachments:files, findings:[finding], steps:[], reservations:0, model_calls:0};
  const row:Receipt = {round:3, role:'integrator', at:2, duration_us:90, action:'Reunir evidencia', instruction:'Conserva la cita.',
    details:['## Un dato de la fuente'], sha256:'recibo-3', parent:'recibo-2'};
  assert.equal(sourceLabel(cite,report), 'Fuente 2 | acta.txt | Línea 3');
  assert.match(sourceLabel({...cite,sha256:'hash-1'},report), /sin correspondencia.*second.*hash-1/);
  const md=receiptMarkdown(report,row,[finding],true);
  for(const value of [report.id, report.project_id, report.thread_id, report.objective, row.action,
    'recibo-2','recibo-3','1970-01-01T00:00:02.000Z','90','Captura second','SHA-256 hash-2',cite.quote,finding.detail])
    assert.ok(md.includes(value),value);
  assert.ok(md.includes('\n    ## Un dato de la fuente') && !md.includes('\n## Un dato de la fuente'));
  assert.ok(!receiptMarkdown(report,row,[],false).includes(cite.quote));
  assert.ok(!receiptMarkdown(report,row,[finding],false).includes(finding.detail));
  assert.notEqual(exportVersion(report), exportVersion({...report,decision:{revision:1,choice:'defer',at:7}}));
  assert.notEqual(exportVersion(report), exportVersion({...report,id:'otro-informe'}));
});
