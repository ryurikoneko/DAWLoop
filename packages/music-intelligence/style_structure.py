"""整曲覆盖、向量自相似和可编辑结构候选；不把几何变化命名为副歌。"""
import json
import math
from pathlib import Path
import time
import numpy as np
import soundfile as sf
from style_lab import digest


def coverage(vectors, asset):
    a=vectors.lab.db.execute('SELECT * FROM assets WHERE id=?',(asset,)).fetchone()
    if not a or digest(a['path'])!=a['sha']:raise ValueError('SOURCE_CHANGED')
    info=sf.info(a['path'])
    intervals=[];frames=0
    for r in vectors.lab.db.execute("SELECT * FROM vectors WHERE asset=? AND version=? AND state='READY' ORDER BY start",(asset,vectors.version)):
        meta=json.loads(r['metadata']);p=vectors.root/r['filename']
        if meta['sourceSha256']!=a['sha'] or digest(p)!=meta['vectorSha256']:
            raise ValueError('COVERAGE_SOURCE_MISMATCH')
        data=np.load(p,allow_pickle=False)
        times=np.asarray(meta['globalTimestamps'])
        expected=np.arange(len(data))/25+r['start']
        if data.shape!=(len(times),1024) or not np.isfinite(data).all() or not np.allclose(times,expected,atol=1e-8) or len(times)==0:
            raise ValueError('COVERAGE_FRAME_GRID_REJECTED')
        first=round(r['start']*info.samplerate)
        last=min(info.frames,round(r['end']*info.samplerate))
        if times[-1]+.04 < last/info.samplerate-1/info.samplerate:
            raise ValueError('COVERAGE_VECTOR_TAIL_MISSING')
        intervals.append((first,last));frames+=len(data)
    cursor=0;gaps=[];covered=0
    for start,end in intervals:
        if start>cursor:gaps.append([cursor,start])
        covered+=max(0,end-max(cursor,start));cursor=max(cursor,end)
    if cursor<info.frames:gaps.append([cursor,info.frames])
    return dict(sourceFrames=info.frames,sampleRate=info.samplerate,duration=info.duration,coveredFrames=covered,coveredSeconds=covered/info.samplerate,coverage=covered/info.frames,gaps=gaps,frameCountWithOverlap=frames,intervals=intervals,complete=not gaps and covered==info.frames)


def features(vectors,asset,seconds=1):
    report=coverage(vectors,asset)
    if not report['complete']:raise ValueError('FULL_SONG_COVERAGE_REQUIRED')
    rows=vectors.lab.db.execute("SELECT * FROM vectors WHERE asset=? AND version=? AND state='READY' ORDER BY start",(asset,vectors.version)).fetchall()
    n=math.ceil(report['duration']/seconds);total=np.zeros((n,1024));count=np.zeros(n)
    for i,r in enumerate(rows):
        values=np.load(vectors.root/r['filename'],allow_pickle=False)
        times=np.asarray(json.loads(r['metadata'])['globalTimestamps'])
        # 重叠区按后窗起点分配，原序列另存不删除；尾窗归属一直到实际终点。
        end=rows[i+1]['start'] if i+1<len(rows) else report['duration']
        keep=(times>=r['start'])&(times<end)
        bins=np.minimum(n-1,(times[keep]/seconds).astype(int))
        np.add.at(total,bins,values[keep]);np.add.at(count,bins,1)
    if np.any(count==0):raise ValueError('EMPTY_TIMELINE_BIN')
    total/=count[:,None]
    return total,report


