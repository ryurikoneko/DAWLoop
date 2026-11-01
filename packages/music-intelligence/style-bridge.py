"""仅供主进程的Style Lab显式研究操作。"""
import json
from pathlib import Path
import sys
import soundfile as sf
from style_lab import StyleLab, digest
from style_omar import VectorLab
from style_structure import load_analysis,edit_section,full_prompt
from style_quality import audition

lab=StyleLab(sys.argv[1])
request=json.loads(sys.stdin.buffer.readline(65537))
method=request['method'];p=request.get('params',{})
if method.startswith('generation'):
    from style_generation import dispatch
    print(json.dumps(dispatch(lab.root,method,p),ensure_ascii=True,allow_nan=False))
    sys.exit(0)
vectors=VectorLab(lab,sys.argv[2])
allowed={'list':set(),'search':{'query','scope'},'feedback':{'query','candidate','liked'},'profile':{'name','segments'},'clip':{'id'},'song':{'asset'},'sectionEdit':{'asset','index','start','end','label'},'fullPrompt':{'assets'},'fullPromptSave':{'assets','text'},'rangeClip':{'asset','start','end'},'rangeSearch':{'asset','start','end','scope'}}
allowed.update(auditionList=set(),auditionRate={'pair','ratings'},auditionReveal={'pair'},auditionPreview={'pair','side'})
allowed['auditionDisposition']={'pair','status','reason'}
allowed['auditionSummary']=set();allowed['auditionLeaveBlind']=set()
if method=='auditionPreview' and 'mode' in p:allowed['auditionPreview']={'pair','side','mode'}
if method not in allowed or set(p)!=allowed[method]:raise ValueError('IPC_REJECTED')
rows=vectors.descriptors()
assets={a['id']:a for a in lab.search()}
if method in ('auditionDisposition','auditionList','auditionRate','auditionReveal','auditionSummary','auditionLeaveBlind'):
    result=audition(lab,method,p)
elif method=='song':
    result=load_analysis(lab,p['asset'])
elif method=='sectionEdit':
    result=edit_section(lab,p['asset'],p['index'],p['start'],p['end'],p['label'])
elif method in ('fullPrompt','fullPromptSave'):
    result=full_prompt(lab,p['assets'])
    if method=='fullPromptSave':
        if not isinstance(p['text'],str) or not 0<len(p['text'])<=20000:raise ValueError('INVALID_PROMPT')
        result.update(english=p['text'],source='USER_EDITED_FROM_FULL_SONG')
    lab.db.execute('CREATE TABLE IF NOT EXISTS full_prompts(id INTEGER PRIMARY KEY,body TEXT,created REAL)')
    import time
    with lab.db:lab.db.execute('INSERT INTO full_prompts(body,created) VALUES(?,?)',(json.dumps(result),time.time()))
elif method=='rangeSearch':
    import numpy as np
    from style_structure import features
    data,coverage=features(vectors,p['asset'])
    if p['scope'] not in ('cross','within') or not 0<=p['start']<p['end']<=coverage['duration']:raise ValueError('INVALID_RANGE')
    if p['end']-p['start']<1:raise ValueError('RANGE_MINIMUM_ONE_SECOND')
    descriptor=data[int(p['start']):int(np.ceil(p['end']))].mean(axis=0)
    descriptor/=max(np.linalg.norm(descriptor),1e-12)
    result=[]
    for row in rows:
        if p['scope']=='cross' and row['asset']==p['asset'] or p['scope']=='within' and row['asset']!=p['asset']:continue
        if row['asset']==p['asset'] and row['start']<p['end']+10 and row['end']>p['start']-10:continue
        cosine=float(np.dot(descriptor,row['vector']))
        result.append(dict(id=row['id'],asset=row['asset'],name=assets[row['asset']]['name'],start=row['start'],end=row['end'],cosine=cosine,score=cosine,preference=0))
    result=sorted(result,key=lambda r:(-r['score'],r['id']))[:5]
elif method=='list':
    result=[dict(id=r['id'],asset=r['asset'],name=assets[r['asset']]['name'],start=r['start'],end=r['end']) for r in rows]
elif method=='search':
    if p['scope'] not in ('cross','within'):
        raise ValueError('IPC_REJECTED')
    result=vectors.search(p['query'],p['scope'])
    for r in result:
        r['name']=assets[r['asset']]['name']
elif method=='feedback':
    vectors.feedback(p['query'],p['candidate'],p['liked'])
    result=True
elif method=='profile':
    result=vectors.save_profile(p['name'],p['segments'])
else:
    if method=='auditionPreview':
        row=audition(lab,'auditionClip',p)
    elif method=='rangeClip':
        import math
        row=p
        if not all(type(v) in (int,float) and math.isfinite(v) for v in (row['start'],row['end'])) or not 0<=row['start']<row['end'] or row['end']-row['start']>7200:raise ValueError('INVALID_RANGE')
    else:
        row=next(r for r in rows if r['id']==p['id'])
    asset=assets[row['asset']]
    if digest(asset['path'])!=asset['sha']:
        raise ValueError('SOURCE_CHANGED')
    info=sf.info(asset['path'])
    if row['end']>info.duration:raise ValueError('INVALID_RANGE')
    audio,rate=sf.read(asset['path'],start=round(row['start']*info.samplerate),stop=round(row['end']*info.samplerate),dtype='float32',always_2d=True)
    folder=lab.root/'audition';folder.mkdir(exist_ok=True)
    import hashlib
    clip=folder/(hashlib.sha256(f"{row['asset']}:{row['start']}:{row['end']}".encode()).hexdigest()+'.wav')
    if not clip.exists():
        sf.write(clip,audio,rate,subtype='PCM_16')
    result=str(clip)
print(json.dumps(result,ensure_ascii=True,allow_nan=False))
