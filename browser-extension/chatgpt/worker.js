// Serialize bridge requests; overlapping checks/polls are normal and must not
// fail a task. Page capture keeps its own guard against concurrent submissions.
let requestQueue = Promise.resolve();
chrome.runtime.onMessageExternal.addListener((job, sender, respond) => {
 if (!sender.url || new URL(sender.url).origin !== 'http://127.0.0.1:8787') return false;
 if (!['check','execute','poll'].includes(job?.action) || typeof job.prompt !== 'string' || job.prompt.length > 500000) {
  respond({status:'failed',error:'Pedido inválido.',result:'',usage:{}}); return false;
 }
 const operation = requestQueue.then(async () => {
  const {chatgptTabId} = await chrome.storage.local.get('chatgptTabId');
  if (!chatgptTabId) throw Error('Clique na extensão dentro da aba ChatGPT e use Conectar esta aba.');
  const tab = await chrome.tabs.get(chatgptTabId);
  if (new URL(tab.url).origin !== 'https://chatgpt.com') throw Error('A aba conectada não está no ChatGPT.');
  if(job.action==='poll' && job.tab_id!==chatgptTabId) return {status:'interrupted',reason:'conversation_changed',submitted:null,result:'',usage:{},error:'A aba vinculada mudou durante a captura.'};
  if(job.context && job.context.tab_id !== chatgptTabId) return {status:'interrupted',reason:'conversation_changed',result:'',error:'A aba vinculada mudou; execução interrompida.'};
  const results = await chrome.scripting.executeScript({target:{tabId:chatgptTabId},func:operateChatGPT,args:[job]});
  if(results[0]?.result) results[0].result.tab_id=chatgptTabId;
  if(results[0]?.result?.context) results[0].result.context.tab_id=chatgptTabId;
  return results[0]?.result || {status:'failed',error:'Sem resposta da aba.',result:'',usage:{}};
 });
 // Recover the queue before replying, including when a request fails.
 requestQueue = operation.then(()=>undefined,()=>undefined);
 operation.then(result=>respond({...result,bridge_protocol:2,worker_version:'0.2.2',capture_mode:'async_poll'}), error => respond({status:'session_closed',reason:'local_transport_failed',submitted:null,error:error.message,result:'',usage:{},bridge_protocol:2,worker_version:'0.2.2',capture_mode:'async_poll'}));
 return true;
});

