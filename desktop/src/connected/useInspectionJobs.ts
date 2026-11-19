import {useRef,useState} from 'react';
import {attachmentApi} from './attachments.ts';
import {request} from './client.ts';

const api=attachmentApi(request);
export type InspectionJob={key:string;project:string;thread:string;session:string;office:string;state:'reading'|'stopping'|'complete'|'error';reportId?:string;error?:string};
export function useInspectionJobs(office:string,session:string){
  const [jobs,setJobs]=useState<InspectionJob[]>([]);
  const flights=useRef(new Set<string>());
  const identity=(p:string,t:string)=>JSON.stringify([office,session,p,t]);
  function record(job:InspectionJob){setJobs(previous=>{
    const others=previous.filter(entry=>entry.key!==job.key);
    return [...others.filter(entry=>entry.state==='reading'||entry.state==='stopping'),...others.filter(entry=>entry.state==='complete'||entry.state==='error').slice(-64),job];
  });}
  async function inspect(project:string,thread:string,ids:string[],objective:string){
    const key=identity(project,thread);
    if(flights.current.has(key))throw Error('ATTACHMENT_READER_BUSY');
    flights.current.add(key);const item={key,project,thread,office,session};
    record({...item,state:'reading'});
    try{
      const result=await api.inspect(project,thread,ids,objective);
      record({...item,state:'complete',reportId:result.id});
      return result;
    }catch(e){
      record({...item,state:'error',error:e instanceof Error?e.message:'ATTACHMENT_READ_FAILED'});throw e;
    }finally{flights.current.delete(key);}
  }
  async function stop(job:InspectionJob){
    if(job.state!=='reading'||!flights.current.has(job.key))return;
    setJobs(old=>old.map(j=>j.key===job.key&&j.state==='reading'?{...j,state:'stopping'}:j));
    try{return await api.cancel(job.project,job.thread);}
    catch(e){setJobs(old=>old.map(j=>j.key===job.key&&j.state==='stopping'?{...j,state:'reading'}:j));throw e;}
  }
  return {jobs:jobs.filter(j=>j.office===office&&j.session===session),inspect,stop};
}
