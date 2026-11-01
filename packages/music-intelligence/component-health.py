"""组件健康检查验证真实解码、数值测量和MIDI读回，不接触用户音频。"""
import json,tempfile
from pathlib import Path
import numpy as np
import soundfile as sf
import librosa
import mido
import soxr
from scipy.signal import lfilter

with tempfile.TemporaryDirectory(prefix='dawloop-component-') as temporary:
 root=Path(temporary)
 audio=np.sin(2*np.pi*440*np.arange(22050)/22050).astype(np.float32)*0.2
 sf.write(root/'health.wav',audio,22050)
 decoded,rate=sf.read(root/'health.wav',dtype='float32')
 assert rate==22050 and len(decoded)==len(audio) and float(librosa.feature.rms(y=decoded).mean())>0
 assert len(soxr.resample(decoded,22050,16000))==16000
 assert np.isfinite(lfilter([1],[1],decoded)).all()
 midi=mido.MidiFile();track=mido.MidiTrack();midi.tracks.append(track)
 track.append(mido.Message('note_on',note=69,velocity=90,time=0));track.append(mido.Message('note_off',note=69,time=480));midi.save(root/'health.mid')
 assert [event.note for event in mido.MidiFile(root/'health.mid').tracks[0] if event.type in ('note_on','note_off')]==[69,69]
print(json.dumps({'component':'basic-audio','librosa':librosa.__version__,'audioDecode':True,'dsp':True,'midiRoundtrip':True}))