def section_analysis(vectors,asset):
    from scipy.signal import find_peaks
    started=time.perf_counter();x,covered=features(vectors,asset)
    # 去除本曲公共分量只用于结构对比，不能解释为乐器或情绪预测。
    centered=x-x.mean(axis=0)
    normalized=centered/np.maximum(np.linalg.norm(centered,axis=1,keepdims=True),1e-12)
    similarity=normalized@normalized.T
    novelty=np.zeros(len(x));radius=8
    for t in range(radius,len(x)-radius):
        left=normalized[t-radius:t].mean(axis=0);right=normalized[t:t+radius].mean(axis=0)
        novelty[t]=float(np.dot(left,left)+np.dot(right,right)-2*np.dot(left,right))
    candidates,_=find_peaks(novelty,distance=12,prominence=max(.03,float(np.std(novelty))*.5))
    bounds=[0]+[int(p) for p in candidates if 8<=p<covered['duration']-8]+[covered['duration']]
    # 以现有全曲DSP记录取测量，不用短片段结果冒充整曲。
    jobs=vectors.lab.db.execute("SELECT * FROM jobs WHERE asset=? AND state='READY' AND start=0 AND end IS NULL ORDER BY rowid DESC",(asset,)).fetchall()
    if not jobs:raise ValueError('FULL_SONG_DSP_REQUIRED')
    dsp=json.loads((vectors.lab.root/jobs[0]['result']).read_text(encoding='utf-8'))
    if dsp.get('sourceSha256')!=vectors.lab.db.execute('SELECT sha FROM assets WHERE id=?',(asset,)).fetchone()[0] or dsp['measurements']['version']!='SONG_DSP_1':
        raise ValueError('DSP_SOURCE_CHANGED')
    if abs(dsp['range'][1]-covered['duration'])>1/covered['sampleRate']:raise ValueError('DSP_FULL_RANGE_REQUIRED')
    assetrow=vectors.lab.db.execute('SELECT * FROM assets WHERE id=?',(asset,)).fetchone()
    sections=[];vectors_section=[]
    for i,(start,end) in enumerate(zip(bounds,bounds[1:])):
        local=normalized[int(start):math.ceil(end)]
        section_vector=local.mean(axis=0);vectors_section.append(section_vector/max(np.linalg.norm(section_vector),1e-12))
        def local_curve(key):return [p[1] for p in dsp[key] if start<=p[0]<end]
        energy=local_curve('energy');centroid=local_curve('spectralCentroid')
        beats=np.asarray([b for b in dsp['beats'] if start<=b<end]);interval=np.diff(beats)
        tempo=float(60/np.median(interval)) if len(interval)>3 else None
        sections.append(dict(id=i,start=start,end=end,label='Unknown',labelSource='UNASSIGNED',confidence=None,novelty=float(novelty[int(start)]) if start<len(novelty) else None,rmsMean=float(np.mean(energy)) if energy else None,centroidMean=float(np.mean(centroid)) if centroid else None,bpmCandidate=tempo,bpmConfidence='low',relationToPrevious=None if i==0 else float(np.dot(vectors_section[i],vectors_section[i-1])),repeats=[]))
    pairs=[]
    for i in range(len(sections)):
        for j in range(i+1,len(sections)):
            if j-i<2:continue
            score=float(np.dot(vectors_section[i],vectors_section[j]));pairs.append(dict(a=i,b=j,similarity=score))
    # 排名候选而非固定相似阈值认定重复，保留相邻声学轨迹复核位置。
    for p in sorted(pairs,key=lambda p:-p['similarity'])[:min(8,len(pairs))]:
        sections[p['a']]['repeats'].append(dict(section=p['b'],similarity=p['similarity'],status='CANDIDATE'))
    result=dict(schemaVersion=1,method='OMAR_L6_centered_1s_checkerboard8s_peaks12s_v1',asset=asset,name=assetrow['name'],sourceSha256=assetrow['sha'],vectorVersion=vectors.version,coverage=covered,dspJob=jobs[0]['id'],sections=sections,novelty=novelty.tolist(),selfSimilarity=np.round(similarity,4).tolist(),curves=dict(energy=dsp['energy'],centroid=dsp['spectralCentroid']),loudness=dsp['measurements']['lufs'],key=dsp['measurements']['key'],bpmCandidates=dsp['bpmCandidates'],semantic=dict(instruments=None,mood=None,arrangement=None,chords=None),elapsedSeconds=time.perf_counter()-started)
    return result


def store_analysis(vectors,asset):
    result=section_analysis(vectors,asset)
    folder=vectors.lab.root/'structure';folder.mkdir(exist_ok=True)
    p=folder/(asset+'.json');temporary=p.with_suffix('.tmp')
    temporary.write_text(json.dumps(result,ensure_ascii=False,allow_nan=False),encoding='utf-8');temporary.replace(p)
    return result


