let occupied = false;
chrome.runtime.onMessageExternal.addListener((job, sender, respond) => {
 if (!sender.url || new URL(sender.url).origin !== 'http://127.0.0.1:8787') return false;
 if (!['check','execute'].includes(job?.action) || typeof job.prompt !== 'string' || job.prompt.length > 500000) {
  respond({status:'failed',error:'Pedido inválido.',result:'',usage:{}}); return false;
 }
 if (occupied) {respond({status:'failed',error:'Aba ocupada.',result:'',usage:{}});return false;}
 occupied = true;
 (async () => {
  const {chatgptTabId} = await chrome.storage.local.get('chatgptTabId');
  if (!chatgptTabId) throw Error('Clique na extensão dentro da aba ChatGPT e use Conectar esta aba.');
  const tab = await chrome.tabs.get(chatgptTabId);
  if (new URL(tab.url).origin !== 'https://chatgpt.com') throw Error('A aba conectada não está no ChatGPT.');
  const results = await chrome.scripting.executeScript({target:{tabId:chatgptTabId},func:operateChatGPT,args:[job]});
  return results[0]?.result || {status:'failed',error:'Sem resposta da aba.',result:'',usage:{}};
 })().then(respond, error => respond({status:'session_closed',error:error.message,result:'',usage:{}})).finally(()=>{occupied=false;});
 return true;
});

async function operateChatGPT(job) {
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
 const before=document.querySelectorAll(responseSelector).length;
 let completedSignal=false;
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
  send.click();
  let sawBusy=false,last='',stableAt=Date.now();
  const deadline=Date.now()+Math.min(job.timeout_ms || 120000,180000);
  while(Date.now()<deadline){
   await new Promise(r=>setTimeout(r,200));
   const busy=[...document.querySelectorAll(busySelector)].some(visible);
   sawBusy ||= busy;
   const responses=[...document.querySelectorAll(responseSelector)].filter(visible);
   if(responses.length<=before) continue;
   const text=responses.at(-1).innerText.trim();
   if(text!==last){last=text;stableAt=Date.now();}
   if(text&&!busy&&(sawBusy||completedSignal)&&Date.now()-stableAt>=1000) {
    if(new TextEncoder().encode(text).length>48000) return {...base,status:'interrupted',submitted:true,error:'Resposta excedeu o limite de 48 KiB da ponte. Consulte a aba; nenhum texto parcial foi considerado conclusão.'};
    return {...base,status:'completed',result:text,submitted:true};
   }
  }
  return {...base,status:'interrupted',submitted:true,error:'Conclusão não confirmada. Confira a aba antes de reenviar.'};
 } finally {observer.disconnect();}
}
