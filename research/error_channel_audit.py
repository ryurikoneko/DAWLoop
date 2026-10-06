"""只审计可见异常边界，不能由Python外层推断原生runner的行为。"""

import dis
import hashlib
import importlib.util
import json
import marshal
from pathlib import Path
import types


def inspect(artifact, catalog):
    raw = Path(artifact).read_bytes()
    if raw[:4] != importlib.util.MAGIC_NUMBER:
        raise ValueError('BYTECODE_VERSION_MISMATCH')
    pending = [marshal.loads(raw[16:])]
    functions = {}
    while pending:
        code = pending.pop()
        if not isinstance(code, types.CodeType):
            raise ValueError('CODE_OBJECT_REQUIRED')
        pending.extend(x for x in code.co_consts if isinstance(x, types.CodeType))
        functions[code.co_name] = code
    tool = functions['run_piano_roll_script']
    instructions = list(dis.get_instructions(tool))
    boundary = next(i for i, op in enumerate(instructions)
                    if op.opname == 'LOAD_ATTR' and op.argval == 'runPRScript')
    call = instructions[boundary + 2]
    if call.opname != 'CALL':
        raise ValueError('NATIVE_BOUNDARY_CHANGED')
    regions = [dict(start=x.start, end=x.end, target=x.target, depth=x.depth)
               for x in dis.Bytecode(tool).exception_entries]
    covered = [x for x in regions if x['start'] <= call.offset < x['end']]
    decorator = list(dis.get_instructions(functions['mcp_tool']))
    tag_only = [x.opname for x in decorator] == [
        'RESUME', 'LOAD_CONST', 'LOAD_FAST', 'STORE_ATTR', 'LOAD_FAST', 'RETURN_VALUE']
    saved_catalog = json.loads(Path(catalog).read_text(encoding='utf-8'))
    tools = saved_catalog['tools']
    return dict(
        host_artifact=Path(artifact).name,
        host_artifact_sha256=hashlib.sha256(raw).hexdigest(),
        scope='DISK_STATIC_AND_SAVED_CATALOG_NOT_NEW_LIVE_DISCOVERY',
        native_call_offset=call.offset, exception_regions=regions,
        native_call_covered_by_local_except=bool(covered),
        window_exception_handler='showWindow errors ignored; execution continues to runPRScript',
        decorator_tag_only=tag_only,
        local_exception_swallowing_proven=False,
        internal_runner_exception_propagation=None,
        host_callback_error_serialization=None,
        bridge_raw_passthrough='bridge.js finish/onRun forwards payload unchanged',
        existing_decoder='response.py _unwrap classifies error/isError as TOOL_ERROR; not raw inspection',
        error_channel_data_propagation='UNRESOLVED',
        classification='C_STATIC_UNRESOLVED',
        structured_note_readback='BLOCKED_ON_CURRENT_NORMAL_RETURN_PATH',
        gopher_structured_readback='NOT_PROVEN_ERROR_PATH_UNTESTED',
        known_catalog_hash=saved_catalog['hash'], tool_count=len(tools),
        tool_names=[x['name'] for x in tools],
        alternative_capabilities=[
            dict(source='saved native catalog', result='NO_IDENTIFIED_DEDICATED_NOTE_ENUMERATOR',
                 limitation='No new live catalog; absence is limited to this catalog'),
            dict(source='existing Controller implementation', result='NO_SCORE_READER_IMPLEMENTED'),
            dict(source='official MIDI channels API', result='STEP_GRID_READS_ONLY_NOT_CERTIFIED_FULL_NOTE_SET',
                 limitation='No complete note enumeration/duplicate multiplicity contract identified'),
            dict(source='official Piano Roll API', result='SCORE_GETNOTE_EXISTS_TRANSPORT_UNPROVEN'),
            dict(source='Community fl_get_piano_roll_state', result='LAST_EXPORTED_FILE_CACHE_EXCLUDED'),
        ],
        error_probe_candidate=dict(
            status='DESIGN_ONLY_NOT_INSTALLED_OR_DISPATCH_ENABLED',
            source='import flpianoroll as flp\n\n\ndef createDialog() -> flp.ScriptDialog:\n'
                   '    return flp.ScriptDialog("DAWLoop Error Contract Probe", "Diagnostic propagation research.")\n\n\n'
                   'def apply(form):\n    count = flp.score.noteCount\n'
                   '    raise RuntimeError("DAWLOOP_PROBE_V1|NOTECOUNT=" + str(count))\n',
            max_dispatches=1, retry=0, fallback=0, note_writes=0,
            sentinel_location='raw error.message or result.isError text, never echoed request/log/metadata',
            positive='sentinel and observed expected count in actual raw error body',
            generic_failure='NO_DATA_OBSERVED_IN_THIS_EXPERIMENT; not proof all exceptions are always swallowed',
            no_callback='EXECUTION_LIFECYCLE_UNRESOLVED',
            capability_limit='diagnostic only; no notes[], freshness, producer binding or VERIFIED',
            lifecycle_side_effect_risk=True,
        ),
        host_started=False, host_calls=0, script_dispatches=0,
        navigation_transactions=0, notes_read_live=False,
    )


if __name__ == '__main__':
    import sys
    result = inspect(sys.argv[1], sys.argv[2])
    destination = Path(sys.argv[3])
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('x', encoding='utf-8', newline='\n') as output:
        json.dump(result, output, ensure_ascii=False, indent=2)
        output.write('\n')
    print(json.dumps({key: result[key] for key in (
        'classification', 'native_call_covered_by_local_except', 'decorator_tag_only',
        'error_channel_data_propagation', 'tool_count', 'host_calls')}))
