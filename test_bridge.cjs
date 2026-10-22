'use strict';
const assert = require('node:assert/strict');
const net = require('node:net');
const {test} = require('node:test');
const {DesktopBridge, continueIfFailed, isUnavailable, turnsFromState, summarize} = require('./desktop_bridge.cjs');

const error = {message:'服务不可用', codexErrorInfo:'serverOverloaded'};
const state = {id:'target-chat', threadRuntimeStatus:{type:'idle'}, turns:[{turnId:'failed-turn',status:'failed',error}]};
const unsupported = /^UNSUPPORTED:/;
function canonicalState() {
  // The live idle snapshot has partial older history and an exhausted newer boundary.
  return {...structuredClone(state), turns:[], turnHistory:{kind:'canonical', history:{
    generation:0, isComplete:false,
    islands:[{id:'island', entries:[{key:'entry', value:'a'}],
      olderBoundary:{status:'available'}, newerBoundary:{status:'exhausted', boundaryId:'tail'}}],
    entitiesByKey:{a:structuredClone(state.turns[0])}
  }}};
}
async function rejectsBeforeSend(candidate) {
  let calls = 0;
  const bridge = {request:async () => { calls++; }};
  await assert.rejects(continueIfFailed(bridge,'owner','target-chat','failed-turn','id',candidate),
    e => unsupported.test(e.message));
  assert.equal(calls,0);
  assert.equal(bridge.submitted,undefined);
}

test('native pipe integration: fragmented frames, exact chat and literal message', async t => {
  const pipe = '\\\\.\\pipe\\codex-muyu-test-' + process.pid;
  const sent = [], sockets = new Set();
  const server = net.createServer(socket => {
    sockets.add(socket); socket.on('close', () => sockets.delete(socket));
    let pending = Buffer.alloc(0);
    const write = value => {
      const body = Buffer.from(JSON.stringify(value)), head = Buffer.alloc(4);
      head.writeUInt32LE(body.length);
      // Split a header across packets to exercise stream framing.
      socket.write(head.subarray(0,2)); socket.write(Buffer.concat([head.subarray(2), body]));
    };
    socket.on('data', data => {
      pending = Buffer.concat([pending, data]);
      while (pending.length >= 4 && pending.length >= pending.readUInt32LE(0) + 4) {
        const n = pending.readUInt32LE(0), m = JSON.parse(pending.subarray(4, n+4));
        pending = pending.subarray(n+4);
        const reply = result => write({type:'response',requestId:m.requestId,method:m.method,resultType:'success',handledByClientId:'owner',result});
        if (m.method === 'initialize') reply({clientId:'test-client'});
        if (m.method === 'thread-owner-discovery') reply({});
        if (m.method === 'thread-stream-following-changed' && m.params.following) {
          write({type:'broadcast',method:'thread-stream-state-changed',version:11,sourceClientId:'owner',params:{hostId:'local',conversationId:'target-chat',change:{type:'snapshot',conversationState:state}}});
        }
        if (m.method === 'thread-follower-start-turn') {
          sent.push(m);
          reply({result:{turn:{id:'new-turn',status:'inProgress'}}});
        }
      }
    });
  });
  await new Promise(resolve => server.listen(pipe, resolve));
  const bridge = new DesktopBridge(pipe);
  try {
    await bridge.connect();
    const owner = (await bridge.request('thread-owner-discovery',{hostId:'local',conversationId:'target-chat'},1)).handledByClientId;
    const snapshot = await bridge.snapshot('target-chat',owner);
    const result = await continueIfFailed(bridge,owner,'target-chat','failed-turn','message-uuid',snapshot);
    assert.equal(result.sent,true);
    assert.equal(result.turnId,'new-turn');
    assert.equal(sent.length,1);
    assert.equal(sent[0].targetClientId,'owner');
    assert.equal(sent[0].version,2);
    assert.deepEqual(sent[0].params, {conversationId:'target-chat',turnStart:{request:{threadId:'target-chat',input:[{type:'text',text:'继续',text_elements:[]}],clientUserMessageId:'message-uuid'},context:{inheritThreadSettings:true}}});
  } finally {
    bridge.close();
    for (const socket of sockets) socket.destroy();
    await new Promise(resolve => server.close(resolve));
  }
});

