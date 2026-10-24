"""Read local Codex history; automatically resume verified service interruptions."""
from __future__ import annotations
import dataclasses
from contextlib import closing
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import threading
import time
import uuid
from app_config import ROOT, DATA_DIR, codex_home

HERE = ROOT
HOME = codex_home()
UUID_PATTERN = re.compile(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', re.I)
UNAVAILABLE = re.compile(r'服务(?:暂时)?不可用|service[ _-](?:temporarily[ _-])?unavailable|servers? (?:are )?(?:currently )?overloaded|selected model is at capacity|\b503\b', re.I)

def is_unavailable(error):
    if not isinstance(error, dict):
        return False
    code = error.get('codexErrorInfo')
    if code == 'serverOverloaded':
        return True
    if isinstance(code, dict) and any(isinstance(v, dict) and v.get('httpStatusCode') == 503 for v in code.values()):
        return True
    return bool(UNAVAILABLE.search(' '.join(str(error.get(k) or '') for k in ('message', 'additionalDetails'))))

def readonly_db(path):
    conn = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=2)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA query_only=ON')
    return conn

@dataclasses.dataclass(frozen=True)
class Failure:
    thread_id: str
    turn_id: str
    title: str
    timestamp: float
    error: str

    @property
    def key(self):
        return self.thread_id + ':' + self.turn_id

class Scanner:
    def __init__(self, home=HOME):
        self.home = Path(home)
    def scan(self):
        with closing(readonly_db(self.home / 'state_5.sqlite')) as state:
            columns = {r['name'] for r in state.execute('PRAGMA table_info(threads)')}
            if not {'id', 'rollout_path', 'source', 'archived'} <= columns:
                raise RuntimeError('Unsupported Codex state schema; run doctor.py and report the version')
            titles = ["NULLIF(name,'')"] if 'name' in columns else []
            if 'title' in columns:
                titles.append("NULLIF(title,'')")
            titles.append('id')
            title_sql = 'COALESCE(' + ','.join(titles) + ')' if len(titles) > 1 else 'id'
            rows = state.execute(f"SELECT id, {title_sql} AS title, rollout_path FROM threads WHERE archived = 0 AND lower(COALESCE(source,'')) NOT LIKE '%subagent%'").fetchall()
        history_path = self.home / 'thread_history_1.sqlite'
        history = readonly_db(history_path)  # Required: never infer terminal state from rollout text.
        found = []
        try:
            for row in rows:
                aliases = UUID_PATTERN.findall(Path(row['rollout_path'] or '').name)
                alias = aliases[-1] if aliases else row['id']
                turn = history.execute('SELECT turn_id, status, error_json, started_at, completed_at FROM thread_turns WHERE thread_id IN (?,?) ORDER BY started_at DESC, rollout_ordinal DESC LIMIT 1', (row['id'], alias)).fetchone()
                if turn:
                    if turn['status'] not in ('failed', 'interrupted'):
                        continue
                    try:
                        error = json.loads(turn['error_json'] or 'null')
                    except ValueError:
                        continue
                    if is_unavailable(error):
                        found.append(Failure(row['id'], turn['turn_id'], row['title'], turn['completed_at'] or turn['started_at'] or 0, str(error.get('message', '服务不可用'))))
        finally:
            if history:
                history.close()
        return sorted(found, key=lambda f: f.timestamp, reverse=True)

