"""仅静态检查本机宿主字节码，不导入或执行宿主模块。"""

import dis
import hashlib
import importlib.util
import json
import marshal
from pathlib import Path
import types


def inspect(path):
    payload = Path(path).read_bytes()
    if payload[:4] != importlib.util.MAGIC_NUMBER:
        raise ValueError('BYTECODE_VERSION_MISMATCH')
    root = marshal.loads(payload[16:])
    pending = [root]
    functions = {}
    while pending:
        code = pending.pop()
        if not isinstance(code, types.CodeType):
            raise ValueError('CODE_OBJECT_REQUIRED')
        pending.extend(value for value in code.co_consts if isinstance(value, types.CodeType))
        functions[code.co_name] = code
    code = functions.get('run_piano_roll_script')
    if code is None:
        raise ValueError('HOST_TOOL_FUNCTION_NOT_FOUND')
    instructions = list(dis.get_instructions(code))
    boundary = next((index for index, item in enumerate(instructions)
                     if item.opname == 'LOAD_ATTR' and item.argval == 'runPRScript'), None)
    if boundary is None:
        raise ValueError('NATIVE_BOUNDARY_NOT_FOUND')
    tail = instructions[boundary:boundary + 4]
    return_forwarded = [item.opname for item in tail] == [
        'LOAD_ATTR', 'LOAD_FAST', 'CALL', 'RETURN_VALUE']
    return {
        'host_artifact': Path(path).name,
        'host_artifact_sha256': hashlib.sha256(payload).hexdigest(),
        'scope': 'DISK_BYTECODE_STATIC_NOT_RUNTIME_LOADED',
        'host_module_executed': False,
        'function': code.co_name,
        'function_source_line': code.co_firstlineno,
        'native_call': 'ilmcp.runPRScript(source)',
        'native_return_forwarded_by_tool': return_forwarded,
        'boundary_offsets': [item.offset for item in tail],
        'boundary_opcodes': [item.opname for item in tail],
        'apply_invocation_implementation_visible': False,
        'apply_return_receiver': None,
        'callback_serializer_implementation_visible': False,
        'classification': 'C_STATIC_UNRESOLVED',
        'direct_return_contract': 'UNRESOLVED',
        'live_calls': 0,
    }


if __name__ == '__main__':
    import sys
    result = inspect(sys.argv[1])
    if len(sys.argv) == 3:
        destination = Path(sys.argv[2])
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open('x', encoding='utf-8', newline='\n') as output:
            json.dump(result, output, ensure_ascii=False, indent=2)
            output.write('\n')
    print(json.dumps(result, ensure_ascii=False))