test('running, stale, wrong chat, cancelled, or unrelated errors never send', async () => {
  const bridge = {request:async () => assert.fail('unexpected send')};
  const cases = [
    {...state,id:'wrong-chat'},
    {...state,threadRuntimeStatus:{type:'active'}},
    {...state,turns:[{turnId:'new-turn',status:'failed',error}]},
    {...state,turns:[{turnId:'failed-turn',status:'completed',error}]},
    {...state,turns:[{turnId:'failed-turn',status:'interrupted',error:null}]},
    {...state,turns:[{turnId:'failed-turn',status:'failed',error:{message:'HTTP 404'}}]},
  ];
  for (const candidate of cases) await assert.rejects(continueIfFailed(bridge,'owner','target-chat','failed-turn','id',candidate), /STALE/);
  assert.equal(bridge.submitted,undefined);
});

test('missing, malformed, and unknown runtime are UNSUPPORTED before submission', async () => {
  for (const runtime of [undefined, null, {}, [], 'idle', {type:'unknown'}, {type:'future'}, {type:0}]) {
    const candidate = {...state,threadRuntimeStatus:runtime};
    await rejectsBeforeSend(candidate);
    assert.throws(() => summarize(candidate), e => unsupported.test(e.message));
  }
  const missing = structuredClone(state); delete missing.threadRuntimeStatus;
  await rejectsBeforeSend(missing);
  for (const candidate of [null, [], {}, {...state,id:42}, {...state,id:''}]) {
    await rejectsBeforeSend(candidate);
  }
});

test('unknown or malformed history never falls back to legacy turns', async () => {
  for (const history of [undefined, null, [], {}, 'canonical', {kind:'legacy'}, {kind:'future'}, {kind:'canonical'}]) {
    await rejectsBeforeSend({...state,turnHistory:history});
  }
});

test('canonical history requires a known tail, entries, and every referenced entity', async () => {
  const mutations = [
    h => { delete h.isComplete; },
    h => { h.isComplete = 'false'; },
    h => { delete h.islands; },
    h => { h.islands = []; },
    h => { h.islands = [null]; },
    h => { delete h.entitiesByKey; },
    h => { h.entitiesByKey = []; },
    h => { delete h.islands[0].newerBoundary; },
    h => { h.islands[0].newerBoundary = {}; },
    h => { h.islands[0].newerBoundary.status = 'available'; },
    h => { h.islands[0].newerBoundary.status = 'unknown'; },
    h => { delete h.islands[0].entries; },
    h => { h.islands[0].entries = []; },
    h => { h.islands[0].entries = {}; },
    h => { h.islands[0].entries.push(null); },
    h => { h.islands[0].entries.push({}); },
    h => { h.islands[0].entries.push({value:''}); },
    h => { h.islands[0].entries.push({value:42}); },
    h => { h.islands[0].entries.push({value:'missing-final-entity'}); },
    h => { h.islands[0].entries.push({value:'b'}); h.entitiesByKey.b = null; },
    h => { h.islands.push({newerBoundary:{status:'exhausted'}}); },
    h => { h.islands.push({entries:[],newerBoundary:{status:'exhausted'}}); },
    h => { h.entitiesByKey.a.status = 'unknown'; },
    h => { h.entitiesByKey.a.turnId = {}; },
  ];
  for (const mutate of mutations) {
    const candidate = canonicalState();
    candidate.turns = state.turns; // A seemingly retryable fallback must not bypass validation.
    mutate(candidate.turnHistory.history);
    await rejectsBeforeSend(candidate);
  }
});

test('malformed legacy turns fail closed', async () => {
  for (const turns of [undefined, null, {}, [], [null], [{}],
    [{...state.turns[0],turnId:' '}], [{...state.turns[0],status:'unknown'}]]) {
    await rejectsBeforeSend({...state,turns});
  }
});

test('canonical history retains the latest actual turn', async () => {
  const canonical = canonicalState();
  canonical.turnHistory.history.islands[0].entries.push({key:'second',value:'b'});
  canonical.turnHistory.history.entitiesByKey.b = {turnId:'new',status:'inProgress'};
  assert.equal(turnsFromState(canonical).at(-1).status,'inProgress');
  const bridge = {request:async () => assert.fail('unexpected send')};
  await assert.rejects(continueIfFailed(bridge,'owner','target-chat','failed-turn','id',canonical), /STALE/);
});

