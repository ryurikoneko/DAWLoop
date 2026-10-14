"""官方 ONNX 转录在独立进程执行；协议输出不混入库的控制台文本。"""
import sys,json,time,contextlib,io,hashlib,math,importlib.util,os
from pathlib import Path
os.environ['NUMBA_CACHE_DIR']=str(Path(os.environ['TEMP'])/'numba-pitch')
os.environ['TF_CPP_MIN_LOG_LEVEL']='3'
if sys.platform=='win32':
    # 可选解码器探测不能启动开发机PATH中的未登记FFmpeg或其他工具。
    windows=Path(os.environ.get('SystemRoot','C:/Windows'))
    os.environ['PATH']=os.pathsep.join([str(windows/'System32'),str(windows)])

def emit(data):
    print(json.dumps(dict(schemaVersion=1,kind='result',data=data),allow_nan=False),flush=True)

def main():
    spec=importlib.util.spec_from_file_location('memory_guard',Path(__file__).with_name('model-worker.py'))
    guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard);handle=guard.protect_memory()
    model=None
    for raw in sys.stdin.buffer:
        assert len(raw)<=65536,'MI_REQUEST_TOO_LARGE'
        r=json.loads(raw);assert r.get('schemaVersion')==1,'MI_SCHEMA_REJECTED';p=r['params'];started=time.monotonic()
        if r['method']=='load':
            with contextlib.redirect_stdout(io.StringIO()):
                import basic_pitch
                from basic_pitch.inference import Model,predict
                candidates=list((Path(basic_pitch.__file__).parent/'saved_models').rglob('*.onnx'))
                assert len(candidates)==1,'MI_MODEL_NOT_READY'
                assert hashlib.sha256(candidates[0].read_bytes()).hexdigest()=='2c3c1d144bfa61ad236e92e169c13535c880469a12a047d4e73451f2c059a0ec','MI_MODEL_HASH_REJECTED'
                model=Model(candidates[0]);assert model.model_type.name=='ONNX','MI_MODEL_RUNTIME_REJECTED'
            emit(dict(source='BASIC_PITCH',version='0.4.0',runtime='ONNX',modelSha256=hashlib.sha256(candidates[0].read_bytes()).hexdigest(),elapsedMs=round((time.monotonic()-started)*1000)))
        elif r['method']=='transcribe':
            assert model is not None,'MI_MODEL_NOT_LOADED'
            import soundfile as sf
            info=sf.info(p['path']);assert 0<info.duration<=120,'MI_TRANSCRIPTION_AUDIO_BUDGET'
            tempo=p['tempo'];assert type(tempo) in (int,float) and math.isfinite(tempo) and 20<=tempo<=300,'MI_TRANSCRIPTION_REQUEST_REJECTED'
            with contextlib.redirect_stdout(io.StringIO()):
                outputs,midi,events=predict(p['path'],model_or_model_path=model,midi_tempo=tempo,multiple_pitch_bends=False)
            notes=[];bends=[];raw_events=[]
            for i,inst in enumerate(midi.instruments):
                assert i<16,'MI_SCORE_TOO_LARGE'
                notes.extend(dict(pitch=int(n.pitch),start=float(n.start*tempo/60),duration=float((n.end-n.start)*tempo/60),velocity=int(n.velocity),part=i) for n in inst.notes)
                bends.extend(dict(start=float(b.time*tempo/60),value=int(b.pitch),part=i) for b in inst.pitch_bends)
            assert len(notes)<=20000 and len(bends)<=50000,'MI_SCORE_TOO_LARGE'
            for start,end,pitch,amplitude,bend in events:
                raw_events.append(dict(startSeconds=float(start),endSeconds=float(end),pitch=int(pitch),amplitude=float(amplitude),pitchBendBins=[int(v) for v in bend] if bend is not None else None))
            emit(dict(schemaVersion=1,tempo=tempo,meter=[4,4],tempoMap=[dict(start=0,bpm=tempo)],notes=notes,pitchBends=bends,source='BASIC_PITCH',edits=[],provenance=dict(provider='Spotify Basic Pitch',version='0.4.0',runtime='ONNX',modelSha256=hashlib.sha256(candidates[0].read_bytes()).hexdigest(),elapsedMs=round((time.monotonic()-started)*1000),durationSeconds=info.duration,sampleRate=info.samplerate,modelSampleRate=22050,multiplePitchBends=False,pitchBendRangeSemitones=2),rawNoteEvents=raw_events))
        else:raise ValueError('MI_METHOD_UNAVAILABLE')

if __name__=='__main__':
    try:main()
    except Exception as e:
        print(json.dumps(dict(schemaVersion=1,kind='error',code=str(e) if str(e).isupper() else 'MI_BASIC_PITCH_FAILED',detail=type(e).__name__+': '+str(e))),flush=True)
        sys.exit(1)
