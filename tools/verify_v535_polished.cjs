/* Check export typography, geometry and extraction with independent PDF readers on Windows. */
'use strict';
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
const {execFileSync}=require('node:child_process');
const {stripTypeScriptTypes}=require('node:module');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const out=path.resolve(process.argv[2]);
const poppler=process.env.PDFTOTEXT||'pdftotext';
const token='Αθήνα 東京 😀',wide='W'.repeat(180);
async function check(){
  fs.mkdirSync(out,{recursive:true});
  const browser=await chromium.launch({channel:'msedge',headless:true});
  try{
    const page=await browser.newPage();
    const source=fs.readFileSync(path.join(__dirname,'../desktop/src/office/reportPdf.ts'),'utf8');
    await page.addScriptTag({content:stripTypeScriptTypes(source.replace('export function reportPdf(','function reportPdf('),{mode:'transform'})});
    const content=['Neural Office · Tipografía',token,wide,'Texto posterior · 24 horas',...Array.from({length:52},(_,i)=>'Línea '+(i+1))];
    const data=await page.evaluate(async list=>Array.from(new Uint8Array(await reportPdf(list).arrayBuffer())),content);
    const file=path.join(out,'tipografia.pdf');fs.writeFileSync(file,Buffer.from(data));
    const run=(args)=>execFileSync(poppler,args,{encoding:'utf8',windowsHide:true});
    const raw=run(['-raw','-enc','UTF-8',file,'-']).replace(/\r/g,'');
    assert(raw.includes(token),JSON.stringify(raw.slice(0,200)));
    assert(raw.replace(/\s/g,'').includes(wide));
    assert(raw.includes('Texto posterior · 24 horas'));
    const xml=run(['-bbox','-enc','UTF-8',file,'-']);
    const words=[...xml.matchAll(/<word xMin="([\d.-]+)" yMin="([\d.-]+)" xMax="([\d.-]+)" yMax="([\d.-]+)"/g)];
    assert(words.length>60);
    for(const [,x1,y1,x2,y2] of words)assert(+x1>=40&&+x2<=555&&+y1>=35&&+y2<=802,[x1,y1,x2,y2].join(','));
    const pages=[...xml.matchAll(/<page width=/g)].length;assert.equal(pages,2);
    const result={pages,words:words.length,xMax:Math.max(...words.map(w=>+w[3])),unicode:token,wideCharacters:wide.length};
    fs.writeFileSync(path.join(out,'geometria.json'),JSON.stringify(result,null,2));console.log(result);
  }finally{await browser.close();}
}
check().catch(e=>{console.error(e);process.exitCode=1;});
