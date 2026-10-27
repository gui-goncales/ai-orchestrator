// Isolated browser session. Never connects to the user's browser or signed-in tabs.
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const [artifactId,reviewId]=process.argv.slice(2);
if(!/^[a-f0-9]{12}$/.test(artifactId||'')||!/^[a-f0-9]{12}$/.test(reviewId||''))throw Error('Invalid IDs');
const root=path.resolve(__dirname,'..');const output=path.join(root,'data','visual-reviews',reviewId);
fs.mkdirSync(output,{recursive:true});if(fs.lstatSync(output).isSymbolicLink())throw Error('Invalid evidence directory');
const url=`http://127.0.0.1:8789/${artifactId}/`;
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
 try{
 const context=await browser.newContext({viewport:{width:1280,height:800}});
 await context.route('**/*',route=>{const u=new URL(route.request().url());return u.origin==='http://127.0.0.1:8789'&&u.pathname.startsWith('/'+artifactId+'/')?route.continue():route.abort()});
 const page=await context.newPage();const errors=[],failed=[],actions=[],images=[],captureWarnings=[];
 page.on('pageerror',e=>errors.push(e.message.slice(0,2000)));
 page.on('response',r=>{if(r.status()>=400)failed.push({url:r.url(),status:r.status()})});
 page.on('requestfailed',r=>failed.push({url:r.url(),error:r.failure()?.errorText}));
 async function settle(){
  await page.waitForFunction(()=>{const frames=window.__gameTest?.getState?.()?.performance?.frames;return document.readyState==='complete'&&(!Number.isFinite(frames)||frames>=10)},null,{timeout:15000}).catch(()=>captureWarnings.push('Aguardar renderização excedeu 15s; a captura pode mostrar um estado ainda incompleto.'));
  await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
 }
 async function snap(name,label){await settle();await page.screenshot({path:path.join(output,name),fullPage:false});const bytes=fs.readFileSync(path.join(output,name));images.push({name,label,sha256:crypto.createHash('sha256').update(bytes).digest('hex'),width:(page.viewportSize()).width,height:(page.viewportSize()).height})}
 await page.goto(url,{waitUntil:'domcontentloaded',timeout:30000});await page.waitForTimeout(1200);
 await snap('desktop.png','Desktop: tela inicial');
 const initialText=(await page.locator('body').innerText()).slice(0,6000);
 const start=page.getByRole('button',{name:/^(jogar|iniciar|play|start)(\s|$)/i}).first();
 if(await start.count()&&await start.isVisible()){
  await start.click({timeout:4000});actions.push('Clique em botão local de início');await page.waitForTimeout(1200);
  await snap('interaction.png','Desktop: após iniciar a aplicação');
 }
 await page.setViewportSize({width:390,height:844});await page.goto(url,{waitUntil:'domcontentloaded',timeout:30000});await page.waitForTimeout(900);await snap('mobile.png','Mobile: tela inicial 390px');
 const mobile=await page.evaluate(()=>({horizontalOverflow:document.documentElement.scrollWidth>innerWidth,title:document.title}));
 const report={version:2,render_readiness:'Document loaded, two animation frames; artifacts exposing __gameTest waited for at least ten frames',artifact_id:artifactId,url,images,actions,initial_text:initialText,mobile,page_errors:errors,failed_requests:failed,capture_warnings:captureWarnings,renderer:'Headless Chrome / SwiftShader software WebGL',scope:'Capturas de estados limitados. Não comprova diversão, partida completa, desempenho de hardware real ou conformidade integral de acessibilidade.',captured_at:new Date().toISOString()};
 fs.writeFileSync(path.join(output,'capture.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
 }finally{await browser.close()}
})().catch(e=>{console.error(e.message);process.exit(1)});
