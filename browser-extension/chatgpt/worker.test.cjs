const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
function setup(url='https://chatgpt.com/c/fixture', executeScript){
 let listener;const calls=[];
 const chrome={runtime:{onMessageExternal:{addListener(fn){listener=fn}}},
 storage:{local:{async get(){return {chatgptTabId:42}}}},tabs:{async get(id){calls.push(['tab',id]);return {id,url}}},
 scripting:{async executeScript(options){calls.push(['script',options.target]);if(executeScript)return executeScript(options);return [{result:{status:'completed',result:'ok'}}]}}};
 vm.runInNewContext(fs.readFileSync(__dirname+'/worker.js','utf8'),{chrome,URL});
 return {listener,calls};
}
test('rejects foreign origins and ports without reading a tab',()=>{
 for(const url of ['https://example.com/','http://127.0.0.1:9999/']){
  const {listener,calls}=setup();assert.equal(listener({action:'execute',prompt:'hi'},{url},()=>assert.fail()),false);assert.equal(calls.length,0);
 }
});
test('operates only the explicitly selected ChatGPT tab',async()=>{
 const {listener,calls}=setup();
 const result=await new Promise(resolve=>assert.equal(listener({action:'execute',prompt:'hi'},{url:'http://127.0.0.1:8787/'},resolve),true));
 assert.equal(result.result,'ok');assert.equal(calls[0][1],42);assert.equal(calls[1][1].tabId,42);
});
test('refuses selected tab navigated to another site',async()=>{
 const {listener,calls}=setup('https://accounts.google.com/');
 const result=await new Promise(resolve=>listener({action:'execute',prompt:'hi'},{url:'http://127.0.0.1:8787/'},resolve));
 assert.equal(result.status,'session_closed');assert.equal(calls.length,1);
});

test('external replies advertise the async protocol and selected tab',async()=>{
 const {listener}=setup();
 const result=await new Promise(resolve=>listener({action:'check',prompt:''},{url:'http://127.0.0.1:8787/'},resolve));
 assert.equal(result.bridge_protocol,2);assert.equal(result.worker_version,'0.2.2');assert.equal(result.capture_mode,'async_poll');assert.equal(result.tab_id,42);
});

const sender={url:'http://127.0.0.1:8787/'};
const request=(listener,action='check')=>new Promise(resolve=>{
 assert.equal(listener({action,prompt:'',id:'fixture',tab_id:42},sender,resolve),true);
});
test('overlapping bridge requests wait and succeed without a busy failure',async()=>{
 let release,started;
 const entered=new Promise(resolve=>{started=resolve});
 let count=0,active=0,maxActive=0;
 const {listener}=setup(undefined,async()=>{
  count++;active++;maxActive=Math.max(maxActive,active);
  if(count===1){started();await new Promise(resolve=>{release=resolve})}
  active--;return [{result:{status:'completed',result:'ok'}}];
 });
 const first=request(listener);
 await entered;
 const second=request(listener,'poll');
 const third=request(listener,'execute');
 assert.equal(count,1);
 release();
 const results=await Promise.all([first,second,third]);
 assert.ok(results.every(result=>result.status==='completed'));
 assert.equal(count,3);assert.equal(maxActive,1);
});
test('a failed bridge request does not poison queued requests',async()=>{
 let count=0;
 const {listener}=setup(undefined,async()=>{
  if(++count===1)throw Error('fixture failure');
  return [{result:{status:'completed',result:'recovered'}}];
 });
 const results=await Promise.all([request(listener),request(listener)]);
 assert.equal(results[0].status,'session_closed');
 assert.equal(results[1].result,'recovered');
});
test('a follow-up requested from the reply callback is accepted',async()=>{
 const {listener}=setup();
 const result=await new Promise(resolve=>{
  listener({action:'check',prompt:''},sender,()=>{request(listener,'poll').then(resolve)});
 });
 assert.equal(result.status,'completed');
});
