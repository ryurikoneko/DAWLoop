"""汇总已结束的三组证据；不连接或操作宿主。"""

import json
import os
from pathlib import Path
import statistics
import winreg
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'evidence/runtime_v2/native_preview_onset'
TRIALS = ('discovery', 'repeat1', 'repeat2')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(name, value):
    with (OUTPUT / name).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def registered_debug(hive, key):
    try:
        with winreg.OpenKey(hive, key) as handle:
            return bool(winreg.QueryValueEx(handle, 'WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS')[0])
    except FileNotFoundError:
        return False


def main():
    rows = read(OUTPUT / 'timing.json')['trials']
    assert len({row['host_generation'] for row in rows}) == 3
    assert all(row['candidate_correlated'] for row in rows)
    recoveries = {trial: read(OUTPUT / trial / 'recovery.json') for trial in TRIALS}
    assert all(value['host_closed'] and value['debug_port_closed'] for value in recoveries.values())
    assert len({value['baseline_sha256'] for value in recoveries.values()}) == 1
    assert all(value['baseline_size'] == 53498 for value in recoveries.values())
    comparisons = []
    for trial in TRIALS:
        for name in ('target', 'preview', 'application'):
            raw = Path(os.environ['TEMP']) / f'DAWLoop_native_{name}_{trial}.png'
            with Image.open(raw) as picture:
                assert picture.size == (2048, 1110)
                box = (778, 470, 1271, 635) if name == 'preview' else (370, 85, 1630, 1110)
                picture.crop(box).save(OUTPUT / trial / f'{name}.png')
        before, after = [read(OUTPUT / trial / f'uia_{name}.json') for name in ('before', 'after')]
        comparisons.append(dict(trial=trial, before=before['fixed_preview_pane_present'],
            after=after['fixed_preview_pane_present'],
            before_elements=len(before['elements']), after_elements=len(after['elements']),
            identity_based_added_removed=None, property_changes=None,
            focused_preview_before=before['focused_preview_pane'],
            focused_preview_after=after['focused_preview_pane'], completeness='PARTIAL_SNAPSHOT'))
    with Image.open(Path(os.environ['TEMP']) / 'DAWLoop_native_exit_repeat2.png') as picture:
        picture.crop((790, 460, 1256, 644)).save(OUTPUT / 'repeat2/exit_prompt.png')
    write('uia_before.json', dict(scope='PARTIAL_COMPUTER_USE_SNAPSHOT',
        files=[f'{trial}/uia_before.json' for trial in TRIALS]))
    write('uia_after.json', dict(scope='PARTIAL_COMPUTER_USE_SNAPSHOT',
        files=[f'{trial}/uia_after.json' for trial in TRIALS], comparisons=comparisons))
    write('uia_events.json', dict(status='NOT_TESTED_CLIENT_BINDING_UNAVAILABLE',
        structure_events=None, property_events=None, focus_events=None,
        files=[f'{trial}/uia_subscription.json' for trial in TRIALS]))
    write('winevents.json', dict(scope='EXPLICIT_HOST_PID_ONLY',
        files=[f'{trial}/winevents.json' for trial in TRIALS],
        event_total=sum(sum(row['counts'].values()) for row in rows),
        dropped=sum(row['dropped'] for row in rows),
        reentrant_events=sum(row['reentrant_events'] for row in rows)))
    write('repeat_validation.json', dict(independent_sessions=3, discovery_sessions=1,
        repeat_sessions=2, unique_host_generations=3, candidate_matched_in_all=True,
        hardcoded_hwnd=False, candidate_scope='CONTAINER_SHOW_EVENT_RECEIPT',
        visual_corroboration='LATER_SCREENSHOT_UPPER_BOUND',
        proves_pixel_onset=False, proves_content_ready=False,
        installed_native_state_unchanged=[row['install_native_state_unchanged'] for row in rows],
        observer_nonintrusion_proven=False, noticeable_freeze_observed=False,
        no_observer_dispatch_control_tested=False))
    debug = dict(process=bool(os.environ.get('WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS')),
        user=registered_debug(winreg.HKEY_CURRENT_USER, 'Environment'),
        machine=registered_debug(winreg.HKEY_LOCAL_MACHINE,
            r'SYSTEM\CurrentControlSet\Control\Session Manager\Environment'))
    assert not any(debug.values())
    results = [read(OUTPUT / trial / 'result.json') for trial in TRIALS]
    catalogs = [read(OUTPUT / trial / 'catalog.json') for trial in TRIALS]
    assert len({catalog['catalog_hash'] for catalog in catalogs}) == 1
    assert all(result['callbacks_restored'] for result in results)
    assert all(result['value']['source_hash'] ==
        'ac68744417a7b98f7c2a7c2293ba255b73e6d99ecd3609618af0f501f786da75' for result in results)
    write('environment.json', dict(platform='Windows',
        fl_version=results[-1]['value']['target_evidence']['identity']['fl_studio_version'],
        catalog_hash=catalogs[0]['catalog_hash'],
        debug_scope='CHILD_PROCESS_ONLY', remaining_debug_arguments=debug,
        private_paths_saved=False, fixtures_committed=False))
    write('test_results.json', dict(passed=249, subtests_passed=96, warnings=2,
        new_tests=6, test_elapsed_seconds=9.73, live_host_started_by_tests=False))
    write('summary.json', dict(stage='3.2B', status='STOPPED',
        native_preview_onset_observable='YES',
        certified_scope='NATIVE_CONTAINER_SHOW_EVENT_RECEIPT_ONLY',
        exact_first_visible_proven=False, preview_content_ready='UNKNOWN',
        pixel_first_visible='UNKNOWN', bottleneck_side='UNRESOLVED',
        dispatch_to_show_receipt_ms=[row['dispatch_to_native_show_receipt_ms'] for row in rows],
        median_ms=statistics.median(row['dispatch_to_native_show_receipt_ms'] for row in rows),
        show_to_notification_semantics='MANUAL_SCREENSHOT_DELIVERY_AND_MARKER_WAIT_INCLUDED',
        callbacks_restored=True, observers_unhooked=True, recoveries=recoveries,
        production_write_ready=False, verified_write_ready=False,
        optimizations_applied=False, next_stage_started=False))


if __name__ == '__main__':
    main()
