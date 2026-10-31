"""复用原受信OMAR worker，保留逐帧向量和版本化研究索引。"""
import hashlib
import json
import os
from pathlib import Path
import queue
import subprocess
import threading
import time
import numpy as np
import soundfile as sf
from style_lab import StyleLab, digest


class Worker:
    def __init__(self, python, worker, settings, folder, log):
        env = dict(os.environ, HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', OMP_NUM_THREADS='2', PYTHONUTF8='1')
        self.errors = open(log, 'ab')
        self.process = subprocess.Popen([str(python), str(Path(worker).with_name('style-omar-host.py'))], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.errors, env=env, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.responses = queue.Queue()
        self.peak_rss = 0
        def read():
            try:
                for line in self.process.stdout:
                    self.responses.put(json.loads(line))
            finally:
                self.responses.put(None)
        threading.Thread(target=read, daemon=True).start()
        try:
            self.loaded = self.call('load', dict(folder=str(folder), files=settings['files'], revision=settings['revision']))
        except Exception:
            self.close()
            raise

    def call(self, method, params, timeout=180):
        self.process.stdin.write((json.dumps(dict(schemaVersion=1, method=method, params=params))+'\n').encode('utf-8'))
        self.process.stdin.flush()
        try:
            response = self.responses.get(timeout=timeout)
        except queue.Empty:
            self.close()
            raise TimeoutError('OMAR_WORKER_TIMEOUT')
        if response is None or response['kind'] != 'result':
            raise RuntimeError(str(response))
        data=response['data']
        if 'workerMemory' in data:
            self.peak_rss=max(self.peak_rss,data['workerMemory']['peakRssBytes'])
        return data

    def close(self):
        if self.process.poll() is None:
            self.process.stdin.close()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        self.errors.close()


class VectorLab:
    def __init__(self, lab, runtime):
        self.lab = lab
        self.runtime = Path(runtime)
        self.settings = next(x for x in json.loads((self.runtime/'models.json').read_text(encoding='utf-8')) if x['id']=='omar-rq')
        config = json.loads((self.runtime/'runtime.json').read_text(encoding='utf-8'))
        self.python = Path(config['omarPython'])
        if digest(self.python) != config['omarPythonSha256']:
            raise ValueError('OMAR_PYTHON_CHANGED')
        self.folder = self.runtime/'models/omar-rq'/self.settings['revision']
        self.worker_path = Path(__file__).with_name('model-worker.py')
        self.version = self.settings['revision']+'-layer6-w30-hop25-'+digest(self.worker_path)[:12]
        self.root = lab.root/'omar'/self.version
        self.root.mkdir(parents=True, exist_ok=True)
        self.lab.db.executescript('''
        CREATE TABLE IF NOT EXISTS vectors(id TEXT PRIMARY KEY, asset TEXT, start REAL, end REAL, version TEXT, state TEXT, filename TEXT, metadata TEXT);
        CREATE TABLE IF NOT EXISTS vector_feedback(query_id TEXT, candidate_id TEXT, liked INTEGER, created REAL);
        ''')

    def recover(self):
        self.lab.recover(lock_name='omar-worker.lock',recover_jobs=False)
        with self.lab.db:
            self.lab.db.execute("UPDATE vectors SET state='QUEUED' WHERE version=? AND state='PROCESSING'",(self.version,))

    def plan(self, assets):
        for asset in assets:
            a = self.lab.db.execute('SELECT * FROM assets WHERE id=?', (asset,)).fetchone()
            if digest(a['path']) != a['sha']:
                raise ValueError('SOURCE_CHANGED')
            info = sf.info(a['path'])
            for start in np.arange(0, info.duration, 25):
                if start and info.duration-start <= 5:
                    break
                end = min(float(start)+30, info.duration)
                identity = hashlib.sha256(f'{asset}:{start:.6f}:{end:.6f}:{self.version}'.encode()).hexdigest()
                with self.lab.db:
                    self.lab.db.execute('INSERT OR IGNORE INTO vectors VALUES(?,?,?,?,?,?,?,?)', (identity, asset, float(start), end, self.version, 'QUEUED', identity+'.npy', None))

    def run(self, maximum=None):
        lock = self.lab.root/'omar-worker.lock'
        fd = os.open(lock, os.O_CREAT|os.O_EXCL|os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode('ascii'))
        os.close(fd)
        worker = None
        started = time.perf_counter()
        completed = 0
        try:
            rows = self.lab.db.execute("SELECT * FROM vectors WHERE version=? AND state!='READY' ORDER BY asset,start", (self.version,)).fetchall()
            if not rows:
                return dict(computed=0, cacheOnly=True)
            worker = Worker(self.python, self.worker_path, self.settings, self.folder, self.root/'worker.log')
            for row in rows:
                if maximum is not None and completed >= maximum:
                    break
                a = self.lab.db.execute('SELECT * FROM assets WHERE id=?', (row['asset'],)).fetchone()
                if digest(a['path']) != a['sha']:
                    raise ValueError('SOURCE_CHANGED')
                info = sf.info(a['path'])
                audio, rate = sf.read(a['path'], start=round(row['start']*info.samplerate), stop=round(row['end']*info.samplerate), dtype='float32', always_2d=True)
                wav = self.root/'input.wav'
                sf.write(wav, audio, rate, subtype='PCM_16')
                pending = self.root/(row['filename']+'.partial')
                pending.unlink(missing_ok=True)
                with self.lab.db:
                    self.lab.db.execute("UPDATE vectors SET state='PROCESSING' WHERE id=?", (row['id'],))
                meta = worker.call('embedding', dict(path=str(wav), output=str(pending)))
                values = np.load(pending, allow_pickle=False)
                if values.shape != tuple(meta['shape']) or values.shape[1] != 1024 or len(values)>750 or not np.isfinite(values).all():
                    raise ValueError('VECTOR_CONTRACT_REJECTED')
                if digest(a['path']) != a['sha']:
                    raise ValueError('SOURCE_CHANGED_DURING_EMBEDDING')
                meta.update(sourceSha256=a['sha'], version=self.version, modelRevision=self.settings['revision'], runtime=worker.loaded, layer=6, windowStart=row['start'], globalTimestamps=[row['start']+t for t in meta['timestamps']], dtype=str(values.dtype), vectorSha256=digest(pending))
                pending.replace(self.root/row['filename'])
                with self.lab.db:
                    self.lab.db.execute("UPDATE vectors SET state='READY',metadata=? WHERE id=?", (json.dumps(meta), row['id']))
                completed += 1
                print(json.dumps(dict(completed=completed, total=len(rows), asset=row['asset'], start=row['start'], shape=meta['shape'], elapsedMs=meta['elapsedMs'])), flush=True)
            return dict(computed=completed, seconds=time.perf_counter()-started, load=worker.loaded, peakRssBytes=worker.peak_rss or None)
        finally:
            if worker:
                worker.close()
            (self.root/'input.wav').unlink(missing_ok=True)
            lock.unlink()

    def descriptors(self):
        rows = []
        for row in self.lab.db.execute("SELECT * FROM vectors WHERE version=? AND state='READY' ORDER BY asset,start", (self.version,)):
            meta = json.loads(row['metadata'])
            p = self.root/row['filename']
            if digest(p) != meta['vectorSha256']:
                raise ValueError('VECTOR_CACHE_CHANGED')
            values = np.load(p, allow_pickle=False)
            # 只将每窗非重叠归属区间划为5秒检索片段，完整原始25Hz序列另存。
            owned_end = min(row['start']+25, row['end'])
            next_row = self.lab.db.execute("SELECT 1 FROM vectors WHERE asset=? AND version=? AND start=?", (row['asset'], self.version, row['start']+25)).fetchone()
            if not next_row:
                owned_end = row['end']
            for start in np.arange(row['start'], owned_end, 5):
                end = min(float(start)+5, owned_end)
                times = np.asarray(meta['globalTimestamps'])
                block = values[(times>=start)&(times<end)]
                if not len(block):
                    continue
                descriptor = block.mean(axis=0, dtype=np.float64)
                norm = np.linalg.norm(descriptor)
                if not np.isfinite(norm) or norm < 1e-12:
                    raise ValueError('ZERO_VECTOR_DESCRIPTOR')
                rows.append(dict(id=f"{row['id']}:{start:.6f}", asset=row['asset'], start=float(start), end=end, vector=descriptor/norm, method='5s mean(layer6) L2; not whole-song pooling'))
        return rows

    def search(self, query_id, scope='cross', limit=5):
        rows = self.descriptors()
        query = next(r for r in rows if r['id']==query_id)
        candidates = []
        for r in rows:
            if r['id']==query_id or scope=='cross' and r['asset']==query['asset'] or scope=='within' and r['asset']!=query['asset']:
                continue
            if r['asset']==query['asset'] and abs(r['start']-query['start'])<15:
                continue
            feedback = self.lab.db.execute('SELECT liked FROM vector_feedback WHERE query_id=? AND candidate_id=? ORDER BY created DESC LIMIT 1', (query_id,r['id'])).fetchone()
            cosine = float(np.dot(query['vector'],r['vector']))
            candidates.append(dict(id=r['id'], asset=r['asset'], start=r['start'], end=r['end'], cosine=cosine, preference=feedback[0] if feedback else 0, score=cosine+(.05*feedback[0] if feedback else 0)))
        return sorted(candidates, key=lambda r:(-r['score'],r['id']))[:limit]

    def feedback(self, query, candidate, liked):
        valid={r['id'] for r in self.descriptors()}
        if query not in valid or candidate not in valid or liked not in (-1,1):
            raise ValueError('INVALID_VECTOR_FEEDBACK')
        with self.lab.db:
            self.lab.db.execute('INSERT INTO vector_feedback VALUES(?,?,?,?)',(query,candidate,liked,time.time()))

    def clusters(self, k=4):
        rows=self.descriptors()
        x=np.stack([r['vector'] for r in rows])
        centers=x[np.linspace(0,len(x)-1,min(k,len(x)),dtype=int)].copy()
        for _ in range(25):
            labels=(x@centers.T).argmax(axis=1)
            for i in range(len(centers)):
                members=x[labels==i]
                if len(members):
                    center=members.mean(axis=0)
                    centers[i]=center/max(np.linalg.norm(center),1e-12)
        return [dict(id=r['id'],asset=r['asset'],start=r['start'],end=r['end'],cluster=int(label)) for r,label in zip(rows,labels)]

    def save_profile(self, name, segments):
        rows={r['id']:r for r in self.descriptors()}
        if not segments or len(segments)>200 or not isinstance(name,str) or not 1<=len(name)<=100 or any(s not in rows for s in segments):
            raise ValueError('INVALID_VECTOR_PROFILE')
        self.lab.db.execute('CREATE TABLE IF NOT EXISTS vector_profiles(id INTEGER PRIMARY KEY,name TEXT,selection TEXT,version TEXT,created REAL)')
        selection=[{k:v for k,v in rows[s].items() if k!='vector'} for s in dict.fromkeys(segments)]
        with self.lab.db:
            cursor=self.lab.db.execute('INSERT INTO vector_profiles(name,selection,version,created) VALUES(?,?,?,?)',(name,json.dumps(selection),self.version,time.time()))
        return cursor.lastrowid
