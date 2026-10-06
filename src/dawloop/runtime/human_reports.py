"""人工报告的持久关联与交付；不拥有宿主执行权限。"""

from contextlib import closing, contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import time


EVENTS = ('ACCEPTED', 'REJECTED', 'LISTENED_OK', 'LISTENED_BAD')


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _id(value):
    if type(value) is not str or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', value):
        raise ValueError('HUMAN_REPORT_ID_INVALID')
    return value


@dataclass(frozen=True)
class HumanReport:
    run_id: str
    session_id: str
    report_id: str
    reported_at: str
    event_type: str
    source: str
    evidence_ref: str
    preview_window: dict | None
    preview_review_confirmed: bool

    @classmethod
    def parse(cls, value):
        if not isinstance(value, dict) or set(value) != set(cls.__dataclass_fields__):
            raise ValueError('HUMAN_REPORT_FIELDS_REQUIRED')
        for key in ('run_id', 'session_id', 'report_id'):
            _id(value[key])
        try:
            timestamp = datetime.fromisoformat(value['reported_at'])
        except (ValueError, TypeError):
            raise ValueError('HUMAN_REPORT_TIMESTAMP_INVALID') from None
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError('HUMAN_REPORT_TIMEZONE_REQUIRED')
        if value['source'] != 'HUMAN' or value['event_type'] not in EVENTS:
            raise ValueError('HUMAN_REPORT_SOURCE_OR_EVENT_INVALID')
        if (type(value['evidence_ref']) is not str or not value['evidence_ref'].strip()
                or type(value['preview_review_confirmed']) is not bool):
            raise ValueError('HUMAN_REPORT_EVIDENCE_REQUIRED')
        window = value['preview_window']
        if value['event_type'] in ('ACCEPTED', 'REJECTED'):
            if (not isinstance(window, dict) or not window
                    or type(window.get('hwnd')) is not int or window['hwnd'] <= 0):
                raise ValueError('HUMAN_REPORT_PREVIEW_REQUIRED')
            if value['event_type'] == 'ACCEPTED' and not value['preview_review_confirmed']:
                raise ValueError('HUMAN_PREVIEW_REVIEW_REQUIRED')
        elif window is not None:
            raise ValueError('LISTENING_REPORT_WINDOW_MUST_BE_NULL')
        # 以解析后的独立副本固定报告内容，调用方修改原dict不能改变已提交报告。
        return cls(**json.loads(_json(value)))


