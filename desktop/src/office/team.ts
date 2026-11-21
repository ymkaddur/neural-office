import type {Citation, Inspection, InspectionFinding} from '../connected/attachments.ts';

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
const receiptClock=new Intl.DateTimeFormat('es-ES',{hour:'2-digit',minute:'2-digit',second:'2-digit'});
export function timeLabel(seconds:number) {
  return receiptClock.format(seconds*1000);
}
export function downloadFile(data:Blob, name:string) {
  const address=URL.createObjectURL(data);
  const link=document.createElement('a');
  link.href=address;link.download=name;
  document.body.append(link);link.click();link.remove();
  window.setTimeout(()=>URL.revokeObjectURL(address),30000);
}
export function textFile(body:string, type='text/plain;charset=utf-8') {return new Blob([body],{type});}

export function exportVersion(report:Inspection) {
  return report.id+'-d'+(report.decision?.revision??0);
}

export function citationPosition(c:Citation) {
  return [c.page&&'Pág. '+c.page,c.line&&'Línea '+c.line,c.column&&'Col. '+c.column,c.pointer,c.member].filter(Boolean).join(' · ');
}

export function sourceLabel(c:Citation, report:Inspection) {
  const index=report.attachments.findIndex(file=>file.id===c.attachment_id && file.sha256===c.sha256);
  const label=index>=0?'Fuente '+(index+1):'Fuente sin correspondencia en el inventario | Captura '+c.attachment_id+' | SHA-256 '+c.sha256;
  return [label,c.name,citationPosition(c)].filter(Boolean).join(' | ');
}

export function receiptMarkdown(report:Inspection, row:Receipt, findings:InspectionFinding[], showConclusions:boolean) {
  const lines=['# '+teamRoles[row.role]+' · Iteración '+row.round,''];
  // Indented literal blocks preserve the evidence, including lines starting with Markdown syntax.
  function field(title:string, value:string) {
    lines.push(title,'',...value.split(/\r\n|[\r\n]/).map(line=>'    '+line),'');
  }
  field('Proyecto',report.project_id);
  field('Hilo',report.thread_id);
  field('Encargo',report.objective);
  field('Entrega',report.id);
  if(report.team)field('Huella de la entrega del equipo',report.team.delivery_sha256);
  field('Revisión de la decisión',String(report.decision?.revision??0));
  field('Instrucción del Director',row.instruction);
  field('Acción registrada',row.action);
  field('Hora (UTC)',new Date(row.at*1000).toISOString());
  field('Duración (µs)',String(row.duration_us));
  field('Detalle',row.details.join('\n'));
  field('Recibo',row.sha256);
  if(row.parent)field('Recibo anterior',row.parent);
  if(findings.length) {
    lines.push(showConclusions?'## Conclusiones de la entrega':'## Fuentes de la entrega','');
    for(const finding of findings) {
      if(showConclusions)field('Hallazgo',finding.title+'\n'+finding.detail);
      for(const c of finding.sources) {
        field('Fuente',[sourceLabel(c,report),'Captura '+c.attachment_id,'SHA-256 '+c.sha256].join('\n'));
        if(c.quote)field('Cita',c.quote);
      }
    }
  }
  return lines.join('\n');
}

export {reportPdf} from './reportPdf.ts';
