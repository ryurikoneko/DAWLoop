"""可选的本地音频—文字对照实验，缓存不覆盖原始结构或向量。"""
import hashlib
import json
import math
from pathlib import Path
import time
from style_lab import digest

# 同组分数只表示候选文字的相对匹配，不转换成概率或客观标签。
GROUPS={
 'voice': [('singing','有人声演唱','Music with a person singing.'),('instrumental','器乐段落','Instrumental music without vocals.'),('speech','说话','A person speaking without music.')],
 'instrumentation':[('electronic','电子合成器','Electronic music with synthesizers and electronic drums.'),('acoustic','原声乐器','Acoustic music with acoustic guitar and acoustic piano.'),('orchestral','管弦音色','Orchestral music with bowed strings and brass instruments.')],
 'synth':[('bright','明亮清脆','Music with bright sparkling synthesizer tones.'),('soft','柔和铺底','Music with soft smooth atmospheric synthesizer pads.'),('distorted','粗粝失真','Music with harsh distorted aggressive synthesizer sounds.')],
 'rhythm':[('dance','舞曲律动','Dance music with a steady beat, kick drum and bass groove.'),('broken','切分节奏','Music with syncopated broken drum rhythms and bass.'),('ambient','弱节拍氛围','Ambient music with sustained tones and no prominent drum beat.')],
 'bass':[('sub','低频铺底','Music with deep sustained sub bass and atmospheric pads.'),('rhythmic','节奏型 Bass','Music with a rhythmic bouncy bass line and punchy drums.'),('light','轻低频','Music with delicate high pitched melody and little bass.')],
 'mood':[('joyful','欢快有活力','Bright cheerful playful energetic music.'),('reflective','柔和抒情','Soft gentle reflective emotional music.'),('aggressive','激进有力量','Aggressive powerful intense music.')],
 'density':[('dense','层次密集','Dense layered music with many instruments playing together.'),('sparse','编配疏朗','Sparse minimal music with only a few sounds.')],
}
ALGORITHM='clap-text-comparison-v1-10s-unfused'


def write_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    pending=path.with_suffix(path.suffix+'.partial')
    pending.write_text(json.dumps(value,ensure_ascii=False,allow_nan=False),encoding='utf-8');pending.replace(path)


def plan(lab,revision):
    rows=[]
    for asset in lab.search():
        source=lab.root/'structure'/(asset['id']+'.json')
        if not source.exists():continue
        structure=json.loads(source.read_text(encoding='utf-8'))
        if structure['sourceSha256']!=asset['sha']:raise ValueError('SEMANTIC_SOURCE_MISMATCH')
        for section in structure['sections']:
            for offset in range(math.ceil((section['end']-section['start'])/10)):
                start=section['start']+offset*10;end=min(start+10,section['end'])
                if end<=start:continue
                token=json.dumps([asset['sha'],revision,ALGORITHM,section['id'],start,end,GROUPS],sort_keys=True)
                rows.append(dict(id=hashlib.sha256(token.encode()).hexdigest(),asset=asset['id'],section=section['id'],start=start,end=end,sourceSha256=asset['sha']))
    return rows


