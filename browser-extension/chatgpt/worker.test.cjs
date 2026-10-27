const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
function setup(url='https://chatgpt.com/c/fixture'){
 let listener;const calls=[];
 const chrome={runtime:{onMessageExternal:{addListener(fn){listener=fn}}},
 storage:{local:{async get(){return {chatgptTabId:42}}}},tabs:{async get(id){calls.push(['tab',id]);return {id,url}}},
 scripting:{async executeScript(options){calls.push(['script',options.target]);return [{result:{status:'completed',result:'ok'}}]}}};
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
