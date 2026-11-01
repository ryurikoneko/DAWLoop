"""保持原模型协议，额外从推理进程内部取得资源计数。"""
import ctypes
from ctypes import wintypes
import importlib.util
import os
from pathlib import Path

spec=importlib.util.spec_from_file_location('existing_model_worker',Path(__file__).with_name('model-worker.py'))
worker=importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)
original_emit=worker.emit


def emit(kind, **payload):
    if kind=='result':
        class Counters(ctypes.Structure):
            _fields_=[('cb',wintypes.DWORD),('faults',wintypes.DWORD)]+[(n,ctypes.c_size_t) for n in ('peak','working','pagedPeak','paged','nonpagedPeak','nonpaged','pagefile','pagefilePeak')]
        values=Counters();values.cb=ctypes.sizeof(values)
        kernel=ctypes.WinDLL('kernel32');kernel.GetCurrentProcess.restype=wintypes.HANDLE
        psapi=ctypes.WinDLL('psapi');psapi.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.c_void_p,wintypes.DWORD]
        if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(),ctypes.byref(values),values.cb):
            raise OSError('MEMORY_COUNTER_UNAVAILABLE')
        payload['data']['workerMemory']=dict(pid=os.getpid(),peakRssBytes=values.peak,workingSetBytes=values.working,pagefileBytes=values.pagefile)
    original_emit(kind,**payload)


worker.emit=emit
worker.main()
