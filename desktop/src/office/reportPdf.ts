// The WebView supplies font fallback. Every rendered line also contains selectable PDF text.
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
  let hex='';
  for (let i=0;i<text.length;i++) hex+=text.charCodeAt(i).toString(16).padStart(4,'0');
  return hex;
}

function wrap(text:string,ctx:CanvasRenderingContext2D) {
  const lines:string[]=[];
  let line='';
  const fits=(value:string)=>ctx.measureText(value).width<=496;
  for (const word of text.split(/\s+/)) {
    if(!word)continue;
    const joined=line?line+' '+word:word;
    if(fits(joined)){line=joined;continue;}
    if(line){lines.push(line);line='';}
    if(fits(word)){line=word;continue;}
    for(const character of word){
      if(line&&!fits(line+character)){lines.push(line);line='';}
      line+=character;
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
  ctx.font='40px Arial, sans-serif';
  ctx.fillStyle='#161616';ctx.fillText(line,0,39,canvas.width);
  return atob(canvas.toDataURL('image/jpeg',.94).split(',')[1]);
}

export function reportPdf(paragraphs:string[]) {
  const measure=document.createElement('canvas').getContext('2d');
  if(!measure)throw new Error('No se pudo medir la tipografía del informe.');
  measure.font='10px Arial, sans-serif';
  const lines=paragraphs.flatMap(p=>p.split(/\r\n|[\n\r\v\f\x1c-\x1e\x85\u2028\u2029]/).flatMap(s=>wrap(s,measure)));
  const objects=['<< /Type /Catalog /Pages 2 0 R >>','',
    '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>'];
  const add=(object:string)=>objects.push(object);
  const streamObject=(s:string)=>add('<< /Length '+s.length+' >>\nstream\n'+s+'\nendstream');
  // A small Type 3 subset gives each Unicode scalar its own code and ToUnicode entry.
  // Positions use the measured line width. The following opaque image supplies the visible glyphs.
  const characters=[...new Set(lines.filter(line=>ansi(line)===null).flatMap(line=>Array.from(line)))];
  const codes=new Map<string,{font:string;code:string;width:number}>();
  const fonts=['/F1 3 0 R'];
  if(characters.length){
    const glyphs=new Map<number,number>();
    for(let offset=0;offset<characters.length;offset+=240){
      const subset=characters.slice(offset,offset+240);
      const font='U'+fonts.length;
      const hex=(n:number)=>n.toString(16).padStart(2,'0');
      const mapping:string[]=[];
      for(let i=0;i<subset.length;i+=100){
        const chunk=subset.slice(i,i+100);
        mapping.push(chunk.length+' beginbfchar',...chunk.map((c,j)=>'<'+hex(i+j+1)+'> <'+utf16(c)+'>'),'endbfchar');
      }
      const cmap=streamObject('/CIDInit /ProcSet findresource begin 12 dict begin begincmap\n/CIDSystemInfo << /Registry (Local) /Ordering (Unicode) /Supplement 0 >> def\n/CMapName /'+font+' def /CMapType 2 def\n1 begincodespacerange\n<01> <f0>\nendcodespacerange\n'+mapping.join('\n')+'\nendcmap CMapName currentdict /CMap defineresource pop end end');
      const names=subset.map((_,i)=>'/g'+(i+1));
      const widths=subset.map(c=>Math.round(measure.measureText(c).width*100));
      const procedures=widths.map((w,i)=>{
        if(!glyphs.has(w))glyphs.set(w,streamObject(w+' 0 0 -200 '+w+' 800 d1'));
        return names[i]+' '+glyphs.get(w)+' 0 R';
      });
      const ref=add('<< /Type /Font /Subtype /Type3 /Name /'+font+' /FontBBox [0 -200 '+Math.max(...widths)+' 800] /FontMatrix [0.001 0 0 0.001 0 0] /FirstChar 1 /LastChar '+subset.length+' /Widths ['+widths.join(' ')+'] /CharProcs << '+procedures.join(' ')+' >> /Encoding << /Type /Encoding /Differences [1 '+names.join(' ')+'] >> /Resources << >> /ToUnicode '+cmap+' 0 R >>');
      fonts.push('/'+font+' '+ref+' 0 R');
      subset.forEach((c,i)=>codes.set(c,{font,code:hex(i+1),width:widths[i]}));
    }
  }
  const pages:number[]=[];
  for (let start=0;start<Math.max(lines.length,1);start+=49) {
    const commands:string[]=[];
    const images:string[]=[];
    for (const [row,line] of lines.slice(start,start+49).entries()) {
      const y=786-row*15;
      const literal=ansi(line);
      if (literal!==null) {
        commands.push('BT /F1 10 Tf 100 Tz 0 Tr 1 0 0 1 44 '+y+' Tm ('+literal+') Tj ET');
        continue;
      }
      const pixels=rasterLine(line);
      const ref=add('<< /Type /XObject /Subtype /Image /Width 2040 /Height 52 /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length '+pixels.length+' >>\nstream\n'+pixels+'\nendstream');
      images.push('/I'+row+' '+ref+' 0 R');
      const runs:{font:string;hex:string}[]=[];
      let advance=0;
      for(const c of line){
        const {font,code,width}=codes.get(c)!;
        advance+=width/100;
        const last=runs.at(-1);
        if(last?.font===font)last.hex+=code;
        else runs.push({font,hex:code});
      }
      const scale=(advance?100*measure.measureText(line).width/advance:100).toFixed(3);
      commands.push('BT '+scale+' Tz 3 Tr 1 0 0 1 44 '+y+' Tm '+runs.map(r=>'/'+r.font+' 10 Tf <'+r.hex+'> Tj').join(' ')+' ET');
      commands.push('q 510 0 0 13 44 '+(y-3)+' cm /I'+row+' Do Q');
    }
    const content=commands.join('\n')+'\n';
    const stream=add('<< /Length '+content.length+' >>\nstream\n'+content+'endstream');
    pages.push(add('<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << '+fonts.join(' ')+' >> /XObject << '+images.join(' ')+' >> >> /Contents '+stream+' 0 R >>'));
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