class Journal:
    """A sending entry is durable before IPC; ambiguous results never auto-retry."""
    def __init__(self, path=DATA_DIR / 'actions.jsonl', clock=time.time, tz=None):
        self.path = Path(path)
        self.clock = clock
        self.tz = tz  # None uses the OS local timezone, including historical DST.
        self.lock = threading.Lock()
        self.states = {}
        self.sent_keys = set()
        self.records = []
        if self.path.exists():
            for line in self.path.read_text(encoding='utf-8').splitlines():
                try:
                    item = json.loads(line)
                    self.states[item['key']] = item['status']
                    self.records.append(item)
                    if item['status'] == 'sent':
                        self.sent_keys.add(item['key'])
                except (ValueError, KeyError):
                    continue

    def blocked(self, failure):
        with self.lock:
            return failure.key in self.sent_keys or self.states.get(failure.key) in ('sending', 'sent', 'unknown', 'stale', 'baseline')

    def record(self, failure, status, message_id=None):
        item = {'at': self.clock(), 'key': failure.key, 'status': status, 'message_id': message_id}
        with self.lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open('a', encoding='utf-8') as f:
                f.write(json.dumps(item, ensure_ascii=False) + '\n')
                f.flush()
                os.fsync(f.fileno())
            self.states[failure.key] = status
            self.records.append(item)
            if status == 'sent':
                self.sent_keys.add(failure.key)

    def initialize_baseline(self, scanner):
        """Enable only after old failures are durably excluded for this Codex home."""
        marker = self.path.with_name('baseline.json')
        identity = os.path.normcase(str(scanner.home.resolve()))
        if marker.exists():
            saved = json.loads(marker.read_text(encoding='utf-8'))
            if saved != {'version': 1, 'codex_home': identity}:
                raise RuntimeError('Runtime directory belongs to a different Codex home; use a separate runtime directory')
            return
        failures = scanner.scan()  # A read error leaves automatic sending disabled.
        for failure in failures:
            if not self.blocked(failure):
                self.record(failure, 'baseline')
        marker.parent.mkdir(parents=True, exist_ok=True)
        temporary = marker.with_suffix('.tmp')
        with temporary.open('w', encoding='utf-8') as stream:
            json.dump({'version': 1, 'codex_home': identity}, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, marker)
        logging.info('Initial baseline saved; skipped %d existing failures', len(failures))

    def daily_count(self, at=None):
        day = datetime.fromtimestamp(self.clock() if at is None else at, self.tz).date()
        with self.lock:
            return len({r.get('message_id') or r['key'] for r in self.records
                        if r.get('status') == 'sent' and datetime.fromtimestamp(r['at'], self.tz).date() == day})

    def last_sent(self, thread_id):
        with self.lock:
            return max((r['at'] for r in self.records if r.get('status') == 'sent' and r['key'].startswith(thread_id + ':')), default=0)

