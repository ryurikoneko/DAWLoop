"""递归全库研究，逐层验收并保留逐曲失败原因。"""
import argparse
import hashlib
import json
from pathlib import Path
import time
import numpy as np
import soundfile as sf
from style_lab import StyleLab,digest
from style_omar import VectorLab
from style_structure import coverage,store_analysis,full_prompt


def save(path,data):
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');temporary.replace(path)


def batch(root,folder,runtime):
    started=time.perf_counter();lab=StyleLab(root);v=VectorLab(lab,runtime)
    report_root=lab.root/'phase3-library';report_root.mkdir(exist_ok=True)
    files=sorted(Path(folder).rglob('*'));files=[p for p in files if p.is_file()]
    inventory=[];pcm_seen={};ids=[]
    for p in files:
        entry=dict(path=str(p),name=p.name,extension=p.suffix.lower(),status='DISCOVERED')
        inventory.append(entry)
        if p.suffix.lower() not in ('.mp3','.wav','.flac'):
            entry.update(status='SKIPPED',reason='UNSUPPORTED_EXTENSION');continue
        try:
            info=sf.info(p);entry.update(duration=info.duration,frames=info.frames,rate=info.samplerate,channels=info.channels,sha256=digest(p))
            if not 0<info.duration<=7200:raise ValueError('DURATION_BUDGET')
            pcm=hashlib.sha256();decoded_frames=0
            pcm.update(f'{info.samplerate}:{info.channels}:FLOAT32'.encode())
            with sf.SoundFile(p) as audio:
                while True:
                    block=audio.read(65536,dtype='float32',always_2d=True)
                    if not len(block):break
                    if not np.isfinite(block).all():raise ValueError('NONFINITE_AUDIO')
                    pcm.update(block.astype('<f4',copy=False).tobytes());decoded_frames+=len(block)
            if decoded_frames!=info.frames:raise ValueError('DECODE_INCOMPLETE')
            entry['decodedPcmSha256']=pcm.hexdigest()
            if pcm.hexdigest() in pcm_seen:
                entry.update(status='DUPLICATE_DECODED_RECORDING',duplicateOf=pcm_seen[pcm.hexdigest()]);continue
            identity=lab.import_audio([p])[0];entry['asset']=identity;pcm_seen[pcm.hexdigest()]=identity
            name=p.stem;artists=name.split(' - ')[0].split(',') if ' - ' in name else []
            entry['credits']=dict(rawFilename=name,artists=artists,collaboration=len(artists)>1 or 'feat.' in name.lower(),remix='remix' in name.lower(),instrumental='instrumental' in name.lower(),attribution='FILENAME_ONLY_PENDING_OWNER_REVIEW',recordingRelationship='EXACT_PCM_DEDUP_ONLY; LOSSY_REENCODE_RELATION_UNKNOWN')
            entry['status']='VALID';ids.append(identity)
            lab.enqueue(identity)
        except Exception as error:entry.update(status='FAILED',reason=str(error))
    save(report_root/'inventory.json',dict(scannedFiles=len(files),validIndependentRecordings=len(ids),files=inventory))
    print(json.dumps(dict(scanFiles=len(files),validIndependentRecordings=len(ids))),flush=True)
    # 原独立缓存2GiB预算逐项执行，失败留状态，不删除别曲结果。
    lab.run(cache_limit=4*1024**3)
    v.plan(ids);vector_result=v.run(cancelled=lambda:(report_root/'CANCEL').exists())
    songs=[]
    for identity in ids:
        entry=next(e for e in inventory if e.get('asset')==identity)
        song=dict(asset=identity,name=entry['name'],duration=entry['duration'],credits=entry['credits'])
        try:
            result=store_analysis(v,identity)
            song.update(status='COMPLETE_MEASURED_STRUCTURE_CANDIDATES',coverage=result['coverage'],sections=result['sections'],lufs=result['loudness'],key=result['key'],bpm=result['bpmCandidates'],semantic=result['semantic'])
        except Exception as error:
            song.update(status='INCOMPLETE',reason=str(error),jobs=[dict(r) for r in lab.db.execute('SELECT state,error FROM jobs WHERE asset=?',(identity,))])
        song['sourceUnchanged']=digest(entry['path'])==entry['sha256'];songs.append(song)
    descriptors=v.descriptors()
    groups=v.clusters(5) if descriptors else []
    complete=[s['asset'] for s in songs if s['status']=='COMPLETE_MEASURED_STRUCTURE_CANDIDATES']
    profile=full_prompt(lab,complete) if complete else None
    links=[]
    for identity in ids:
        selected=[r for r in descriptors if r['asset']==identity]
        if selected:
            query=selected[len(selected)//2]
            links.append(dict(asset=identity,query={k:w for k,w in query.items() if k!='vector'},matches=v.search(query['id'],'cross',3)))
    report=dict(scannedFiles=len(files),validIndependentRecordings=len(ids),completedSongs=sum(s['status']=='COMPLETE_MEASURED_STRUCTURE_CANDIDATES' for s in songs),songs=songs,skips=[e for e in inventory if e['status']!='VALID'],vectorRun=vector_result,elapsedSeconds=time.perf_counter()-started,vectorDiskBytes=sum(p.stat().st_size for p in v.root.glob('*.npy')),cacheBytes=sum(p.stat().st_size for p in (lab.root/'decode').glob('*')),clusters=groups,crossSongLinks=links,profile=profile,retrievalQuality='UNVALIDATED_HIGH_RAW_COSINE_BASELINE',humanAudition='NOT_TESTED',cpuGpuUtilization='NOT_SAMPLED_CPU_ONLY_MODEL',semantics='NOT_RELIABLY_IDENTIFIED')
    save(report_root/'report.json',report)
    print(json.dumps(dict(completedSongs=report['completedSongs'],total=len(ids),elapsedSeconds=report['elapsedSeconds'],peakRssBytes=vector_result.get('peakRssBytes'))),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--folder',required=True);p.add_argument('--runtime',required=True);a=p.parse_args();batch(a.root,a.folder,a.runtime)
