"""保存零派发失败与恢复，不把离线结果升级为现场认证。"""

import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/'evidence/runtime_v2/local_preview_fast_path'


def write(name,value):
    with (OUTPUT/name).open('x',encoding='utf-8') as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2)
        stream.write('\n')


def main():
    raise RuntimeError('HISTORICAL_REPORT_WRITER_RETIRED_USE_UNIFIED_DOCUMENT')
    directory=OUTPUT/'session_1'
    trace=json.loads((directory/'trace.json').read_text(encoding='utf-8'))
    recovery=json.loads((directory/'recovery.json').read_text(encoding='utf-8'))
    assert trace==[] and recovery['host_closed'] and recovery['debug_port_closed']
    assert not (directory/'session.json').exists()
    assert not (OUTPUT/'dispatch_intents').exists()
    write('readonly_diagnostic.json',dict(error_code='HOST_DISCONNECTED',status='UNAVAILABLE',
        backend_calls=0,reads=[],backend_connect_ms=2038.8045,
        source='EXISTING_NATIVE_PROBE_AFTER_DISCOVERY_FAILURE',callbacks_restored=None))
    write('summary.json',dict(stage='3.3',status='STOPPED',local_preview_fast_path='NOT_READY',
        implementation='OFFLINE_TESTED',live_attempted_sessions=1,live_dispatched_sessions=0,
        detections=None,false_positives=None,false_negatives=None,dpi_roi_errors=None,
        remaining_sessions='NOT_RUN_AFTER_SMOKE_DISCOVERY_FAILURE',
        live_timing=dict(baseline_ms=None,dispatch_to_pixel_ms=None,
            pixel_to_confirmation_ms=None,confirmation_to_runtime_ms=None),
        external_preview_notification_required=False,network_required_for_local_detector=False,
        full_live_workflow_proven=False,exact_set_verified=False,production_write_ready=False,
        discovery_failure='HOST_DISCOVERY_FAILED',diagnostic_error='HOST_DISCONNECTED',
        host_object_confirmed=False,live_catalog=None,root_cause=None,
        no_save_exit=True,baseline=recovery,debug_environment_retained=False,
        tests=dict(passed=261,subtests_passed=96,warnings=2),
        memory_service_available=False,memory_checkpoint_written=False,
        source_scope='FIXED_FOUR_NOTE_EXPERIMENT_ONLY',next_stage_started=False))
    addition='[KNOWN｜HIGH] 3.3已实现并停止：本地三帧确认直接通知与视口指纹守卫离线通过，新增8项／全套261项、96项子测试通过；仅固定四音符、未验证。首次现场在宿主发现阶段失败，只读探测端点不可达，四音符派发0次；其余4会话未运行，本地快速路径现场未就绪。不保存正常退出、基线摘要未变、宿主及端口关闭。外置记忆服务无可调用接口，检查点未写回；未进入3.4。'
    for relative,link in [
        ('docs/progress/DAWLOOP_RUNTIME_V2_PROGRESS.md','../RUNTIME_V2_MILESTONE_3_3.md'),
        ('docs/RUNTIME_V2_STATUS.md','RUNTIME_V2_MILESTONE_3_3.md'),
        ('docs/NATIVE_GOPHER.md','RUNTIME_V2_MILESTONE_3_3.md'),
        ('docs/BENCHMARKS.md','RUNTIME_V2_MILESTONE_3_3.md')]:
        path=ROOT/relative
        raw=path.read_bytes(); text=raw.decode('utf-8')
        newline='\r\n' if b'\r\n' in raw else '\n'
        position=text.index(newline)+len(newline)
        value=newline+addition+' 见 [3.3报告]('+link+')。'+newline+newline
        path.write_bytes((text[:position]+value+text[position:]).encode('utf-8'))
    print(json.dumps(dict(status='STOPPED_NOT_READY',dispatch_count=0)))


if __name__=='__main__':
    main()