class HumanReportStore:
    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        self.path = self.directory / 'human_reports.sqlite3'
        if not self.path.is_file():
            raise ValueError('HUMAN_REPORT_STORE_NOT_INITIALIZED')

    @classmethod
    def create(cls, directory, *, run_id, session_id, operation_id):
        for value in (run_id, session_id, operation_id):
            _id(value)
        directory = Path(directory).resolve()
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / 'human_reports.sqlite3'
        with path.open('xb'):
            pass
        with closing(sqlite3.connect(path)) as db, db:
            db.executescript('''
                CREATE TABLE binding (
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                    run_id TEXT NOT NULL, session_id TEXT NOT NULL, operation_id TEXT NOT NULL,
                    phase TEXT NOT NULL, preview TEXT, terminal BLOB, terminal_hash TEXT);
                CREATE TABLE reports (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT, report_id TEXT NOT NULL UNIQUE,
                    payload TEXT NOT NULL, received_at TEXT NOT NULL, linked INTEGER NOT NULL,
                    delivery TEXT NOT NULL, reason TEXT NOT NULL);
            ''')
            db.execute('INSERT INTO binding VALUES(1,?,?,?,?,NULL,NULL,NULL)',
                       (run_id, session_id, operation_id, 'RUNNING'))
        return cls(directory)

    @contextmanager
    def _transaction(self):
        # 提交、领取和终止共用数据库事务，避免晚到报告落入已结束的实时队列。
        db = sqlite3.connect(f'{self.path.as_uri()}?mode=rw', uri=True, timeout=2)
        db.row_factory = sqlite3.Row
        try:
            db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def _binding(self, db):
        row = db.execute('SELECT * FROM binding').fetchone()
        if row['terminal_hash']:
            original = self.directory / 'fast_music_result.json'
            if not original.is_file() or hashlib.sha256(original.read_bytes()).hexdigest() != row['terminal_hash']:
                raise ValueError('ORIGINAL_RUN_RESULT_CHANGED')
        return row

    def bind_preview(self, window):
        payload = _json(window)
        with self._transaction() as db:
            row = self._binding(db)
            if row['phase'] != 'RUNNING':
                raise ValueError('HUMAN_REPORT_PREVIEW_PHASE_INVALID')
            if row['preview'] is not None and row['preview'] != payload:
                raise ValueError('HUMAN_REPORT_PREVIEW_CHANGED')
            db.execute('UPDATE binding SET preview=? WHERE singleton=1', (payload,))

    def begin_accept(self):
        with self._transaction() as db:
            row = self._binding(db)
            if row['phase'] != 'RUNNING' or row['preview'] is None:
                raise ValueError('HUMAN_REPORT_ACCEPT_PHASE_INVALID')
            db.execute("UPDATE binding SET phase='WAITING_ACCEPT' WHERE singleton=1")

    def submit(self, value):
        report = HumanReport.parse(value)
        payload = _json(asdict(report))
        with self._transaction() as db:
            row = self._binding(db)
            existing = db.execute('SELECT * FROM reports WHERE report_id=?', (report.report_id,)).fetchone()
            if existing is not None:
                if existing['payload'] != payload:
                    raise ValueError('HUMAN_REPORT_ID_CONFLICT')
                return self._receipt(existing)
            linked = report.run_id == row['run_id'] and report.session_id == row['session_id']
            reason = 'LINKED' if linked else 'RUN_SESSION_MISMATCH'
            if linked and report.event_type in ('ACCEPTED', 'REJECTED'):
                linked = row['preview'] is not None and _json(report.preview_window) == row['preview']
                reason = 'LINKED' if linked else 'PREVIEW_BINDING_MISMATCH'
            delivery = 'UNLINKED'
            if linked:
                delivery = ('PENDING' if report.event_type in ('ACCEPTED', 'REJECTED')
                    and row['phase'] in ('RUNNING', 'WAITING_ACCEPT') else 'LATE')
            db.execute('INSERT INTO reports(report_id,payload,received_at,linked,delivery,reason) '
                'VALUES(?,?,?,?,?,?)', (report.report_id, payload,
                    datetime.now(timezone.utc).isoformat(), int(linked), delivery, reason))
            return self._receipt(db.execute('SELECT * FROM reports WHERE report_id=?',
                (report.report_id,)).fetchone())

    @staticmethod
    def _receipt(row):
        return dict(report=json.loads(row['payload']), received_at=row['received_at'],
                    linked=bool(row['linked']), delivery=row['delivery'], reason=row['reason'])

    def claim_accept(self, *, deadline=None, clock=time.monotonic):
        with self._transaction() as db:
            row = self._binding(db)
            if row['phase'] != 'WAITING_ACCEPT':
                return None
            if deadline is not None and clock() >= deadline:
                return None
            pending = db.execute("SELECT * FROM reports WHERE delivery='PENDING' ORDER BY sequence").fetchall()
            if not pending:
                return None
            events = {json.loads(item['payload'])['event_type'] for item in pending}
            if len(events) != 1:
                raise ValueError('CONFLICTING_HUMAN_DECISIONS')
            report = pending[0]
            db.execute("UPDATE reports SET delivery='REALTIME' WHERE report_id=?", (report['report_id'],))
            db.execute("UPDATE reports SET delivery='LATE' WHERE delivery='PENDING'")
            db.execute("UPDATE binding SET phase='ACCEPT_CLOSED' WHERE singleton=1")
            return self._receipt(db.execute('SELECT * FROM reports WHERE report_id=?',
                (report['report_id'],)).fetchone())

    def end_accept(self):
        with self._transaction() as db:
            row = self._binding(db)
            if row['phase'] in ('RUNNING', 'WAITING_ACCEPT'):
                db.execute("UPDATE binding SET phase='ACCEPT_CLOSED' WHERE singleton=1")
            db.execute("UPDATE reports SET delivery='LATE' WHERE delivery='PENDING'")

    def finalize(self, original_bytes):
        value = json.loads(original_bytes)
        digest = hashlib.sha256(original_bytes).hexdigest()
        with self._transaction() as db:
            row = self._binding(db)
            if value.get('operation_id') != row['operation_id']:
                raise ValueError('TERMINAL_OPERATION_MISMATCH')
            if row['terminal'] is not None:
                if bytes(row['terminal']) != original_bytes:
                    raise ValueError('TERMINAL_RESULT_IMMUTABLE')
                return
            original = self.directory / 'fast_music_result.json'
            if not original.is_file() or original.read_bytes() != original_bytes:
                raise ValueError('TERMINAL_RESULT_FILE_REQUIRED')
            db.execute("UPDATE binding SET phase='CLOSED', terminal=?, terminal_hash=? WHERE singleton=1",
                       (original_bytes, digest))
            db.execute("UPDATE reports SET delivery='LATE' WHERE delivery='PENDING'")

    def snapshot(self):
        with self._transaction() as db:
            row = self._binding(db)
            result = json.loads(bytes(row['terminal'])) if row['terminal'] is not None else None
            reports = [self._receipt(item) for item in db.execute('SELECT * FROM reports ORDER BY sequence')]
            return dict(run_id=row['run_id'], session_id=row['session_id'], operation_id=row['operation_id'],
                phase=row['phase'], preview_window=json.loads(row['preview']) if row['preview'] else None,
                run_result=dict(terminal_state=result['state'], error_code=result.get('error_code'),
                    host_completion=result.get('completion'), application_observed=result.get('application'),
                    immutable=True, sha256=row['terminal_hash']) if result else None,
                human_reports=reports, late_evidence=dict(
                    human_reports=[r for r in reports if r['delivery'] == 'LATE']),
                runtime_resumed=False, dispatches_added=0,
                producer_target_binding='NOT_VERIFIED', exact_set='NOT_VERIFIED')


def acceptance_receipt(record, operation_id):
    report = HumanReport.parse(record['report'])
    if not record['linked'] or record['delivery'] != 'REALTIME':
        raise ValueError('REALTIME_HUMAN_REPORT_REQUIRED')
    if report.event_type == 'REJECTED':
        raise ValueError('HUMAN_ACCEPT_REJECTED')
    if report.event_type != 'ACCEPTED':
        raise ValueError('HUMAN_ACCEPT_EVENT_REQUIRED')
    return dict(operation_id=operation_id, evidence_ref=report.evidence_ref, observer='human',
        accept_actor='human', accepted=True, preview_review_confirmed=report.preview_review_confirmed,
        window=report.preview_window, human_report=asdict(report), delivery=record['delivery'],
        received_at=record['received_at'])
