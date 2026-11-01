"""工作台的秒轴数据适配；模型原始文件不参与编辑写入。"""
import sys,json,wave,traceback,collections
from pathlib import Path
import numpy as np
import soundfile as sf
import mido,pretty_midi
sys.stdin.reconfigure(encoding='utf-8')
sys.stdout.reconfigure(encoding='utf-8')

def emit(data):print(json.dumps(dict(schemaVersion=1,kind='result',data=data),allow_nan=False),flush=True)
def inspect(p):
 y,sr=sf.read(p['path'],dtype='float32',always_2d=True);x=y.mean(axis=1)
 sf.write(p['wav'],x,sr,subtype='PCM_16')
 peaks=[float(np.max(np.abs(a))) for a in np.array_split(x,min(1600,len(x))) if len(a)]
 return dict(duration=len(x)/sr,sampleRate=sr,peaks=peaks)
def midi_data(path):
 m=pretty_midi.PrettyMIDI(str(path));mid=mido.MidiFile(str(path));elapsed=0;tempo=[]
 for msg in mid:
  elapsed+=msg.time
  if msg.type=='set_tempo':tempo.append(dict(time=elapsed,bpm=mido.tempo2bpm(msg.tempo)))
 return m,tempo
def restore(p):
 folder=Path(p['folder']);ref=json.loads((folder/'composer-reference.json').read_text(encoding='utf-8')) if (folder/'composer-reference.json').exists() else {}
 tracks=[];tempo=[]
 for id,file in [('vocal','Suno_Vocal.mid'),('melody','Suno_Melody.mid'),('chords','Suno_Chords.mid'),('bass','Suno_Bass.mid')]:
  target=folder/file
  if not target.exists():continue
  m,t=midi_data(target);tempo=tempo or t
  notes=[dict(id=f'{id}-{i}-{j}',pitch=n.pitch,start=n.start,end=n.end,velocity=n.velocity) for i,ins in enumerate(m.instruments) for j,n in enumerate(ins.notes)]
  tracks.append(dict(id=id,notes=notes,provenance='RECONSTRUCTED_FROM_LABEL' if id=='chords' else 'LOW_REGISTER_CANDIDATE' if id=='bass' else 'MODEL_PREDICTION'))
 if (folder/'Suno_Combined.mid').exists():_,tempo=midi_data(folder/'Suno_Combined.mid')
 return dict(tracks=tracks,tempo=tempo,chords=ref.get('chords',[]),keys=ref.get('keys',[]),structure=ref.get('structure',[]),beats=ref.get('beats',[]),rawDirectory=str(folder))
def sheet_result(p):
 folder=Path(p['folder']);tracks=[]
 m,tempo=midi_data(folder/'transcription.mid')
 for ins in m.instruments:
  id='chords' if ins.name=='Chords' else 'vocal' if 'vocal' in ins.name.lower() else 'melody'
  tracks.append(dict(id=id,notes=[dict(id=f'{id}-{i}',pitch=n.pitch,start=n.start,end=n.end,velocity=n.velocity) for i,n in enumerate(ins.notes)],provenance='RECONSTRUCTED_FROM_LABEL' if id=='chords' else 'MODEL_PREDICTION'))
 def lab(name):return [l.split() for l in (folder/name).read_text(encoding='utf-8').splitlines() if l.strip()]
 chords=[dict(start=float(a),end=float(b),label=c,confidence='UNCALIBRATED_MODEL_PREDICTION',voicing='RECONSTRUCTED_FROM_LABEL') for a,b,c in lab('chord.lab')]
 # 原始播放MIDI可能固定tempo；实际拍点用于建立秒轴tempo map。
 beats=lab('beat.lab');tempo=[dict(time=0,bpm=100)]
 for a,b in zip(beats,beats[1:]):
  dt=float(b[0])-float(a[0]);bpm=60*4/int(a[3])/dt
  if 20<=bpm<=300:tempo.append(dict(time=float(a[0]),bpm=bpm))
 return dict(tracks=tracks,tempo=tempo,chords=chords,keys=lab('key.lab'),structure=lab('structure.lab'),beats=beats,rawDirectory=str(folder))
