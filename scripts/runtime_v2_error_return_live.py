"""复用前轮会话与取证路径，仅替换固定异常研究合同。"""

import hashlib
from pathlib import Path
import runtime_v2_scalar_return_live as live
from research.error_return_contract import assess_error_response

live.OUTPUT = live.ROOT / 'evidence/runtime_v2/error_return/session_1'
live.SOURCE = live.ROOT / 'research/piano_roll_probe/error_return_v1.pyscript'
live.HASH = 'e03610c0c9551d31086e8f7b5a07d0b57821563d4851e9d9ac9fefb1ae2d1a1e'
live.PROBE_ID = 'ERROR_RETURN_PROBE_V1'
live.BRIDGE_METHOD = 'invokeFixedErrorProbe'
live.OPERATION_ID = 'error-return-session-1'
live.ASSESSOR = assess_error_response
base_freeze = live.freeze


def freeze():
    result = base_freeze()
    for name in ('scripts/runtime_v2_error_return_live.py',
                 'research/error_return_contract.py',
                 'research/piano_roll_probe/error_return_v1.pyscript'):
        result[name] = hashlib.sha256((live.ROOT / name).read_bytes()).hexdigest()
    return result


live.freeze = freeze

if __name__ == '__main__':
    live.main()
