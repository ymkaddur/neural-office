/* Render the production application with its real local stdio service and an isolated picker. */
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const os=require('node:os');
const {execFile,spawn}=require('node:child_process');
const {promisify}=require('node:util');
const runFile=promisify(execFile);
const readline=require('node:readline');
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
readline.createInterface({input:core.stdout}).on('line',line=>{
  const reply=JSON.parse(line);const finish=waiting.get(reply.id);
  if(finish){waiting.delete(reply.id);finish.resolve(reply);}
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
async function checked(method,params){const response=await call(method,params);assert.equal(response.ok,true,JSON.stringify(response.error));return response.result;}
const address='http://127.0.0.1:52375';
const project='Portal de clientes',thread='main';
const allowed=new Set(['describe','models.list','projects.list','snapshot.get','project.history','attachments.pick','attachments.list',
  'attachments.cancel','attachments.threads','attachments.inspect','attachments.view','attachments.history','attachments.report',
  'attachments.activity','attachments.decide','library.list','library.change','library.history','events.read','attempt.get','attempt.lookup']);
const roster=['Investigador','Planificador','Implementador','Verificador','Escéptico','Integrador'];
const pages=['Director',...roster,'Memoria','Skills','Ajustes'];
let browser;
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
      const paths=await chooseFiles();
      envelope=paths.length?await call('host.attachments.capture',{...params,paths}):{version:1,ok:true,result:[]};
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
    assert.deepEqual(errors,[]);
    fs.writeFileSync(path.join(out,'recorrido.json'),JSON.stringify({engine:'Edge + Python stdio',views:entries,checks:['6 × 3 recibos','PDF y JSON descargados','restauración de foco','persistencia al recargar','aceptación de skill','encargo desde el compositor','ventana estrecha','saludo guardado sin delegación'],errors},null,2));
    const links=entries.map(e=>'<figure><a href="'+e.name+'"><img src="'+e.name+'" loading="lazy" alt="'+e.title+'"></a><figcaption>'+e.title+' · '+(e.theme==='dark'?'Oscuro':'Claro')+'</figcaption></figure>').join('');
    fs.writeFileSync(path.join(out,'galeria.html'),'<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Neural Office V5.35</title><style>body{margin:32px;background:#191a18;color:#efeee7;font:16px system-ui}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(380px,100%),1fr));gap:16px}figure{margin:0}img{width:100%}figcaption{padding:6px 0 16px}</style><h1>Neural Office V5.35</h1><p>Veinte capturas del escritorio conectado al servicio Python en Windows. Abre una imagen para verla a tamaño real.</p><main>'+links+'</main></html>');
    console.log('PASS · 20 vistas y recorrido interactivo');
  }catch(e){await page.screenshot({path:path.join(out,'diagnostico.png')});fs.writeFileSync(path.join(out,'diagnostico.txt'),String(e)+'\n'+await page.locator('body').innerText()+'\n'+errors.join('\n'));throw e;}
}
main().catch(e=>{console.error(e);process.exitCode=1;}).finally(async()=>{pickerLifetime.abort();if(browser?.isConnected())await browser.close();core.stdin.end();});
