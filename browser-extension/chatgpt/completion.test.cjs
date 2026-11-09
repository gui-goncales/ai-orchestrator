const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
async function fixture(mode){
 let now=0,clicked=0;
 const prompt=mode.includes('clipped')?'Long prompt '+ 'x'.repeat(14000):'fixture';
 const input={offsetWidth:1,textContent:'',focus(){}};
 const send={offsetWidth:1,click(){clicked++}};
 const busy={offsetWidth:1};
 const response={offsetWidth:1,innerText:'partial',closest(selector){if(selector.includes('message-id'))return mode.startsWith('virtual')?{getAttribute(){return 'new-id'}}:null;
 if(selector==='[data-talvt-turn-state]')return {getAttribute(){return (['modern','async-modern','empty'].includes(mode)||mode.startsWith('virtual'))&&now>5000?'complete':'streaming'}};return {closest(){return {querySelector(){return ((['normal','promotion','new-chat','promotion-no-echo','promotion-other','promote-then-switch'].includes(mode)||mode.startsWith('promotion-clipped')) && now>5000)||(mode==='late'&&now>200000)?{}:null}}}}}};
 const doc={body:{},execCommand(){return true},querySelectorAll(s){
  if(s.includes('contenteditable'))return [input];
  if(s.includes('send-button'))return [send];
  if(s.includes('stop-button'))return clicked&&(mode==='slow'||now<(mode==='late'?200000:5000))?[busy]:[];
  if(s.includes('author-role="user"'))return clicked&&mode!=='promotion-no-echo'?[{innerText:mode.includes('clipped')?(mode.includes('wrong')?'z'+prompt.slice(1,10240):prompt.slice(0,mode.includes('short')?1000:10240)):prompt}]:[];
  if(s.includes('assistant-message')){if(mode.startsWith('virtual')&&!clicked)return [{offsetWidth:1,closest(){return {getAttribute(){return 'old-id'}}}}];response.innerText=mode==='empty'?'':now>5000?'complete':'partial';if(mode==='background')response.offsetWidth=0;return clicked?[response]:[];}
  return [];
 }};
 const temporary='/c/local-chatgpt%3A19fc7bb4-432d-4de6-b598-9aab2d8a7990';
 const saved='/c/6ae0ca7e-fcb4-83e8-98ce-4bc8548fe433';
 const location={origin:'https://chatgpt.com',pathname:mode==='new-chat'?'/':mode.startsWith('promotion')||mode==='promote-then-switch'?temporary:'/c/fixture'};
 const context={chrome:{runtime:{onMessageExternal:{addListener(){}}}},document:doc,location,URL,
  Date:{now:()=>now},setTimeout(fn,ms){now+=ms;if(mode==='switch'&&now>1000)location.pathname='/c/other';
   if((mode.startsWith('promotion')||mode==='promote-then-switch')&&now>1000)location.pathname=mode==='promotion-other'?temporary.replace('19fc7bb4','29fc7bb4'):saved;
   if(mode==='new-chat'&&now>1000)location.pathname=now>2000?saved:temporary;
   if(mode==='promote-then-switch'&&now>2000)location.pathname='/c/other';
   fn()},
  MutationObserver:class{observe(){}disconnect(){}},HTMLTextAreaElement:class{},Event:class{},TextEncoder,Node:{ELEMENT_NODE:1}};
 vm.createContext(context);vm.runInContext(fs.readFileSync(__dirname+'/worker.js','utf8'),context);
 const job={id:'fixture-job',action:'execute',prompt,timeout_ms:mode==='late'?240000:8000};
 if(mode==='virtual-context') {context.__orchestratorDocumentToken='fixture-document';job.context={document_token:'fixture-document',url:'https://chatgpt.com/c/fixture',assistant_id:'old-id',count:999}}
 let result=await context.operateChatGPT(mode==='async-modern'?{...job,async_capture:true}:job);
 if(mode==='async-modern') {
  assert.equal(result.status,'accepted');
  // A duplicate start only retrieves the existing capture, even while pending.
  await context.operateChatGPT({...job,async_capture:true});
  for(let i=0;i<100&&['accepted','pending'].includes(result.status);i++)result=await context.operateChatGPT({action:'poll',id:job.id});
  const again=await context.operateChatGPT({...job,async_capture:true});
  assert.equal(again.result,result.result);
 }

 return {result,clicked,context};
}
test('slow streaming never executes partial response',async()=>{const {result,clicked}=await fixture('slow');assert.equal(result.status,'interrupted');assert.equal(result.result,'');assert.equal(clicked,1);assert.equal(result.reason,'provider_timeout')});
test('normal completion requires final turn control',async()=>{const {result}=await fixture('normal');assert.equal(result.status,'completed');assert.equal(result.result,'complete')});
test('stable text without final control is not completion',async()=>{const {result,clicked}=await fixture('capture');assert.equal(result.status,'interrupted');assert.equal(result.result,'');assert.equal(clicked,1)});
test('conversation switch interrupts without returning commands',async()=>{const {result}=await fixture('switch');assert.equal(result.reason,'conversation_changed');assert.equal(result.result,'')});