def aggregate(structure,windows,revision):
    sections=[]
    for section in structure['sections']:
        rows=[w for w in windows if w['section']==section['id']]
        groups={}
        for group in GROUPS:
            candidates=[]
            for identity,label,text in GROUPS[group]:
                observed=[(next(c['cosine'] for c in w['groups'][group] if c['id']==identity),w['end']-w['start']) for w in rows]
                score=sum(s*n for s,n in observed)/sum(n for _,n in observed) if observed else None
                candidates.append(dict(id=identity,label=label,text=text,cosine=score))
            ranked=sorted(candidates,key=lambda c:-(c['cosine'] if c['cosine'] is not None else -1))
            margin=ranked[0]['cosine']-ranked[1]['cosine'] if rows else None
            groups[group]=dict(candidates=ranked,top=ranked[0]['id'] if margin is not None and margin>=.015 else None,margin=margin,validation='MODEL_PREDICTION_UNREVIEWED')
        sections.append(dict(id=section['id'],start=section['start'],end=section['end'],modelRevision=revision,sourceSha256=structure['sourceSha256'],groups=groups,windowIds=[w['id'] for w in rows],function=None,chords=None,vocalLanguage=None,drumsBassRelationship=None,validation='MODEL_PREDICTION_UNREVIEWED'))
    transitions=[dict(fromSection=a['id'],toSection=b['id'],time=b['start'],changedCandidates=[g for g in GROUPS if a['groups'][g]['top']!=b['groups'][g]['top']],interpretation=None,validation='CANDIDATE_CHANGE_ONLY') for a,b in zip(sections,sections[1:])]
    return dict(schemaVersion=1,asset=structure['asset'],sourceSha256=structure['sourceSha256'],modelRevision=revision,algorithm=ALGORITHM,duration=structure['coverage']['duration'],sections=sections,transitions=transitions,wholeSongDescription=None,validation='MODEL_PREDICTION_UNREVIEWED')


def result_view(lab):
    root=lab.root/'phase6';status=root/'status.json';result=root/'results.json'
    return dict(status=json.loads(status.read_text(encoding='utf-8')) if status.exists() else dict(state='NOT_INSTALLED',completed=0,total=0),songs=json.loads(result.read_text(encoding='utf-8')) if result.exists() else [])


