'use strict';
// Read-only by default. Only --continue starts a new turn.
const net = require('node:net');
const crypto = require('node:crypto');
const PIPE = String.raw`\\.\pipe\codex-ipc`;
const isObject = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const isId = value => typeof value === 'string' && value.trim().length > 0;
function unsupported(detail) { throw new Error('UNSUPPORTED: ' + detail); }

class DesktopBridge {
  constructor(pipe = PIPE) {
    this.pipe = pipe; this.clientId = 'initializing-client';
    this.pending = new Map(); this.listeners = new Set(); this.buffer = Buffer.alloc(0);
  }
  async connect() {
    this.socket = net.createConnection(this.pipe);
    this.socket.on('data', b => {
      this.buffer = Buffer.concat([this.buffer, b]);
      while (this.buffer.length >= 4) {
        const n = this.buffer.readUInt32LE(0);
        if (!n || n > 268435456) { this.socket.destroy(new Error('Invalid IPC frame')); return; }
        if (this.buffer.length < n + 4) return;
        try {
          const message = JSON.parse(this.buffer.subarray(4, n + 4).toString('utf8'));
          this.buffer = this.buffer.subarray(n + 4); this.receive(message);
        } catch (e) { this.socket.destroy(new Error('Invalid IPC JSON: ' + e.message)); return; }
      }
    });
    this.socket.on('error', e => this.fail(e));
    this.socket.on('close', () => this.fail(new Error('Desktop IPC disconnected')));
    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => { this.socket.destroy(); reject(new Error('Desktop IPC connect timeout')); }, 5000);
      this.socket.once('connect', () => { clearTimeout(timer); resolve(); });
      this.socket.once('error', e => { clearTimeout(timer); reject(e); });
    });
    const response = await this.request('initialize', {clientType: 'codex-auto-retry-kitchen'}, 0);
    if (!isId(response.result?.clientId)) unsupported('missing initialization client ID');
    this.clientId = response.result.clientId;
  }
  fail(error) { for (const p of this.pending.values()) p.reject(error); this.pending.clear(); }
  write(message) {
    const body = Buffer.from(JSON.stringify(message), 'utf8'), header = Buffer.alloc(4);
    header.writeUInt32LE(body.length); this.socket.write(Buffer.concat([header, body]));
  }
  receive(message) {
    if (!isObject(message)) unsupported('malformed IPC message');
    if (message.type === 'client-discovery-request') {
      this.write({type:'client-discovery-response', requestId:message.requestId, response:{canHandle:false}});
    } else if (message.type === 'response') {
      const pending = this.pending.get(message.requestId);
      if (pending) { this.pending.delete(message.requestId); pending.resolve(message); }
    } else if (message.type === 'request') {
      this.write({type:'response', requestId:message.requestId, resultType:'error', error:'no-handler-for-request'});
    } else { for (const listener of this.listeners) listener(message); }
  }
  async request(method, params, version, targetClientId, timeoutMs = 10000) {
    const requestId = crypto.randomUUID();
    let timer;
    try {
      const reply = await new Promise((resolve, reject) => {
        timer = setTimeout(() => { this.pending.delete(requestId); reject(new Error(`${method}: timeout; outcome may be unknown`)); }, timeoutMs + 1000);
        this.pending.set(requestId, {resolve, reject});
        this.write({type:'request', requestId, sourceClientId:this.clientId, version, method, params, targetClientId, timeoutMs});
      });
      if (!isObject(reply) || reply.type !== 'response' || reply.requestId !== requestId ||
          !['success', 'error'].includes(reply.resultType)) unsupported('malformed response envelope');
      // Live initialize/discovery replies echo method and handledByClientId, but no version.
      if (reply.resultType === 'success' || Object.hasOwn(reply, 'method')) {
        if (reply.method !== method) unsupported('response method mismatch');
      }
      if (reply.resultType !== 'success') throw new Error(`${method}: ${reply.error}`);
      if (!isId(reply.handledByClientId) || (targetClientId && reply.handledByClientId !== targetClientId)) {
        unsupported('response owner missing or mismatched');
      }
      return reply;
    } finally { clearTimeout(timer); this.pending.delete(requestId); }
  }
  follow(threadId, owner, following) {
    this.write({type:'broadcast', method:'thread-stream-following-changed', sourceClientId:this.clientId,
      targetClientIds:[owner], version:1, params:{conversationId:threadId, hostId:'local', following}});
  }
  async snapshot(threadId, owner) {
    let timer, listener;
    try {
      return await new Promise((resolve, reject) => {
        timer = setTimeout(() => reject(new Error('Desktop state snapshot timeout')), 8000);
        listener = m => {
          if (m.type === 'broadcast' && m.method === 'thread-stream-state-changed' && m.sourceClientId === owner &&
              m.params?.conversationId === threadId && m.params?.hostId === 'local') {
            if (m.version !== 11) { reject(new Error('UNSUPPORTED: snapshot protocol version')); return; }
            if (m.params.change?.type === 'snapshot') resolve(m.params.change.conversationState);
          }
        };
        this.listeners.add(listener); this.follow(threadId, owner, true);
      });
    } finally { clearTimeout(timer); this.listeners.delete(listener); }
  }
  close() { this.socket?.destroy(); }
}

