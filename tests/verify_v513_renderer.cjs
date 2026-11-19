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
let pickerFiles=inputs;
const replies=readline.createInterface({input:core.stdout});
replies.on('line',line=>{const answer=JSON.parse(line);const callback=pending.get(answer.id);if(callback){pending.delete(answer.id);callback.resolve(answer);}});
core.on('exit',code=>{for(const entry of pending.values())entry.reject(Error('Sidecar exit '+code));pending.clear();});
core.stderr.on('data',chunk=>process.stderr.write(chunk));
function call(message){return new Promise((resolve,reject)=>{pending.set(message.id,{resolve,reject});core.stdin.write(JSON.stringify(message)+'\n');});}
const goal='Revisa la entrega del portal y compara el plazo de primera respuesta.';

async function contrastSamples(page, theme){
  const targets=[
    ['marca','.desk-brand strong'], ['búsqueda','.desk-search span'], ['saldo','#project-balance span:last-child'],
    ['encabezado','.thread-document h1'], ['inspector','.file-inspector h2'],
    ['nombre de archivo','.file-list strong'], ['capacidad del archivo','.file-list small'],
    ['tamaño del archivo','.file-list code'], ['nota local','.desk-caption span:last-child'],
    ['adjuntar','.desk-attach'], ['acción primaria','.desk-primary'],
    ['instrucción vacía','.desk-composer textarea','placeholder']
  ];
  async function sample(label,selector,kind='text'){
    const node=page.locator(selector).first();
    await node.waitFor({state:'visible'});
    if(kind==='focus'){
      await page.keyboard.press('Tab');
      await node.focus();
    }
    return node.evaluate((el,{label,theme,kind})=>{
      const canvas=document.createElement('canvas').getContext('2d',{willReadFrequently:true});
      function rgba(css){
        canvas.clearRect(0,0,1,1);
        canvas.fillStyle=css; canvas.fillRect(0,0,1,1);
        const [r,g,b,a]=canvas.getImageData(0,0,1,1).data;
        return [r,g,b,a/255];
      }
      function over(top,bottom){
        const a=top[3]+bottom[3]*(1-top[3]);
        return a ? [...[0,1,2].map(i=>(top[i]*top[3]+bottom[i]*bottom[3]*(1-top[3]))/a),a] : [0,0,0,0];
      }
      function light(color){
        const c=color.slice(0,3).map(v=>v/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4);
        return c[0]*.2126+c[1]*.7152+c[2]*.0722;
      }
      if(kind==='placeholder' && el.value)throw Error('Placeholder is hidden');
      const style=getComputedStyle(el,kind==='placeholder'?'::placeholder':null);
      const focus=kind==='focus';
      if(focus&&(!el.matches(':focus-visible')||style.outlineStyle==='none'||parseFloat(style.outlineWidth)<=0))
        throw Error('Missing keyboard focus: '+label);
      let fg=rgba(focus?style.outlineColor:style.color),bg=[0,0,0,0];
      if(kind==='placeholder')fg[3]*=Number(style.opacity);
      const outside=focus&&parseFloat(style.outlineOffset)>=0;
      for(let parent=outside?el.parentElement:el;parent;parent=parent.parentElement){
        const layer=getComputedStyle(parent);
        if(layer.filter!=='none'||layer.mixBlendMode!=='normal'||(layer.backgroundImage!=='none'&&bg[3]<1))
          throw Error('Unsupported compositing layer: '+label);
        const color=rgba(layer.backgroundColor);
        fg=over(fg,color);bg=over(bg,color);
        fg[3]*=Number(layer.opacity);bg[3]*=Number(layer.opacity);
      }
      if(bg[3]<1)throw Error('Missing opaque background: '+label);
      const high=Math.max(light(fg),light(bg)),low=Math.min(light(fg),light(bg));
      const large=parseFloat(style.fontSize)>=24||(parseFloat(style.fontSize)>=18.6667&&Number(style.fontWeight)>=700);
      const minimum=focus||large?3:4.5;
      const ratio=(high+.05)/(low+.05);
      const pixels=c=>'#'+c.slice(0,3).map(v=>Math.round(v).toString(16).padStart(2,'0')).join('');
      return {theme,label,kind,foreground:pixels(fg),background:pixels(bg),
        ratio:Number(ratio.toFixed(3)),minimum,passed:ratio>=minimum,
        ...(focus?{outline_width:parseFloat(style.outlineWidth),offset:parseFloat(style.outlineOffset)}
          :{font_px:parseFloat(style.fontSize),weight:style.fontWeight})};
    },{label,theme,kind});
  }
  await page.mouse.move(0,0);
  const rows=[];
  for(const [name,selector,kind] of targets)rows.push(await sample(name,selector,kind));
  for(const [name,selector] of [['foco adjuntar','.desk-attach'],['foco inspeccionar','.desk-primary'],['foco buscar','.desk-search']])
    rows.push(await sample(name,selector,'focus'));
  return rows;
}

