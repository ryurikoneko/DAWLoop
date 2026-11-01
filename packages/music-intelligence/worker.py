"""隔离音频与符号任务；仅接受服务签发的本地资产，不访问宿主。"""
import sys,json,math,hashlib,time,heapq
from pathlib import Path
import numpy as np
import soundfile as sf
import librosa
import mido

def emit(kind, **data):
    print(json.dumps(dict(schemaVersion=1,kind=kind,**data),allow_nan=False),flush=True)

def validate(score):
    assert score.get('schemaVersion')==1 and 20<=score['tempo']<=300,'INVALID_SCORE'
    notes=score['notes'];assert len(notes)<=20000,'SCORE_TOO_LARGE'
    for n in notes:
        assert all(type(n[k]) in (int,float) and math.isfinite(n[k]) for k in ('pitch','start','duration','velocity','part')),'INVALID_NOTE'
        assert int(n['pitch'])==n['pitch'] and int(n['velocity'])==n['velocity'] and int(n['part'])==n['part'] and 0<=n['pitch']<=127 and 0<=n['start']<=86400 and 0<n['duration']<=3600 and 1<=n['velocity']<=127 and 0<=n['part']<=15,'INVALID_NOTE'
    bends=score.get('pitchBends',[]);assert len(bends)<=50000,'SCORE_TOO_LARGE'
    for b in bends:
        assert all(type(b[k]) in (int,float) and math.isfinite(b[k]) for k in ('start','value','part')) and 0<=b['start']<=86400 and type(b['value'])==int and -8192<=b['value']<=8191 and type(b['part'])==int and 0<=b['part']<=15,'INVALID_PITCH_BEND'
    return score

def write_midi(score,path):
    validate(score);mid=mido.MidiFile(ticks_per_beat=480)
    meta=mido.MidiTrack();mid.tracks.append(meta)
    tempo_map=score.get('tempoMap') or [dict(start=0,bpm=score['tempo'])]
    assert len(tempo_map)<=10000,'TEMPO_MAP_TOO_LARGE'
    previous=0
    for event in sorted(tempo_map,key=lambda e:e['start']):
        assert math.isfinite(event['start']) and event['start']>=0 and 20<=event['bpm']<=300,'INVALID_TEMPO_MAP'
        tick=round(event['start']*480);meta.append(mido.MetaMessage('set_tempo',tempo=mido.bpm2tempo(event['bpm']),time=tick-previous));previous=tick
    meter=score.get('meter',[4,4]);assert meter[0] in range(1,33) and meter[1] in (1,2,4,8,16,32),'INVALID_METER'
    meta.insert(0,mido.MetaMessage('time_signature',numerator=meter[0],denominator=meter[1],time=0))
    for part in sorted(set(n['part'] for n in score['notes'])|set(b['part'] for b in score.get('pitchBends',[]))):
        lanes=[[]];pitch_lanes={}
        # MIDI事件没有noteId；同音高重叠需独立事件轨道才能无歧义读回，不改变原通道。
        for n in sorted((n for n in score['notes'] if n['part']==part),key=lambda n:(round(n['start']*480),round((n['start']+n['duration'])*480))):
            start=round(n['start']*480);end=round((n['start']+n['duration'])*480)
            assert end>start,'MIDI_NOTE_BELOW_TICK_RESOLUTION'
            heap=pitch_lanes.setdefault(n['pitch'],[])
            lane=heapq.heappop(heap)[1] if heap and heap[0][0]<=start else len(heap)
            heapq.heappush(heap,(end,lane))
            if lane==len(lanes):lanes.append([])
            lanes[lane].extend([(start,1,mido.Message('note_on',channel=int(part),note=int(n['pitch']),velocity=int(n['velocity']))),(end,0,mido.Message('note_off',channel=int(part),note=int(n['pitch']),velocity=0))])
        for b in score.get('pitchBends',[]):
            if b['part']==part:lanes[0].append((round(b['start']*480),0,mido.Message('pitchwheel',channel=part,pitch=b['value'])))
        for events in lanes:
            tr=mido.MidiTrack();mid.tracks.append(tr);prev=0
            for tick,_,msg in sorted(events,key=lambda e:(e[0],e[1])):msg.time=tick-prev;tr.append(msg);prev=tick
    mid.save(path)
    restored=read_midi(path)
    key=lambda n:(int(n['part']),int(n['pitch']),round(n['start']*480),round((n['start']+n['duration'])*480)-round(n['start']*480),int(n['velocity']))
    assert sorted(map(key,score['notes']))==sorted(map(key,restored['notes'])),'MIDI_READBACK_MISMATCH'
    bend_key=lambda b:(b['part'],round(b['start']*480),b['value'])
    assert sorted(map(bend_key,score.get('pitchBends',[])))==sorted(map(bend_key,restored['pitchBends'])),'MIDI_BEND_READBACK_MISMATCH'
    return dict(schemaVersion=1,notes=len(score['notes']),verified=True,sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest())