test('partial older canonical history with known tail supports idle retry', async () => {
  const canonical = canonicalState();
  assert.equal(summarize(canonical).runtime.type,'idle');
  assert.equal(summarize(canonical).turnCount,1);
  let calls = 0;
  const bridge = {request:async () => {calls++; return {result:{result:{turn:{id:'new-turn'}}}};}};
  const result = await continueIfFailed(bridge,'owner','target-chat','failed-turn','id',canonical);
  assert.equal(result.turnId,'new-turn');
  assert.equal(calls,1);
});

test('canonical completed idle snapshot shape is accepted without submission', async () => {
  const canonical = canonicalState();
  canonical.turnHistory.history.entitiesByKey.a.status = 'completed';
  assert.equal(summarize(canonical).latest[0].status,'completed');
  const bridge = {request:async () => assert.fail('unexpected send')};
  await assert.rejects(continueIfFailed(bridge,'owner','target-chat','failed-turn','id',canonical), /STALE/);
});

test('unconfirmed response fails closed with submitted flag', async () => {
  const bridge = {request:async () => ({result:{}})};
  await assert.rejects(continueIfFailed(bridge,'owner','target-chat','failed-turn','id',state), /outcome unknown/);
  assert.equal(bridge.submitted,true);
});

test('invalid or reused returned turn IDs preserve the unknown submitted outcome', async () => {
  for (const id of [undefined, null, '', '   ', 7, {}, [], 'failed-turn']) {
    let calls = 0;
    const bridge = {request:async () => {calls++; return {result:{result:{turn:{id}}}};}};
    await assert.rejects(continueIfFailed(bridge,'owner','target-chat','failed-turn','id',state),
      e => unsupported.test(e.message) && /outcome unknown/.test(e.message));
    assert.equal(calls,1);
    assert.equal(bridge.submitted,true);
  }
});

function responseBridge(mutate = () => {}) {
  const bridge = new DesktopBridge('unused-test-pipe');
  bridge.write = request => {
    const reply = {type:'response',requestId:request.requestId,method:request.method,
      resultType:'success',handledByClientId:'owner',result:{}};
    mutate(reply);
    bridge.receive(reply);
  };
  return bridge;
}

test('observed response envelope works without a response version', async () => {
  const bridge = responseBridge();
  const response = await bridge.request('thread-owner-discovery',{},1,'owner');
  assert.equal(response.handledByClientId,'owner');
  assert.equal(Object.hasOwn(response,'version'),false);
  assert.equal(bridge.pending.size,0);
});

test('response method, owner, and result type mismatches are UNSUPPORTED', async () => {
  const mutations = [
    r => { delete r.method; },
    r => { r.method = 'different-method'; },
    r => { delete r.handledByClientId; },
    r => { r.handledByClientId = ''; },
    r => { r.handledByClientId = {}; },
    r => { r.handledByClientId = 'different-owner'; },
    r => { delete r.resultType; },
    r => { r.resultType = 'unknown'; },
  ];
  for (const mutate of mutations) {
    const bridge = responseBridge(mutate);
    await assert.rejects(bridge.request('thread-follower-start-turn',{},2,'owner'),
      e => unsupported.test(e.message));
    assert.equal(bridge.pending.size,0);
  }
});

test('routing errors do not require success-only response fields', async () => {
  const bridge = responseBridge(r => {
    r.resultType = 'error'; r.error = 'no-client-found';
    delete r.method; delete r.handledByClientId;
  });
  await assert.rejects(bridge.request('thread-owner-discovery',{},1), /thread-owner-discovery: no-client-found/);
});

test('unknown snapshot protocol version is UNSUPPORTED', async () => {
  for (const version of [undefined, 10, 12, '11']) {
    const bridge = new DesktopBridge('unused-test-pipe');
    bridge.follow = () => bridge.receive({type:'broadcast',method:'thread-stream-state-changed',
      sourceClientId:'owner',version,params:{conversationId:'target-chat',hostId:'local',
        change:{type:'snapshot',conversationState:state}}});
    await assert.rejects(bridge.snapshot('target-chat','owner'), e => unsupported.test(e.message));
    assert.equal(bridge.listeners.size,0);
  }
});

test('error match does not broaden generic disconnections', () => {
  assert.equal(isUnavailable({message:'stream disconnected before completion'}),false);
  assert.equal(isUnavailable({message:'HTTP 503 Service Unavailable'}),true);
});
