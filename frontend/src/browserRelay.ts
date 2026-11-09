
// A command is sent once, after confirming the extension's capture protocol.
// Read-only requests (check/poll) are idempotent, so transient channel failures
// are retried; the execute command is never repeated.
const TRANSIENT_REASONS=['extension_channel_timeout','extension_channel_lost','extension_empty_reply'];
export async function runBrowserJob(runtime:any, job:any, stopped:()=>boolean=()=>false,
  options:{now?:()=>number;sleep?:(ms:number)=>Promise<void>;channelTimeoutMs?:number;readRetries?:number}={}) {
  const now=options.now??Date.now;
  const sleep=options.sleep??((ms:number)=>new Promise<void>(resolve=>setTimeout(resolve,ms)));
  const readRetries=options.readRetries??8;
  let confirmed:boolean|null=false, phase='preflight', polls=0, protocol:number|undefined, version:string|undefined;
  const decorate=(value:any)=>({...value,channel_phase:phase,poll_count:polls,job_id:job.id,
   ...(protocol?{bridge_protocol:protocol,worker_version:version}:{})});
  const failure=(reason:string)=>decorate({status:'interrupted',reason,submitted:confirmed,result:'',usage:{},
   error:phase==='preflight'?'Não foi possível verificar a extensão; nenhuma mensagem foi enviada.':
    'Canal de captura interrompido. O envio pode ter ocorrido; confira a aba. Nenhuma mensagem foi reenviada.'});
  if(!runtime?.sendMessage)return decorate({status:'session_closed',reason:'extension_unavailable',submitted:false,result:'',usage:{},error:'Extensão não encontrada. Abra o Orchestrator no Chrome com a extensão instalada.'});
  const send=(message:any)=>new Promise<any>(resolve=>{
   let settled=false;
   const finish=(value:any)=>{if(!settled){settled=true;clearTimeout(timer);resolve(value)}};
   const timer=setTimeout(()=>finish(failure('extension_channel_timeout')),options.channelTimeoutMs??10000);
   try{runtime.sendMessage(job.extension_id,message,(reply:any)=>{
    const error=runtime.lastError;
    finish(error?failure('extension_channel_lost'):
     reply&&typeof reply==='object'&&typeof reply.status==='string'?reply:failure('extension_empty_reply'));
   })}catch{finish(failure('extension_channel_lost'))}
  });
  if(stopped())return {...failure('local_capture_cancelled'),submitted:false};
  const deadline=now()+job.timeout_ms;
  // Only for check/poll: they never submit anything, so a transient channel
  // failure (frozen background tab, suspended service worker) is safe to retry.
  const read=async(message:any)=>{
   let reply=await send(message);
   for(let attempt=0;TRANSIENT_REASONS.includes(reply?.reason)&&attempt<readRetries;attempt++){
    if(stopped()||now()>=deadline)break;
    await sleep(1000);
    reply=await send(message);
   }
   return reply;
  };
  if(job.action==='check')return decorate(await read(job));
  const probe=await read({id:job.id+'-probe',action:'check',prompt:''});
  if(probe.reason || !['validation_required','available','completed'].includes(probe.status))return decorate({...probe,submitted:false});
  protocol=probe.bridge_protocol;version=probe.worker_version;
  if(protocol!==2 || probe.capture_mode!=='async_poll')return decorate({status:'validation_required',reason:'extension_upgrade_required',submitted:false,result:'',usage:{},
   error:'A extensão ativa não confirmou captura assíncrona (protocolo 2). Recarregue AI Orchestrator · ChatGPT 0.2.0 e a página do Orchestrator. Nenhuma mensagem foi enviada.'});
  if(!probe.session_ready || !probe.controls_mapped)return decorate({...probe,submitted:false});
  if(stopped())return failure('local_capture_cancelled');
  if(now()>=deadline)return failure('capture_timeout');
  phase='start';confirmed=null;
  let result=await send({...job,async_capture:true});
  const tabId=probe.tab_id;
  // An uncertain acknowledgement may still have started capture. Recover only
  // its existing state; never send execute again, even if the capture is missing.
  if(TRANSIENT_REASONS.includes(result.reason)) {
   if(stopped() || now()>=deadline)return decorate(result);
   phase='poll';polls++;
   result=await read({id:job.id,action:'poll',prompt:'',tab_id:tabId});
  }
  while(['accepted','pending'].includes(result.status)) {
   if(result.submitted===true)confirmed=true;
   if(stopped())return failure('local_capture_cancelled');
   if(now()>=deadline)return failure('capture_timeout');
   await sleep(1000);
   phase='poll';polls++;
   result=await read({id:job.id,action:'poll',prompt:'',tab_id:tabId});
  }
  if(result.submitted==null && confirmed)result.submitted=true;
  return decorate(result);
 }