def read_midi(path):
    mid=mido.MidiFile(path);assert mid.type!=2,'MIDI_TYPE_UNSUPPORTED'
    notes=[];bends=[];tempo=120;meter=[4,4];tempo_map=[]
    for tr in mid.tracks:
        tick=0;active={}
        for msg in tr:
            tick+=msg.time
            if msg.type=='set_tempo':tempo_map.append(dict(start=tick/mid.ticks_per_beat,bpm=mido.tempo2bpm(msg.tempo)));tempo=tempo_map[0]['bpm']
            if msg.type=='time_signature':meter=[msg.numerator,msg.denominator]
            if msg.type=='pitchwheel':bends.append(dict(start=tick/mid.ticks_per_beat,value=msg.pitch,part=msg.channel))
            if msg.type not in ('note_on','note_off'):continue
            k=(msg.channel,msg.note)
            if msg.type=='note_on' and msg.velocity:
                assert k not in active,'OVERLAPPING_SAME_PITCH_UNSUPPORTED';active[k]=(tick,msg.velocity)
            elif k in active:
                start,vel=active.pop(k);notes.append(dict(part=msg.channel,pitch=msg.note,start=start/mid.ticks_per_beat,duration=(tick-start)/mid.ticks_per_beat,velocity=vel))
        assert not active,'UNTERMINATED_NOTE'
    return validate(dict(schemaVersion=1,tempo=tempo,meter=meter,tempoMap=tempo_map,notes=notes,pitchBends=bends,source='USER_EDITED',edits=[]))

def analyze(path,start,end):
    import importlib.util
    spec=importlib.util.spec_from_file_location('dawloop_song_dsp',Path(__file__).with_name('song-dsp.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module.analyze(path,start,end,emit)

def waveform(path):
    with sf.SoundFile(path) as f:
        peaks=np.zeros(1024);frames=f.frames;position=0
        while True:
            block=f.read(65536,dtype='float32',always_2d=True)
            if not len(block):break
            values=np.abs(block).max(axis=1)
            bins=np.minimum(1023,((np.arange(len(block))+position)*1024/max(1,frames)).astype(int))
            np.maximum.at(peaks,bins,values);position+=len(block)
        return dict(assetId=None,duration=frames/f.samplerate,peaks=peaks.tolist())

def main():
    raw=sys.stdin.buffer.readline(1048577);assert len(raw)<=1048576,'REQUEST_TOO_LARGE'
    request=json.loads(raw);assert request['schemaVersion']==1,'SCHEMA_REJECTED'
    method=request['method'];p=request['params']
    if method=='status':value=dict(provider='basic',version=librosa.__version__,python=sys.version.split()[0])
    elif method=='analyze':value=analyze(p['path'],p.get('start',0),p.get('end'))
    elif method=='reviewOffsets':
        import importlib.util
        spec=importlib.util.spec_from_file_location('dawloop_offset_review',Path(__file__).with_name('offset-review.py'));module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);value=module.review_offsets(p['path'],p['score'])
    elif method=='waveform':value=waveform(p['path'])
    elif method=='readMidi':value=read_midi(p['path'])
    elif method=='writeMidi':value=write_midi(p['score'],p['path'])
    else:raise ValueError('METHOD_UNAVAILABLE')
    emit('result',data=value)

if __name__=='__main__':
    try:main()
    except Exception as e:emit('error',code=str(e) if str(e).isupper() else 'MI_WORKER_FAILED',detail=f'{type(e).__name__}: {e}'[:2000]);sys.exit(1)