test('slow response can complete beyond the old three minute limit',async()=>{const {result,clicked}=await fixture('late');assert.equal(result.status,'completed');assert.equal(clicked,1)});

for(const mode of ['promotion','new-chat'])test(`accepts verified provisional conversation transition: ${mode}`,async()=>{
 const {result,clicked}=await fixture(mode);assert.equal(result.status,'completed');assert.equal(clicked,1);
 assert.equal(result.context.url,'https://chatgpt.com/c/6ae0ca7e-fcb4-83e8-98ce-4bc8548fe433');
});
for(const mode of ['promotion-no-echo','promotion-other','promote-then-switch'])test(`rejects unverified transition: ${mode}`,async()=>{
 const {result,clicked}=await fixture(mode);assert.equal(result.reason,'conversation_changed');assert.equal(result.result,'');assert.equal(clicked,1);
});

test('long collapsed prompt verifies promotion at the exact ChatGPT DOM limit',async()=>{
 const {result,clicked}=await fixture('promotion-clipped');
 assert.equal(result.status,'completed');assert.equal(result.result,'complete');assert.equal(clicked,1);
});
for(const mode of ['promotion-clipped-wrong','promotion-clipped-short'])test(`rejects mismatched or arbitrary clipped prefix: ${mode}`,async()=>{
 const {result,clicked}=await fixture(mode);assert.equal(result.reason,'conversation_changed');assert.equal(result.result,'');assert.equal(clicked,1);
});

test('current DOM explicit complete state confirms the response',async()=>{const {result}=await fixture('modern');assert.equal(result.status,'completed');assert.equal(result.result,'complete')});
test('current DOM streaming state never confirms stable text',async()=>{const {result}=await fixture('modern-streaming');assert.equal(result.reason,'capture_timeout');assert.equal(result.result,'')});

test('virtualized turn keeps DOM count fixed but captures the new message ID',async()=>{const {result,clicked}=await fixture('virtual');assert.equal(result.status,'completed');assert.equal(result.context.assistant_id,'new-id');assert.equal(clicked,1)});
test('async capture acknowledges immediately and duplicate starts never resend',async()=>{const {result,clicked}=await fixture('async-modern');assert.equal(result.status,'completed');assert.equal(clicked,1)});

test('binding follows last message ID when earlier turns disappear between rounds',async()=>{const {result}=await fixture('virtual-context');assert.equal(result.status,'completed');assert.equal(result.context.assistant_id,'new-id')});
test('expired cached request IDs are tombstones and never restart capture',async()=>{
 const {context}=await fixture('async-modern');
 for(let i=0;i<18;i++)context.__orchestratorCaptureJobs['old-'+i]={result:{status:'completed',submitted:true,result:'fixture'}};
 await context.operateChatGPT({id:'new-job',action:'execute',prompt:'fixture',async_capture:true,timeout_ms:8000});
 const result=await context.operateChatGPT({id:'fixture-job',action:'execute',prompt:'fixture',async_capture:true});
 assert.equal(result.reason,'capture_expired');assert.equal(result.result,'');
});

 test('completed empty response releases capture instead of waiting for timeout',async()=>{
 const {result,clicked}=await fixture('empty');assert.equal(result.reason,'empty_response');assert.equal(result.status,'interrupted');assert.equal(result.submitted,true);assert.equal(result.result,'');assert.equal(clicked,1);
 });
 test('a previous pending capture blocks new submission with an explicit recovery reason',async()=>{
 const {context}=await fixture('normal');context.__orchestratorCaptureJobs.old={submitted:true};
 const result=await context.operateChatGPT({id:'another-job',action:'execute',prompt:'new',async_capture:true});
 assert.equal(result.reason,'capture_in_progress');assert.equal(result.submitted,false);assert.equal(result.status,'interrupted');assert.equal(result.result,'');
 });
