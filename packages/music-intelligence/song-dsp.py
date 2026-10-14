"""有界整曲测量；响度滤波状态跨解码块延续，特征帧按唯一时间区间归属。"""
import math
import hashlib
import json
import numpy as np
import soundfile as sf
import librosa
import soxr
from scipy.signal import lfilter

RATE = 22050
HOP = 512
FFT = 2048
CORE = (30 * RATE // HOP) * HOP
MARGIN = (RATE // HOP) * HOP
CONFIG = dict(analysisRate=RATE,nFft=FFT,hopLength=HOP,window='hann',fluxCenter=False,
    fluxNormalization='L1_PER_FRAME',fluxDifference='POSITIVE_L1',
    channelAggregation='PEAK_MAX_RMS_MEAN_SQUARE_ALL_SAMPLES',pcmFullScale=1,
    decodeBlockFrames=65536,maxSeconds=7200,maxSampleRate=192000,maxChannels=8,
    resampler='soxr_hq_stream',featureCoreFrames=CORE,featureMarginFrames=MARGIN,
    maxCurvePoints=1200,chromaFft=8192,chromaHop=2048)

class Loudness:
    def __init__(self, rate, channels):
        self.channels = channels
        self.window = round(.4 * rate)
        self.hop = round(.1 * rate)
        self.pending = np.empty(0)
        self.powers = []
        self.filters = []
        # 双线性变换对应标准48kHz系数；RLB分子不做额外通带归一化。
        for frequency, quality, shelf in [(1681.974450955533, .7071752369554196, True),
                                          (38.13547087602444, .5003270373238773, False)]:
            k = math.tan(math.pi * frequency / rate)
            divisor = 1 + k / quality + k * k
            a = [1, 2*(k*k-1)/divisor, (1-k/quality+k*k)/divisor]
            if shelf:
                high = 10**(3.999843853973347/20)
                middle = high**.4996667741545416
                b = [(high+middle*k/quality+k*k)/divisor,
                     2*(k*k-high)/divisor,(high-middle*k/quality+k*k)/divisor]
            else:
                b = [1,-2,1]
            self.filters.append((b,a,np.zeros((2,channels))))

    def add(self, block):
        if self.channels > 2:
            return
        values = block.astype('float64')
        for i,(b,a,state) in enumerate(self.filters):
            values,state = lfilter(b,a,values,axis=0,zi=state)
            self.filters[i] = (b,a,state)
        energy = np.square(values).sum(axis=1)
        self.pending = np.concatenate((self.pending,energy))
        windows = max(0,1+(len(self.pending)-self.window)//self.hop)
        if windows:
            cumulative = np.concatenate(([0.],np.cumsum(self.pending)))
            indices = np.arange(windows)*self.hop
            self.powers.extend(((cumulative[indices+self.window]-cumulative[indices])/self.window).tolist())
            self.pending = self.pending[windows*self.hop:]

    def result(self):
        metadata = dict(standard='ITU-R BS.1770-5 / EBU R128',version='bs1770-stream-1',
            blockMs=400,hopMs=100,absoluteGate=-70,relativeGate=-10,
            channelLayout='mono' if self.channels==1 else 'stereo' if self.channels==2 else 'unsupported',
            blocks=len(self.powers),truePeakMeasured=False)
        if self.channels>2:
            return dict(value=None,status='NOT_READY',reasonCode='MI_LUFS_CHANNEL_LAYOUT_UNKNOWN',**metadata)
        if not self.powers:
            return dict(value=None,status='UNKNOWN',reasonCode='MI_LUFS_TOO_SHORT',**metadata)
        powers=np.asarray(self.powers)
        absolute=10**((-70+.691)/10)
        initial=powers[powers>absolute]
        if not len(initial):
            return dict(value=None,status='UNKNOWN',reasonCode='MI_LUFS_BELOW_GATE',**metadata)
        threshold=max(absolute,float(initial.mean())*.1)
        accepted=powers[powers>threshold]
        return dict(value=-.691+10*math.log10(float(accepted.mean())),status='READY',reasonCode=None,
                    relativeThreshold=-.691+10*math.log10(float(initial.mean()))-10,**metadata)

MAJOR=np.array([6.35,2.23,3.48,2.33,4.38,4.09,2.52,5.19,2.39,3.66,2.29,2.88])
MINOR=np.array([6.33,2.68,3.52,5.38,2.60,3.53,2.54,4.75,3.98,2.69,3.34,3.17])

def key_detection(chroma, seconds, rms):
    values=np.asarray(chroma,dtype='float64')
    ranking=[]
    if np.std(values)>1e-8:
        for mode,template in [('major',MAJOR),('minor',MINOR)]:
            for tonic in range(12):
                score=float(np.corrcoef(values,np.roll(template,tonic))[0,1])
                ranking.append(dict(tonic=tonic,mode=mode,score=score))
        ranking.sort(key=lambda x:x['score'],reverse=True)
    reason='MI_KEY_NO_TONAL_EVIDENCE'
    if ranking and seconds>=2 and rms>1e-6 and values.max()/max(values.sum(),1e-12)<.7:
        reason=None if ranking[0]['score']>=.5 and ranking[0]['score']-ranking[1]['score']>=.05 else 'MI_KEY_AMBIGUOUS'
    elif seconds<2:
        reason='MI_KEY_TOO_SHORT'
    return dict(status='READY' if reason is None else 'UNKNOWN',reasonCode=reason,
        candidates=ranking,primary=ranking[0] if reason is None else None,
        method='Krumhansl-Kessler template Pearson correlation; time-weighted frame chroma',
        version='kk-chroma-1',calibrationStatus='UNCALIBRATED',confidenceScore=None)

def analyze(path,start,end,emit):
    info=sf.info(path)
    assert 0<info.duration<=7200,'AUDIO_TOO_LONG'
    assert type(start) in (int,float) and math.isfinite(start) and start>=0,'INVALID_RANGE'
    assert end is None or type(end) in (int,float) and math.isfinite(end) and end>start,'INVALID_RANGE'
    assert 8000<=info.samplerate<=192000 and 1<=info.channels<=8,'MI_ANALYSIS_DECODE_BUDGET'
    first=round(start*info.samplerate);last=min(info.frames,round(end*info.samplerate) if end is not None else info.frames)
    assert last>first,'INVALID_RANGE'
    start,end=first/info.samplerate,last/info.samplerate
    count=last-first
    digest=hashlib.sha256(json.dumps(dict(format='PCM_F32LE_INTERLEAVED_V1',sampleRate=info.samplerate,
        channels=info.channels,firstFrame=first,lastFrame=last),sort_keys=True,separators=(',',':')).encode('ascii')+b'\n')
    loudness=Loudness(info.samplerate,info.channels)
    resampler=soxr.ResampleStream(info.samplerate,RATE,1,dtype='float32',quality='HQ')
    buffer=np.empty(0,dtype='float32');origin=0;core_start=0
    energy=[];centroid=[];flux=[];onsets=[];beats=[];windows=[];tempo_votes=[]
    chroma_sum=np.zeros(12);chroma_frames=0;centroid_sum=0.;feature_frames=0
    peaks=np.zeros(120);peak=0.;square=0.;position=0;max_buffer=0

    def features(core_end):
        nonlocal buffer,origin,core_start,chroma_sum,chroma_frames,centroid_sum,feature_frames
        y=buffer[:core_end+MARGIN-origin]
        if len(y)<FFT:
            y=np.pad(y,(0,FFT-len(y)))
        magnitude=np.abs(librosa.stft(y,n_fft=FFT,hop_length=HOP,window='hann',center=False))
        times=origin+(np.arange(magnitude.shape[1])*HOP+FFT/2)
        owned=(times>=core_start)&(times<core_end)&(times/RATE<=end-start)
        rms=librosa.feature.rms(y=y,frame_length=FFT,hop_length=HOP,center=False)[0]
        sc=librosa.feature.spectral_centroid(S=magnitude,sr=RATE)[0]
        centroid_sum+=float(sc[owned].sum(dtype='float64'));feature_frames+=int(owned.sum())
        for i in np.flatnonzero(owned):
            timestamp=start+float(times[i])/RATE
            energy.append([timestamp,float(rms[i])]);centroid.append([timestamp,float(sc[i])])
        # 调性需要低音区的半音分辨率；与动态特征分开FFT，但沿用全曲固定帧网格。
        chroma_offset=(-origin)%2048
        tonal_y=y[chroma_offset:]
        if len(tonal_y)<8192:tonal_y=np.pad(tonal_y,(0,8192-len(tonal_y)))
        tonal_magnitude=np.abs(librosa.stft(tonal_y,n_fft=8192,hop_length=2048,window='hann',center=False))
        cr=librosa.feature.chroma_stft(S=tonal_magnitude**2,sr=RATE,n_fft=8192,tuning=0,norm=np.inf)
        tonal_times=origin+chroma_offset+np.arange(cr.shape[1])*2048+4096
        tonal_owned=(tonal_times>=core_start)&(tonal_times<core_end)&(tonal_times/RATE<=end-start)
        chroma_sum+=cr[:,tonal_owned].sum(axis=1,dtype='float64');chroma_frames+=int(tonal_owned.sum())
        totals=magnitude.sum(axis=0,keepdims=True)
        normalized=np.divide(magnitude,totals,out=np.zeros_like(magnitude),where=totals>0)
        changes=np.maximum(np.diff(normalized,axis=1),0).sum(axis=0)
        for i in np.flatnonzero(owned):
            if i>0:flux.append([start+float(times[i])/RATE,float(changes[i-1])])
        envelope=librosa.onset.onset_strength(S=librosa.power_to_db(magnitude**2),sr=RATE,hop_length=HOP,center=False)
        detected=librosa.onset.onset_detect(onset_envelope=envelope,sr=RATE,hop_length=HOP,units='frames')
        tempo,tracked=librosa.beat.beat_track(onset_envelope=envelope,sr=RATE,hop_length=HOP,units='frames')
        for collection,indices in [(onsets,detected),(beats,tracked)]:
            for i in indices:
                frame=origin+int(i)*HOP
                if core_start<=frame<core_end and frame/RATE<=end-start:
                    timestamp=start+frame/RATE
                    if not collection or timestamp-collection[-1]>HOP/RATE*.5:collection.append(timestamp)
        tempo=float(np.asarray(tempo).reshape(-1)[0])
        if tempo>0:tempo_votes.append((tempo,(core_end-core_start)/RATE))
        windows.append(dict(start=start+core_start/RATE,end=min(end,start+core_end/RATE),
            featureFrames=int(owned.sum()),contextStart=start+origin/RATE,
            contextEnd=min(end,start+(origin+len(y))/RATE)))
        core_start=core_end
        drop=max(0,core_start-MARGIN-origin)
        buffer=buffer[drop:];origin+=drop

    with sf.SoundFile(path) as file:
        file.seek(first)
        while position<count:
            block=file.read(min(65536,count-position),dtype='float32',always_2d=True)
            assert len(block)>0 and np.isfinite(block).all(),'MI_AUDIO_DECODE_FAILED'
            digest.update(block.astype('<f4',copy=False).tobytes(order='C'))
            peak=max(peak,float(np.max(np.abs(block))))
            square+=float(np.square(block,dtype='float64').sum())
            loudness.add(block)
            mono=block.mean(axis=1)
            bins=np.minimum(119,((np.arange(len(block))+position)*120/count).astype(int))
            np.maximum.at(peaks,bins,np.abs(block).max(axis=1))
            position+=len(block)
            buffer=np.concatenate((buffer,resampler.resample_chunk(mono,last=position==count)))
            max_buffer=max(max_buffer,len(buffer))
            while origin+len(buffer)>=core_start+CORE+MARGIN:features(core_start+CORE)
            emit('progress',progress=.95*position/count)
        total=origin+len(buffer)
        if total>core_start:features(total)
    rms=math.sqrt(square/(count*info.channels))
    chroma=(chroma_sum/max(1,chroma_frames)).tolist()
    # 每个可视桶保留峰值位置；底层起音/节拍保留事件时间，不平均窗口速度。
    def reduced(rows):
        if len(rows)<=1200:return rows
        return [max(part,key=lambda row:row[1]) for part in np.array_split(np.asarray(rows),1200)]
    energy=[list(map(float,row)) for row in reduced(energy)]
    centroid=[list(map(float,row)) for row in reduced(centroid)]
    flux=[list(map(float,row)) for row in reduced(flux)]
    bpm=[]
    tempo_evidence=dict(method='duration-weighted tempo-mode; cross-window onset interval check',windows=len(tempo_votes),consistent=False)
    if tempo_votes:
        grouped={}
        for value,weight in tempo_votes:grouped[round(value/2)*2]=grouped.get(round(value/2)*2,0)+weight
        mode=max(grouped,key=grouped.get)
        selected=[(v,w) for v,w in tempo_votes if abs(v-mode)<=4]
        candidate=sum(v*w for v,w in selected)/sum(w for _,w in selected)
        intervals=np.diff(onsets)
        eligible=intervals[(intervals>=.18)&(intervals<=1.5)]
        interval_bpm=60/float(np.median(eligible)) if len(eligible)>=3 else None
        agreement=sum(w for _,w in selected)/sum(w for _,w in tempo_votes)
        tempo_evidence.update(windowAgreement=agreement,onsetIntervalBpm=interval_bpm,
            consistent=bool(agreement>=.6 and interval_bpm is not None and min(abs(candidate-interval_bpm*x)/candidate for x in [.5,1,2])<.15))
        if len(tempo_votes)==1 or tempo_evidence['consistent']:bpm=[round(candidate,2)]
    tonal=[dict(pitchClass=int(i),strength=float(chroma[i]),confidence='low',method='chroma_peak_not_key_classifier') for i in np.argsort(chroma)[-3:][::-1]]
    measurements=dict(version='SONG_DSP_1',config=CONFIG,implementationVersion=f'song-dsp-1/librosa-{librosa.__version__}',
        windowSha256=digest.hexdigest(),windowEncoding='PCM_F32LE_INTERLEAVED_V1',samplePeak=peak,
        samplePeakDbfs=20*math.log10(peak) if peak>0 else None,rms=rms,rmsDbfs=20*math.log10(rms) if rms>0 else None,
        crestFactor=peak/rms if rms>0 else None,spectralFlux=flux,lufs=loudness.result(),
        key=key_detection(chroma,end-start,rms),windows=windows,
        aggregation=dict(nativeFrames=count,nativeSamples=count*info.channels,squareSum=square,
            chromaFrames=chroma_frames,curveReduction='max-value-per-equal-frame-bucket <=1200',
            maxMonoBufferFrames=max_buffer,featureOwnership='half-open core interval; global frame centers',tempo=tempo_evidence))
    return dict(schemaVersion=1,kind='MusicAnalysis',source='BASIC_DSP',duration=info.duration,sampleRate=info.samplerate,
        channels=info.channels,format=info.format,range=[start,end],waveform=peaks.tolist(),bpmCandidates=bpm,
        bpmConfidence='low',beats=beats,onsets=onsets,energy=energy,spectralCentroid=centroid,chroma=chroma,
        tonalCandidates=tonal,segmentCandidates=[],measurements=measurements,
        provenance=dict(provider='librosa',version=librosa.__version__,measured=['samplePeak','rms','spectralFlux','lufs'],estimated=['bpmCandidates','key']),
        profile=dict(schemaVersion=1,kind='MusicProfile',rhythmic=dict(bpmCandidates=bpm),harmonic=dict(chroma=chroma,key=measurements['key']),
            timbral=dict(centroidMean=centroid_sum/feature_frames if feature_frames else None),
            energy=dict(mean=rms),structural=dict(boundaryCandidates=[]),genreMoodHypotheses=[],userDescription='',notModelFineTuning=True))