async function fontSizes(page){
  return page.evaluate(()=>Object.fromEntries(
    ['.desk513','.desk-composer textarea','.file-inspector h2'].map(selector=>{
      const node=document.querySelector(selector);
      if(!node||!node.getClientRects().length)throw Error('Scale sample not on screen: '+selector);
      return [selector,parseFloat(getComputedStyle(node).fontSize)];
    })
  ));
}

function contrastSummary(rows){
  return [...new Set(rows.map(row=>row.theme))].map(theme=>{
    const visible=rows.filter(row=>row.theme===theme);
    const minimum=group=>{
      assert(group.length,'Missing contrast sample for '+theme);
      return Math.min(...group.map(row=>row.ratio));
    };
    return {theme, samples:visible.length,
      normal_text_min:minimum(visible.filter(row=>row.kind!=='focus'&&row.minimum===4.5)),
      large_text_min:minimum(visible.filter(row=>row.kind!=='focus'&&row.minimum===3)),
      keyboard_focus_min:minimum(visible.filter(row=>row.kind==='focus'))};
  });
}

// CDP identifies only this test browser. The sidecar tree also includes the Windows
// virtualenv launcher. Working sets can share pages, so private bytes are reported too.
async function resourceSnapshot(cdp){
  const {processInfo}=await cdp.send('SystemInfo.getProcessInfo');
  const wanted=processInfo.map(p=>p.id);
  if(!wanted.length||![core.pid,...wanted].every(pid=>Number.isSafeInteger(pid)&&pid>0))throw Error('Invalid process inventory.');
  const ps=[
    "$ErrorActionPreference='Stop'",
    "$edge=@("+wanted.join(',')+")",
    "$sidecar=@("+core.pid+")",
    "$inventory=@(Get-CimInstance Win32_Process -Property ProcessId,ParentProcessId)",
    "do { $n=$sidecar.Count; $sidecar+=@($inventory | Where-Object { $_.ParentProcessId -in $sidecar -and $_.ProcessId -notin $sidecar } | ForEach-Object { [int]$_.ProcessId }) } while ($n -lt $sidecar.Count)",
    "$rows=@(foreach ($processId in @($edge+$sidecar)) {",
    "  try { $p=[Diagnostics.Process]::GetProcessById($processId) } catch [ArgumentException] { continue }",
    "  try { [PSCustomObject]@{ pid=$processId; group=if($processId -in $edge){'edge'}else{'sidecar'}; birth=$p.StartTime.ToUniversalTime().Ticks.ToString(); cpu_ms=$p.TotalProcessorTime.TotalMilliseconds; working_bytes=$p.WorkingSet64; private_bytes=$p.PrivateMemorySize64 } } catch [InvalidOperationException] { if(!$p.HasExited){throw} } finally { $p.Dispose() }",
    "})",
    "[PSCustomObject]@{ utc=[DateTime]::UtcNow.ToString('o'); rows=$rows } | ConvertTo-Json -Compress"
  ].join('\n');
  const {stdout}=await require('node:util').promisify(child.execFile)('powershell.exe',['-NoLogo','-NoProfile','-NonInteractive','-Command',ps],{timeout:15000,windowsHide:true});
  const snapshot=JSON.parse(stdout);
  for(const group of ['edge','sidecar'])assert(snapshot.rows.some(row=>row.group===group),'Missing resource group '+group);
  return snapshot;
}

