"""只读显示当前 FL Studio 目标身份；不会触发音符写入。"""

import asyncio
import argparse
import json
from pathlib import Path

from dawloop.adapters.fl_studio_mcp.identity import read_current_target

PROJECT_NAME = "DAWLoop_Live_Verification"


def main() -> int:
    parser = argparse.ArgumentParser(description="只读查询 FL Studio 测试目标身份")
    parser.add_argument("--midi-port", required=True, help="与 FL Studio 中启用的 DAWLoop 控制器对应的精确 MIDI 输出端口名")
    parser.add_argument("--settings-dir", type=Path, help="活动 FL Studio Settings 目录；用于非默认用户数据位置")
    args = parser.parse_args()
    try:
        identity = asyncio.run(read_current_target(args.midi_port, settings_dir=args.settings_dir))
    except Exception as error:
        print(json.dumps({"status": "STOP", "reason": type(error).__name__}, ensure_ascii=False))
        return 1
    if identity.project_id != PROJECT_NAME:
        print(json.dumps({"status": "STOP", "reason": "PROJECT_TITLE_MISMATCH"}, ensure_ascii=False))
        return 1
    print(json.dumps({"status": "READBACK_RECEIVED", "actual": identity.to_dict()}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
