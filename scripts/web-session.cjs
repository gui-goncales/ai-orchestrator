// Operates only the visible chat UI in an explicitly dedicated Chrome profile.
// No cookie/storage export, credential extraction, fetch replay, or login automation.
const {chromium}=require('playwright');
async function visible(page, selector){
 if(!selector)return null;
 const all=page.locator(selector);const matches=[];
 for(let i=0;i<await all.count();i++)if(await all.nth(i).isVisible())matches.push(all.nth(i));
 if(matches.length!==1)return null;
 return matches[0];
}
async function discover(page,c){
 const found={};
 if(!c.input_selector){
  for(const selector of ['[contenteditable="true"][data-composer-markdown]','textarea','[contenteditable="true"][role="textbox"]','[contenteditable="true"][data-placeholder]']){
   const input=await visible(page,selector);
   if(input){found.input_selector=await input.evaluate((el,fallback)=>el.id?'#'+CSS.escape(el.id):fallback,selector);break}
  }
 }
 if(!c.response_selector){
  for(const selector of ['[data-markdown-text-style="assistant-message"]','.chat-content-assistant-message[data-error-only="false"]','[data-message-author-role="assistant"] .markdown','[data-testid="assistant-message"]','.assistant-message .message-content']){
   if(await page.locator(selector).count()){found.response_selector=selector;break}
  }
 }
 if(!c.busy_selector){
  for(const selector of ['button.template_stop_message_button','button[aria-label="Stop generating"]','button[aria-label="Stop response"]','button[aria-label="Parar geração"]','[data-testid="stop-button"]']){
   if(await page.locator(selector).count()){found.busy_selector=selector;break}
  }
 }
 return found;
}
async function inspect(page,c){
 const origin=new URL(c.chat_url).origin;
 if(new URL(page.url()).origin!==origin)return {session_ready:false,error:'Abra uma conversa no site do provedor.'};
 if(/\/(login|signin|sign-in|auth)(\/|$)/i.test(new URL(page.url()).pathname)||await page.locator('input[type="password"]:visible').count())return {session_ready:false,error:'Conclua o login na janela dedicada.'};
 if(origin==='https://tess.im'){
   const signed=await page.evaluate(()=>window.tessChatConfig?.auth?.isAnonymous===false && !!document.querySelector('#userProfileDropdown'));
   if(!signed)return {session_ready:false,error:'Tess ainda não confirmou uma sessão autenticada.'};
 }
 const input=await visible(page,c.input_selector);
 return {session_ready:!!input,controls_mapped:!!(input&&c.response_selector&&c.busy_selector),
         error:input?null:'Login ou mapeamento do campo de mensagem pendente.'};
}
async function run(data){
 let c={...data.config};
 let browser;try{browser=await chromium.connectOverCDP(data.endpoint,{timeout:8000})}catch{return {status:'session_closed',reason:'browser_unavailable',session_ready:false,controls_mapped:false,result:'',usage:{},error:'A janela dedicada está fechada ou indisponível. Reabra a sessão; seu login pode estar salvo.'}};
 const origin=new URL(c.chat_url).origin;
 const pages=browser.contexts().flatMap(ctx=>ctx.pages()).filter(p=>{try{return new URL(p.url()).origin===origin}catch{return false}});
 // Prefer the configured conversation; never navigate an existing tab or select a different account.
 let page=data.context ? pages.find(p=>p.url().split(/[?#]/)[0]===data.context.url) : pages.find(p=>p.url()===c.chat_url);
 if(!data.context && !page && pages.length===1)page=pages[0];
 if(!page)return {status:'session_closed',reason:'conversation_missing',session_ready:false,controls_mapped:false,result:'',usage:{},error:'Abra uma única conversa no navegador dedicado. O login pode estar salvo, mas a conversa não está aberta.'};
 if(data.action!=='check')await page.bringToFront();
 const suggested=data.action==='check'?await discover(page,c):{};
 c={...c,...suggested};
 const check=await inspect(page,c);
 if(data.action==='check'){
  const u=new URL(page.url());
  return {...check,suggested_config:suggested,status:check.session_ready?'validation_required':'authentication_required',
    // Query values/fragments may include credentials, so never return them.
    conversation_url:u.origin+u.pathname,usage:{},result:''};
 }
 if(!check.session_ready)return {status:'authentication_required',result:'',usage:{},error:check.error};
 if(!check.controls_mapped)return {status:'failed',result:'',usage:{},error:'Mapeie os seletores de resposta e geração em andamento antes de executar.'};
 const input=await visible(page,c.input_selector);
 if(!input||!await input.isEditable())return {status:'failed',result:'',usage:{},error:'Campo de mensagem indisponível.'};
 const draft=await input.evaluate(el=>('value' in el?el.value:el.textContent)||'');
 if(draft.trim())return {status:'failed',result:'',usage:{},error:'Há um rascunho na conversa; envie ou remova antes de executar.'};
 if(await page.locator(c.busy_selector).filter({visible:true}).count())return {status:'failed',result:'',usage:{},error:'A conversa já está gerando uma resposta.'};
 const responses=page.locator(c.response_selector);
 const before=await responses.count();
 const responseId=async()=>await responses.count() ? responses.last().evaluate(el=>el.closest('[data-chatgpt-selection-message-id]')?.getAttribute('data-chatgpt-selection-message-id') || el.closest('[data-message-id]')?.getAttribute('data-message-id') || null) : null;
 const beforeId=await responseId();
 const documentToken=await page.evaluate(()=>globalThis.__orchestratorDocumentToken ||= String(Date.now())+Math.random());
 let initialURL=page.url().split(/[?#]/)[0];
 if(data.context && ((data.context.assistant_id ? beforeId!==data.context.assistant_id : before!==data.context.count) || documentToken!==data.context.document_token))return {status:'interrupted',reason:'conversation_changed',result:'',usage:{},error:'Contexto da conversa alterado; execução interrompida.'};
 await input.fill(data.prompt);
 if(c.send_selector){
  const send=await visible(page,c.send_selector);
  if(!send||!await send.isEnabled())return {status:'failed',result:'',usage:{},error:'Envio indisponível. O rascunho foi preservado.'};
  await send.click();
 }else await input.press('Enter');
 let submitted=null,last='',stableSince=0,sawBusy=false,lastBusy=false;
 const deadline=Date.now()+data.timeout_ms;
 while(Date.now()<deadline){
  await page.waitForTimeout(500);
  const currentURL=page.url().split(/[?#]/)[0];
  if(currentURL!==initialURL) {
   const previous=new URL(initialURL), current=new URL(currentURL);
   const oldPath=decodeURIComponent(previous.pathname), newPath=decodeURIComponent(current.pathname);
   const provisional=value=>/^\/c\/local-chatgpt:[a-f0-9-]+$/i.test(value);
   const persisted=value=>/^\/c\/[a-f0-9]{8}-[a-f0-9-]{27}$/i.test(value);
   const normalize=value=>value.replace(/\s+/g,' ').trim();
   const users=page.locator('[data-message-author-role="user"], [data-user-message-bubble] .whitespace-pre-wrap');
   const echo=await users.count() ? await users.last().innerText() : '';
   // ChatGPT's collapsed user message exposes the first 10,240 characters.
   // Accept only this exact boundary, never an arbitrary prompt prefix.
   const echoMatches=normalize(echo)===normalize(data.prompt) ||
     (echo.length===10240 && data.prompt.length>10240 &&
      normalize(echo)===normalize(data.prompt.slice(0,10240)));
   const sameDocument=await page.evaluate(()=>globalThis.__orchestratorDocumentToken);
   const promotion=origin==='https://chatgpt.com' && current.origin===origin &&
     sameDocument===documentToken &&
     ((oldPath==='/' && !data.context && before===0 && (provisional(newPath)||persisted(newPath))) ||
      (provisional(oldPath)&&persisted(newPath))) && echoMatches;
   if(!promotion)return {status:'interrupted',reason:'conversation_changed',submitted,result:'',usage:{},error:'Sessão redirecionada; confira o envio antes de retomar.'};
   initialURL=currentURL;
   submitted=true;
  }
  const busy=await page.locator(c.busy_selector).filter({visible:true}).count()>0;
  sawBusy ||= busy;
  lastBusy=busy;
  if(busy) submitted=true;
  const count=await responses.count();
  const latestId=await responseId();
  if(!count || (latestId ? latestId===beforeId : count<=before))continue;
  submitted=true;
  const text=(await responses.last().innerText()).trim();
  if(text!==last){last=text;stableSince=Date.now()}
  // ChatGPT needs a final-turn action control as well as idle generation and stable text.
  const finalControl=await responses.last().evaluate(el=>el.closest('[data-talvt-turn-state]')?.getAttribute('data-talvt-turn-state')==='complete'||!!el.closest('article')?.querySelector('[data-testid="copy-turn-action-button"], [data-testid="good-response-turn-action-button"]'));
  if(Buffer.byteLength(text,'utf8')>48000)return {status:'interrupted',reason:'response_limit',submitted,result:'',usage:{},error:'Resposta excedeu 48 KiB; consulte a conversa. Nenhum texto parcial foi executado.'};
  if(text&&(origin==='https://chatgpt.com'?finalControl:sawBusy)&&!busy&&Date.now()-stableSince>=2000)return {status:'completed',reason:'response_complete',submitted:true,result:text,usage:{},context:{assistant_id:latestId,document_token:documentToken,url:page.url().split(/[?#]/)[0],count}};
 }
 return {status:'interrupted',reason:lastBusy?'provider_timeout':'capture_timeout',submitted,result:'',usage:{},error:lastBusy?'Tempo limite do provedor: continua gerando. Não reenvie.':'Falha de captura: término não confirmado. Confira a conversa antes de retomar.'};
}
module.exports={run,inspect,visible,discover};
if(require.main===module){let raw='';process.stdin.on('data',b=>raw+=b);process.stdin.on('end',async()=>{
 try{process.stdout.write(JSON.stringify(await run(JSON.parse(raw))),()=>process.exit(0))}
 catch{process.stdout.write(JSON.stringify({status:'interrupted',reason:'capture_failed',submitted:null,result:'',usage:{},error:'Sessão indisponível ou controles alterados. Verifique login e mapeamento antes de repetir.'}),()=>process.exit(1))}
})}