async function operateChatGPT(job) {
 // Keep capture in the page; external messaging and the service worker only make
 // short requests. A slow response must not hold one Chrome channel open for minutes.
 const jobs=globalThis.__orchestratorCaptureJobs ||= Object.create(null);
 const pending=entry=>entry.result || {status:'pending',submitted:entry.submitted??null,result:'',usage:{}};
 if(job.action==='poll') {
  return jobs[job.id] ? pending(jobs[job.id]) : {status:'interrupted',reason:'capture_context_lost',submitted:null,result:'',usage:{},error:'O contexto de captura foi perdido. Confira a aba; nenhum reenvio foi feito.'};
 }
 if(job.action==='execute' && job.async_capture===true) {
  if(typeof job.id!=='string' || !/^[a-zA-Z0-9-]{1,80}$/.test(job.id))return {status:'failed',result:'',usage:{},error:'ID de captura inválido.'};
  if(jobs[job.id])return pending(jobs[job.id]);
  if(Object.values(jobs).some(entry=>!entry.result))return {status:'interrupted',reason:'capture_in_progress',submitted:false,result:'',usage:{},error:'A aba ainda acompanha uma captura anterior. Nenhuma mensagem nova foi enviada. Aguarde; se a geração já terminou, atualize a aba ChatGPT antes de retomar.'};
  // Retain tombstones so an old request ID can never submit a second command.
  for(const key of Object.keys(jobs).slice(0,-16)) {
   const previous=jobs[key];
   if(previous.result&&!previous.expired)jobs[key]={expired:true,result:{status:'interrupted',reason:'capture_expired',submitted:previous.result.submitted??null,result:'',usage:{},error:'Captura antiga expirada; este ID não será reenviado.'}};
  }
  const entry=jobs[job.id]={submitted:null};
  capture(job).then(result=>{entry.result=result},()=>{entry.result={status:'interrupted',reason:'capture_failed',submitted:entry.submitted,result:'',usage:{},error:'Falha de captura; confira a aba antes de retomar.'}});
  return {status:'accepted',submitted:null,result:'',usage:{}};
 }
 return capture(job);

 async function capture(job) {
 const visible = el => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
 const one = selector => {const matches=[...document.querySelectorAll(selector)].filter(visible);return matches.length===1?matches[0]:null;};
 const inputSelector = '[contenteditable="true"][data-composer-markdown], #prompt-textarea';
 const responseSelector = '[data-markdown-text-style="assistant-message"], [data-message-author-role="assistant"] .markdown';
 const busySelector = '[data-testid="stop-button"], button[aria-label="Stop generating"], button[aria-label="Stop response"], button[aria-label="Parar geração"], button[aria-label="Parar resposta"]';
 const input=one(inputSelector);
 const base={result:'',usage:{}};
 if (location.origin !== 'https://chatgpt.com' || !input || /\/(auth|login|signin)(\/|$)/.test(location.pathname)) return {...base,status:'authentication_required',session_ready:false,error:'Conclua o login normalmente no ChatGPT.'};
 if (job.action==='check') return {...base,status:'validation_required',session_ready:true,controls_mapped:true};
 if ((input.value || input.textContent || '').trim()) return {...base,status:'failed',error:'Há um rascunho. Envie ou remova antes de executar.'};
 if ([...document.querySelectorAll(busySelector)].some(visible)) return {...base,status:'failed',error:'A aba já está gerando uma resposta.'};
 const responseId=el=>el?.closest('[data-chatgpt-selection-message-id]')?.getAttribute?.('data-chatgpt-selection-message-id') || el?.closest('[data-message-id]')?.getAttribute?.('data-message-id') || null;
 // A background tab may report zero layout rectangles even while its DOM is intact.
// Response identity must not depend on viewport layout or the active browser tab.
const lastResponse=()=>[...document.querySelectorAll(responseSelector)].at(-1);
 const documentToken=globalThis.__orchestratorDocumentToken ||= String(Date.now())+Math.random();
 const path=()=>location.origin+location.pathname;
 if(job.context && (job.context.document_token!==documentToken || job.context.url!==path() || (job.context.assistant_id ? job.context.assistant_id!==responseId(lastResponse()) : job.context.count!==document.querySelectorAll(responseSelector).length))) return {...base,status:'interrupted',reason:'conversation_changed',error:'Conversa alterada ou contexto perdido; execução interrompida.'};
 let boundPath=path();
 const before=document.querySelectorAll(responseSelector).length;
 const beforeId=responseId(lastResponse());
 let completedSignal=false;
 let submissionAttempted=false;
 const observer=new MutationObserver(records=>{
  for(const record of records){
   const element=record.target.nodeType===Node.ELEMENT_NODE?record.target:record.target.parentElement;
   const status=element?.closest('[role="status"]');
   if(status && /^(resposta concluída|response complete|response completed)$/i.test(status.textContent.trim())) completedSignal=true;
   for(const node of record.addedNodes || []) if(node.nodeType===Node.ELEMENT_NODE){
    const statuses=[...(node.matches('[role="status"]')?[node]:[]),...node.querySelectorAll('[role="status"]')];
    if(statuses.some(el=>/^(resposta concluída|response complete|response completed)$/i.test(el.textContent.trim()))) completedSignal=true;
   }
  }
 });
 observer.observe(document.body,{subtree:true,childList:true,characterData:true});
 try {
  input.focus();
  if (input instanceof HTMLTextAreaElement) {
   Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(input,job.prompt);
   input.dispatchEvent(new Event('input',{bubbles:true}));
  } else if (!document.execCommand('insertText',false,job.prompt)) return {...base,status:'failed',error:'O campo não aceitou o texto. Nenhum envio confirmado.'};
  await new Promise(r=>setTimeout(r,150));
  const send=one('[data-testid="send-button"], button[aria-label="Send prompt"], button[aria-label="Enviar prompt"], button[aria-label="Enviar mensagem"], button[aria-label="Send message"], button[aria-label="Enviar"]');
  if(!send || send.disabled) return {...base,status:'failed',error:'Botão enviar não reconhecido. Rascunho preservado; confira o mapeamento.'};
  submissionAttempted=true;
  send.click();
  let submitted=null;
  let sawBusy=false,lastBusy=false,last='',stableAt=Date.now();
  const deadline=Date.now()+(job.timeout_ms || 120000);
  while(Date.now()<deadline){
   await new Promise(r=>setTimeout(r,200));
   if(path()!==boundPath) {
    // A newly created chat first uses /c/local-chatgpt:<uuid>, then its persisted ID.
    // Permit only that promotion (or the initial empty composer), with the submitted
    // user message still present in this document. Established chats never migrate.
    const previous=new URL(boundPath), current=new URL(path());
    const oldPath=decodeURIComponent(previous.pathname), newPath=decodeURIComponent(current.pathname);
    const provisional=value=>/^\/c\/local-chatgpt:[a-f0-9-]+$/i.test(value);
    const persisted=value=>/^\/c\/[a-f0-9]{8}-[a-f0-9-]{27}$/i.test(value);
    const normalize=value=>value.replace(/\s+/g,' ').trim();
    const users=[...document.querySelectorAll('[data-message-author-role="user"], [data-user-message-bubble] .whitespace-pre-wrap')];
    const echo=users.at(-1)?.innerText || '';
    // ChatGPT collapses long submitted messages to exactly 10,240 UTF-16
    // characters in the DOM. Match only that observed clipping boundary;
    // arbitrary prefixes must never authorize a conversation transition.
    const echoMatches=normalize(echo)===normalize(job.prompt) ||
      (echo.length===10240 && job.prompt.length>10240 &&
       normalize(echo)===normalize(job.prompt.slice(0,10240)));
    const promotion=previous.origin===current.origin &&
      ((oldPath==='/' && !job.context && before===0 && (provisional(newPath)||persisted(newPath))) ||
       (provisional(oldPath)&&persisted(newPath))) &&
      echoMatches;
    if(!promotion) return {...base,status:'interrupted',submitted,reason:'conversation_changed',error:'Conversa trocada durante a resposta; nenhum resultado foi executado.'};
    boundPath=path();
    submitted=true;
   }
   const busy=[...document.querySelectorAll(busySelector)].some(visible);
   sawBusy ||= busy;
   lastBusy=busy;
   if(busy) submitted=true;
   if(jobs[job.id])jobs[job.id].submitted=submitted;
   // Background/frozen tabs can have stale layout metrics; use DOM state and
// explicit completion signals rather than geometric visibility for capture.
const responses=[...document.querySelectorAll(responseSelector)];
   const latest=responses.at(-1);
   const latestId=responseId(latest);
   if(!latest || (latestId ? latestId===beforeId : responses.length<=before)) continue;
   submitted=true;
   if(jobs[job.id])jobs[job.id].submitted=true;
   const text=(responses.at(-1).innerText || responses.at(-1).textContent || '').trim();
   if(text!==last){last=text;stableAt=Date.now();}
   const turn=responses.at(-1).closest('[data-message-author-role="assistant"]')?.closest('article');
   const explicitComplete=responses.at(-1).closest('[data-talvt-turn-state]')?.getAttribute?.('data-talvt-turn-state')==='complete';
   const finalControl=explicitComplete || !!turn?.querySelector('[data-testid="copy-turn-action-button"], [data-testid="good-response-turn-action-button"]');
   if(!busy&&(completedSignal||finalControl)&&Date.now()-stableAt>=1000) {
    if(!text)return {...base,status:'interrupted',reason:'empty_response',submitted:true,error:'O ChatGPT encerrou a resposta sem conteúdo. Nenhuma ferramenta foi executada a partir dessa resposta. Confira a aba antes de retomar.'};
    if(new TextEncoder().encode(text).length>48000) return {...base,status:'interrupted',submitted:true,error:'Resposta excedeu o limite de 48 KiB da ponte. Consulte a aba; nenhum texto parcial foi considerado conclusão.'};
    return {...base,status:'completed',reason:'response_complete',result:text,submitted:true,context:{assistant_id:latestId,document_token:documentToken,url:path(),count:document.querySelectorAll(responseSelector).length}};
   }
  }
  return {...base,status:'interrupted',submitted,reason:lastBusy?'provider_timeout':'capture_timeout',error:lastBusy?'Tempo limite do provedor: a aba continua gerando. Não reenvie.':'Falha de captura: término não confirmado. Confira a aba antes de reenviar.'};
 } catch(error) {return {...base,status:'interrupted',submitted:submissionAttempted?null:false,reason:'capture_failed',error:'Falha de captura; confira a aba antes de retomar.'};} finally {observer.disconnect();}
}
}