function resourceWindow(start,end){
  const seconds=(Date.parse(end.utc)-Date.parse(start.utc))/1000;
  assert(seconds>0);
  const result={from_utc:start.utc,to_utc:end.utc,seconds,groups:{}};
  for(const group of ['edge','sidecar']){
    const before=start.rows.filter(row=>row.group===group),after=end.rows.filter(row=>row.group===group);
    const id=row=>row.pid+'/'+row.birth;
    const original=new Map(before.map(row=>[id(row),row]));
    const common=after.filter(row=>original.has(id(row)));
    const cpuMs=common.reduce((sum,row)=>sum+row.cpu_ms-original.get(id(row)).cpu_ms,0);
    const mib=(rows,key)=>Number((rows.reduce((sum,row)=>sum+row[key],0)/1048576).toFixed(2));
    result.groups[group]={processes_start:before.length,processes_end:after.length,processes_common:common.length,
      cpu_ms_common:Number(cpuMs.toFixed(2)),cpu_pct_one_core:Number((cpuMs/(seconds*10)).toFixed(2)),
      working_set_mib_start:mib(before,'working_bytes'),working_set_mib_end:mib(after,'working_bytes'),
      private_mib_start:mib(before,'private_bytes'),private_mib_end:mib(after,'private_bytes')};
  }
  return result;
}

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
    if(message.method==='attachments.pick')message={...message,method:'host.attachments.capture',params:{...message.params,paths:pickerFiles}};
    if(message.method==='source.pick')message={...message,method:'host.source.capture',params:{...message.params,path:path.join(root,'examples','audit-sample.html')}};
    return await call(message);
  });
  await ctx.addInitScript(()=>{window.isTauri=true;window.__TAURI_INTERNALS__={invoke:(op,params)=>window.officeTestIPC(op,params)};});
  const page=await ctx.newPage();page.on('pageerror',e=>errors.push(e.message));page.setDefaultTimeout(15000);
  const btn=(s)=>page.getByRole('button',{name:s,exact:true});
  const heading=(s)=>page.getByRole('heading',{name:s,exact:true});
  const save=(name)=>page.screenshot({path:path.join(out,name+'.png')});
  const box=page.getByRole('textbox',{name:'Instrucción para el Director'});
  const themeIs=async dark=>page.waitForFunction(flag=>document.querySelector('.desk513')?.classList.contains('theme-dark')===flag,dark);
  const measures={contrast:[],contrast_scope:{
    surface:'Edge headless, hilo con adjuntos, selección visible, 1440 × 900, estilo calculado y fondos opacos compuestos.',
    normal_text_ratio:4.5,large_text_ratio:3,keyboard_focus_ratio:3,
    large:'24 px, o al menos 18⅔ px con peso ≥700.',
    references:['https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html','https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html'],
    scope:'Doce muestras de lectura y acción y tres contornos de foco por paleta. No cubre todos los estados, lectores de pantalla, colores forzados ni una certificación WCAG.'
  },high_contrast:{},density:{},fonts:{},selection:{},drafts:{}};
  const cdp=await browser.newBrowserCDPSession();
  async function sampleTheme(theme){
    const rows=await contrastSamples(page,theme);
    measures.contrast.push(...rows);
    const fileRow=page.locator('.file-list button').first();
    const padding=()=>fileRow.evaluate(el=>parseFloat(getComputedStyle(el).paddingTop));
    const comfortable=await padding();
    await page.keyboard.press('Control+,');await btn('Compacta').click();await btn('Volver al hilo').click();
    measures.density[theme]={selector:'.file-list button',comfortable_padding_px:comfortable,compact_padding_px:await padding()};
    await page.keyboard.press('Control+,');await btn('Cómoda').click();await btn('Volver al hilo').click();
    await page.keyboard.press('Control+,');await page.getByLabel('Alto contraste',{exact:true}).check();await btn('Volver al hilo').click();
    const enhanced=await contrastSamples(page,theme);
    const muted=sample=>sample.find(row=>row.label==='capacidad del archivo');
    const standard=muted(rows),high=muted(enhanced);
    measures.high_contrast[theme]={sample:standard.label,normal:standard.ratio,enhanced:high.ratio,
      normal_color:standard.foreground,enhanced_color:high.foreground,
      enhanced_samples_all_pass:enhanced.every(row=>row.passed),samples:enhanced};
    await page.keyboard.press('Control+,');await page.getByLabel('Alto contraste',{exact:true}).uncheck();await btn('Volver al hilo').click();
  }
  function writeMeasures(){
    fs.writeFileSync(path.join(out,'measures.json'),JSON.stringify(measures,null,2));
  }
  async function ready(){await page.locator('.engine-state i.ready').waitFor();await page.locator('.desk-fault').count().then(n=>assert.equal(n,0));}
  try {
    await page.goto('http://127.0.0.1:52371');await ready();
    await btn('Crear otro proyecto').click();
    await page.getByRole('textbox',{name:'Nombre del proyecto',exact:true}).fill('Portal de soporte');
    await btn('Abrir proyecto').click();
    await page.locator('.breadcrumbs').getByText('Portal de soporte',{exact:true}).waitFor();
    await btn('Adjuntar archivos').click();
    await page.getByRole('checkbox',{name:'Incluir movil.jpg',exact:true}).waitFor();
    await page.keyboard.press('Control+,');
    assert.equal(await btn('Sistema').getAttribute('aria-pressed'),'true');
    await btn('Volver al hilo').click();
    await themeIs(true);
    await sampleTheme('Azul noche');
    measures.fonts[100]=await fontSizes(page);
    await page.emulateMedia({colorScheme:'light'});await themeIs(false);
    await sampleTheme('Arena');
    measures.contrast_summary=contrastSummary(measures.contrast);
    await page.emulateMedia({colorScheme:'dark'});await themeIs(true);
    measures.system_theme='dark → light → dark';writeMeasures();
    await box.fill(goal);
    await save('01-hilo-adjuntos');
    const idleStart=await resourceSnapshot(cdp);
    await new Promise(resolve=>setTimeout(resolve,2000));
    const idleEnd=await resourceSnapshot(cdp);
    const clickAt=performance.now();
    await btn('Inspeccionar · 0 intentos').click(); await page.locator('.citation-row').first().waitFor();
    const untilFindingMs=performance.now()-clickAt;
    const inspected=await resourceSnapshot(cdp);
    measures.resources={
      surface:'Edge headless con bundle de producción y sidecar Python real por stdio. Selector y puente nativo sustituidos.',
      scope:'Edge según los procesos del navegador publicados por CDP. Sidecar Python y descendientes presentes al muestrear. Excluye el proceso Node de pruebas, consulta a modelos y núcleo Tauri.',
      limits:'Dos muestras por ventana. CPU acumulada sólo de procesos presentes en ambos extremos. La suma de working sets puede repetir páginas compartidas. Los lectores fugaces y los picos entre muestras no se cuantifican. El intervalo incluye el coste temporal de muestrear desde PowerShell.',
      logical_cpus:os.cpus().length, cpu_base:'100% = un núcleo lógico',memory_unit:'MiB = 1048576 bytes',
      idle_with_five_sources:resourceWindow(idleStart,idleEnd),
      five_source_local_inspection:resourceWindow(idleEnd,inspected),
      action_to_first_visible_finding_ms:Number(untilFindingMs.toFixed(1))};
    writeMeasures();
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
    measures.fonts[115]=await fontSizes(page);
    await page.keyboard.press('Control+,');await btn('125 %').click();await btn('Volver al hilo').click();
    measures.fonts[125]=await fontSizes(page);
    await page.keyboard.press('Control+,');await btn('115 %').click();await btn('Volver al hilo').click();
    for(const size of [115,125])for(const selector of Object.keys(measures.fonts[100])){
      const ratio=measures.fonts[size][selector]/measures.fonts[100][selector];
      assert(Math.abs(ratio-size/100)<.025,'Scale '+size+' broken on '+selector+': '+ratio);
    }
    writeMeasures();
    await btn('Ver adjuntos').click();await page.locator('.file-list button').filter({hasText:'entrega.zip'}).click();
    const divider=page.getByRole('separator',{name:'Ancho del hilo y el inspector',exact:true});
    await divider.press('Shift+ArrowLeft');
    await btn('visual/movil.jpg').click();await page.locator('.image-stage img').waitFor();
    assert((await page.locator('.image-stage img').evaluate(el=>el.naturalHeight))>0);
    await page.getByRole('navigation',{name:'Árbol del paquete'}).waitFor();
    assert.equal(await page.locator('.package-context.has-member').evaluate(el=>getComputedStyle(el).display),'grid');
    await btn('Ampliar zoom').click();assert.match(await page.locator('.image-tools').innerText(),/125/);
    await btn('Reducir zoom').click();await btn('Reducir zoom').click();
    const mobileImage=await page.locator('.image-stage img').boundingBox();
    const inspectorFooter=await page.locator('.file-inspector>footer').boundingBox();
    assert(mobileImage&&inspectorFooter&&mobileImage.y+mobileImage.height<=inspectorFooter.y+1,
      'La vista móvil de referencia no cabe con el árbol visible.');
    await save('05-paquete');
    await divider.press('Enter');
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
    await page.setViewportSize({width:1440,height:900});
    if(!await page.locator('.file-inspector').isVisible())await btn('Inspector').click();
    if(await btn('Ver adjuntos').isVisible())await btn('Ver adjuntos').click();
    const includePdf=page.getByRole('checkbox',{name:'Incluir especificacion.pdf',exact:true});
    const permit=btn('Consultar al modelo');
    await page.waitForFunction(()=>!document.querySelector('.desk-secondary:disabled'));
    await includePdf.uncheck();assert(await permit.isDisabled());
    const callsBefore=calls.filter(name=>name==='models.list'||name==='attachments.preview').length;
    await permit.dispatchEvent('click');
    assert.equal(calls.filter(name=>name==='models.list'||name==='attachments.preview').length,callsBefore);
    await includePdf.check();
    assert(await permit.isEnabled());
    measures.selection.exclusion_blocks_model=true;
    // The same thread now has nine attachments captured in two valid batches.
    pickerFiles=Array.from({length:4},(_,i)=>{
      const name=path.join(example,'nota-'+(i+1)+'.json');
      fs.writeFileSync(name,JSON.stringify({nota:i+1}),{flag:'wx'}); return name;
    });
    await btn('Adjuntar archivos').click();
    const inputsOnScreen=page.locator('.file-list input[type=checkbox]');
    await page.waitForFunction(()=>document.querySelectorAll('.file-list input[type=checkbox]').length===9);
    const checked=()=>page.locator('.file-list input:checked').count();
    measures.selection.initial_included=await checked();
    if(measures.selection.initial_included===9){
      measures.selection.nine_blocks_inspection=await btn('Inspeccionar · 0 intentos').isDisabled();
      await inputsOnScreen.last().uncheck();
    }
    assert.equal(await checked(),8);assert(await btn('Inspeccionar · 0 intentos').isEnabled());
    const ninth=page.locator('.file-list input:not(:checked)').first();
    if(await ninth.isEnabled())await ninth.click();
    measures.selection.after_trying_ninth=await checked();
    if(measures.selection.after_trying_ninth===9)await inputsOnScreen.last().uncheck();
    await btn('Inspeccionar · 0 intentos').click();
    await page.getByText('8 adjuntos en esta entrega',{exact:false}).waitFor();
    measures.selection.inspected=8;writeMeasures();
    const draftA='Borrador de lectura alfa',draftB='Borrador de lectura beta';
    const navTo=async title=>{await page.locator('.nav-threads button').filter({hasText:title}).click();};
    const stored=()=>page.locator('.file-list input[type=checkbox]').count();
    const mutators=()=>calls.filter(m=>['attachments.pick','attachments.inspect','attachments.preview','attempt.start'].includes(m)).length;
    const beforeDrafts=mutators();
    await page.locator('.new-task').click();await box.fill(draftA);await page.locator('.nav-threads button').filter({hasText:draftA}).waitFor();
    assert.equal(await stored(),0);
    await page.locator('.new-task').click();await page.waitForFunction(()=>document.querySelector('.desk-composer textarea')?.value==='');
    await box.fill(draftB);await page.locator('.nav-threads button').filter({hasText:draftB}).waitFor();
    assert.equal(await stored(),0);
    await navTo(draftA);await page.waitForFunction(txt=>document.querySelector('.desk-composer textarea')?.value===txt,draftA);
    await navTo(draftB);await page.waitForFunction(txt=>document.querySelector('.desk-composer textarea')?.value===txt,draftB);
    assert.equal(mutators(),beforeDrafts);
    measures.drafts={threads:2,attachments:0,same_window_restored:true,mutations:0};writeMeasures();
    assert(measures.selection.initial_included<=8&&measures.selection.after_trying_ninth<=8,'La selección visible excede ocho archivos.');
    assert.deepEqual(measures.contrast.filter(row=>!row.passed),[],'Contraste medido bajo el mínimo de la muestra.');
    for(const [theme,row] of Object.entries(measures.high_contrast)){
      assert(row.enhanced>row.normal&&row.enhanced_samples_all_pass,'Ajuste de alto contraste sin mejora comprobada: '+theme);
      assert(measures.density[theme].compact_padding_px<measures.density[theme].comfortable_padding_px,'Ajuste de densidad sin reducción comprobada: '+theme);
    }
    assert(!calls.includes('attempt.start')&&!calls.includes('models.list'));assert.deepEqual(errors,[]);
    const evidence={surface:'Microsoft Edge + production React + actual stdio Python. Picker and Tauri bridge substituted only in this test.',browser:browser.version(),sha256:Object.fromEntries(inputs.map(f=>[path.basename(f),crypto.createHash('sha256').update(fs.readFileSync(f)).digest('hex')])),checks:['multi-select','PDF page 2','JSON line 4','24 vs 48','receipt expansion','ZIP member image and zoom','appearance/density/scale/contrast','keyboard search','reopen persistent thread','390px draft and overflow','0 model calls'],requests:[...new Set(calls)],errors};
    evidence.checks.push('named project', 'OS theme change', 'computed colors, including keyboard focus', 'high contrast preference', '100/115/125% measured text', 'two text-only drafts', 'eight-source scope', 'excluded source blocks model','Windows process accounting for Edge and Python');
    evidence.measures=measures;
    fs.writeFileSync(path.join(out,'renderer.json'),JSON.stringify(evidence,null,2));console.log('PASS '+evidence.checks.join(', '));
  }catch(e){writeMeasures();await save('failed-state');fs.writeFileSync(path.join(out,'failed.txt'),[String(e),await page.locator('body').innerText(),JSON.stringify(calls),JSON.stringify(errors)].join('\n'));throw e;}
 }finally{await browser.close();}
}
main().catch(err=>{console.error(err);process.exitCode=1;}).finally(()=>{core.stdin.end();});
