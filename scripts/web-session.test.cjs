const {test}=require('node:test');const assert=require('node:assert/strict');const vm=require('node:vm');const fs=require('node:fs');
async function fixture(mode){
 let now=0,sent=0;
 const prompt=mode.includes('clipped')?'Long prompt '+ 'x'.repeat(14000):'local';
 const temporary='https://chatgpt.com/c/local-chatgpt%3A19fc7bb4-432d-4de6-b598-9aab2d8a7990';
 const saved='https://chatgpt.com/c/6ae0ca7e-fcb4-83e8-98ce-4bc8548fe433';
 const url=()=>mode.startsWith('promotion')?(now>1000?saved:temporary):`https://chatgpt.com/c/${mode==='switch'&&now>1000?'other':'fixture'}`;
 const input={isVisible:async()=>true,isEditable:async()=>true,evaluate:async()=>'',fill:async()=>{},press:async()=>{sent++}};
 const response={innerText:async()=>now<5000?'partial':'complete',evaluate:async(fn)=>fn({closest(selector){if(selector.includes('message-id'))return mode.startsWith('virtual')?{getAttribute(){return sent?'new-id':'old-id'}}:null;return selector==='[data-talvt-turn-state]'?{getAttribute(){return (mode==='modern'||mode.startsWith('virtual'))&&now>5000?'complete':'streaming'}}:{querySelector(){return (mode==='normal'||mode.startsWith('promotion'))&&now>5000?{}:null}}}})};
 const page={url,evaluate:async()=>'fixture-document',bringToFront:async()=>{},waitForTimeout:async(ms)=>{now+=ms},locator(selector){
  if(selector==='#input')return {count:async()=>1,nth:()=>input};
  if(selector.includes('author-role="user"'))return {count:async()=>sent,last:()=>({innerText:async()=>mode==='promotion-no-echo'?'other':mode.includes('clipped')?(mode.includes('wrong')?'z'+prompt.slice(1,10240):prompt.slice(0,mode.includes('short')?1000:10240)):prompt})};
  if(selector==='#response')return {count:async()=>mode.startsWith('virtual')?1:sent,last:()=>response};
  return {count:async()=>0,filter(){return {count:async()=>sent&&(mode==='slow'||now<5000)?1:0}}};
 }};
 const sandbox={require:()=>({chromium:{connectOverCDP:async()=>({contexts:()=>[{pages:()=>[page]}]})}}),module:{exports:{}},Date:{now:()=>now},URL,Buffer};
 vm.runInNewContext(fs.readFileSync(__dirname+'/web-session.cjs','utf8'),sandbox);
 const result=await sandbox.module.exports.run({...(mode==='virtual-context'?{context:{url:url(),document_token:'fixture-document',assistant_id:'old-id',count:999}}:{}),endpoint:'fixture',action:'execute',prompt,timeout_ms:8000,config:{chat_url:url(),input_selector:'#input',response_selector:'#response',busy_selector:'#busy'}});
 return {result,sent};
}
for(const mode of ['normal','slow','capture','switch'])test(`Playwright fixture: ${mode}`,async()=>{const {result,sent}=await fixture(mode);assert.equal(sent,1);assert.equal(result.status,mode==='normal'?'completed':'interrupted');assert.equal(result.result,mode==='normal'?'complete':'');if(mode==='switch')assert.equal(result.reason,'conversation_changed')});

for(const mode of ['promotion','promotion-no-echo'])test(`Playwright provisional transition: ${mode}`,async()=>{
 const {result,sent}=await fixture(mode);assert.equal(sent,1);
 assert.equal(result.status,mode==='promotion'?'completed':'interrupted');
 if(mode==='promotion-no-echo')assert.equal(result.reason,'conversation_changed');
});

for(const mode of ['modern','modern-streaming'])test(`Playwright current completion state: ${mode}`,async()=>{
 const {result,sent}=await fixture(mode);assert.equal(sent,1);assert.equal(result.status,mode==='modern'?'completed':'interrupted');
});

test('Playwright captures a virtualized response with unchanged DOM count',async()=>{const {result,sent}=await fixture('virtual');assert.equal(result.status,'completed');assert.equal(result.context.assistant_id,'new-id');assert.equal(sent,1)});

test('Playwright binding survives removal of old turns with stable last ID',async()=>{const {result}=await fixture('virtual-context');assert.equal(result.status,'completed');assert.equal(result.context.assistant_id,'new-id')});

test('Playwright accepts exact collapsed long prompt during promotion',async()=>{const {result,sent}=await fixture('promotion-clipped');assert.equal(result.status,'completed');assert.equal(sent,1)});
for(const mode of ['promotion-clipped-wrong','promotion-clipped-short'])test(`Playwright rejects invalid collapsed echo: ${mode}`,async()=>{const {result}=await fixture(mode);assert.equal(result.reason,'conversation_changed');assert.equal(result.result,'')});
