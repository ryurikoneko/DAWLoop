"""官方模型的离线适配；发布资格由服务的独立验收门决定。"""
import contextlib
import hashlib
import io
import math
from pathlib import Path

def extract_local(audio, sample_rate, model_directory, reviewed_files):
    import numpy as np
    import torch
    import torchaudio
    from omar_rq import get_model
    folder=Path(model_directory).resolve()
    # Gin 可以绑定可执行对象，因此只有审核过的精确配置字节才可加载。
    for name in ('config.gin','model.ckpt'):
        source=folder/name
        if source.is_symlink() or hashlib.sha256(source.read_bytes()).hexdigest()!=reviewed_files.get(name):
            raise ValueError('OMAR_SOURCE_NOT_REVIEWED')
    samples=torch.as_tensor(np.asarray(audio),dtype=torch.float32)
    if samples.ndim!=1 or not torch.isfinite(samples).all() or sample_rate<=0:
        raise ValueError('OMAR_AUDIO_REJECTED')
    if sample_rate!=24000:samples=torchaudio.functional.resample(samples,sample_rate,24000)
    if not 1<=samples.numel()<=24000*7200:raise ValueError('OMAR_AUDIO_BUDGET_REJECTED')
    with contextlib.redirect_stdout(io.StringIO()):
        model=get_model(config_file=folder/'config.gin',device='cpu')
    eps=float(model.eps)
    if not math.isfinite(eps) or abs(eps-25)>.01:raise ValueError('OMAR_EMBEDDING_RATE_MISMATCH')
    blocks=[];timestamps=[]
    with torch.inference_mode():
        for offset in range(0,samples.numel(),24000*30):
            block=samples[offset:offset+24000*30]
            values=model.extract_embeddings(block.unsqueeze(0),layers=(6,))
            if values.ndim!=4 or values.shape[0]!=1 or values.shape[1]!=1 or not torch.isfinite(values).all():
                raise ValueError('OMAR_TENSOR_CONTRACT_REJECTED')
            data=values[0,0].cpu().numpy()
            times=np.arange(data.shape[0])/eps+offset/24000
            valid=times<(offset+block.numel())/24000
            blocks.append(data[valid]);timestamps.extend(times[valid].tolist())
    return dict(schemaVersion=1,provider='omar-rq',rate=eps,
                embeddings=np.concatenate(blocks),timestamps=timestamps,
                confidence='unknown',semanticStyleClassification=False)
