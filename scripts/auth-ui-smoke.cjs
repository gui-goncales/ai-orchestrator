const {chromium}=require('playwright');const fs=require('node:fs');
(async()=>{const browser=await chromium.launch({channel:'chrome',headless:true});try{
 const page=await browser.newPage({viewport:{width:1440,height:1050}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:8787');await page.getByText('Conectado',{exact:true}).waitFor();await page.getByRole('button',{name:'Agents',exact:true}).click();
 await page.getByRole('heading',{name:'Conectar pela conta',exact:true}).waitFor();
 if(await page.locator('input[name="key_env"]').count())throw Error('API key form still active');
 const state=await page.evaluate(async()=>await(await fetch('/api/state')).json());
 const tess=state.providers.find(p=>p.id==='web-tess');if(!tess||tess.state!=='available')throw Error('Tess not available');
 if(state.providers.some(p=>p.id.startsWith('api-')))throw Error('API provider active');
 const task=state.tasks.find(t=>t.id==='93606b5bc48f');if(task?.status!=='completed'||task.result!=='TESS_AUTH_OK')throw Error('Real smoke result absent');
 await page.screenshot({path:'evidence/auth-agents-desktop.png',fullPage:true});
 await page.setViewportSize({width:390,height:844});await page.screenshot({path:'evidence/auth-agents-mobile.png',fullPage:true});
 if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1))throw Error('Mobile overflow');
 if(errors.length)throw Error(errors.join('\n'));
 fs.writeFileSync('evidence/auth-ui.json',JSON.stringify({passed:true,checks:['login session form','Tess available after real orchestrator task','API providers absent','no API credential input','mobile without overflow','no page errors'],task_id:task.id},null,2));
 console.log('PASS: active orchestrator login UI and real Tess result');
 }finally{await browser.close()}})().catch(e=>{console.error(e);process.exit(1)});
