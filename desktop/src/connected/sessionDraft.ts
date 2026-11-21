import {request} from './client.ts';

type Address={session_id:string;project_id:string;thread_id:string};
type DraftReply=Address&{text:string;revision:number;evicted:null|{project_id:string;thread_id:string}};
const pending=new Map<string,Promise<void>>();
export async function readSessionDraft(session:string,project:string,thread:string){
  const address={session_id:session,project_id:project,thread_id:thread};
  await pending.get(JSON.stringify(address));
  return request<DraftReply>('draft.get',address).then(reply=>verify(address,reply));
}
function verify(address:Address,reply:DraftReply){
  if(!reply||reply.session_id!==address.session_id||reply.project_id!==address.project_id||reply.thread_id!==address.thread_id||
     typeof reply.text!=='string'||!Number.isSafeInteger(reply.revision)||reply.revision<0)throw Error('DRAFT_IDENTITY_CHANGED');
  return reply;
}
// Each editor owns one address and at most one admitted write. Later keystrokes replace the pending value.
export function draftWriter(initial:DraftReply,onError:(reason:string)=>void,onEviction:(project:string,thread:string)=>void){
  const address={session_id:initial.session_id,project_id:initial.project_id,thread_id:initial.thread_id};
  let revision=initial.revision,synced=initial.text,desired=initial.text,running=false;
  let inFlight='',sentText='';
  const canStore=(text:string)=>new TextEncoder().encode(text).byteLength<=12000&&!text.includes('\0');
  // A closing WebView cannot wait for the previous ACK before sending its final edit.
  const finish=()=>{
    if(!running||sentText===desired||!canStore(desired))return;
    void request('draft.put',{...address,text:desired,expected_revision:revision,edit_id:crypto.randomUUID(),after_edit:inFlight}).catch(()=>{});
  };
  async function flush(){
    if(running)return;
    running=true;
    try {
      while(desired!==synced){
        const sent=desired;
        if(!canStore(sent)){
          onError('El borrador supera los límites de la memoria de sesión. Puedes copiarlo o guardarlo en esta pestaña.');return;
        }
        inFlight=crypto.randomUUID();sentText=sent;
        const reply=verify(address,await request<DraftReply>('draft.put',{...address,text:sent,expected_revision:revision,edit_id:inFlight,after_edit:'none'}));
        if(reply.text!==sent)throw Error('DRAFT_RESPONSE_CHANGED');
        revision=reply.revision;synced=reply.text;
        if(reply.evicted)onEviction(reply.evicted.project_id,reply.evicted.thread_id);
      }
    }catch(e){onError('La última edición sigue en el editor. Guárdala en esta pestaña antes de recargar. ('+(e instanceof Error?e.message:'DRAFT_WRITE_FAILED')+')');}
    finally{running=false;window.removeEventListener('pagehide',finish);}
  }
  return (text:string)=>{
    desired=text;
    if(running||desired===synced)return;
    window.addEventListener('pagehide',finish);
    const key=JSON.stringify(address),work=flush();
    pending.set(key,work);
    void work.finally(()=>{if(pending.get(key)===work)pending.delete(key);});
  };
}
