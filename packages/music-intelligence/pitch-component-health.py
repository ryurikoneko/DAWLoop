"""安装晋级要求真实ONNX推理，不以导入成功代替模型健康检查。"""
import hashlib,json,tempfile
from pathlib import Path
import numpy as np
import soundfile as sf
import basic_pitch
from basic_pitch.inference import Model,predict
files=list((Path(basic_pitch.__file__).parent/'saved_models').rglob('*.onnx'))
assert len(files)==1
assert hashlib.sha256(files[0].read_bytes()).hexdigest()=='2c3c1d144bfa61ad236e92e169c13535c880469a12a047d4e73451f2c059a0ec'
model=Model(files[0]);assert model.model_type.name=='ONNX'
with tempfile.TemporaryDirectory(prefix='pitch-health-') as d:
 audio=np.sin(2*np.pi*440*np.arange(66150)/22050).astype(np.float32)*0.2
 wav=Path(d)/'owned-tone.wav';sf.write(wav,audio,22050)
 _,midi,_=predict(wav,model_or_model_path=model,midi_tempo=120)
 assert any(n.pitch==69 for part in midi.instruments for n in part.notes)
print(json.dumps({'component':'basic-pitch','runtime':'ONNX','inference':True,'source':'BASIC_PITCH'}))
