"""只读显示当前 FL Studio 目标身份；不会触发音符写入。"""

import asyncio
import json

from dawloop.adapters.fl_studio_mcp.identity import read_current_target

PROJECT_NAME = "DAWLoop_Live_Verification"


def main() -> int:
    try:
        identity = asyncio.run(read_current_target())
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
