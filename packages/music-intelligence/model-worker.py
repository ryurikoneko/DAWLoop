"""固定模型的后台协议；不访问网络或外部宿主。"""
import contextlib
import hashlib
import io
import json
import os
import sys
import time
from pathlib import Path


def emit(kind, **data):
    print(json.dumps(dict(schemaVersion=1, kind=kind, **data), allow_nan=False), flush=True)


def protect_memory():
    if os.name != 'nt':
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (10 * 1024**3, 10 * 1024**3))
        return None
    import ctypes
    from ctypes import wintypes
    class Basic(ctypes.Structure):
        _fields_ = [('a', ctypes.c_int64), ('b', ctypes.c_int64), ('flags', wintypes.DWORD), ('min', ctypes.c_size_t), ('max', ctypes.c_size_t), ('active', wintypes.DWORD), ('affinity', ctypes.c_size_t), ('priority', wintypes.DWORD), ('scheduling', wintypes.DWORD)]
    class Counters(ctypes.Structure):
        _fields_ = [(k, ctypes.c_uint64) for k in ['read', 'write', 'other', 'readBytes', 'writeBytes', 'otherBytes']]
    class Extended(ctypes.Structure):
        _fields_ = [('basic', Basic), ('io', Counters), ('processMemory', ctypes.c_size_t), ('jobMemory', ctypes.c_size_t), ('peakProcess', ctypes.c_size_t), ('peakJob', ctypes.c_size_t)]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    handle = kernel.CreateJobObjectW(None, None)
    limits = Extended()
    limits.basic.flags = 0x100 | 0x2000
    limits.processMemory = 10 * 1024**3
    if not handle or not kernel.SetInformationJobObject(handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)) or not kernel.AssignProcessToJobObject(handle, kernel.GetCurrentProcess()):
        raise ValueError('MI_MEMORY_LIMIT_UNAVAILABLE')
    return handle


def main():
    memory_guard = protect_memory()
    model = None
    for raw in sys.stdin.buffer:
        if len(raw) > 65536:
            raise ValueError('MI_REQUEST_TOO_LARGE')
        request = json.loads(raw)
        if request.get('schemaVersion') != 1:
            raise ValueError('MI_SCHEMA_REJECTED')
        p = request['params']
        started = time.monotonic()
        if request['method'] == 'load':
            import numpy as np
            import torch
            import torchaudio
            from omar_rq import get_model
            torch.set_num_threads(2)
            folder = Path(p['folder']).resolve()
            for name in ['config.gin', 'model.ckpt']:
                source = folder / name
                digest = hashlib.sha256()
                with source.open('rb') as file:
                    for chunk in iter(lambda: file.read(1024 * 1024), b''):
                        digest.update(chunk)
                if source.is_symlink() or digest.hexdigest() != p['files'].get(name):
                    raise ValueError('MI_MODEL_HASH_REJECTED')
            config = (folder / 'config.gin').read_text(encoding='utf-8')
            if any(line.lstrip().startswith(('import ', 'from ', 'include ')) for line in config.splitlines()):
                raise ValueError('MI_MODEL_CONFIG_REVIEW_REQUIRED')
            # 固定配置只引用已安装官方模块，权重只允许安全张量反序列化。
            os.environ['TORCH_FORCE_WEIGHTS_ONLY_LOAD'] = '1'
            with contextlib.redirect_stdout(io.StringIO()):
                model = get_model(config_file=folder / 'config.gin', device='cpu')
            if abs(float(model.eps) - 25) > .01:
                raise ValueError('MI_EMBEDDING_RATE_REJECTED')
            emit('result', data=dict(source='OMAR_RQ', codeVersion=__import__('importlib.metadata',fromlist=['version']).version('omar-rq'), torchVersion=torch.__version__, revision=p['revision'], device='cpu', memoryLimitBytes=10 * 1024**3, elapsedMs=round((time.monotonic()-started)*1000)))
        elif request['method'] == 'embedding':
            if model is None:
                raise ValueError('MI_MODEL_NOT_LOADED')
            import wave
            with wave.open(p['path'], 'rb') as audio:
                if audio.getsampwidth() != 2 or audio.getnframes() > audio.getframerate() * 30:
                    raise ValueError('MI_OMAR_AUDIO_BUDGET_REJECTED')
                rate = audio.getframerate()
                samples = np.frombuffer(audio.readframes(audio.getnframes()), dtype='<i2').reshape(-1, audio.getnchannels()).mean(axis=1) / 32768
            tensor = torch.as_tensor(samples, dtype=torch.float32)
            if rate != 24000:
                tensor = torchaudio.functional.resample(tensor, rate, 24000)
            with torch.inference_mode(), contextlib.redirect_stdout(io.StringIO()):
                values = model.extract_embeddings(tensor.unsqueeze(0), layers=(6,))
            if values.ndim != 4 or values.shape[0] != 1 or values.shape[1] != 1 or not torch.isfinite(values).all():
                raise ValueError('MI_EMBEDDING_CONTRACT_REJECTED')
            data = values[0, 0].cpu().numpy()
            times = np.arange(data.shape[0]) / float(model.eps)
            valid = times < tensor.numel() / 24000
            data, times = data[valid], times[valid]
            with open(p['output'], 'xb') as file:
                np.save(file, data, allow_pickle=False)
            emit('result', data=dict(schemaVersion=1, source='OMAR_RQ', shape=list(data.shape), timestamps=times.tolist(), norms=np.linalg.norm(data, axis=1).tolist(), rate=25, resampledRate=24000, inputRate=rate, duration=tensor.numel()/24000, elapsedMs=round((time.monotonic()-started)*1000), semanticStyleClassification=False))
        else:
            raise ValueError('MI_METHOD_UNAVAILABLE')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        emit('error', code=str(error) if str(error).isupper() else 'MI_MODEL_RUNTIME_FAILED', detail=type(error).__name__ + ': ' + str(error)[:2000])
        sys.exit(1)