function turnsFromState(state) {
  if (!isObject(state)) unsupported('malformed conversation state');
  const history = state.turnHistory;
  let turns;
  if (Object.hasOwn(state, 'turnHistory')) {
    if (!isObject(history) || history.kind !== 'canonical') unsupported('unknown history kind');
    const h = history.history;
    if (!isObject(h) || typeof h.isComplete !== 'boolean' || !Array.isArray(h.islands) ||
        !h.islands.length || !isObject(h.entitiesByKey)) unsupported('malformed canonical history');
    // Partial older history is supported only when the latest boundary is known.
    if (h.islands.at(-1)?.newerBoundary?.status !== 'exhausted') unsupported('canonical history tail is not complete');
    turns = [];
    for (const island of h.islands) {
      if (!isObject(island) || !Array.isArray(island.entries) || !island.entries.length) {
        unsupported('missing canonical history entries');
      }
      for (const entry of island.entries) {
        if (!isObject(entry) || !isId(entry.value) || !Object.hasOwn(h.entitiesByKey, entry.value)) {
          unsupported('unresolved canonical history entity');
        }
        turns.push(h.entitiesByKey[entry.value]);
      }
    }
  } else {
    turns = state.turns;
  }
  if (!Array.isArray(turns) || !turns.length || turns.some(turn =>
      !isObject(turn) || !isId(turn.turnId) || !['failed', 'interrupted', 'inProgress', 'completed'].includes(turn.status))) {
    unsupported('malformed or unknown turn history');
  }
  return turns;
}
function runtimeType(state) {
  if (!isObject(state) || !isId(state.id) || !isObject(state.threadRuntimeStatus) ||
      !['idle', 'active', 'systemError'].includes(state.threadRuntimeStatus.type)) unsupported('missing or unknown runtime state');
  return state.threadRuntimeStatus.type;
}
function summarize(state) {
  runtimeType(state);
  const turns = turnsFromState(state);
  return {id:state.id, title:state.title, runtime:state.threadRuntimeStatus, resumeState:state.resumeState,
    keys:Object.keys(state), turnCount:turns.length,
    latest:turns.slice(-2).map(t => ({turnId:t.turnId, status:t.status, error:t.error, keys:Object.keys(t)}))};
}
async function main() {
  const [mode, threadId, expectedTurnId, messageId] = process.argv.slice(2);
  if (!['--connect','--probe','--continue'].includes(mode) || (mode !== '--connect' && !threadId)) throw new Error('Usage: --connect, --probe THREAD, or --continue THREAD FAILED_TURN MESSAGE_ID');
  const bridge = new DesktopBridge(); let owner;
  try {
    await bridge.connect();
    if (mode === '--connect') { console.log(JSON.stringify({ok:true, connected:true, sent:false})); return; }
    owner = (await bridge.request('thread-owner-discovery', {hostId:'local', conversationId:threadId}, 1)).handledByClientId;
    if (!isId(owner)) unsupported('missing conversation owner');
    const state = await bridge.snapshot(threadId, owner);
    if (mode === '--probe') { console.log(JSON.stringify({ok:true, owner, state:summarize(state)})); return; }
    if (!expectedTurnId || !messageId) throw new Error('Missing failed turn or message ID');
    console.log(JSON.stringify(await continueIfFailed(bridge, owner, threadId, expectedTurnId, messageId, state)));
  } catch (e) { e.submitted = !!bridge.submitted; throw e;
  } finally { if (owner) { try { bridge.follow(threadId, owner, false); } catch {} } bridge.close(); }
}

function isUnavailable(error) {
  if (!error || typeof error !== 'object') return false;
  const code = error.codexErrorInfo;
  if (code === 'serverOverloaded') return true;
  if (code && typeof code === 'object' && Object.values(code).some(v => v?.httpStatusCode === 503)) return true;
  return /服务(?:暂时)?不可用|service[ _-](?:temporarily[ _-])?unavailable|servers? (?:are )?(?:currently )?overloaded|selected model is at capacity|\b503\b/i.test([error.message,error.additionalDetails].filter(Boolean).join(' '));
}
async function continueIfFailed(bridge, owner, threadId, expectedTurnId, messageId, state) {
  if (![owner, threadId, expectedTurnId, messageId].every(isId)) unsupported('invalid submission identifiers');
  const runtime = runtimeType(state);
  const turns = turnsFromState(state), latest = turns.at(-1);
  if (state.id !== threadId || !['idle', 'systemError'].includes(runtime) || latest?.turnId !== expectedTurnId ||
      !['failed','interrupted'].includes(latest?.status) || !isUnavailable(latest.error)) {
    throw new Error('STALE: conversation changed, is running, or no longer has the expected service error');
  }
  bridge.submitted = true;
  const response = await bridge.request('thread-follower-start-turn', {conversationId:threadId, turnStart:{
    request:{threadId, input:[], clientUserMessageId:messageId},
    context:{inheritThreadSettings:true}}}, 2, owner, 30000);
  const newTurnId = response?.result?.result?.turn?.id;
  if (!isId(newTurnId) || newTurnId === expectedTurnId) {
    throw new Error('UNSUPPORTED: send response did not confirm a new turn; outcome unknown');
  }
  return {ok:true, sent:true, threadId, clientUserMessageId:messageId, turnId:newTurnId};
}

module.exports = {DesktopBridge, turnsFromState, isUnavailable, continueIfFailed, summarize};
if (require.main === module) main().catch(e => { console.log(JSON.stringify({ok:false,error:e.message,submitted:!!e.submitted})); process.exitCode = 1; });
