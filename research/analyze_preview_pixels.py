"""离线汇总像素与原生事件；保留无效首组和负差值。"""

import json
from pathlib import Path
from analyze_native_preview import analyze_trial

ROOT = Path(__file__).resolve().parents[1]/'evidence/runtime_v2/preview_pixel_onset'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(name,value):
    with (ROOT/name).open('x',encoding='utf-8') as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2)
        stream.write('\n')


def main():
    rows=[]
    for number in range(1,4):
        name=f'session_{number}'
        directory=ROOT/name
        if (directory/'native_at_preview.json').exists():
            native=analyze_trial(directory)
        else:
            events=read(directory/'winevents.json')
            trace=read(directory/'trace.json')
            dispatch=next(e for e in trace if e['event']=='native_dispatch_begin')
            native=dict(host_generation=read(directory/'session.json')['host_generation'],
                native_dispatch_ns=dispatch['timestamp'],candidate_correlated=False,
                preview_native_event_ns=None,runtime_preview_notification_ns=None,
                unhooked=events['unhooked'],dropped=events['dropped'],
                invalid_reason='UI_OBSERVATION_TIMEOUT_NO_CORRELATION_SNAPSHOT')
        metrics=read(directory/'pixel_metrics.json')
        recovery=read(directory/'recovery.json')
        result=read(directory/'result.json')
        trace=read(directory/'trace.json')
        assert sum(e['event']=='native_dispatch_begin' for e in trace)==1
        assert recovery['host_closed'] and recovery['debug_port_closed']
        assert result['callbacks_restored'] and native['unhooked']
        valid=number>1 and metrics['error'] is None and metrics['onset'] is not None and metrics['stable_ns'] is not None
        onset=metrics['onset'] if valid else None
        dispatch=native['native_dispatch_ns']
        show=native['preview_native_event_ns']
        if valid:
            assert onset['last_absent_capture_start_ns']>=dispatch
            assert onset['observed_at_ns']<onset['confirmed_at_ns']<=metrics['stable_ns']
        row=dict(session=name,measurement_valid=valid,
            invalid_reason='LOGICAL_PHYSICAL_COORDINATES_NOT_REGISTERED' if number==1 else None,
            native=native,pixel_observed_ns=onset['observed_at_ns'] if valid else None,
            stable_ns=metrics['stable_ns'] if valid else None,
            pixel_confirmation_ns=onset['confirmed_at_ns'] if valid else None,
            onset_interval_ns=[onset['last_absent_capture_start_ns'],onset['observed_at_ns']] if valid else None,
            onset_interval_width_ms=(onset['observed_at_ns']-onset['last_absent_capture_start_ns'])/1e6 if valid else None,
            dispatch_to_pixel_ms=(onset['observed_at_ns']-dispatch)/1e6 if valid else None,
            show_receipt_to_pixel_ms=(onset['observed_at_ns']-show)/1e6 if valid and show is not None else None,
            pixel_to_stable_ms=(metrics['stable_ns']-onset['observed_at_ns'])/1e6 if valid else None,
            pixel_to_runtime_notification_ms=(native['runtime_preview_notification_ns']-onset['observed_at_ns'])/1e6 if valid and native['runtime_preview_notification_ns'] is not None else None,
            capture={k:v for k,v in metrics.items() if k not in ('frames','onset')},
            completion=result['value']['completion_status'],recovery=recovery)
        rows.append(row)
        write(name+'.json',row)
    valid=[row for row in rows if row['measurement_valid']]
    assert len({row['native']['host_generation'] for row in rows})==3
    write('capture_config.json',dict(logical_roi=[620,300,850,450],
        physical_roi=[775,375,1062,562],scale=[1.25,1.25],baseline_frames=40,
        desired_fps=60,persistence=3,stable_frames=5,
        invalid_session='session_1',same_rules_after_registration=['session_2','session_3'],
        scope='PIANO_ROLL_NOTE_REGION',gpu_completion_measured=False))
    write('native_events.json',dict(files=[f'session_{i}/winevents.json' for i in range(1,4)]))
    write('pixel_metrics.json',dict(files=[f'session_{i}/pixel_metrics.json' for i in range(1,4)]))
    write('onset_candidates.json',dict(trials=rows,
        semantics='FIRST_SAMPLED_FOUR_NOTE_STRUCTURE_CONFIRMED_BY_THREE_FRAMES',
        content_stable_semantics='FIVE_LOW_CHANGE_SAMPLED_FRAMES_NOT_HOST_SEMANTIC_COMPLETION'))
    write('summary.json',dict(stage='3.2C',status='STOPPED',sessions=3,
        valid_pixel_sessions=len(valid),preview_content_onset_observable='YES' if len(valid)>=2 else 'NO',
        bottleneck_side='RUNTIME_OBSERVER_OR_DELIVERY' if len(valid)>=2 else 'UNRESOLVED',
        attribution_scope='EXISTING_MANUAL_SCREENSHOT_AND_MARKER_NOTIFICATION_CHAIN_ONLY',
        successful_completion_sessions=sum(row['completion']=='COMPLETION_CONFIRMED' for row in rows),
        ui_observation_timeout_sessions=['session_3'],
        automatic_runtime_polling_bottleneck_proven=False,
        gpu_render_timestamp_known=False,production_write_ready=False,verified_write_ready=False,
        observers_stopped=True,callbacks_restored=True,host_closed=True,debug_port_closed=True,
        optimization_applied=False,series_3_2_closed=True,next_stage_started=False))
    print(json.dumps([{k:r[k] for k in ('session','measurement_valid','dispatch_to_pixel_ms',
        'show_receipt_to_pixel_ms','pixel_to_stable_ms','pixel_to_runtime_notification_ms',
        'onset_interval_width_ms')} for r in rows]))


if __name__=='__main__':
    main()
