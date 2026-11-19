/* Edge renders the production bundle. This test substitutes only the native picker/IPC transport. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const child = require('node:child_process');
const readline = require('node:readline');
const crypto = require('node:crypto');
const root = path.resolve(__dirname,'..');
const dist = path.join(root,'desktop','dist');
const playwright = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const out = process.argv[2];
const python = process.env.NEURAL_OFFICE_PYTHON || 'python';
if (!out || !fs.existsSync(path.join(dist,'index.html'))) throw Error('Provide an output directory and build the frontend.');
const work = fs.mkdtempSync(path.join(os.tmpdir(),'neural-office-render-'));
const example = path.join(work,'entrada');
fs.mkdirSync(out,{recursive:true});
child.execFileSync(python,[path.join(root,'examples/multiformat/build_example.py'),example]);
const inputs=['especificacion.pdf','entrega.zip','manifiesto.json','portada.png','movil.jpg'].map(n=>path.join(example,n));
const core=child.spawn(python,['-B','-m','neural_office.desktop_stdio','--state',path.join(work,'office.sqlite3')],{cwd:root,stdio:['pipe','pipe','pipe'],windowsHide:true});
const pending=new Map(), calls=[], errors=[];
const replies=readline.createInterface({input:core.stdout});
replies.on('line',line=>{const answer=JSON.parse(line);const callback=pending.get(answer.id);if(callback){pending.delete(answer.id);callback.resolve(answer);}});
core.on('exit',code=>{for(const entry of pending.values())entry.reject(Error('Sidecar exit '+code));pending.clear();});
core.stderr.on('data',chunk=>process.stderr.write(chunk));
function call(message){return new Promise((resolve,reject)=>{pending.set(message.id,{resolve,reject});core.stdin.write(JSON.stringify(message)+'\n');});}
const goal='Revisa la entrega del portal y compara el plazo de primera respuesta.';
async function main(){
 const browser=await playwright.chromium.launch({channel:'msedge',headless:true});
 try{
  const ctx=await browser.newContext({viewport:{width:1440,height:900},colorScheme:'dark',deviceScaleFactor:1});
  await ctx.route('http://127.0.0.1:52371/**',route=>{
    const pathname=new URL(route.request().url()).pathname.slice(1)||'index.html';
    const file=path.resolve(dist,pathname);
    if(!file.startsWith(dist+path.sep)||!fs.existsSync(file))return route.abort();
    return route.fulfill({path:file,contentType:({'.js':'text/javascript','.css':'text/css','.html':'text/html'})[path.extname(file)]});
  });
  await ctx.exposeBinding('officeTestIPC',async(_,op,{message})=>{
    assert.equal(op,'desktop_request');assert(!message.method.startsWith('host.'));
    calls.push(message.method);
    if(message.method==='attachments.pick')message={...message,method:'host.attachments.capture',params:{...message.params,paths:inputs}};
    if(message.method==='source.pick')message={...message,method:'host.source.capture',params:{...message.params,path:path.join(root,'examples','audit-sample.html')}};
    return await call(message);
  });
  await ctx.addInitScript(()=>{window.isTauri=true;window.__TAURI_INTERNALS__={invoke:(op,params)=>window.officeTestIPC(op,params)};});
  const page=await ctx.newPage();page.on('pageerror',e=>errors.push(e.message));page.setDefaultTimeout(15000);
  const btn=(s)=>page.getByRole('button',{name:s,exact:true});
  const heading=(s)=>page.getByRole('heading',{name:s,exact:true});
  const save=(name)=>page.screenshot({path:path.join(out,name+'.png')});
  async function ready(){await page.locator('.engine-state i.ready').waitFor();await page.locator('.desk-fault').count().then(n=>assert.equal(n,0));}
  try {
    await page.goto('http://127.0.0.1:52371');await ready();
    await page.getByRole('textbox',{name:'Instrucción para el Director'}).fill(goal);
    await btn('Adjuntar archivos').click();
    await page.getByRole('checkbox',{name:'Incluir movil.jpg',exact:true}).waitFor();
    await save('01-hilo-adjuntos');
    await btn('Inspeccionar · 0 intentos').click(); await page.locator('.citation-row').first().waitFor();
    assert.match(await page.locator('.thread-document').innerText(),/24/);assert.match(await page.locator('.thread-document').innerText(),/48/);
    await page.locator('.citation-row').filter({hasText:'especificacion.pdf'}).click();await page.locator('.image-stage img').waitFor();
    assert.match(await page.locator('.viewer-toolbar').innerText(),/2\s*\/\s*2/);
    await page.keyboard.press('Control+,');await btn('Claro').click();await btn('Volver al hilo').click();
    assert(!await page.locator('.desk513').evaluate(el=>el.classList.contains('theme-dark')));await save('02-evidencia-arena');
    await page.locator('.citation-row').filter({hasText:'manifiesto.json'}).click();await page.locator('.line-target').waitFor();
    assert.match(await page.locator('.line-target').innerText(),/48/);
    await page.locator('.desk-events summary').filter({hasText:'Actividad de la inspección'}).click();
    assert((await page.locator('.desk-events li').count())>=2);await save('03-actividad-real');
    await page.keyboard.press('Control+,');await btn('Oscuro').click();await btn('Compacta').click();await btn('115 %').click();
    await page.getByLabel('Alto contraste',{exact:true}).check();await save('04-apariencia');await btn('Volver al hilo').click();
    await btn('Ver adjuntos').click();await page.locator('.file-list button').filter({hasText:'entrega.zip'}).click();
    await page.locator('.package-list button').filter({hasText:'movil.jpg'}).click();await page.locator('.image-stage img').waitFor();
    assert((await page.locator('.image-stage img').evaluate(el=>el.naturalHeight))>0);
    await btn('Ampliar zoom').click();assert.match(await page.locator('.image-tools').innerText(),/125/);await save('05-paquete');
    await page.keyboard.press('Control+k');await page.getByRole('textbox',{name:'Buscar por nombre o proyecto'}).fill('apariencia');
    await page.locator('.command-results button').first().click();await page.getByRole('dialog',{name:'Apariencia'}).waitFor();await page.keyboard.press('Escape');
    await page.reload();await ready();await page.locator('.nav-threads button').filter({hasText:goal}).first().click();
    await page.locator('.citation-row').first().waitFor();
    assert.equal(await page.locator('.desk513').getAttribute('data-density'),'compact');assert.equal(await page.locator('.desk513').getAttribute('data-contrast'),'true');
    const pdf=page.locator('.citation-row').filter({hasText:'especificacion.pdf'});await pdf.click();await page.locator('.image-stage img').waitFor();
    await page.setViewportSize({width:390,height:740});await page.getByRole('button',{name:'Inspector',exact:true}).click();
    await page.getByRole('textbox',{name:'Instrucción para el Director'}).fill('Mi borrador para revisar después.');
    await page.keyboard.press('Control+,');await btn('125 %').click();await btn('Volver al hilo').click();
    assert.equal(await page.getByRole('textbox',{name:'Instrucción para el Director'}).inputValue(),'Mi borrador para revisar después.');
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await save('06-ventana-estrecha');
    assert(!calls.includes('attempt.start')&&!calls.includes('models.list'));assert.deepEqual(errors,[]);
    const evidence={surface:'Microsoft Edge + production React + actual stdio Python. Picker and Tauri bridge substituted only in this test.',browser:browser.version(),sha256:Object.fromEntries(inputs.map(f=>[path.basename(f),crypto.createHash('sha256').update(fs.readFileSync(f)).digest('hex')])),checks:['multi-select','PDF page 2','JSON line 4','24 vs 48','receipt expansion','ZIP member image and zoom','appearance/density/scale/contrast','keyboard search','reopen persistent thread','390px draft and overflow','0 model calls'],requests:[...new Set(calls)],errors};
    fs.writeFileSync(path.join(out,'renderer.json'),JSON.stringify(evidence,null,2));console.log('PASS '+evidence.checks.join(', '));
  }catch(e){await save('failed-state');fs.writeFileSync(path.join(out,'failed.txt'),[String(e),await page.locator('body').innerText(),JSON.stringify(calls),JSON.stringify(errors)].join('\n'));throw e;}
 }finally{await browser.close();}
}
main().catch(err=>{console.error(err);process.exitCode=1;}).finally(()=>{core.stdin.end();});
