import math
import numpy as np
import soundfile as sf

def review_offsets(path,score):
    assert score['source']=='SHEETSAGE2','MI_OFFSET_SOURCE_REJECTED'
    tempo_map=sorted(score.get('tempoMap',[]),key=lambda n:n['start'])
    assert len(tempo_map)<=1,'MI_OFFSET_TEMPO_MAP_UNSUPPORTED'
    tempo=score['tempo'];unit=60/tempo
    ordered=sorted(score['notes'],key=lambda n:n['start'])
    assert all(a['start']+a['duration']<=b['start']+.01 for a,b in zip(ordered,ordered[1:])),'MI_OFFSET_REVIEW_MONOPHONIC_ONLY'
    with sf.SoundFile(path) as f:
        assert f.frames/f.samplerate<=30,'MI_OFFSET_AUDIO_BUDGET'
        rate=f.samplerate;audio=f.read(dtype='float32',always_2d=True).mean(axis=1)
    result=dict(score);result['source']='USER_EDITED';result['notes']=[dict(n) for n in score['notes']];suggestions=[]
    hop=max(1,round(rate*.005))
    for i,n in enumerate(result['notes']):
        start=round(n['start']*unit*rate);end=min(len(audio),round((n['start']+n['duration'])*unit*rate));block=audio[start:end]
        rms=np.array([math.sqrt(float(np.mean(block[j:j+hop]**2))) for j in range(0,len(block),hop)])
        if not len(rms) or rms.max()<.003:
            suggestions.append(dict(noteIndex=i,state='NO_ENERGY_KEEP_FOR_REVIEW'));continue
        quiet=rms<max(.001,float(rms.max())*.08);run=0;cut=None
        # 只建议明确静音间隙；不将持续尾音或混音背景推断为音符结束。
        for j,low in enumerate(quiet):
            if j*hop/rate<.08:continue
            run=run+1 if low else 0
            if run>=16:cut=(j-run+1)*hop/rate;break
        if cut is None:continue
        new_duration=cut/unit
        if .03<new_duration*unit<n['duration']*unit-.05:
            previous=n['duration'];n['duration']=new_duration;suggestions.append(dict(noteIndex=i,state='SILENCE_TRIM_CANDIDATE',originalDuration=previous,newDuration=new_duration))
    result['provenance']={**score.get('provenance',{}),'originalSource':'SHEETSAGE2','postprocessing':'BASIC_DSP_SILENCE_GAP_REVIEW','confidence':'low','notModelAccuracyRepair':True,'suggestions':suggestions}
    result['edits']=[*score.get('edits',[]),dict(kind='USER_REQUESTED_OFFSET_REVIEW',suggestions=suggestions)]
    return result
