import {invoke,isTauri} from '@tauri-apps/api/core';
import {directorTextScope,excerptScope,type Citation} from './attachments.ts';

export const hasNativeHost=()=>isTauri();
export type Requester=<T>(method:string,params?:Record<string,unknown>)=>Promise<T>;
export const request:Requester=async<T>(method:string,params:Record<string,unknown>={})=>{
  if(!hasNativeHost()) throw Error('NATIVE_HOST_REQUIRED');
  const id=crypto.randomUUID(),message={version:1,id,method,params};
  if(new TextEncoder().encode(JSON.stringify(message)).length>16384) throw Error('DESKTOP_MESSAGE_SIZE');
  let envelope:unknown;
  try {envelope=await invoke('desktop_request',{message});}
  catch(error) {throw Error(typeof error==='string'&&/^[A-Z][A-Z0-9_]{0,95}$/.test(error)?error:'HOST_CONNECTION_UNAVAILABLE');}
  if(!envelope||typeof envelope!=='object') throw Error('HOST_RESPONSE_INVALID');
  const r=envelope as {version:unknown;id:unknown;ok:unknown;result:unknown;error:{code?:unknown}|null};
  if(r.version!==1||r.id!==id||typeof r.ok!=='boolean') throw Error('HOST_RESPONSE_INVALID');
  if(!r.ok) throw Error(typeof r.error?.code==='string'&&/^[A-Z][A-Z0-9_]{0,95}$/.test(r.error.code)?r.error.code:'DESKTOP_OPERATION_FAILED');
  return r.result as T;
};
export type Finding={code:string;line:number;column:number};
export type FindingPage={session_id:string;project_id:string;source_sha256:string;offset:number;total:number;findings:Finding[]};
export type Report={schema:number;scope:string;source_sha256:string;findings:Finding[];model_commentary_status:string;role_outputs:{role:string;content:string}[];authorized_fragments?:Citation[];thread_id?:string;inspection_id?:string};
type ReportMetadata={attempt_id:string;state:string;sha256:string;bytes:number;encoding:string;media_type:string;verdict:{passed:boolean;coverage:string};mode:string;generation_limited?:boolean};
type Chunk={attempt_id:string;sha256:string;offset:number;next_offset:number;eof:boolean;chunk_sha256:string;base64:string};
const sha=async(data:Uint8Array)=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',data as Uint8Array<ArrayBuffer>)),b=>b.toString(16).padStart(2,'0')).join('');
export async function readReport(send:Requester,attemptId:string,current:()=>boolean=()=>true) {
  const meta=await send<ReportMetadata>('report.get',{attempt_id:attemptId});
  if(meta.attempt_id!==attemptId||!Number.isSafeInteger(meta.bytes)||meta.bytes<1||meta.bytes>4*1024*1024||!/^[a-f0-9]{64}$/.test(meta.sha256)) throw Error('REPORT_CONTRACT');
  if(meta.state!=='ACCEPTED'||meta.verdict?.passed!==true) throw Error('REPORT_NOT_ACCEPTED');
  const bytes=new Uint8Array(meta.bytes);
  let offset=0,chunks=0;
  while(offset<meta.bytes) {
    if(++chunks>128)throw Error('REPORT_CHUNK_BUDGET');
    if(!current()) throw Error('REPORT_READ_SUPERSEDED');
    const chunk=await send<Chunk>('report.read',{attempt_id:attemptId,offset,limit:65536});
    if(typeof chunk.base64!=='string'||chunk.base64.length>87384) throw Error('REPORT_CHUNK_SIZE');
    const part=Uint8Array.from(atob(chunk.base64),c=>c.charCodeAt(0));
    if(chunk.attempt_id!==attemptId||chunk.sha256!==meta.sha256||chunk.offset!==offset||part.length<1||part.length>65536||chunk.next_offset!==offset+part.length||chunk.next_offset>meta.bytes||chunk.eof!==(chunk.next_offset===meta.bytes)||await sha(part)!==chunk.chunk_sha256) throw Error('REPORT_CHUNK_CHANGED');
    bytes.set(part,offset);offset=chunk.next_offset;
  }
  if(await sha(bytes)!==meta.sha256) throw Error('REPORT_HASH_CHANGED');
  const text=new TextDecoder('utf-8',{fatal:true}).decode(bytes),report=JSON.parse(text) as Report;
  if(report.schema!==1||!['static-html-checks-v1','static-html-checks-v2','static-html-checks-v3','static-html-checks-v4',excerptScope,directorTextScope].includes(report.scope)||report.model_commentary_status!=='UNVERIFIED_ASSISTANCE'||!Array.isArray(report.findings)||report.findings.length>10000||!Array.isArray(report.role_outputs)||report.role_outputs.length>7) throw Error('REPORT_CONTENT_INVALID');
  if(report.scope===excerptScope||report.scope===directorTextScope){
    const fragments=report.authorized_fragments;
    if(!Array.isArray(fragments)||(report.scope===directorTextScope?fragments.length!==0:fragments.length<1||fragments.length>8)||report.findings.length!==0||
      !report.thread_id||!report.inspection_id||report.role_outputs.length!==1||
      report.role_outputs[0]?.role!=='director'||fragments.some(f=>!f||typeof f.name!=='string'||typeof f.quote!=='string'||
      !/^[a-z0-9_-]{1,64}$/i.test(f.attachment_id)||!/^[a-f0-9]{64}$/.test(f.sha256))) throw Error('REPORT_EXCERPTS_INVALID');
  }
  for(const f of report.findings) if(typeof f.code!=='string'||!Number.isSafeInteger(f.line)||!Number.isSafeInteger(f.column)||f.line<1||f.column<1) throw Error('REPORT_FINDING_INVALID');
  for(const r of report.role_outputs) if(typeof r.role!=='string'||typeof r.content!=='string') throw Error('REPORT_COMMENTARY_INVALID');
  return {meta,report,text};
}
