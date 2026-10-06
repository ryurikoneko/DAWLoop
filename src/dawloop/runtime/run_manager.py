"""后台拥有既有 FAST 调用；MCP 重发和服务重启都不能重放写事务。"""

import asyncio
import copy
from contextlib import closing, contextmanager
from dataclasses import dataclass
import hashlib
import inspect
import json
import math
from pathlib import Path
import re
import sqlite3
import sys
import time
from uuid import uuid4

from .fast_music import FastMusicResult, FastMusicRuntime, _plan
from .human_reports import HumanReport, HumanReportStore
from .native_write import NativeWriteJournal


POLICY = dict(add_only=True, max_notes=16, retry=0, fallback_after_dispatch=0)
SLICE_HASH = '7b7b6989b579350abfa7d50890c33e4f5bc4a9514c07b5132ff6b7afae048f3a'


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


@dataclass(frozen=True)
class RunContext:
    operation_id: str
    run_id: str
    session_id: str
    directory: Path
    ledger_directory: Path
    settings_dir: Path
    expected_build: str
    readiness: dict


class RunManager:
    def __init__(self, directory, *, settings_dir, expected_build, runtime_factory=None,
                 readiness=None, experimental_authorized=False, allowed_target=None):
        if settings_dir is None or not Path(settings_dir).is_dir():
            raise ValueError('EXPLICIT_CONTROLLER_SETTINGS_REQUIRED')
        if type(expected_build) is not str or not expected_build.strip():
            raise ValueError('EXPECTED_CONTROLLER_BUILD_REQUIRED')
        if runtime_factory is not None and (not callable(runtime_factory)
                or inspect.iscoroutinefunction(runtime_factory)
                or inspect.iscoroutinefunction(getattr(runtime_factory, '__call__', None))):
            raise ValueError('SYNCHRONOUS_RUNTIME_FACTORY_REQUIRED')
        if readiness is not None and not callable(readiness):
            raise ValueError('READINESS_PROVIDER_REQUIRED')
        self.root = Path(directory).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.settings_dir = Path(settings_dir).resolve()
        self.expected_build = expected_build
        self.factory = runtime_factory
        self.readiness = readiness
        self.authorized = experimental_authorized is True
        self.allowed_target = copy.deepcopy(allowed_target)
        self.tasks = {}
        self.runtimes = {}
        self.closed = False
        self.path = self.root / 'runs.sqlite3'
        self.lock_file = (self.root / 'manager.lock').open('a+b')
        try:
            self._lock(True)
        except OSError as error:
            self.lock_file.close()
            raise ValueError('RUN_MANAGER_ALREADY_RUNNING') from error
        try:
            with self._db() as db:
                db.execute('''CREATE TABLE IF NOT EXISTS runs (
                    operation_id TEXT PRIMARY KEY, run_id TEXT UNIQUE NOT NULL,
                    session_id TEXT NOT NULL, fingerprint TEXT NOT NULL,
                    state TEXT NOT NULL, terminal INTEGER NOT NULL DEFAULT 0,
                    result_hash TEXT)''')
            self._recover()
        except BaseException:
            self._lock(False)
            self.lock_file.close()
            raise

    def _lock(self, acquire):
        self.lock_file.seek(0)
        if sys.platform == 'win32':
            import msvcrt
            if acquire and self.lock_file.read(1) == b'':
                self.lock_file.write(b'0')
                self.lock_file.flush()
            self.lock_file.seek(0)
            msvcrt.locking(self.lock_file.fileno(), msvcrt.LK_NBLCK if acquire else msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB if acquire else fcntl.LOCK_UN)

    @contextmanager
    def _db(self):
        with closing(sqlite3.connect(self.path, timeout=2)) as db:
            db.row_factory = sqlite3.Row
            with db:
                yield db

    def _row(self, run_id):
        with self._db() as db:
            row = db.execute('SELECT * FROM runs WHERE run_id=?', (run_id,)).fetchone()
        if row is None:
            raise ValueError('RUN_NOT_FOUND')
        return dict(row)

    def _recover(self):
        with self._db() as db:
            rows = db.execute('SELECT * FROM runs WHERE terminal=0').fetchall()
            for row in rows:
                folder = self.root / row['run_id']
                store = HumanReportStore(folder)
                original = folder / 'fast_music_result.json'
                if original.exists():
                    data = original.read_bytes()
                    result = json.loads(data)
                    store.finalize(data)
                    db.execute('UPDATE runs SET state=?,terminal=1,result_hash=? WHERE run_id=?',
                        (result['state'], hashlib.sha256(data).hexdigest(), row['run_id']))
                else:
                    # 进程消失不是宿主取消；没有原结果时只隔离，绝不自动继续。
                    store.end_accept()
                    db.execute("UPDATE runs SET state='STOPPED_ORPHANED_UNKNOWN',terminal=1 WHERE run_id=?",
                               (row['run_id'],))

    async def components(self, *, ignore_run=None):
        from dawloop.adapters.gopher_native.write_backend import CERTIFIED_CATALOG, CERTIFIED_VERSION
        snapshot = {}
        provider_error = None
        if self.readiness is not None:
            try:
                snapshot = copy.deepcopy(await self.readiness())
                if not isinstance(snapshot, dict):
                    raise ValueError('READINESS_INVALID')
            except Exception:
                snapshot, provider_error = {}, 'READINESS_UNAVAILABLE'
        controller = snapshot.get('controller', {})
        gopher = snapshot.get('gopher', {})
        observation = snapshot.get('observation', {})
        if not all(isinstance(v, dict) for v in (controller, gopher, observation)):
            controller, gopher, observation = {}, {}, {}
            provider_error = 'READINESS_INVALID'
        c = {k: controller.get(k) for k in ('connected', 'build_id', 'session_generation', 'project_generation')}
        c.update({k: controller.get(k) for k in ('project_title', 'project_title_status')})
        g = {k: gopher.get(k) for k in ('discovered', 'bridge_connected', 'host_generation',
            'target_id', 'bridge_epoch', 'catalog_hash', 'fl_version', 'bootstrap_required', 'poisoned')}
        o = {k: observation.get(k) for k in ('ready', 'request_generation')}
        timestamp = snapshot.get('observed_at')
        fresh = (type(timestamp) in (int, float) and math.isfinite(timestamp)
                 and 0 <= time.time() - timestamp <= 60)
        text = lambda value: type(value) is str and bool(value.strip())
        controller_ok = (c['connected'] is True and c['build_id'] == self.expected_build
            and all(text(c[k]) for k in ('session_generation', 'project_generation')))
        gopher_ok = (g['discovered'] is True and g['bridge_connected'] is True
            and g['bootstrap_required'] is False and g['poisoned'] is False
            and all(text(g[k]) for k in ('host_generation', 'target_id', 'bridge_epoch'))
            and g['catalog_hash'] == CERTIFIED_CATALOG and g['fl_version'] == CERTIFIED_VERSION)
        observation_ok = o['ready'] is True and text(o['request_generation'])
        consumed = None
        if text(g['host_generation']):
            host_key = hashlib.sha256(g['host_generation'].encode('utf-8')).hexdigest()
            consumed = int((self.root / 'dispatch_intents' / ('host_' + host_key + '.json')).exists())
        with self._db() as db:
            active = [r[0] for r in db.execute('SELECT run_id FROM runs WHERE terminal=0')
                      if r[0] != ignore_run]
            unresolved = db.execute("SELECT 1 FROM runs WHERE terminal=1 AND state IN "
                "('STOPPED_AFTER_DISPATCH_UNKNOWN','STOPPED_ORPHANED_UNKNOWN',"
                "'STOPPED_EVIDENCE_STORAGE_ERROR') LIMIT 1").fetchone() is not None
        blockers = []
        for ok, reason in ((not self.closed, 'RUN_MANAGER_CLOSED'),
                (self.factory is not None, 'LIVE_RUNTIME_NOT_CONFIGURED'),
                (self.authorized, 'EXPERIMENTAL_AUTHORIZATION_REQUIRED'),
                (self.allowed_target is not None, 'WRITE_SCOPE_UNCONFIGURED'),
                (fresh, 'READINESS_STALE_OR_UNKNOWN'), (controller_ok, 'CONTROLLER_NOT_READY'),
                (gopher_ok, 'GOPHER_BOOTSTRAP_REQUIRED' if g['bootstrap_required'] is True else 'GOPHER_NOT_READY'),
                (observation_ok, 'OBSERVATION_NOT_READY'),
                (snapshot.get('disposable_session') is True, 'DISPOSABLE_SESSION_REQUIRED'),
                (not unresolved, 'UNRESOLVED_PRIOR_DISPATCH'),
                (consumed == 0, 'HOST_DISPATCH_BUDGET_UNAVAILABLE'), (not active, 'RUN_ACTIVE')):
            if not ok:
                blockers.append(reason)
        if provider_error:
            blockers.append(provider_error)
        blockers.extend(snapshot.get('reasons', []) if isinstance(snapshot.get('reasons'), list) else [])
        ready = not blockers
        return dict(controller=c, gopher=g, observation=o,
            dispatch=dict(budget_total=1, budget_consumed=consumed, dispatch_allowed=ready,
                          unresolved_prior_dispatch=unresolved),
            runtime='FAST_READY' if ready else 'NOT_READY',
            blockers=blockers, reasons=list(blockers), observed_at=timestamp, evidence_fresh=fresh,
            scope='DISPOSABLE_FIXED_16_NOTE_SLICE')

    @staticmethod
    def _binding(components):
        # 描述标题不参与代次绑定，空值或标题改变不能代替工程代次判断。
        controller = {k: components['controller'][k] for k in
                      ('connected', 'build_id', 'session_generation', 'project_generation')}
        return (controller, components['gopher'], components['observation'])

    async def create(self, operation_id, target, musical_plan):
        if self.closed:
            raise ValueError('RUN_MANAGER_CLOSED')
        if type(operation_id) is not str or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', operation_id):
            raise ValueError('OPERATION_ID_REQUIRED')
        target, musical_plan = copy.deepcopy(target), copy.deepcopy(musical_plan)
        _, rendered = _plan(target, musical_plan, operation_id, POLICY)
        payload = _json(dict(target=target, musical_plan=musical_plan))
        fingerprint = hashlib.sha256(payload.encode('utf-8')).hexdigest()
        with self._db() as db:
            existing = db.execute('SELECT * FROM runs WHERE operation_id=?', (operation_id,)).fetchone()
        if existing is not None:
            if existing['fingerprint'] != fingerprint:
                raise ValueError('OPERATION_ID_CONFLICT')
            return self._handle(dict(existing), reused=True)
        if rendered.sha256 != SLICE_HASH or (self.allowed_target is not None and target != self.allowed_target):
            raise ValueError('CERTIFIED_MUSIC_SLICE_REQUIRED')
        components = await self.components()
        if components['runtime'] != 'FAST_READY':
            raise ValueError('FAST_NOT_READY:' + ','.join(components['blockers']))
        run_id, session_id = uuid4().hex, uuid4().hex
        context = RunContext(operation_id, run_id, session_id, self.root / run_id,
            self.root / 'dispatch_intents', self.settings_dir, self.expected_build, components)
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            existing = db.execute('SELECT * FROM runs WHERE operation_id=?', (operation_id,)).fetchone()
            if existing is not None:
                if existing['fingerprint'] != fingerprint:
                    raise ValueError('OPERATION_ID_CONFLICT')
                return self._handle(dict(existing), reused=True)
            if db.execute('SELECT 1 FROM runs WHERE terminal=0').fetchone():
                raise ValueError('RUN_ACTIVE')
            store = HumanReportStore.create(context.directory, run_id=run_id,
                session_id=session_id, operation_id=operation_id)
            (context.directory / 'request.json').write_text(payload, encoding='utf-8')
            (context.directory / 'run_context.json').write_text(_json(dict(
                operation_id=operation_id, run_id=run_id, session_id=session_id,
                readiness=components, source_hash=rendered.sha256)), encoding='utf-8')
            db.execute('INSERT INTO runs VALUES(?,?,?,?,?,0,NULL)',
                (operation_id, run_id, session_id, fingerprint, 'CREATED'))
        self.tasks[run_id] = asyncio.create_task(self._execute(context, store, target, musical_plan),
                                               name='dawloop-fast-' + run_id)
        return dict(run_id=run_id, session_id=session_id, operation_id=operation_id,
                    initial_state='CREATED', reused=False)

    @staticmethod
    def _handle(row, *, reused):
        return dict(run_id=row['run_id'], session_id=row['session_id'],
            operation_id=row['operation_id'], initial_state=row['state'], reused=reused)

    def _event(self, context, event):
        if event.get('operation_id') != context.operation_id:
            raise ValueError('RUN_EVENT_MISMATCH')
        if event.get('state') == 'READY_FOR_HUMAN_ACCEPT':
            with self._db() as db:
                db.execute("UPDATE runs SET state='WAITING_FOR_HUMAN_ACCEPT' WHERE run_id=? AND terminal=0",
                           (context.run_id,))

    async def _execute(self, context, store, target, musical_plan):
        runtime = None
        invoked = False
        try:
            with self._db() as db:
                db.execute("UPDATE runs SET state='PREPARING_TARGET' WHERE run_id=?", (context.run_id,))
            current = await self.components(ignore_run=context.run_id)
            if current['runtime'] != 'FAST_READY' or self._binding(current) != self._binding(context.readiness):
                raise ValueError('RUN_CONTEXT_CHANGED')
            runtime = self.factory(context, store)
            if not isinstance(runtime, FastMusicRuntime):
                raise ValueError('FAST_RUNTIME_REQUIRED')
            journal = runtime.backend.journal
            if (not isinstance(journal, NativeWriteJournal)
                    or journal.directory.resolve() != context.ledger_directory):
                raise ValueError('SHARED_DISPATCH_LEDGER_REQUIRED')
            if getattr(runtime.backend.interaction, 'report_store', None) is not store:
                raise ValueError('RUN_HUMAN_REPORT_STORE_REQUIRED')
            self.runtimes[context.run_id] = runtime
            invoked = True
            result = await runtime.execute_fast_music_plan(target, musical_plan,
                operation_id=context.operation_id, experimental_authorized=self.authorized,
                on_event=lambda event: self._event(context, event))
        except asyncio.CancelledError:
            result = runtime.last_result if runtime is not None else None
            if result is None:
                result = FastMusicResult(context.operation_id, error_code='RUN_CANCELLED')
        except Exception as error:
            result = FastMusicResult(context.operation_id, error_code=str(error)
                if isinstance(error, ValueError) else 'RUN_EXECUTION_ERROR')
            if invoked:
                result.state, result.dispatch, result.completion = 'STOPPED_AFTER_DISPATCH_UNKNOWN', 'UNKNOWN', 'UNKNOWN'
        try:
            raw = (_json(result.to_dict()) + '\n').encode('utf-8')
            with (context.directory / 'fast_music_result.json').open('xb') as stream:
                stream.write(raw)
                stream.flush()
                import os
                os.fsync(stream.fileno())
            store.finalize(raw)
            with self._db() as db:
                db.execute('UPDATE runs SET state=?,terminal=1,result_hash=? WHERE run_id=?',
                    (result.state, hashlib.sha256(raw).hexdigest(), context.run_id))
        except Exception:
            with self._db() as db:
                db.execute("UPDATE runs SET state='STOPPED_EVIDENCE_STORAGE_ERROR',terminal=1 WHERE run_id=?",
                           (context.run_id,))
            store.end_accept()

    async def status(self, run_id=None):
        components = await self.components()
        if run_id is None:
            return components
        row = self._row(run_id)
        store = HumanReportStore(self.root / run_id)
        report_snapshot = store.snapshot()
        result = None
        if row['result_hash']:
            raw = (self.root / run_id / 'fast_music_result.json').read_bytes()
            if hashlib.sha256(raw).hexdigest() != row['result_hash']:
                raise ValueError('ORIGINAL_RUN_RESULT_CHANGED')
            result = json.loads(raw)
            # 大量底层身份与图像元数据保存在原证据中，日常查询不重复塞进模型上下文。
            result.pop('evidence', None)
        state = row['state']
        runtime = self.runtimes.get(run_id)
        if not row['terminal'] and runtime is not None:
            record = runtime.backend.last_execution or {}
            if record.get('application_status') == 'APPLICATION_OBSERVED':
                state = 'APPLICATION_OBSERVED'
            elif state != 'WAITING_FOR_HUMAN_ACCEPT' and record.get('dispatch_status') == 'DISPATCHED':
                state = 'DISPATCHED'
            elif state == 'PREPARING_TARGET' and runtime.backend.prepared is not None:
                state = 'TARGET_CONFIRMED'
        return dict(**self._handle(row, reused=False), state=state, terminal=bool(row['terminal']),
            readiness=components, run_result=result, human_reports=report_snapshot['human_reports'],
            preview_window=report_snapshot['preview_window'],
            evidence_ref=run_id + '/fast_music_result.json' if row['result_hash'] else None,
            result_sha256=row['result_hash'],
            producer_target_binding='NOT_VERIFIED', exact_set='NOT_VERIFIED')

    def submit_human_report(self, report):
        parsed = HumanReport.parse(report)
        self._row(parsed.run_id)
        return HumanReportStore(self.root / parsed.run_id).submit(report)

    async def close(self, timeout=5):
        if self.lock_file.closed:
            return
        self.closed = True
        active = [task for task in self.tasks.values() if not task.done()]
        for task in active:
            task.cancel()
        if active:
            _, pending = await asyncio.wait(active, timeout=timeout)
            if pending:
                raise RuntimeError('RUN_TEARDOWN_FAILED')
        self._recover()
        self._lock(False)
        self.lock_file.close()
