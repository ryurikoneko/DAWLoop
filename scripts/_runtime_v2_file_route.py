"""保留历史源码与离线测试，拒绝再次启动已关闭的文件现场路线。"""

import json
from pathlib import Path


def require_open_file_snapshot_route():
    marker = Path(__file__).resolve().parents[1] / 'evidence/runtime_v2/file_snapshot_route.json'
    if not marker.exists():
        raise RuntimeError('文件快照路线状态未知，拒绝安装及现场派发')
    state = json.loads(marker.read_text(encoding='utf-8'))
    if not isinstance(state, dict) or state.get('status') != 'OPEN':
        raise RuntimeError('钢琴卷帘文件快照路线已关闭或状态未知，拒绝安装及现场派发')
