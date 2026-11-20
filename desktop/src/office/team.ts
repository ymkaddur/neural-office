export const teamRoles = {
  researcher: 'Investigador', planner: 'Planificador', implementer: 'Implementador',
  verifier: 'Verificador', skeptic: 'Escéptico', integrator: 'Integrador',
} as const;

export type Specialist = keyof typeof teamRoles;
export type Receipt = {
  round:number; role:Specialist; instruction:string; action:string; details:string[];
  at:number; duration_us:number; parent:string|null; sha256:string;
};
export type TeamReview = {
  version:1; engine:'deterministic'; rounds:3; receipts:Receipt[];
  delivery:{objective:string; results:string[]; limitations:string[]; sources:{name:string;sha256:string}[]};
  delivery_sha256:string;
};
export function timeLabel(seconds:number) {
  return new Intl.DateTimeFormat('es-ES',{hour:'2-digit',minute:'2-digit',second:'2-digit'}).format(seconds*1000);
}
export function downloadFile(data:Blob, name:string) {
  const address=URL.createObjectURL(data);
  const link=document.createElement('a');
  link.href=address;link.download=name;
  document.body.append(link);link.click();link.remove();
  window.setTimeout(()=>URL.revokeObjectURL(address),30000);
}
export function textFile(body:string, type='text/plain;charset=utf-8') {return new Blob([body],{type});}

export {reportPdf} from './reportPdf.ts';
