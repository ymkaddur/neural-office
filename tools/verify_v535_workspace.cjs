/* Render the production application with its real local stdio service and an isolated picker. */
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const os=require('node:os');
const {execFile,spawn}=require('node:child_process');
const {promisify}=require('node:util');
const runFile=promisify(execFile);
const {randomUUID}=require('node:crypto');
const playwright=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const root=path.resolve(__dirname,'..'),dist=path.join(root,'desktop','dist');
const interactive=process.argv.includes('--open');
const out=path.resolve(process.argv[2]);
fs.mkdirSync(out,{recursive:true});
const office=fs.mkdtempSync(path.join(os.tmpdir(),'oficina-v535-'));
const sourceFolder=path.join(office,'archivos');
fs.mkdirSync(sourceFolder);
const inputs=[
  ['requisitos.md','El equipo acordó una primera respuesta en 24 horas.\nVerificar el plazo de la entrega antes de publicarla.\n'],
  ['entrega.csv','campo,valor\nprimera_respuesta_horas,48\nidioma,es\n'],
  ['mediciones.instrumento',Buffer.from([0,15,25,31,127,255,0,9])],
].map(([name,body])=>{const file=path.join(sourceFolder,name);fs.writeFileSync(file,body);return file;});
const python=process.env.NEURAL_OFFICE_PYTHON||'python';
const core=spawn(python,['-B','-m','neural_office.desktop_stdio','--state',path.join(office,'estado.db')],{cwd:root,stdio:['pipe','pipe','pipe'],windowsHide:true});
const waiting=new Map();
let incoming='';
core.stdout.setEncoding('utf8').on('data',chunk=>{
  incoming+=chunk;
  let end;
  // The host protocol uses LF bytes. U+2028 and U+2029 can be part of a JSON string.
  while((end=incoming.indexOf('\n'))>=0){
    const reply=JSON.parse(incoming.slice(0,end));incoming=incoming.slice(end+1);
    const finish=waiting.get(reply.id);
    if(finish){waiting.delete(reply.id);finish.resolve(reply);}
  }
});
core.stderr.on('data',chunk=>process.stderr.write(chunk));
core.on('exit',code=>{for(const r of waiting.values())r.reject(Error('Core exited '+code));waiting.clear();});
const call=(method,params={})=>new Promise((resolve,reject)=>{
  const id=randomUUID();waiting.set(id,{resolve,reject});
  core.stdin.write(JSON.stringify({version:1,id,method,params})+'\n');
});
async function chooseFiles(){
  if(!interactive)return inputs;
  const picker=[
    'import json, sys, tkinter as tk',
    'from tkinter import filedialog',
    'root = tk.Tk()',
    'root.withdraw()',
    "root.attributes('-topmost', True)",
    "paths = filedialog.askopenfilenames(parent=root, title='Adjuntar archivos al hilo', initialdir=sys.argv[1])",
    'root.destroy()',
    'print(json.dumps(list(paths), ensure_ascii=True))',
  ].join('\n');
  const {stdout}=await runFile(python,['-I','-B','-c',picker,sourceFolder],{windowsHide:true,signal:pickerLifetime.signal});
  return JSON.parse(stdout);
}
const pickerLifetime=new AbortController();
async function checked(method,params){
  for(const delay of [0,50,100,200,400,800]){
    if(delay)await new Promise(done=>setTimeout(done,delay));
    const response=await call(method,params);
    // The stdio service returns HOST_BUSY only before admitting a request to its lane.
    if(response.error?.code==='HOST_BUSY'&&delay<800)continue;
    assert.equal(response.ok,true,method+' '+JSON.stringify(response.error));
    return response.result;
  }
}
const address='http://127.0.0.1:52375';
const project='Portal de clientes',thread='main';
const allowed=new Set(['describe','models.list','projects.list','snapshot.get','project.history','attachments.pick','attachments.list',
  'attachments.cancel','attachments.threads','attachments.inspect','attachments.view','attachments.history','attachments.report',
  'attachments.activity','attachments.decide','attachments.search','library.list','library.change','library.for_draft','library.history','events.read','attempt.events','attempt.get','attempt.lookup','attempt.recover','attempt.cancel']);
