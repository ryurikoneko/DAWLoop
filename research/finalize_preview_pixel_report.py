"""保留原换行，汇总已核实现场证据。"""

import hashlib
import json
import os
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
EVIDENCE=ROOT/'evidence/runtime_v2/preview_pixel_onset'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    raise RuntimeError('HISTORICAL_REPORT_WRITER_RETIRED_USE_UNIFIED_DOCUMENT')
    source_hash='ac68744417a7b98f7c2a7c2293ba255b73e6d99ecd3609618af0f501f786da75'
    baseline_hash='a2f9922d6b8cdc7f7627428d0d7072ed7dcab0a4f666fef42145c0c6e91b006f'
    catalog_hash='514d035244b0aea4d94fbb5ce8cad79415878e76dca6c85d94e1ebf692f4234e'
    for number in range(1,4):
        directory=EVIDENCE/f'session_{number}'
        result=read(directory/'result.json')
        catalog=read(directory/'catalog.json')
        recovery=read(directory/'recovery.json')
        assert result['value']['source_hash']==source_hash
        assert result['value']['note_count']==4
        assert catalog['catalog_hash']==catalog_hash and len(catalog['tools'])==48
        assert recovery['baseline_sha256']==baseline_hash and recovery['baseline_size']==53498
    fixture=Path(os.environ['TEMP'])/'DAWLoop_RuntimeV2_PianoRollProbe.flp'
    assert hashlib.sha256(fixture.read_bytes()).hexdigest()==baseline_hash
    for path in EVIDENCE.rglob('*.json'):
        read(path)
        content=path.read_text(encoding='utf-8')
        assert 'C:\\Users\\' not in content and 'C:/Users/' not in content
    environment=dict(fl_version='26.1.6 build 5639',catalog_count=48,catalog_hash=catalog_hash,
        baseline_sha256=baseline_hash,baseline_size=fixture.stat().st_size,
        source_sha256=source_hash,temporary_debug_environment_retained=False,
        actual_scale=[1.25,1.25],host_closed=True,debug_port_closed=True,
        timestamp='2026-10-01',private_paths_retained=False,
        tests=dict(passed=253,subtests_passed=96,warnings=2),
        notification_chain_components=['computer_use_capture','tool_delivery','model_processing','marker_delivery'],
        per_component_latency_ms=None,network_contribution_ms=None,
        automated_polling_latency_ms=None,stage_closed_guard_verified=True)
    with (EVIDENCE/'environment.json').open('x',encoding='utf-8') as stream:
        json.dump(environment,stream,ensure_ascii=False,indent=2)
        stream.write('\n')
    summary='[KNOWN｜HIGH] 3.2C已完成并停止：三个独立会话各单次四音符；首组125%坐标错位保留为无效，后两组首次像素采样在派发后45.3801／45.5326毫秒，出现区间宽21.8406／22.8489毫秒，约100.4毫秒后图像稳定。第二组人工观察与交付通知晚21.29秒，不能归因自动轮询；第三组人工标记超时、完成未知，像素采样仍有效。全套253项／96项子测试通过；三组不保存退出、基线摘要未变、回调及监听恢复、宿主及临时端口关闭。3.2系列关闭，未优化、未进入3.3。'
    for relative,link in [
        ('docs/progress/DAWLOOP_RUNTIME_V2_PROGRESS.md','../RUNTIME_V2_MILESTONE_3_2C.md'),
        ('docs/RUNTIME_V2_STATUS.md','RUNTIME_V2_MILESTONE_3_2C.md'),
        ('docs/NATIVE_GOPHER.md','RUNTIME_V2_MILESTONE_3_2C.md'),
        ('docs/BENCHMARKS.md','RUNTIME_V2_MILESTONE_3_2C.md')]:
        path=ROOT/relative
        raw=path.read_bytes()
        text=raw.decode('utf-8')
        newline='\r\n' if b'\r\n' in raw else '\n'
        position=text.index(newline)+len(newline)
        addition=newline+summary+' 见 [现场报告]('+link+')。'+newline+newline
        path.write_bytes((text[:position]+addition+text[position:]).encode('utf-8'))
    print(json.dumps(dict(status='FINALIZED',source_catalog_baseline_consistent=True),ensure_ascii=False))


if __name__=='__main__':
    main()
