"""锁定 SheetSage2 与父模型的只读转录；仅使用官方 waveform 接口。"""
import base64
import sys,json,importlib,importlib.util,hashlib,time,contextlib,io,wave
from pathlib import Path

def emit(data):
    print(json.dumps(dict(schemaVersion=1,kind='result',data=data),allow_nan=False),flush=True)

def main():
    spec=importlib.util.spec_from_file_location('memory_guard',Path(__file__).with_name('model-worker.py'));guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard);handle=guard.protect_memory();model=None
    for raw in sys.stdin.buffer:
        assert len(raw)<=65536,'MI_REQUEST_TOO_LARGE';r=json.loads(raw);assert r['schemaVersion']==1,'MI_SCHEMA_REJECTED';p=r['params'];started=time.monotonic()
        if r['method']=='load':
            models=json.loads(Path(p['manifest']).read_text(encoding='utf-8'));assert len(models)==2,'MI_MODEL_HASH_REJECTED'
            assert models[0]['revision']=='32c7c7473e7b59e1ed36bd8a8fefbd11ae8d468a' and models[1]['revision']=='d8ba1c745e733b3908ce6ad16ebeb17ac7600a42','MI_MODEL_HASH_REJECTED'
            for m in models:
                for row in m['files']:
                    file=Path(m['folder'])/row['name'];assert file.parent==Path(m['folder']) and not file.is_symlink(),'MI_MODEL_HASH_REJECTED'
                    digest=hashlib.sha256()
                    with file.open('rb') as stream:
                        for b in iter(lambda:stream.read(1024*1024),b''):digest.update(b)
                    assert digest.hexdigest()==row['sha256'],'MI_MODEL_HASH_REJECTED'
            with contextlib.redirect_stdout(io.StringIO()):
                import torch
                torch.set_num_threads(2)
                folder=Path(models[0]['folder']);name='dawloop_sheet_frozen'
                spec=importlib.util.spec_from_file_location(name,folder/'__init__.py',submodule_search_locations=[str(folder)])
                module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
                cls=importlib.import_module(name+'.modeling_sheetsage2').SheetSage2Model
                model=cls.from_pretrained(str(folder),base_model_path=models[1]['folder'],local_files_only=True,torch_dtype=torch.float32,attn_implementation='sdpa').eval()
            emit(dict(source='SHEETSAGE2',revision=models[0]['revision'],parentRevision=models[1]['revision'],device='cpu',elapsedMs=round((time.monotonic()-started)*1000)))
        elif r['method']=='transcribe':
            assert model is not None,'MI_MODEL_NOT_LOADED'
            import numpy as np
            with wave.open(p['path'],'rb') as f:
                assert f.getsampwidth()==2 and f.getnframes()/f.getframerate()<=30,'MI_SHEET_AUDIO_BUDGET'
                rate=f.getframerate();samples=np.frombuffer(f.readframes(f.getnframes()),dtype='<i2').reshape(-1,f.getnchannels()).mean(axis=1).astype(np.float32)/32768
            with contextlib.redirect_stdout(io.StringIO()):
                result=model.transcribe(samples,sampling_rate=rate,output_dir=None,render_audio=False,render_score=False,dtype='fp32',melody_only=True)
            import mido
            midi=mido.MidiFile(file=io.BytesIO(result['midi']));notes=[];tempos=[];meter=[4,4]
            for tr in midi.tracks:
                tick=0;active={}
                for msg in tr:
                    tick+=msg.time
                    if msg.type=='set_tempo':tempos.append(dict(start=tick/midi.ticks_per_beat,bpm=mido.tempo2bpm(msg.tempo)))
                    if msg.type=='time_signature':meter=[msg.numerator,msg.denominator]
                    if msg.type not in ['note_on','note_off']:continue
                    key=(msg.channel,msg.note)
                    if msg.type=='note_on' and msg.velocity:
                        assert key not in active,'MI_SHEET_OVERLAPPING_NOTE';active[key]=(tick,msg.velocity)
                    elif key in active:
                        start,vel=active.pop(key);notes.append(dict(pitch=msg.note,start=start/midi.ticks_per_beat,duration=(tick-start)/midi.ticks_per_beat,velocity=vel,part=msg.channel))
                assert not active,'MI_SHEET_UNTERMINATED_NOTE'
            emit(dict(schemaVersion=1,source='SHEETSAGE2',notes=notes,tempo=tempos[0]['bpm'] if tempos else 120,meter=meter,tempoMap=tempos,edits=[],abc=result.get('abc'),rawMidiBase64=base64.b64encode(result['midi']).decode('ascii'),provenance=dict(provider='SheetSage2',revision=models[0]['revision'],parentRevision=models[1]['revision'],elapsedMs=round((time.monotonic()-started)*1000),warnings=result.get('warnings',[]),durationSeconds=len(samples)/rate,device='cpu',waveformInput=True)))
        else:raise ValueError('MI_METHOD_UNAVAILABLE')

if __name__=='__main__':
    try:main()
    except Exception as e:
        print(json.dumps(dict(schemaVersion=1,kind='error',code=str(e) if str(e).isupper() else 'MI_SHEET_RUNTIME_FAILED',detail=type(e).__name__+': '+str(e))),flush=True);sys.exit(1)