def run(root,runtime):
    import os,sys
    from style_lab import StyleLab
    lab=StyleLab(root);folder=lab.root/'phase6';config=json.loads((folder/'provider.json').read_text(encoding='utf-8'))
    model=Path(config['modelFolder']);revision=config['revision']
    status=folder/'status.json';cancel=folder/'cancel.request';lock=folder/'semantic.lock'
    if lock.exists():
        pid=int(lock.read_text(encoding='ascii'))
        if sys.platform=='win32':
            import ctypes
            kernel=ctypes.WinDLL('kernel32',use_last_error=True);kernel.OpenProcess.restype=ctypes.c_void_p
            handle=kernel.OpenProcess(0x1000,False,pid)
            if handle:
                kernel.CloseHandle.argtypes=[ctypes.c_void_p];kernel.CloseHandle(handle);raise ValueError('SEMANTIC_WORKER_PRESENT')
            if ctypes.get_last_error()!=87:raise ValueError('SEMANTIC_WORKER_LIVENESS_UNKNOWN')
        else:
            try:os.kill(pid,0)
            except ProcessLookupError:pass
            else:raise ValueError('SEMANTIC_WORKER_PRESENT')
        lock.unlink()
    fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.write(fd,str(os.getpid()).encode());os.close(fd)
    started=time.perf_counter();cpu=time.process_time();completed=0;total=0;peak=0
    try:
        windows=plan(lab,revision);total=len(windows)
        write_json(status,dict(state='LOADING',completed=0,total=total,modelRevision=revision,workerPid=os.getpid()))
        for item in config['files']:
            if digest(model/item['name'])!=item['sha256']:raise ValueError('SEMANTIC_MODEL_CHANGED')
        # 只追加受管环境的数值/音频库目录，OMAR 环境本身不安装或改写包。
        sys.path.append(str(Path(runtime)/'environments/basic-v1/Lib/site-packages'))
        import numpy as np
        import soundfile as sf
        from scipy.signal import resample_poly
        import torch
        from transformers import ClapModel,ClapProcessor
        torch.set_num_threads(4);torch.manual_seed(2606);np.random.seed(2606)
        load_start=time.perf_counter()
        processor=ClapProcessor.from_pretrained(str(model),local_files_only=True)
        net=ClapModel.from_pretrained(str(model),local_files_only=True,weights_only=True).eval()
        labels=[(g,i,l,t) for g,items in GROUPS.items() for i,l,t in items]
        with torch.inference_mode():
            texts=net.get_text_features(**processor(text=[r[3] for r in labels],return_tensors='pt',padding=True));texts=torch.nn.functional.normalize(texts,dim=-1)
        loaded=time.perf_counter()-load_start
        assets={a['id']:a for a in lab.search()};verified=set();values=[]
        for w in windows:
            if cancel.exists():raise InterruptedError('CANCELLED')
            a=assets[w['asset']]
            if a['id'] not in verified:
                if digest(a['path'])!=a['sha']:raise ValueError('SOURCE_CHANGED')
                verified.add(a['id'])
            cache=folder/'windows'/(w['id']+'.json');cached=None
            if cache.exists():
                cached=json.loads(cache.read_text(encoding='utf-8'))
                if any(cached.get(k)!=w[k] for k in w) or cached.get('modelRevision')!=revision:raise ValueError('SEMANTIC_CACHE_MISMATCH')
            if cached is None:
                info=sf.info(a['path']);audio,rate=sf.read(a['path'],start=round(w['start']*info.samplerate),stop=round(w['end']*info.samplerate),dtype='float32',always_2d=True);audio=audio.mean(axis=1)
                audio=resample_poly(audio,48000//math.gcd(rate,48000),rate//math.gcd(rate,48000)) if rate!=48000 else audio
                with torch.inference_mode():
                    inputs=processor(audio=audio,sampling_rate=48000,return_tensors='pt',padding='repeatpad',truncation='rand_trunc')
                    emb=net.get_audio_features(**inputs);emb=torch.nn.functional.normalize(emb,dim=-1);scores=(emb@texts.T)[0].cpu().numpy()
                groups={g:[] for g in GROUPS}
                for (g,i,l,t),score in zip(labels,scores):groups[g].append(dict(id=i,label=l,text=t,cosine=float(score)))
                cached=dict(w,modelRevision=revision,groups=groups,validation='MODEL_PREDICTION_UNREVIEWED')
                write_json(cache,cached)
            values.append(cached);completed+=1
            import ctypes
            if sys.platform=='win32':
                class Counters(ctypes.Structure):_fields_=[('cb',ctypes.c_ulong),('fault',ctypes.c_ulong)]+[(n,ctypes.c_size_t) for n in ('peak','working','qpp','qpu','qnp','qn','page','peakPage')]
                c=Counters();c.cb=ctypes.sizeof(c);kernel=ctypes.WinDLL('kernel32');kernel.GetCurrentProcess.restype=ctypes.c_void_p
                psapi=ctypes.WinDLL('psapi');psapi.GetProcessMemoryInfo.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_ulong]
                if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(),ctypes.byref(c),c.cb):raise OSError('MEMORY_SAMPLE_FAILED')
                peak=max(peak,c.peak)
            write_json(status,dict(state='PROCESSING',completed=completed,total=total,asset=w['asset'],section=w['section'],elapsedSeconds=time.perf_counter()-started,cpuSeconds=time.process_time()-cpu,peakRssBytes=peak,modelLoadSeconds=loaded,modelRevision=revision,workerPid=os.getpid()))
        for a in assets.values():
            if a['id'] in verified and digest(a['path'])!=a['sha']:raise ValueError('SOURCE_CHANGED_DURING_ANALYSIS')
        songs=[aggregate(json.loads((lab.root/'structure'/(a+'.json')).read_text(encoding='utf-8')),[w for w in values if w['asset']==a],revision) for a in sorted(verified)]
        write_json(folder/'results.json',songs)
        write_json(status,dict(state='READY',completed=completed,total=total,elapsedSeconds=time.perf_counter()-started,cpuSeconds=time.process_time()-cpu,peakRssBytes=peak,modelLoadSeconds=loaded,modelRevision=revision,cacheBytes=sum(p.stat().st_size for p in (folder/'windows').glob('*.json'))))
    except BaseException as error:
        write_json(status,dict(state='CANCELLED' if isinstance(error,InterruptedError) else 'FAILED',completed=completed,total=total,error=str(error),elapsedSeconds=time.perf_counter()-started))
        if not isinstance(error,InterruptedError):raise
    finally:
        lock.unlink(missing_ok=True);lab.db.close()


if __name__=='__main__':
    import sys
    run(sys.argv[1],sys.argv[2])
