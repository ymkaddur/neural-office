'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {createHash}=require('node:crypto');

module.exports=async function verifyInspector({page,checked,project,python,runFile,root,sourceFolder,out}){
  const directory=path.join(sourceFolder,'ejemplo-inspector');
  await runFile(python,[path.join(root,'examples','multiformat','build_example.py'),directory],{windowsHide:true});
  const manifest=path.join(directory,'manifiesto.json'),packagePath=path.join(directory,'entrega.zip');
  const owner={project_id:project,thread_id:'prueba-con-identidad'};
  const captures=await checked('host.attachments.capture',{...owner,paths:[path.join(directory,'especificacion.pdf'),manifest,packagePath]});
  const report=await checked('attachments.inspect',{...owner,attachment_ids:captures.slice(0,2).map(f=>f.id),objective:'Compara el plazo de primera respuesta.'});
  assert(report.findings.some(f=>f.sources.some(c=>c.page===2&&c.region?.length===4)));
  await page.getByRole('navigation',{name:'Navegación principal'}).getByRole('button',{name:'Proyectos',exact:true}).click();
  await page.keyboard.press('Control+k');
  await page.getByRole('textbox',{name:'Buscar por nombre o proyecto'}).fill(report.objective);
  await page.getByRole('region',{name:'Entregas',exact:true}).getByRole('button',{name:new RegExp(report.id.slice(0,8))}).click();
  const panel=page.locator('.file-inspector');
  async function enter(locator){await locator.focus();await page.keyboard.press('Enter');}
  async function focused(){await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));return page.evaluate(()=>{const e=document.activeElement;return e.getAttribute('aria-label')||e.textContent?.trim().slice(0,80)||e.tagName;});}
  const pageNumber=number=>panel.locator('.viewer-toolbar span').filter({hasText:number+' / 2'}).waitFor();
  const receipt=async()=>({quotes:await panel.locator('blockquote').allTextContents(),marks:await panel.locator('.pdf-hit').count(),focus:await focused()});
  const cite=page.locator('.citation-row').filter({hasText:'especificacion.pdf'}).first();
  await enter(cite);await panel.locator('.pdf-hit').waitFor();
  const observed={initial:await receipt()};
  await enter(panel.getByRole('button',{name:'Página anterior'}));await pageNumber(1);observed.other=await receipt();
  await enter(panel.getByRole('button',{name:'Página siguiente'}));await pageNumber(2);observed.back=await receipt();

  await page.evaluate(()=>{const host=window.__TAURI_INTERNALS__,invoke=host.invoke.bind(host);
    window.inspectorProbe={restore:()=>{host.invoke=invoke;},delay:false,omitMemberHash:false};
    host.invoke=async(operation,payload)=>{const value=await invoke(operation,payload),probe=window.inspectorProbe;
      if(payload?.message?.method==='attachments.view'&&value?.result){
        if(probe.delay){probe.delay=false;await new Promise(resolve=>{probe.release=resolve;});}
        if(probe.omitMemberHash&&value.result.member){const result={...value.result};delete result.member_sha256;return {...value,result};}
      }return value;};
  });
  try{
    await page.evaluate(()=>{window.inspectorProbe.delay=true;});
    await enter(panel.getByRole('button',{name:'Página anterior'}));await page.waitForFunction(()=>typeof window.inspectorProbe.release==='function');
    const composer=page.getByRole('textbox',{name:'Instrucción para el Director'});await composer.focus();await page.keyboard.insertText('Borrador durante la lectura');
    await page.evaluate(()=>window.inspectorProbe.release());await pageNumber(1);observed.focusAfterTyping=await focused();
    await enter(panel.getByRole('button',{name:'Ver adjuntos'}));
    const zip=panel.locator('.file-list button').filter({hasText:'entrega.zip'});await enter(zip);
    const member=panel.getByRole('button',{name:'manifiesto.json',exact:true});await member.waitFor();observed.openedFileFocus=await focused();await enter(member);
    const identity=panel.locator('details.viewer-details').filter({hasText:'Identidad de la captura'});
    await panel.locator('.source-text').waitFor();await identity.waitFor();
    const readIdentity=async()=>({text:await identity.textContent(),hashes:await identity.locator('code').allTextContents()});
    observed.zip=await readIdentity();
    await enter(panel.getByRole('button',{name:'Ver adjuntos'}));await zip.waitFor();observed.restoredFileFocus=await zip.evaluate(e=>e===document.activeElement);
    await page.evaluate(()=>{window.inspectorProbe.omitMemberHash=true;});
    await enter(zip);await enter(member);await panel.locator('.source-text').waitFor();
    await identity.waitFor();observed.legacyZip=await readIdentity();
  }finally{await page.evaluate(()=>{window.inspectorProbe.restore();delete window.inspectorProbe;});}
  const hash=file=>createHash('sha256').update(fs.readFileSync(file)).digest('hex');
  fs.writeFileSync(path.join(out,'inspector.json'),JSON.stringify(observed,null,2));
  assert.equal(observed.initial.marks,1);assert.equal(observed.initial.quotes.length,1);
  assert.equal(observed.other.marks,0);assert.deepEqual(observed.other.quotes,[]);
  assert.equal(observed.back.marks,1);assert.deepEqual(observed.back.quotes,observed.initial.quotes);
  assert.equal(observed.other.focus,'Página siguiente');assert.equal(observed.back.focus,'Página anterior');
  assert.equal(observed.focusAfterTyping,'Instrucción para el Director');
  assert.equal(observed.openedFileFocus,'entrega.zip');assert.equal(observed.restoredFileFocus,true);
  assert.deepEqual(observed.zip.hashes,[hash(manifest),hash(packagePath)]);
  assert.match(observed.zip.text,/SHA-256 del archivo del ZIP/);assert.match(observed.zip.text,/SHA-256 del paquete/);
  assert.deepEqual(observed.legacyZip.hashes,[hash(packagePath)]);assert.match(observed.legacyZip.text,/Huella del archivo no disponible/);
};
