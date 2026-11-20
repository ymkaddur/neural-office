// Use PDF text for WinAnsi and a WebView-rendered line for scripts that need font fallback.
// ActualText preserves the original characters for copying and accessible extraction.
const encoding = new Map(Array.from('€‚ƒ„…†‡ˆ‰Š‹ŒŽ‘’“”•–—˜™š›œžŸ').map((c,i) => [
  c, [128,130,131,132,133,134,135,136,137,138,139,140,142,145,146,147,148,149,150,151,152,153,154,155,156,158,159][i],
]));

function ansi(text:string) {
  let result='';
  for (const c of text) {
    const value=c.codePointAt(0)!;
    if ((value>=32 && value<=126) || (value>=160 && value<=255)) result+=c;
    else if (encoding.has(c)) result+=String.fromCharCode(encoding.get(c)!);
    else return null;
  }
  return result.replace(/[\\()]/g,c=>'\\'+c);
}

function utf16(text:string) {
  let hex='FEFF';
  for (let i=0;i<text.length;i++) hex+=text.charCodeAt(i).toString(16).padStart(4,'0');
  return hex;
}

function wrap(text:string) {
  const lines:string[]=[];
  let line='';
  for (const word of text.split(/\s+/)) {
    const chars=Array.from(word);
    if (line && Array.from(line).length+chars.length+1>81) {lines.push(line);line='';}
    for (let i=0;i<chars.length;i+=81) {
      const part=chars.slice(i,i+81).join('');
      if (i+81<chars.length) lines.push(part);
      else line+=(line?' ':'')+part;
    }
  }
  lines.push(line);
  return lines;
}

function rasterLine(line:string) {
  const canvas=document.createElement('canvas');
  canvas.height=52; canvas.width=2040;
  const ctx=canvas.getContext('2d');
  if (!ctx) throw new Error('El visor no ha podido componer esta línea del PDF.');
  ctx.fillStyle='#fff';ctx.fillRect(0,0,canvas.width,canvas.height);
  ctx.font='40px "Segoe UI", sans-serif';
  ctx.fillStyle='#161616';ctx.fillText(line,0,39,canvas.width);
  return atob(canvas.toDataURL('image/jpeg',.94).split(',')[1]);
}

export function reportPdf(paragraphs:string[]) {
  const lines=paragraphs.flatMap(p=>p.split(/\r\n|\r|\n/).flatMap(wrap));
  const objects=['<< /Type /Catalog /Pages 2 0 R >>','',
    '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>'];
  const add=(object:string)=>objects.push(object);
  const pages:number[]=[];
  for (let start=0;start<Math.max(lines.length,1);start+=49) {
    const commands:string[]=[];
    const images:string[]=[];
    for (const [row,line] of lines.slice(start,start+49).entries()) {
      const y=786-row*15;
      const literal=ansi(line);
      if (literal!==null) {
        commands.push('BT /F1 10 Tf 1 0 0 1 44 '+y+' Tm ('+literal+') Tj ET');
        continue;
      }
      const pixels=rasterLine(line);
      const ref=add('<< /Type /XObject /Subtype /Image /Width 2040 /Height 52 /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length '+pixels.length+' >>\nstream\n'+pixels+'\nendstream');
      images.push('/I'+row+' '+ref+' 0 R');
      const actual='/Span << /ActualText <'+utf16(line)+'> >> BDC ';
      commands.push(actual+'q 510 0 0 13 44 '+(y-3)+' cm /I'+row+' Do Q EMC');
    }
    const content=commands.join('\n')+'\n';
    const stream=add('<< /Length '+content.length+' >>\nstream\n'+content+'endstream');
    pages.push(add('<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> /XObject << '+images.join(' ')+' >> >> /Contents '+stream+' 0 R >>'));
  }
  objects[1]='<< /Type /Pages /Count '+pages.length+' /Kids ['+pages.map(ref=>ref+' 0 R').join(' ')+'] >>';
  let pdf='%PDF-1.4\n';
  const offsets=[0];
  for (const [i,object] of objects.entries()) {
    offsets.push(pdf.length);
    pdf+=(i+1)+' 0 obj\n'+object+'\nendobj\n';
  }
  const xref=pdf.length;
  pdf+='xref\n0 '+offsets.length+'\n0000000000 65535 f \n'+offsets.slice(1).map(n=>String(n).padStart(10,'0')+' 00000 n \n').join('')+
    'trailer\n<< /Size '+offsets.length+' /Root 1 0 R >>\nstartxref\n'+xref+'\n%%EOF\n';
  return new Blob([Uint8Array.from(pdf,c=>c.charCodeAt(0))],{type:'application/pdf'});
}