class Sender:
    def __init__(self, scanner, journal, node='node', invoke=None, opener=None):
        self.scanner, self.journal, self.node = scanner, journal, node
        self.invoke = invoke or self._invoke
        self.opener = opener or (lambda thread_id: os.startfile('codex://threads/' + thread_id))
        self.lock = threading.Lock()

    def _invoke(self, *args):
        result = subprocess.run([self.node, str(HERE / 'desktop_bridge.cjs'), *args], capture_output=True, text=True, encoding='utf-8', timeout=50, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        for line in reversed(result.stdout.splitlines()):
            try:
                return json.loads(line)
            except ValueError:
                continue
        raise RuntimeError((result.stderr or '桌面连接未返回有效结果')[-500:])

    @staticmethod
    def state_supported(probe):
        state = probe.get('state')
        if not isinstance(state, dict) or not isinstance(state.get('runtime'), dict):
            return False
        if state['runtime'].get('type') not in ('idle', 'active', 'systemError'):
            return False
        latest = state.get('latest')
        return (isinstance(latest, list) and all(isinstance(t, dict)
                and isinstance(t.get('turnId'), str) and t['turnId']
                and isinstance(t.get('status'), str) for t in latest))

    @staticmethod
    def state_matches(failure, probe):
        if not Sender.state_supported(probe):
            return False
        state = probe['state']
        latest = (state['latest'] or [{}])[-1]
        return (state.get('id') == failure.thread_id and state['runtime']['type'] in ('idle', 'systemError')
                and latest.get('turnId') == failure.turn_id and latest.get('status') in ('failed', 'interrupted')
                and is_unavailable(latest.get('error')))

    def send(self, failure):
        if not self.lock.acquire(blocking=False):
            return 'busy', '正在发送，请稍候'
        try:
            if self.journal.blocked(failure):
                return 'stale', '这次中断已处理'
            if not any(f.key == failure.key for f in self.scanner.scan()):
                self.journal.record(failure, 'stale')
                return 'stale', '对话已恢复，已跳过'
            probe = self.invoke('--probe', failure.thread_id)
            if not probe.get('ok') and 'no-client-found' in probe.get('error', ''):
                # Open only the exact interrupted chat if no owner is connected.
                self.opener(failure.thread_id)
                for _ in range(3):
                    time.sleep(1)
                    probe = self.invoke('--probe', failure.thread_id)
                    if probe.get('ok'):
                        break
            if not probe.get('ok'):
                logging.warning('Preflight failed for %s: %s', failure.thread_id, probe.get('error'))
                return 'error', '连接失败，稍后自动重试'
            if not self.state_supported(probe):
                logging.warning('Unsupported desktop state; no message submitted')
                return 'error', 'Unsupported desktop state; no message submitted'
            if not self.state_matches(failure, probe):
                self.journal.record(failure, 'stale')
                return 'stale', '对话状态已变化，已跳过'
            message_id = str(uuid.uuid4())
            self.journal.record(failure, 'sending', message_id)
            try:
                result = self.invoke('--continue', failure.thread_id, failure.turn_id, message_id)
            except Exception:
                self.journal.record(failure, 'unknown', message_id)
                logging.exception('Send outcome unknown for %s', failure.thread_id)
                return 'unknown', '发送结果未确认，请打开该对话检查'
            if (result.get('ok') is True and result.get('sent') is True
                    and result.get('threadId') == failure.thread_id
                    and result.get('clientUserMessageId') == message_id
                    and isinstance(result.get('turnId'), str) and result['turnId'].strip()
                    and result['turnId'] != failure.turn_id):
                self.journal.record(failure, 'sent', message_id)
                return 'sent', '已直接启动该对话的新轮次'
            if not result.get('submitted', True):
                stale = 'STALE:' in result.get('error', '')
                self.journal.record(failure, 'stale' if stale else 'retryable', message_id)
                return ('stale', '对话状态已变化，已跳过') if stale else ('error', '未发送；打开对应对话后重试')
            self.journal.record(failure, 'unknown', message_id)
            logging.warning('Send outcome unknown for %s: %s', failure.thread_id, result.get('error'))
            return 'unknown', '发送结果未确认，请打开该对话检查'
        except Exception:
            logging.exception('Retry failed for %s', failure.thread_id)
            return 'error', '读取失败，请查看运行日志后重试'
        finally:
            self.lock.release()

class LiveFilter:
    """Use desktop state to drop stale history candidates before showing them."""
    def __init__(self, invoke, ttl=5):
        self.invoke, self.ttl, self.cache = invoke, ttl, {}

    def filter(self, failures):
        visible = []
        for failure in failures:
            cached = self.cache.get(failure.key)
            now = time.monotonic()
            if cached and now - cached[0] < self.ttl:
                keep = cached[1]
            else:
                try:
                    probe = self.invoke('--probe', failure.thread_id)
                    # Unopened chats may have no owner. History still detects them;
                    # clicking opens and verifies the exact thread before sending.
                    keep = not probe.get('ok') or Sender.state_matches(failure, probe)
                except Exception:
                    keep = True
                self.cache[failure.key] = (now, keep)
            if keep:
                visible.append(failure)
        keys = {f.key for f in failures}
        self.cache = {k: v for k, v in self.cache.items() if k in keys}
        return visible

class AutoRetry:
    """One confirmed send per failed turn; per-chat spacing persists on restart."""
    def __init__(self, scanner, journal, sender, notify, stopped=lambda: False, clock=time.time, interval=30):
        self.scanner, self.journal, self.sender = scanner, journal, sender
        self.notify, self.stopped, self.clock, self.interval = notify, stopped, clock, interval
        self.retry_after = {}
        self.errors = {}

    def tick(self):
        failures = self.scanner.scan()
        active = {f.key for f in failures}
        self.retry_after = {k: v for k, v in self.retry_after.items() if k in active}
        self.errors = {k: v for k, v in self.errors.items() if k in active}
        for failure in reversed(failures):
            if self.stopped():
                return
            now = self.clock()
            if self.journal.blocked(failure) or now < self.retry_after.get(failure.key, 0):
                continue
            if now < self.journal.last_sent(failure.thread_id) + self.interval:
                continue
            status, message = self.sender.send(failure)
            logging.info('Automatic retry thread=%s turn=%s status=%s', failure.thread_id, failure.turn_id, status)
            if status == 'sent':
                self.notify({'kind': 'sent', 'count': self.journal.daily_count(), 'thread_id': failure.thread_id, 'title': failure.title})
            elif status == 'unknown':
                self.notify({'kind': 'unknown', 'thread_id': failure.thread_id, 'title': failure.title})
            elif status in ('error', 'busy'):
                attempts = self.errors.get(failure.key, 0) + 1
                self.errors[failure.key] = attempts
                self.retry_after[failure.key] = self.clock() + min(60, 5 * 2 ** min(attempts-1, 4))
