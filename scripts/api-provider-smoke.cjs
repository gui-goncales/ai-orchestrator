const {chromium}=require('playwright');
const http=require('node:http');
const fs=require('node:fs');
(async()=>{
 const api=http.createServer((req,res)=>{let raw='';req.on('data',b=>raw+=b);req.on('end',()=>{if(req.url!=='/v1/chat/completions')throw Error('Unexpected API path');const data=JSON.parse(raw);if(data.model!=='fixture-model')throw Error('Wrong model');res.setHeader('Content-Type','application/json');res.end(JSON.stringify({choices:[{finish_reason:'stop',message:{content:'API_FIXTURE_OK'}}],usage:{prompt_tokens:7,completion_tokens:2}}))})});
 await new Promise(resolve=>api.listen(0,'127.0.0.1',resolve));
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:8788');await page.getByText('Conectado',{exact:true}).waitFor();
 await page.getByRole('button',{name:'Agents',exact:true}).click();
 await page.getByLabel('Protocolo',{exact:true}).selectOption('openai');
 await page.getByLabel('ID da conexão',{exact:true}).fill('api-smoke');await page.getByLabel('Nome',{exact:true}).fill('Modelo de teste');
 await page.getByLabel('URL base',{exact:true}).fill('http://127.0.0.1:'+api.address().port+'/v1');await page.getByLabel('Modelo',{exact:true}).fill('fixture-model');
 await page.getByRole('button',{name:'Salvar conexão',exact:true}).click();await page.getByRole('heading',{name:'Modelo de teste API',exact:true}).waitFor();
 await page.screenshot({path:'evidence/api-providers-desktop.png',fullPage:true});
 await page.getByRole('button',{name:'Nova tarefa',exact:true}).click();await page.getByLabel('Objetivo',{exact:true}).fill('TESTE API: responder sem acessar arquivos.');
 await page.getByLabel('Agente',{exact:true}).selectOption('api-smoke');await page.getByLabel('Entrega',{exact:true}).selectOption('direct');
 await page.getByRole('button',{name:'Iniciar tarefa',exact:true}).click();
 await page.waitForFunction(async()=>{const d=await(await fetch('/api/state')).json();return d.tasks.some(t=>t.provider==='api-smoke'&&t.status==='completed'&&t.result.includes('API_FIXTURE_OK'))});
 await page.setViewportSize({width:390,height:844});await page.getByLabel('Navegar',{exact:true}).selectOption('Agents');
 await page.screenshot({path:'evidence/api-providers-mobile.png',fullPage:true});
 if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1))throw Error('Mobile overflow');if(errors.length)throw Error(errors.join('\n'));
 fs.writeFileSync('evidence/api-providers-browser.json',JSON.stringify({mode:'local HTTP fixture; no paid API',checks:['register API in Agents','select provider','end-to-end task through local HTTP','mobile layout','no page errors'],passed:true},null,2));console.log('PASS: provider registration and HTTP task from UI');
 }finally{await browser.close();await new Promise(resolve=>api.close(resolve))}
})().catch(e=>{console.error(e);process.exit(1)});
