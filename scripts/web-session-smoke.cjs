const {chromium}=require('playwright');
const {run}=require('./web-session.cjs');
const http=require('node:http');const fs=require('node:fs');const os=require('node:os');const path=require('node:path');
(async()=>{
 const profile=fs.mkdtempSync(path.join(os.tmpdir(),'orchestrator-session-test-'));
 const server=http.createServer((req,res)=>{res.setHeader('Content-Type','text/html');res.end(`<!doctype html><title>Session fixture</title><textarea id="prompt"></textarea><button id="send">Send</button><button id="stop" hidden>Stop</button><div id="answers"></div><script>document.getElementById('send').onclick=()=>{const stop=document.getElementById('stop');const prompt=document.getElementById('prompt');stop.hidden=false;const msg=document.createElement('div');msg.className='assistant';answers.append(msg);prompt.value='';setTimeout(()=>{msg.textContent='SESSION_FIXTURE_OK';stop.hidden=true},1200)};</script>`)});
 await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const context=await chromium.launchPersistentContext(profile,{channel:'chrome',headless:true,args:['--remote-debugging-port=0','--remote-debugging-address=127.0.0.1']});
 try{
  const page=context.pages()[0];const url='http://127.0.0.1:'+server.address().port+'/chat';await page.goto(url);
  const endpoint='http://127.0.0.1:'+fs.readFileSync(path.join(profile,'DevToolsActivePort'),'utf8').split('\n')[0];
  const config={id:'web-fixture',name:'Fixture',login_url:url,chat_url:url,input_selector:'#prompt',send_selector:'#send',response_selector:'.assistant',busy_selector:'#stop'};
  // This local HTTP fixture calls the worker directly; production config only permits HTTPS.
  const check=await run({action:'check',config,endpoint});if(!check.session_ready||!check.controls_mapped)throw Error('Check failed');
  const result=await run({action:'execute',config,endpoint,prompt:'hello',timeout_ms:8000});
  if(result.status!=='completed'||result.result!=='SESSION_FIXTURE_OK')throw Error('Execution failed: '+JSON.stringify(result));
  await page.locator('.assistant').first().evaluate(el=>el.setAttribute('data-testid','assistant-message'));
  await page.locator('#stop').evaluate(el=>el.setAttribute('data-testid','stop-button'));
  const discovery=await run({action:'check',config:{...config,input_selector:'',response_selector:'',busy_selector:''},endpoint});
  if(!discovery.controls_mapped||discovery.suggested_config.input_selector!=='#prompt')throw Error('Generic chat controls not discovered');
  await page.locator('#prompt').fill('existing draft');
  const draft=await run({action:'execute',config,endpoint,prompt:'overwrite?',timeout_ms:3000});
  if(draft.status!=='failed'||await page.locator('#prompt').inputValue()!=='existing draft')throw Error('Draft overwritten');
  await page.locator('#prompt').fill('');
  await page.evaluate(()=>{document.getElementById('send').onclick=()=>{const answer=document.createElement('div');answer.className='assistant';answer.textContent='Unconfirmed text';document.getElementById('answers').append(answer);document.getElementById('prompt').value=''}});
  const unconfirmed=await run({action:'execute',config,endpoint,prompt:'no lifecycle',timeout_ms:3000});
  if(unconfirmed.status==='completed')throw Error('Stability alone accepted as completion');
  await page.goto(url.replace('/chat','/login'));
  const login=await run({action:'check',config,endpoint});if(login.session_ready)throw Error('Login page treated as ready');
  fs.writeFileSync('evidence/web-session-browser.json',JSON.stringify({passed:true,mode:'isolated local browser fixture; no model API',checks:['CDP dedicated session attach','composer readiness','UI submission','assistant response extraction','observed generation completion','draft protection','login page rejection','stable text alone does not confirm completion']},null,2));
  console.log('PASS: browser session submission and completion, draft protection, login guard');
 }finally{await context.close();await new Promise(r=>server.close(r));fs.rmSync(profile,{recursive:true,force:true})}
 process.exit(0);
})().catch(e=>{console.error(e);process.exit(1)});