const roster=['Investigador','Planificador','Implementador','Verificador','Escéptico','Integrador'];
const pages=['Director',...roster,'Memoria','Skills','Ajustes'];
let browser;
let pickerLimitOnce=false,interruptNextInspection=false,finishInterruptedRead,staleRecoveryOnce=false,conflicts=0;
async function main(){
  const files=await checked('host.attachments.capture',{project_id:project,thread_id:thread,paths:inputs});
  const report=await checked('attachments.inspect',{project_id:project,thread_id:thread,attachment_ids:files.map(f=>f.id),objective:'Inspecciona los archivos de la entrega.'});
  assert.equal(report.team.receipts.length,18);assert(report.team.delivery.limitations.length>0);
  const source={project_id:project,thread_id:thread,report_id:report.id};
  async function entry(kind,title,body){
    const id=randomUUID();
    await checked('library.change',{...source,kind,title,body,entry_id:id,operation:'create',expected_revision:0});
    return id;
  }
  await entry('memory','Plazo de respuesta','El documento de requisitos fija 24 horas. El CSV declara 48. La decisión sigue pendiente.');
  const title='Revisión de entregas';
  const skill=await entry('skill',title,'Cita el documento y conserva los límites de lectura.');
  await checked('library.change',{...source,kind:'skill',title,entry_id:skill,operation:'accept',expected_revision:1,body:''});
  await checked('library.change',{...source,kind:'skill',title,entry_id:skill,operation:'propose',expected_revision:2,body:'Cita el documento y conserva los límites de lectura. Identifica también la versión.'});
  browser=await playwright.chromium.launch({channel:'msedge',headless:!interactive});
  const context=await browser.newContext({viewport:{width:1440,height:900},colorScheme:'dark',deviceScaleFactor:1,acceptDownloads:true});
  const mime={'.html':'text/html','.js':'text/javascript','.css':'text/css','.png':'image/png','.ico':'image/x-icon'};
  await context.route('**/*',async route=>{
    const url=new URL(route.request().url());
    if(url.origin!==address)return route.abort();
    const file=path.resolve(dist,'.'+decodeURIComponent(url.pathname==='/'?'/index.html':url.pathname));
    if(!file.startsWith(dist+path.sep)||!fs.existsSync(file))return route.abort();
    return route.fulfill({path:file,contentType:mime[path.extname(file)]});
  });
  await context.exposeBinding('officeReview',async({frame,page},op,{message})=>{
    assert.equal(frame,page.mainFrame());assert.equal(new URL(frame.url()).origin,address);
    assert.equal(op,'desktop_request');assert(allowed.has(message.method));
    const params=message.params;
    let envelope;
    if(message.method==='attachments.pick'){
      if(pickerLimitOnce){pickerLimitOnce=false;throw 'HOST_PICKER_FILE_LIMIT';}
      const paths=await chooseFiles();
      envelope=paths.length?await call('host.attachments.capture',{...params,paths}):{version:1,ok:true,result:[]};
    }else if(interruptNextInspection&&message.method==='attachments.inspect'){
      interruptNextInspection=false;
      envelope=await new Promise(resolve=>{finishInterruptedRead=()=>resolve({version:1,ok:false,result:null,error:{code:'ATTACHMENT_READ_CANCELLED'}});});
    }else if(finishInterruptedRead&&message.method==='attachments.cancel'){
      finishInterruptedRead();finishInterruptedRead=undefined;envelope={version:1,ok:true,result:{cancelled:true}};
    }else if(staleRecoveryOnce&&message.method==='attempt.recover'){
      staleRecoveryOnce=false;
      envelope=await call(message.method,{...params,expected_revision:params.expected_revision-1});
      assert.equal(envelope.error?.code,'DESKTOP_REVISION_CHANGED');conflicts++;
    }else envelope=await call(message.method,params);
    return {...envelope,id:message.id};
  });
  await context.addInitScript(()=>{window.isTauri=true;window.__TAURI_INTERNALS__={invoke:(op,params)=>window.officeReview(op,params)};});
  const page=await context.newPage();page.setDefaultTimeout(10000);
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const button=name=>page.getByRole('button',{name,exact:true});
  const workspace=()=>page.getByRole('region',{name:'Trabajo del equipo y archivos de entrega'});
  const go=async name=>{await page.getByRole('navigation',{name:'Navegación principal'}).getByRole('button',{name,exact:true}).click();};
  const entries=[];
  async function shot(index,theme){
    const name=String(index+1).padStart(2,'0')+'-'+(theme==='dark'?'oscuro':'claro')+'.png';
    await page.screenshot({path:path.join(out,name),animations:'disabled'});entries.push({name,title:pages[index],theme});
  }
  await page.goto(address);
  try{
    await workspace().waitFor();
    assert(await page.getByRole('heading',{name:'He leído 2 de 3 archivos'}).isVisible());
    assert(await page.getByText('Comprobación local · 0 llamadas al modelo',{exact:true}).isVisible());
    if(interactive){
      await page.evaluate(()=>{document.title='Neural Office V5.35 · Revisión en Edge';});
      console.log('Oficina de prueba abierta en Edge con el núcleo local y selector de archivos.');
      await new Promise(resolve=>browser.on('disconnected',resolve));
      return;
    }
    for(const theme of ['dark','light']){
      await page.emulateMedia({colorScheme:theme});
      await page.waitForFunction(d=>document.querySelector('.arcade535')?.classList.contains('theme-dark')===d,theme==='dark');
      await go('Proyectos');await workspace().waitFor();
      const palette=await page.locator('.arcade535').evaluate(el=>{
        const style=getComputedStyle(el);
        const value=name=>style.getPropertyValue('--'+name).trim();
        const luminance=hex=>{
          const channels=hex.slice(1).match(/../g).map(n=>parseInt(n,16)/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4);
          return channels.reduce((sum,v,i)=>sum+v*[.2126,.7152,.0722][i],0);
        };
        const contrast=(a,b)=>(Math.max(a,b)+.05)/(Math.min(a,b)+.05);
        const ratios=['paper','nav','bar','surface','selection','wash'].flatMap(bg=>['ink','strong','muted'].map(fg=>contrast(luminance(value(bg)),luminance(value(fg)))));
        return {paper:value('paper'),nav:value('nav'),minimum:Math.min(...ratios),pairs:ratios.length};
      });
      assert.equal(palette.paper,theme==='dark'?'#101216':'#fbfaf7');assert(palette.minimum>=4.5);
      fs.writeFileSync(path.join(out,'contraste-'+theme+'.json'),JSON.stringify(palette,null,2));
      await shot(0,theme);
      for(const [i,name] of roster.entries()){
        const trigger=button('Abrir hilo de '+name);await trigger.click();
        const dialog=page.getByRole('dialog',{name:'Hilo de '+name});await dialog.waitFor();
        await button('Iteración 1').click();assert.equal(await button('Iteración 1').getAttribute('aria-pressed'),'true');
        await button('Iteración 3').click();assert.equal(await dialog.getByRole('textbox').count(),0);
        await shot(i+1,theme);await page.keyboard.press('Escape');
        assert(await trigger.evaluate(b=>b===document.activeElement));
      }
      await go('Memoria y skills');await page.getByRole('heading',{name:'Plazo de respuesta'}).waitFor();await shot(7,theme);
      await button('Skills').click();await page.getByRole('heading',{name:title}).waitFor();await shot(8,theme);
      await go('Ajustes');await page.getByRole('heading',{name:'Ajustes generales'}).waitFor();await shot(9,theme);
      const high=page.getByLabel('Alto contraste');
      await high.check();
      assert.equal(await page.locator('.arcade535').evaluate(el=>getComputedStyle(el).getPropertyValue('--muted').trim()),theme==='dark'?'#e1e7f0':'#413e37');
      await high.uncheck();
    }
    await page.getByLabel('Reducir movimiento').check();
    await page.reload();await workspace().waitFor();
    assert.equal(await page.locator('.arcade535').getAttribute('data-motion'),'true');
    const download=page.waitForEvent('download');await button('Descargar informe.pdf').click();
    await (await download).saveAs(path.join(out,'informe.pdf'));
    const evidence=page.waitForEvent('download');await button('Descargar evidencia.json').click();
    await (await evidence).saveAs(path.join(out,'evidencia.json'));
    assert.deepEqual(JSON.parse(fs.readFileSync(path.join(out,'evidencia.json'),'utf8')).team,report.team);
    await go('Memoria y skills');await button('Skills').click();await button('Aceptar propuesta').click();await button('Proponer cambio').waitFor();
    await button('Usar en un borrador').click();
    const draft=page.getByRole('textbox',{name:'Instrucción para el Director'});
    await draft.waitFor();
    assert((await draft.inputValue()).includes('Identifica también la versión.'));
    await draft.fill('Identifica los archivos adjuntos.');await button('Enviar · 0 intentos').click();
    await page.locator('.user-turn p').filter({hasText:'Identifica los archivos adjuntos.'}).waitFor();
    await workspace().waitFor();await page.reload();await page.locator('.user-turn p').filter({hasText:'Identifica los archivos adjuntos.'}).waitFor();
    await page.setViewportSize({width:540,height:780});await button('Ver equipo').click();await button('Abrir hilo de Escéptico').click();
    await page.getByRole('dialog',{name:'Hilo de Escéptico'}).waitFor();await page.keyboard.press('Escape');await button('Volver al Director').click();
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true);
    await draft.fill('Hola');await button('Enviar · 0 intentos').click();
    await page.getByRole('heading',{name:'Hola. ¿Qué quieres revisar?'}).waitFor();
    assert.equal(await workspace().count(),0);
    await page.reload();await page.getByRole('heading',{name:'Hola. ¿Qué quieres revisar?'}).waitFor();
    await page.setViewportSize({width:1280,height:800});
    const savedDraft='Conservar este borrador, con espacios.';
    await draft.fill(savedDraft);await page.keyboard.press('Control+k');
    const search=page.getByRole('textbox',{name:'Buscar por nombre o proyecto'});
    assert(await search.evaluate(el=>document.activeElement===el));
    await page.keyboard.type('archivos adjuntos');
    assert.equal(await search.inputValue(),'archivos adjuntos');assert.equal(await draft.inputValue(),savedDraft);
    await page.getByRole('region',{name:'Entregas',exact:true}).getByRole('button').first().click();
    await page.locator('.user-turn p').filter({hasText:'Identifica los archivos adjuntos.'}).waitFor();
    await page.reload();await page.locator('.user-turn p').filter({hasText:'Identifica los archivos adjuntos.'}).waitFor();
    await page.setViewportSize({width:760,height:540});
    const stamps=page.locator('.earlier-turn time');assert(await stamps.count()>0);
    assert(await stamps.evaluateAll(nodes=>nodes.every(el=>el.getBoundingClientRect().width>=36&&el.getBoundingClientRect().height<30)));
    await page.setViewportSize({width:1440,height:900});
    await button('Abrir hilo de Integrador').click();await button('Iteración 3').click();
    await page.setViewportSize({width:1000,height:510});
    const sheet=page.getByRole('dialog',{name:'Hilo de Integrador'});
    const header=await sheet.locator('header').boundingBox();
    assert(await sheet.locator('.sheet-body').evaluate(el=>{el.scrollTop=el.scrollHeight;return el.scrollTop>0;}));
    const scrolled=await sheet.locator('header').boundingBox();assert(Math.abs(header.y-scrolled.y)<1);
    await button('Iteración 2').click();await button('Cerrar hilo del especialista').click();
    await page.setViewportSize({width:1440,height:900});
    await button('Abrir hilo de Investigador').click();await button('Iteración 2').click();
    const specialist=page.getByRole('dialog',{name:'Hilo de Investigador'});
    await specialist.getByRole('button',{name:'requisitos.md',exact:true}).first().click();
    await page.getByRole('complementary',{name:'Inspector de archivos'}).getByRole('heading',{name:'requisitos.md'}).waitFor();
    await button('Volver al especialista · Iteración 2').click();assert.equal(await button('Iteración 2').getAttribute('aria-pressed'),'true');await page.keyboard.press('Escape');
    await go('Memoria y skills');await button('Skills').click();await button('Usar en un borrador').waitFor();
    await checked('library.change',{...source,kind:'skill',title,body:'',entry_id:skill,operation:'retire',expected_revision:4});
    await button('Usar en un borrador').click();await page.getByText('La skill fue retirada. Tu borrador se conserva.',{exact:true}).waitFor();
    await go('Proyectos');
    const unicodeName='registro.txt',unicode=path.join(sourceFolder,unicodeName);
    const token='Αθήνα 東京 😀';
    fs.writeFileSync(unicode,'Primera línea\u2028Segunda '+token+'\n'+('W'.repeat(180))+'\nÚltima línea');
    await checked('host.attachments.capture',{project_id:project,thread_id:thread,paths:[unicode]});
    await page.reload();await workspace().waitFor();
    await draft.fill('Busca «'+token+'» en '+unicodeName+'.');await button('Enviar · 0 intentos').click();
    await page.locator('.desk-lede').filter({hasText:'aparece en el texto recuperado de registro.txt'}).waitFor();
    const evidenceDrawer=page.locator('details.evidence-drawer');await evidenceDrawer.locator('summary').click();
    await evidenceDrawer.getByRole('button',{name:/registro\.txt/}).click();
    await page.waitForFunction(t=>document.querySelector('.source-text .line-target code')?.textContent==='Segunda '+t,token);
    await page.screenshot({path:path.join(out,'cita-unicode.png')});
    await draft.fill('Inspecciona el contenido de registro.txt.');await button('Enviar · 0 intentos').click();
    await page.locator('.user-turn p').filter({hasText:'Inspecciona el contenido de registro.txt.'}).waitFor();
    const unicodeDownload=page.waitForEvent('download');await button('Descargar informe.pdf').click();
    const exported=await unicodeDownload,filePath=path.join(sourceFolder,'revision.pdf');
    assert.match(exported.suggestedFilename(),/^informe-.+\.pdf$/);await exported.saveAs(filePath);
    fs.copyFileSync(filePath,path.join(out,'unicode.pdf'));
    const [pdfFile]=await checked('host.attachments.capture',{project_id:project,thread_id:thread,paths:[filePath]});
    const reimport=await checked('attachments.inspect',{project_id:project,thread_id:thread,attachment_ids:[pdfFile.id],objective:'Busca «'+token+'» en revision.pdf.'});
    assert(reimport.findings[0].sources[0].quote.includes(token),JSON.stringify(reimport.findings));
    assert.equal(reimport.findings[0].sources[0].name,'revision.pdf');
    fs.writeFileSync(path.join(out,'reimportacion.json'),JSON.stringify(reimport.findings,null,2));
    const controller=spawn(python,['-B','-m','tests.v535_interrupted_excerpt',path.join(office,'estado.db'),project,thread,reimport.id],{cwd:root,stdio:['pipe','pipe','pipe'],windowsHide:true});
    controller.stderr.on('data',chunk=>process.stderr.write(chunk));
    const exit=new Promise(resolve=>controller.once('exit',resolve));
    try{
      const packet=await Promise.race([new Promise(resolve=>controller.stdout.once('data',chunk=>resolve(JSON.parse(chunk.toString('utf8'))))),exit.then(code=>{throw Error('Controller exited before ready: '+code);})]);
      await page.reload();
      await button('Comprobar recuperación').click();
      await page.getByText('El núcleo confirma que la consulta sigue en ejecución.',{exact:true}).waitFor();
      controller.stdin.end('interrupt\n');assert.equal(await exit,0);
      await page.reload();await button('Comprobar recuperación').waitFor();
      const before=await checked('attempt.get',{attempt_id:packet.attempt});
      assert.equal(before.state,'RUNNING');assert.equal(before.inspection_id,reimport.id);
      await page.getByRole('region',{name:'Control del trabajo en curso'}).getByRole('button',{name:/Detener trabajo/}).click();
      staleRecoveryOnce=true;
      await button('Comprobar recuperación').click();
      await page.getByRole('region',{name:'Control del trabajo en curso'}).waitFor({state:'hidden'});
      const after=await checked('attempt.get',{attempt_id:packet.attempt});
      assert.equal(after.state,'CANCELLED');assert.equal(after.id,before.id);assert.equal(after.inspection_id,reimport.id);
      const snapshot=await checked('snapshot.get',{project_after:0,attempt_after:0,limit:100});
      assert.equal(snapshot.projects.find(p=>p.id===project).attempts_consumed,1);
      assert.equal(after.calls.length,1);assert.equal(after.outputs.length,0);
      assert.equal(conflicts,1);
      fs.writeFileSync(path.join(out,'recuperacion.json'),JSON.stringify({provider:'fixture · sin inferencia Ollama',before,after,revision_conflicts:conflicts,attempts_consumed:1},null,2));
    }finally{if(controller.exitCode===null&&!controller.killed)controller.kill();await exit;}
    const alternate='otro-hilo';
    const [separateFile]=await checked('host.attachments.capture',{project_id:project,thread_id:alternate,paths:[inputs[0]]});
    const archived=await checked('attachments.inspect',{project_id:project,thread_id:alternate,attachment_ids:[separateFile.id],objective:'Busca «24 horas» en requisitos.md.'});
    await page.keyboard.press('Control+k');await search.fill('24 horas');
    await page.getByRole('region',{name:'Entregas',exact:true}).getByRole('button',{name:new RegExp(archived.id.slice(0,8))}).click();
    await page.locator('.user-turn p').filter({hasText:archived.objective}).waitFor();
    await page.reload();await page.locator('.user-turn p').filter({hasText:archived.objective}).waitFor();
    const beforeStop='Busca «otra frase» en requisitos.md.';
    await draft.fill(beforeStop);pickerLimitOnce=true;await button('Adjuntar archivos').click();
    await page.getByRole('alert').getByRole('button',{name:'Elegir archivos'}).waitFor();
    assert.equal(await draft.inputValue(),beforeStop);
    interruptNextInspection=true;await button('Enviar · 0 intentos').click();
    await page.getByRole('button',{name:'Detener lectura · '+project}).click();
    await page.getByText('Lectura detenida por el núcleo. Se conservan el borrador y la selección.',{exact:true}).waitFor();
    assert.equal(await draft.inputValue(),beforeStop);
    assert.deepEqual(errors,[]);
    fs.writeFileSync(path.join(out,'recorrido.json'),JSON.stringify({engine:'Edge + Python stdio, selector y transporte Tauri sustituidos para la prueba',views:entries,checks:['6 × 3 recibos','PDF y JSON descargados','restauración de foco','persistencia al recargar','aceptación y retirada concurrente de skill','encargo desde el compositor','ventana estrecha','saludo sin delegación','búsqueda con espacios y borrador','entrega histórica tras recargar','hora a 760 × 540','ida y vuelta entre especialista y cita','línea Unicode','PDF exportado y reimportado'],errors},null,2));
    const links=entries.map(e=>'<figure><a href="'+e.name+'"><img src="'+e.name+'" loading="lazy" alt="'+e.title+'"></a><figcaption>'+e.title+' · '+(e.theme==='dark'?'Oscuro':'Claro')+'</figcaption></figure>').join('');
    fs.writeFileSync(path.join(out,'galeria.html'),'<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Neural Office V5.35-POLISHED</title><style>body{margin:32px;background:#101216;color:#e2e5eb;font:16px system-ui}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(380px,100%),1fr));gap:16px}figure{margin:0}img{width:100%}figcaption{padding:6px 0 16px}</style><h1>Neural Office V5.35-POLISHED</h1><p>Veinte capturas del escritorio conectado al servicio Python en Windows. Abre una imagen para verla a tamaño real.</p><main>'+links+'</main></html>');
    console.log('PASS · 20 vistas y recorrido interactivo');
  }catch(e){await page.screenshot({path:path.join(out,'diagnostico.png')});fs.writeFileSync(path.join(out,'diagnostico.txt'),String(e)+'\n'+await page.locator('body').innerText()+'\n'+errors.join('\n'));throw e;}
}
main().catch(e=>{console.error(e);process.exitCode=1;}).finally(async()=>{pickerLifetime.abort();if(browser?.isConnected())await browser.close();core.stdin.end();});