def export(p):
 s=p['session'];tempo=sorted(s['tempo'] or [dict(time=0,bpm=120)],key=lambda r:r['time'])
 if tempo[0]['time']>0:tempo.insert(0,dict(time=0,bpm=tempo[0]['bpm']))
 points=[];tick=0;prev=0;bpm=tempo[0]['bpm']
 for r in tempo:
  tick+=(r['time']-prev)*960*bpm/60;points.append((r['time'],tick,r['bpm']));prev=r['time'];bpm=r['bpm']
 def to_tick(t):
  a,b,c=next((r for r in reversed(points) if r[0]<=t),points[0]);return round(b+(t-a)*960*c/60)
 mid=mido.MidiFile(type=1,ticks_per_beat=960);meta=mido.MidiTrack();mid.tracks.append(meta);last=0
 for a,t,b in points:
  at=round(t);meta.append(mido.MetaMessage('set_tempo',tempo=round(60e6/b),time=at-last));last=at
 if s.get('beats'):
  numerator,denominator=collections.Counter((int(b[2]),int(b[3])) for b in s['beats']).most_common(1)[0][0];meta.insert(0,mido.MetaMessage('time_signature',numerator=numerator,denominator=denominator))
 expected=[];channels=[0,1,2,3,4,5,6,7,8,10,11,12,13,14,15];active={}
 selected=[(i,tr) for i,tr in enumerate(s['tracks']) if p['track']=='combined' or tr['id']==p['track']]
 # 同音高尾音重叠不能共享通道，否则目标音源与回读器会提前结束重复音。
 for start,i,n in sorted(((n['start'],i,n) for i,tr in selected for n in tr['notes']),key=lambda row:(row[0],row[1],row[2]['pitch'],row[2]['end'])):
  preferred=channels[i];available=[c for c in [preferred]+[c for c in channels if c!=preferred] if active.get((c,n['pitch']),-1)<=start]
  assert available,'STUDIO_MIDI_VOICE_LIMIT'
  n['_channel']=available[0];active[(available[0],n['pitch'])]=n['end']
 for channel,tr in enumerate(s['tracks']):
  if p['track']!='combined' and tr['id']!=p['track']:continue
  track=mido.MidiTrack();mid.tracks.append(track);track.append(mido.MetaMessage('track_name',name=tr['id']));ev=[]
  for n in tr['notes']:
   a,b=to_tick(n['start']),to_tick(n['end']);assert b>a,'STUDIO_NOTE_TOO_SHORT'
   ev.extend([(a,1,n),(b,0,n)]);expected.append(n)
  last=0
  for t,on,n in sorted(ev,key=lambda e:(e[0],e[1])):
   track.append(mido.Message('note_on' if on else 'note_off',channel=n['_channel'],note=n['pitch'],velocity=n['velocity'] if on else 0,time=t-last));last=t
 target=Path(p['path']);mid.save(str(target));actual=[n for ins in pretty_midi.PrettyMIDI(str(target)).instruments for n in ins.notes]
 assert len(actual)==len(expected),'STUDIO_MIDI_COUNT_MISMATCH'
 a=sorted(actual,key=lambda n:(n.pitch,n.start,n.end));b=sorted(expected,key=lambda n:(n['pitch'],n['start'],n['end']))
 error=max([max(abs(x.start-y['start']),abs(x.end-y['end'])) for x,y in zip(a,b)] or [0])
 assert error<.003 and all(x.pitch==y['pitch'] and x.velocity==y['velocity'] for x,y in zip(a,b)),'STUDIO_MIDI_READBACK_FAILED'
 return dict(path=str(target),notes=len(actual),maxErrorSeconds=error)
for line in sys.stdin:
 try:
  r=json.loads(line);emit({'inspect':inspect,'restore':restore,'sheetResult':sheet_result,'export':export}[r['method']](r['params']))
 except Exception as e:
  print(json.dumps(dict(schemaVersion=1,kind='error',code=str(e) if str(e).isupper() else 'STUDIO_WORKER_FAILED',detail=str(e))),flush=True)