def load_analysis(lab,asset):
    if not isinstance(asset,str) or len(asset)!=24 or any(c not in '0123456789abcdef' for c in asset):raise ValueError('INVALID_ASSET')
    result=json.loads((lab.root/'structure'/(asset+'.json')).read_text(encoding='utf-8'))
    a=lab.db.execute('SELECT * FROM assets WHERE id=?',(asset,)).fetchone()
    if not a or digest(a['path'])!=result['sourceSha256']:raise ValueError('SOURCE_CHANGED')
    lab.db.execute('CREATE TABLE IF NOT EXISTS structure_edits(id INTEGER PRIMARY KEY,asset TEXT,section INTEGER,start REAL,end REAL,label TEXT,created REAL)')
    for edit in lab.db.execute('SELECT * FROM structure_edits WHERE asset=? ORDER BY id',(asset,)):
        s=result['sections'][edit['section']]
        if s['start']!=edit['start'] or s['end']!=edit['end']:
            s.update(rmsMean=None,centroidMean=None,bpmCandidate=None,repeats=[],summaryNeedsRefresh=True)
        s.update(start=edit['start'],end=edit['end'],label=edit['label'],labelSource='USER_EDITED')
    return result


def edit_section(lab,asset,index,start,end,label):
    result=load_analysis(lab,asset)
    if type(index)!=int or not 0<=index<len(result['sections']) or not isinstance(label,str) or not 1<=len(label)<=60 or not all(math.isfinite(v) for v in (start,end)) or not 0<=start<end<=result['coverage']['duration']:raise ValueError('INVALID_SECTION_EDIT')
    # 段落始终连续，移动共享边界会同时更新邻段，不留下虚假全曲覆盖。
    sections=result['sections'];updates=[(index,start,end,label)]
    if index==0 and start!=0 or index==len(sections)-1 and end!=result['coverage']['duration']:raise ValueError('ENDPOINT_LOCKED')
    if index:
        prev=sections[index-1]
        if start<=prev['start']:raise ValueError('BOUNDARY_ORDER')
        updates.append((index-1,prev['start'],start,prev['label']))
    if index+1<len(sections):
        nxt=sections[index+1]
        if end>=nxt['end']:raise ValueError('BOUNDARY_ORDER')
        updates.append((index+1,end,nxt['end'],nxt['label']))
    with lab.db:
        for i,a,b,name in updates:lab.db.execute('INSERT INTO structure_edits(asset,section,start,end,label,created) VALUES(?,?,?,?,?,?)',(asset,i,a,b,name,time.time()))
    return load_analysis(lab,asset)


def full_prompt(lab,assets):
    results=[load_analysis(lab,a) for a in dict.fromkeys(assets)]
    if not results:raise ValueError('NO_SONGS_SELECTED')
    evidence=[];phrases=['Create an original composition.']
    for r in results:
        if not r['coverage']['complete']:raise ValueError('FULL_SONG_COVERAGE_REQUIRED')
        evidence.append(dict(asset=r['asset'],range=[0,r['coverage']['duration']],method=r['method'],sections=[dict(start=s['start'],end=s['end'],rms=s.get('rmsMean'),centroid=s.get('centroidMean')) for s in r['sections']]))
    tempos=[v for r in results for v in r['bpmCandidates']]
    if tempos:phrases.append(f"Explore a tempo around {np.median(tempos):.0f} BPM, an estimate available for {len(tempos)} of {len(results)} references.")
    lengths=[s['end']-s['start'] for r in results for s in r['sections']]
    phrases.append(f"Develop contrasting passages on an approximately {np.median(lengths):.0f}-second scale, then revisit earlier material with variation.")
    phrases.append('Shape energy and spectral brightness across the full arrangement; write an original melody and harmony.')
    preferences=[dict(row) for row in lab.db.execute('SELECT * FROM ratings ORDER BY created') if row['asset'] in assets]
    for p in preferences:
        if p['likes']:phrases.append('User preference: '+p['likes']+'.')
        if p['avoids']:phrases.append('Avoid: '+p['avoids']+'.')
    return dict(english=' '.join(phrases),evidence=evidence,preferences=preferences,source='FULL_SONG_RULE_ASSISTED',unresolved=['instrumentation','mood','verified_chord_progression','section_function'],structureSuggestionIsCreative=True)
