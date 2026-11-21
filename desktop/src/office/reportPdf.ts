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

export type ReportParagraph=string|{kind:'heading'|'quote';text:string};
type PrintRow={visible:string;semantic:string;image:boolean};

function wrap(text:string,ctx:CanvasRenderingContext2D) {
  const lines:string[]=[];
  let line='',longToken=false;
  const fits=(value:string)=>ctx.measureText(value).width<=496;
  for(const part of text.match(/\s+|\S+/gu)??[]){
    if(fits(line+part)){line+=part;continue;}
    if(line){lines.push(line);line='';}
    if(fits(part)){line=part;continue;}
    if(/\S/u.test(part))longToken=true;
    for(const character of part){
      if(line&&!fits(line+character)){lines.push(line);line='';}
      line+=character;
    }
  }
  lines.push(line);
  return {lines,longToken};
}

function rasterLine(line:string) {
  const canvas=document.createElement('canvas');
  canvas.height=52; canvas.width=2040;
  const ctx=canvas.getContext('2d');
  if (!ctx) throw new Error('El visor no ha podido componer esta línea del PDF.');
  ctx.fillStyle='#fff';ctx.fillRect(0,0,canvas.width,canvas.height);
  ctx.font='40px Arial, sans-serif';
  ctx.fillStyle='#161616';ctx.fillText(line,0,39,canvas.width);
  if(ansi(line)===null)return {color:'/DeviceRGB',bits:8,filter:'/DCTDecode',data:atob(canvas.toDataURL('image/jpeg',.94).split(',')[1])};
  // Mostly white rows of four-times-resolution Latin text fit a small monochrome image.
  const pixels=ctx.getImageData(0,0,canvas.width,canvas.height).data;
  const bitmap=new Uint8Array(canvas.width*canvas.height/8);
  for(let i=0;i<bitmap.length;i++){
    let bits=0;
    for(let b=0;b<8;b++)bits=(bits<<1)|(pixels[(i*8+b)*4]>=155?1:0);
    bitmap[i]=bits;
  }
  const output:number[]=[];
  for(let at=0;at<bitmap.length;){
    let end=at+1;
    while(end<bitmap.length&&end-at<128&&bitmap[end]===bitmap[at])end++;
    if(end-at>1){output.push(257-(end-at),bitmap[at]);at=end;continue;}
    while(end<bitmap.length&&end-at<128&&bitmap[end]!==bitmap[end+1])end++;
    output.push(end-at-1,...bitmap.subarray(at,end));at=end;
  }
  output.push(128);
  return {color:'/DeviceGray',bits:1,filter:'/RunLengthDecode',data:String.fromCharCode(...output)};
}

function printPages(paragraphs:ReportParagraph[],measure:CanvasRenderingContext2D){
  const pages:PrintRow[][]=[[]];
  let page=pages[0];
  const newPage=()=>{page=[];pages.push(page);};
  const blocks:{rows:PrintRow[];heading:boolean}[]=[];
  for(const paragraph of paragraphs){
    const text=typeof paragraph==='string'?paragraph:paragraph.text;
    const heading=typeof paragraph!=='string'&&paragraph.kind==='heading';
    const quote=typeof paragraph!=='string'&&paragraph.kind==='quote';
    const rows:PrintRow[]=[];
    for(const source of text.split(/\r\n|[\n\r\v\f\x1c-\x1e\x85\u2028\u2029]/)){
      const visible=source.replace(/\t/g,'    ');
      const wrapped=wrap(visible,measure);
      // The visible rows remain at reading size, while one selectable span preserves
      // the source line for copying a citation or searching for a long identifier.
      const keepSource=visible!==source||wrapped.longToken||(quote&&wrapped.lines.length>1);
      wrapped.lines.forEach((line,i)=>{
        const semantic=keepSource?(i===0?source:''):line;
        rows.push({visible:line,semantic,image:keepSource||ansi(line)===null});
      });
    }
    blocks.push({rows,heading});
  }
  for(const [i,{rows,heading}] of blocks.entries()){
    if(heading&&page.length){
      let keep=rows.length;
      for(let next=i+1;next<blocks.length&&keep<49;next++){
        const block=blocks[next];
        if(block.heading||block.rows.every(row=>!row.visible.trim()))keep+=block.rows.length;
        else{keep++;break;}
      }
      if(page.length+Math.min(keep,49)>49)newPage();
    }
    for(const row of rows){if(page.length===49)newPage();page.push(row);}
  }
  return pages;
}

export function reportPdf(paragraphs:ReportParagraph[]) {
  const measure=document.createElement('canvas').getContext('2d');
  if(!measure)throw new Error('No se pudo medir la tipografía del informe.');
  measure.font='10px Arial, sans-serif';
  const layout=printPages(paragraphs,measure);
  const objects=['<< /Type /Catalog /Pages 2 0 R >>','',
    '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>'];
  const add=(object:string)=>objects.push(object);
  const streamObject=(s:string)=>add('<< /Length '+s.length+' >>\nstream\n'+s+'\nendstream');
  // A small Type 3 subset gives each Unicode scalar its own code and ToUnicode entry.
  // Positions use the measured line width. The following opaque image supplies the visible glyphs.
  const characters=[...new Set(layout.flat().flatMap(row=>ansi(row.semantic)===null?Array.from(row.semantic):[]))];
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
      // Tab stops belong to the visible line. A second advance for the semantic
      // tab makes geometry-based extractors invent a space after /ActualText.
      const widths=subset.map(c=>c==='\t'?0:Math.round(measure.measureText(c).width*100));
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
  for (const rows of layout) {
    const commands:string[]=[];
    const images:string[]=[];
    for(const [row,{visible,semantic:line,image}] of rows.entries()){
      const y=786-row*15;
      if(image){
        const pixels=rasterLine(visible);
        const ref=add('<< /Type /XObject /Subtype /Image /Width 2040 /Height 52 /ColorSpace '+pixels.color+' /BitsPerComponent '+pixels.bits+' /Filter '+pixels.filter+' /Length '+pixels.data.length+' >>\nstream\n'+pixels.data+'\nendstream');
        images.push('/I'+row+' '+ref+' 0 R');
        commands.push('/Artifact BMC q 510 0 0 13 44 '+(y-3)+' cm /I'+row+' Do Q EMC');
      }
      if(!line)continue;
      const literal=ansi(line);
      const width=measure.measureText(line).width;
      if(image)commands.push('/Span << /ActualText <feff'+utf16(line)+'> >> BDC');
      if(literal!==null){
        const scale=Math.min(100,496/Math.max(width,1)*100).toFixed(3);
        commands.push('BT /F1 10 Tf '+scale+' Tz '+(image?'3':'0')+' Tr 1 0 0 1 44 '+y+' Tm ('+literal+') Tj ET');
        if(image)commands.push('EMC');
        continue;
      }
      const runs:{font:string;hex:string}[]=[];
      let advance=0;
      for(const c of line){
        const {font,code,width}=codes.get(c)!;
        advance+=width/100;
        const last=runs.at(-1);
        if(last?.font===font)last.hex+=code;
        else runs.push({font,hex:code});
      }
      const scale=(advance?100*Math.min(width,496)/advance:100).toFixed(3);
      commands.push('BT '+scale+' Tz 3 Tr 1 0 0 1 44 '+y+' Tm '+runs.map(r=>'/'+r.font+' 10 Tf <'+r.hex+'> Tj').join(' ')+' ET');
      if(image)commands.push('EMC');
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
