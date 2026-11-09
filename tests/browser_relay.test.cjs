
const {test}=require('node:test');const assert=require('node:assert/strict');
const {runBrowserJob}=require('../frontend/src/browserRelay.ts');
const job={id:'fixture-job',extension_id:'fixture-extension',action:'execute',prompt:'private initial context',timeout_ms:600000};
const probe={status:'validation_required',bridge_protocol:2,worker_version:'0.2.0',capture_mode:'async_poll',session_ready:true,controls_mapped:true,tab_id:42};
test('slow capture polls beyond five minutes and sends the prompt exactly once',async()=>{
  let now=0,polls=0;const messages=[];
  const runtime={sendMessage(id,msg,done){messages.push(msg);done(msg.action==='check'?probe:msg.action==='execute'?{status:'accepted',tab_id:42}:++polls<350?{status:'pending',submitted:true}:{status:'completed',result:'complete',submitted:true})}};
  const result=await runBrowserJob(runtime,job,()=>false,{now:()=>now,sleep:async ms=>{now+=ms}});
  assert.equal(result.result,'complete');assert.ok(now>300000);
  assert.equal(messages.filter(m=>m.action==='execute').length,1);
  assert.equal(messages.filter(m=>m.prompt===job.prompt).length,1);
  assert.ok(messages.slice(2).every(m=>m.action==='poll'&&m.prompt===''&&m.tab_id===42));
  assert.equal(result.bridge_protocol,2);assert.equal(result.channel_phase,'poll');assert.equal(result.poll_count,350);
});
test('lost channel after confirmed submission never retries execute',async()=>{
  let now=0,polls=0;const messages=[];
  const runtime={lastError:null,sendMessage(id,msg,done){messages.push(msg);
   if(msg.action==='check')done(probe);
   else if(msg.action==='execute')done({status:'accepted',tab_id:42});
   else if(++polls===1)done({status:'pending',submitted:true});
   else {this.lastError={message:'fixture channel closed'};done();this.lastError=null;}
  }};
  const result=await runBrowserJob(runtime,job,()=>false,{now:()=>now,sleep:async ms=>{now+=ms}});
  assert.equal(result.reason,'extension_channel_lost');assert.equal(result.submitted,true);
  assert.equal(result.channel_phase,'poll');assert.equal(messages.filter(m=>m.action==='execute').length,1);assert.equal(result.result,'');
});
test('uncertain start acknowledgement recovers result only by poll',async()=>{
  let sends=0,polls=0,late;
  const runtime={sendMessage(id,msg,done){
   if(msg.action==='check')done(probe);
   else if(msg.action==='execute'){sends++;late=done;}
   else {polls++;done({status:'completed',submitted:true,result:'recovered'})}
  }};
  const result=await runBrowserJob(runtime,job,()=>false,{channelTimeoutMs:1});
  assert.equal(result.result,'recovered');assert.equal(result.submitted,true);assert.equal(sends,1);assert.equal(polls,1);
  late({status:'accepted',tab_id:42});assert.equal(sends,1);
});
test('lost page capture context stops without resubmitting',async()=>{
  let now=0,starts=0;
  const runtime={sendMessage(id,msg,done){
   if(msg.action==='check')done(probe);
   else if(msg.action==='execute'){starts++;done({status:'accepted',tab_id:42})}
   else done({status:'interrupted',reason:'capture_context_lost',result:''});
  }};
  const result=await runBrowserJob(runtime,job,()=>false,{now:()=>now,sleep:async ms=>{now+=ms}});
  assert.equal(result.reason,'capture_context_lost');assert.equal(starts,1);
});
test('poll deadline and local cancellation do not issue new commands',async()=>{
  let now=0,starts=0;
  const runtime={sendMessage(id,msg,done){if(msg.action==='check')return done(probe);if(msg.action==='execute')starts++;done({status:'pending',tab_id:42,submitted:true})}};
  const result=await runBrowserJob(runtime,{...job,timeout_ms:1500},()=>false,{now:()=>now,sleep:async ms=>{now+=ms}});
  assert.equal(result.reason,'capture_timeout');assert.equal(result.submitted,true);assert.equal(starts,1);
  const cancelled=await runBrowserJob(runtime,job,()=>true);
  assert.equal(cancelled.submitted,false);assert.equal(starts,1);
});
test('legacy extension cannot receive any execute command',async()=>{
  const actions=[];
  const result=await runBrowserJob({sendMessage(id,msg,done){actions.push(msg.action);done({status:'validation_required',session_ready:true,controls_mapped:true})}},job);
  assert.equal(result.reason,'extension_upgrade_required');assert.equal(result.submitted,false);assert.deepEqual(actions,['check']);
});
test('preflight timeout is diagnosed before any prompt is submitted',async()=>{
  const actions=[];
  const result=await runBrowserJob({sendMessage(id,msg){actions.push(msg.action)}},job,()=>false,{channelTimeoutMs:1,readRetries:2,sleep:async()=>{}});
  assert.equal(result.reason,'extension_channel_timeout');assert.equal(result.channel_phase,'preflight');assert.equal(result.submitted,false);assert.deepEqual(actions,['check','check','check']);
});
test('timed out start followed by missing capture never repeats execute',async()=>{
  const actions=[];
  const runtime={sendMessage(id,msg,done){actions.push(msg.action);if(msg.action==='check')done(probe);else if(msg.action==='poll')done({status:'interrupted',reason:'capture_context_lost',submitted:null,result:''})}};
  const result=await runBrowserJob(runtime,job,()=>false,{channelTimeoutMs:1});
  assert.equal(result.reason,'capture_context_lost');assert.equal(result.submitted,null);assert.deepEqual(actions,['check','execute','poll']);
});
test('transient channel failures during polling are retried and the result is captured',async()=>{
  let now=0,polls=0;const messages=[];
  const runtime={lastError:null,sendMessage(id,msg,done){messages.push(msg);
   if(msg.action==='check')return done(probe);
   if(msg.action==='execute')return done({status:'accepted',tab_id:42});
   polls++;
   if(polls===1)return done({status:'pending',submitted:true});
   if(polls<=3){this.lastError={message:'fixture channel closed'};done();this.lastError=null;return;}
   if(polls===4)return done();
   done({status:'completed',result:'complete',submitted:true});
  }};
  const result=await runBrowserJob(runtime,job,()=>false,{now:()=>now,sleep:async ms=>{now+=ms}});
  assert.equal(result.status,'completed');assert.equal(result.result,'complete');assert.equal(result.submitted,true);
  assert.equal(messages.filter(m=>m.action==='execute').length,1);
  assert.equal(messages.filter(m=>m.prompt===job.prompt).length,1);
});
test('transient probe failure is retried before the prompt is submitted',async()=>{
  let checks=0,starts=0;
  const runtime={sendMessage(id,msg,done){
   if(msg.action==='check'){if(++checks<3)return done();return done(probe)}
   if(msg.action==='execute'){starts++;return done({status:'accepted',tab_id:42})}
   done({status:'completed',result:'ok',submitted:true});
  }};
  const result=await runBrowserJob(runtime,job,()=>false,{channelTimeoutMs:1,sleep:async()=>{}});
  assert.equal(result.result,'ok');assert.equal(starts,1);assert.equal(checks,3);
});
