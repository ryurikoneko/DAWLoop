"""仅供主进程的Style Lab显式研究操作。"""
import json
from pathlib import Path
import sys
import soundfile as sf
from style_lab import StyleLab, digest
from style_omar import VectorLab

lab=StyleLab(sys.argv[1])
vectors=VectorLab(lab,sys.argv[2])
request=json.loads(sys.stdin.buffer.readline(65537))
method=request['method'];p=request.get('params',{})
allowed={'list':set(),'search':{'query','scope'},'feedback':{'query','candidate','liked'},'profile':{'name','segments'},'clip':{'id'}}
if method not in allowed or set(p)!=allowed[method]:
    raise ValueError('IPC_REJECTED')
rows=vectors.descriptors()
assets={a['id']:a for a in lab.search()}
if method=='list':
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
    row=next(r for r in rows if r['id']==p['id'])
    asset=assets[row['asset']]
    if digest(asset['path'])!=asset['sha']:
        raise ValueError('SOURCE_CHANGED')
    info=sf.info(asset['path'])
    audio,rate=sf.read(asset['path'],start=round(row['start']*info.samplerate),stop=round(row['end']*info.samplerate),dtype='float32',always_2d=True)
    folder=lab.root/'audition';folder.mkdir(exist_ok=True)
    import hashlib
    clip=folder/(hashlib.sha256(row['id'].encode()).hexdigest()+'.wav')
    if not clip.exists():
        sf.write(clip,audio,rate,subtype='PCM_16')
    result=str(clip)
print(json.dumps(result,ensure_ascii=True,allow_nan=False))
