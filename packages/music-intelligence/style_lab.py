"""本地风格研究资料库；不调用宿主或网络。"""
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
import uuid


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


class StyleLab:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.root / 'library.sqlite', timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS assets(id TEXT PRIMARY KEY, name TEXT, path TEXT, sha TEXT UNIQUE, observed REAL);
        CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, asset TEXT, start REAL, end REAL, state TEXT, progress REAL, error TEXT, result TEXT, elapsed REAL);
        CREATE TABLE IF NOT EXISTS ratings(id INTEGER PRIMARY KEY, asset TEXT, start REAL, end REAL, score REAL, likes TEXT, avoids TEXT, created REAL);
        CREATE TABLE IF NOT EXISTS profiles(id TEXT PRIMARY KEY, name TEXT, assets TEXT, created REAL);
        CREATE TABLE IF NOT EXISTS prompts(id TEXT PRIMARY KEY, profile TEXT, body TEXT, created REAL);
        ''')

    def import_audio(self, paths):
        ids = []
        for value in paths:
            p = Path(value).resolve()
            if p.suffix.lower() not in ('.mp3', '.wav') or not p.is_file():
                raise ValueError('请选择存在的 MP3 或 WAV 文件')
            sha = digest(p)
            identity = sha[:24]
            with self.db:
                self.db.execute('INSERT OR IGNORE INTO assets VALUES(?,?,?,?,?)', (identity, p.stem, str(p), sha, time.time()))
                self.db.execute('UPDATE assets SET observed=? WHERE id=?', (time.time(), identity))
            ids.append(identity)
        return ids

    def search(self, text=''):
        return [dict(row, availability='AVAILABLE' if Path(row['path']).is_file() else 'MISSING_SOURCE')
                for row in self.db.execute('SELECT * FROM assets WHERE name LIKE ? ORDER BY name', ('%' + text + '%',))]

    def enqueue(self, asset, start=0, end=None):
        if not math.isfinite(start) or start < 0 or end is not None and (not math.isfinite(end) or end <= start):
            raise ValueError('INVALID_RANGE')
        if not self.db.execute('SELECT 1 FROM assets WHERE id=?', (asset,)).fetchone():
            raise ValueError('UNKNOWN_ASSET')
        prior = self.db.execute('SELECT id FROM jobs WHERE asset=? AND start=? AND end IS ? AND state IN (\'READY\',\'QUEUED\',\'PROCESSING\')', (asset, start, end)).fetchone()
        if prior:
            return prior['id']
        job = uuid.uuid4().hex
        with self.db:
            self.db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?)', (job, asset, start, end, 'QUEUED', 0, None, None, None))
        return job

    def cancel(self, job):
        with self.db:
            self.db.execute("UPDATE jobs SET state=CASE WHEN state='PROCESSING' THEN 'CANCEL_REQUESTED' ELSE 'CANCELLED' END WHERE id=? AND state IN ('PROCESSING','QUEUED')", (job,))

    def retry(self, job):
        with self.db:
            self.db.execute("UPDATE jobs SET state='QUEUED',progress=0,error=NULL WHERE id=? AND state IN ('FAILED','CANCELLED','INTERRUPTED')", (job,))

    def recover(self, lock_name='worker.lock', recover_jobs=True):
        if lock_name not in ('worker.lock','omar-worker.lock'):
            raise ValueError('UNKNOWN_WORKER_LOCK')
        lock = self.root / lock_name
        if lock.exists():
            pid = int(lock.read_text(encoding='ascii'))
            if sys.platform == 'win32':
                import ctypes
                kernel = ctypes.WinDLL('kernel32', use_last_error=True)
                kernel.OpenProcess.restype = ctypes.c_void_p
                handle = kernel.OpenProcess(0x1000, False, pid)
                if handle:
                    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
                    kernel.CloseHandle(handle)
                    raise ValueError('WORKER_STILL_PRESENT')
                if ctypes.get_last_error() != 87:
                    raise ValueError('WORKER_LIVENESS_UNKNOWN')
            else:
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    pass
                else:
                    raise ValueError('WORKER_STILL_PRESENT')
            lock.unlink()
        if recover_jobs:
            with self.db:
                self.db.execute("UPDATE jobs SET state='INTERRUPTED',error='WORKER_INTERRUPTED' WHERE state IN ('PROCESSING','CANCEL_REQUESTED')")

    def rate(self, asset, score, start=0, end=None, likes='', avoids=''):
        if not math.isfinite(score) or not 0 <= score <= 5 or not math.isfinite(start) or start < 0 or end is not None and (not math.isfinite(end) or end <= start):
            raise ValueError('INVALID_RATING')
        if not self.db.execute('SELECT 1 FROM assets WHERE id=?', (asset,)).fetchone():
            raise ValueError('UNKNOWN_ASSET')
        with self.db:
            self.db.execute('INSERT INTO ratings(asset,start,end,score,likes,avoids,created) VALUES(?,?,?,?,?,?,?)', (asset, start, end, score, likes, avoids, time.time()))

    def run(self, timeout=180, cache_limit=2 * 1024**3):
        # 独占事务锁不跨音频计算持有，其他连接仍可提交取消请求。
        lock = self.root / 'worker.lock'
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode('ascii'))
        os.close(fd)
        try:
            for row in self.db.execute("SELECT * FROM jobs WHERE state='QUEUED' ORDER BY rowid").fetchall():
                job = dict(row)
                asset = self.db.execute('SELECT * FROM assets WHERE id=?', (job['asset'],)).fetchone()
                started = time.perf_counter()
                with self.db:
                    claimed = self.db.execute("UPDATE jobs SET state='PROCESSING' WHERE id=? AND state='QUEUED'", (job['id'],)).rowcount
                if not claimed:
                    continue
                child = None
                try:
                    original = Path(asset['path'])
                    if digest(original) != asset['sha']:
                        raise ValueError('SOURCE_CHANGED')
                    import soundfile as sf
                    info = sf.info(original)
                    if not 0 < info.duration <= 7200 or not 1 <= info.channels <= 8:
                        raise ValueError('AUDIO_BUDGET_EXCEEDED')
                    cache = self.root / 'decode'
                    cache.mkdir(exist_ok=True)
                    decoded = cache / (asset['sha'] + '.wav')
                    if not decoded.exists():
                        required = info.frames * info.channels * 4 + 4096
                        if required + sum(p.stat().st_size for p in cache.iterdir()) > cache_limit:
                            raise ValueError('DECODE_CACHE_BUDGET_EXCEEDED')
                        temp = decoded.with_suffix('.partial')
                        try:
                            with sf.SoundFile(original) as reader, sf.SoundFile(temp, 'w', samplerate=info.samplerate, channels=info.channels, format='WAV', subtype='FLOAT') as writer:
                                while True:
                                    block = reader.read(65536, dtype='float32', always_2d=True)
                                    if not len(block):
                                        break
                                    writer.write(block)
                            temp.replace(decoded)
                        finally:
                            temp.unlink(missing_ok=True)
                    output = self.root / (job['id'] + '.pending')
                    with output.open('wb') as stream:
                        progress_path = self.root / (job['id'] + '.progress')
                        child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--child', str(decoded), str(job['start']), str(job['end']), str(progress_path)], stdout=stream, stderr=subprocess.STDOUT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                        while child.poll() is None:
                            state = self.db.execute('SELECT state FROM jobs WHERE id=?', (job['id'],)).fetchone()[0]
                            if state == 'CANCEL_REQUESTED' or time.perf_counter() - started > timeout:
                                child.terminate()
                                child.wait(timeout=10)
                                raise ValueError('CANCELLED' if state == 'CANCEL_REQUESTED' else 'TIMEOUT')
                            try:
                                progress = float(progress_path.read_text(encoding='ascii'))
                                with self.db:
                                    self.db.execute('UPDATE jobs SET progress=? WHERE id=?', (min(.99, max(0, progress)), job['id']))
                            except (OSError, ValueError):
                                pass
                            time.sleep(.2)
                    if child.returncode:
                        raise ValueError(output.read_text(encoding='utf-8', errors='replace')[-1200:])
                    result = json.loads(output.read_text(encoding='utf-8'))
                    if digest(original) != asset['sha']:
                        raise ValueError('SOURCE_CHANGED_DURING_ANALYSIS')
                    result.update(sourceSha256=asset['sha'], assetId=asset['id'], modelRevision=None)
                    destination = self.root / (job['id'] + '.json')
                    destination.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
                    with self.db:
                        self.db.execute("UPDATE jobs SET state='READY',progress=1,result=?,elapsed=? WHERE id=?", (destination.name, time.perf_counter()-started, job['id']))
                    output.unlink()
                    progress_path.unlink(missing_ok=True)
                except Exception as error:
                    if child and child.poll() is None:
                        child.kill()
                        child.wait()
                    with self.db:
                        self.db.execute('UPDATE jobs SET state=?,error=?,elapsed=? WHERE id=?', ('CANCELLED' if str(error) == 'CANCELLED' else 'FAILED', str(error), time.perf_counter()-started, job['id']))
        finally:
            lock.unlink()

    def create_profile(self, name, assets, jobs=None):
        identity = uuid.uuid4().hex
        selected = list(dict.fromkeys(assets))
        if jobs is not None:
            for job in jobs:
                row = self.db.execute('SELECT asset FROM jobs WHERE id=?', (job,)).fetchone()
                if not row or row['asset'] not in selected:
                    raise ValueError('PROFILE_JOB_BINDING_MISMATCH')
        selection = selected if jobs is None else dict(assets=selected, jobs=jobs)
        with self.db:
            self.db.execute('INSERT INTO profiles VALUES(?,?,?,?)', (identity, name, json.dumps(selection), time.time()))
        return identity

    def summarize(self, identity):
        profile = self.db.execute('SELECT * FROM profiles WHERE id=?', (identity,)).fetchone()
        if not profile:
            raise ValueError('UNKNOWN_PROFILE')
        evidence = []
        selection = json.loads(profile['assets'])
        selected_jobs = selection.get('jobs') if isinstance(selection, dict) else None
        for asset in selection['assets'] if isinstance(selection, dict) else selection:
            for job in self.db.execute("SELECT * FROM jobs WHERE asset=? AND state='READY' ORDER BY rowid", (asset,)):
                if selected_jobs is not None and job['id'] not in selected_jobs:
                    continue
                result = json.loads((self.root / job['result']).read_text(encoding='utf-8'))
                rating = self.db.execute('SELECT * FROM ratings WHERE asset=? AND start<=? AND (end IS NULL OR end>=?) ORDER BY created DESC LIMIT 1', (asset, result['range'][0], result['range'][1])).fetchone()
                energy = result['energy']
                changes = sorted([(abs(b[1]-a[1]), b[0]) for a,b in zip(energy,energy[1:])], reverse=True)[:3]
                evidence.append(dict(job=job['id'], asset=asset, range=result['range'], bpm=result['bpmCandidates'], bpmConfidence=result['bpmConfidence'], keyCandidates=result['measurements']['key']['candidates'][:3], lufs=result['measurements']['lufs']['value'], centroid=result['profile']['timbral']['centroidMean'], energyChangeCandidates=[dict(time=t, delta=d, method='adjacent RMS change; not certified section boundary') for d,t in changes], algorithm=result['measurements']['implementationVersion'], rating=dict(rating) if rating else None))
        if not evidence:
            raise ValueError('NO_READY_EVIDENCE')
        # 单首有多片段时先归一化曲内权重，避免切片数量替用户决定偏好。
        counts = {a: sum(e['asset']==a for e in evidence) for a in {e['asset'] for e in evidence}}
        weights = [(1 + e['rating']['score'] if e['rating'] else 1)/counts[e['asset']] for e in evidence]
        means = {}
        for key in ('lufs', 'centroid'):
            values = [(e[key], w) for e,w in zip(evidence,weights) if e[key] is not None]
            means[key] = sum(v*w for v,w in values)/sum(w for _,w in values) if values else None
        tempos = [(e['bpm'][0],w) for e,w in zip(evidence,weights) if e['bpm']]
        means['bpm'] = sum(v*w for v,w in tempos)/sum(w for _,w in tempos) if tempos else None
        prompt = ('Create an original track. ' + (f"Reference tempo estimates span {min(v for v,_ in tempos):.0f}–{max(v for v,_ in tempos):.0f} BPM; explore around {means['bpm']:.0f} BPM. " if tempos else 'Choose the tempo manually; reference tempo estimates are inconclusive. ') + f"Reference spectral centroid averages {means['centroid']:.0f} Hz; use this as an audio comparison target, not an instrument label. " + 'Develop an original melody and harmonic progression.')
        likes = list(dict.fromkeys(e['rating']['likes'] for e in evidence if e['rating'] and e['rating']['likes']))
        avoids = list(dict.fromkeys(e['rating']['avoids'] for e in evidence if e['rating'] and e['rating']['avoids']))
        if likes:
            prompt += ' User-selected priorities: ' + '; '.join(likes) + '.'
        if avoids:
            prompt += ' Avoid, as requested by the user: ' + '; '.join(avoids) + '.'
        return dict(schemaVersion=1, profileId=identity, name=profile['name'], means=means, evidence=evidence, tempoCoverage=dict(available=len(tempos), observations=len(evidence)), userPreferences=dict(likes=likes, avoids=avoids), englishPrompt=prompt, semanticStatus='NOT_EVALUATED', contradictions='Tempo estimates may include half/double time; missing estimates are not votes for a common tempo. No artist-specific attribution.', structureSuggestion='USER_EDITABLE: intro → verse → contrasting section → return → outro', suggestedStructureIsMeasured=False)

    def save_prompt(self, profile, text):
        if not isinstance(text, str) or not 0 < len(text) <= 20000 or not self.db.execute('SELECT 1 FROM profiles WHERE id=?', (profile,)).fetchone():
            raise ValueError('INVALID_PROMPT')
        identity = uuid.uuid4().hex
        with self.db:
            self.db.execute('INSERT INTO prompts VALUES(?,?,?,?)', (identity, profile, text, time.time()))
        return identity


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True)
    parser.add_argument('--folder', type=Path)
    parser.add_argument('--limit', type=int, default=3)
    args = parser.parse_args()
    lab = StyleLab(args.root)
    ids = lab.import_audio(sorted(p for p in args.folder.iterdir() if p.suffix.lower() in ('.mp3','.wav'))[:args.limit])
    for asset in ids:
        lab.enqueue(asset)
    lab.run()
    profile = lab.create_profile('Reference collection', ids)
    summary = lab.summarize(profile)
    lab.save_prompt(profile, summary['englishPrompt'])
    (lab.root/'profile.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'profile':profile,'jobs':[dict(r) for r in lab.db.execute('SELECT id,state,elapsed,error FROM jobs')]},ensure_ascii=False))


if __name__ == '__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--child':
        spec=importlib.util.spec_from_file_location('song_dsp',Path(__file__).with_name('song-dsp.py'))
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        def progress(kind, **values):
            if kind == 'progress':
                Path(sys.argv[5]).write_text(str(values['progress']), encoding='ascii')
        cpu=time.process_time()
        result=module.analyze(sys.argv[2],float(sys.argv[3]),None if sys.argv[4]=='None' else float(sys.argv[4]),progress)
        result['resourceUsage']={'cpuSeconds':time.process_time()-cpu,'peakRssBytes':None}
        print(json.dumps(result,ensure_ascii=True))
    else:
        main()
