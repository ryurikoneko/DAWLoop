"""对指定 FL MIDI 输入执行一次无 DAW 状态副作用的触发连通性检查。"""

import argparse
import json
import uuid
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="只测试 DAWLoop Controller 是否收到 MIDI 触发")
    parser.add_argument("--midi-port", required=True, help="FL 控制器对应的精确 MIDI 输出端口名")
    parser.add_argument("--settings-dir", type=Path, required=True, help="FL 活动 Settings 目录")
    args = parser.parse_args()

    from fl_studio_mcp.utils.midi_connection import MIDIConnection

    class ExactPortConnection(MIDIConnection):
        def __init__(self):
            super().__init__()
            self._hardware_dir = args.settings_dir / "Hardware" / "DAWLoopMCP"
            self._command_file = self._hardware_dir / "mcp_command.json"
            self._response_file = self._hardware_dir / "mcp_response.json"

        def connect(self) -> bool:
            if self.is_connected:
                return True
            import mido
            if args.midi_port not in mido.get_output_names():
                raise ValueError("MIDI_PORT_UNAVAILABLE")
            self._port = mido.open_output(args.midi_port)
            self._port_name = args.midi_port
            self._connected = True
            self._error = None
            return True

    connection = ExactPortConnection()
    if connection._command_file.exists():
        print(json.dumps({"status": "STOP", "stage": "preflight", "error_code": "MIDI_COMMAND_QUEUE_BUSY"}))
        return 1

    request_id = uuid.uuid4().hex
    try:
        response = connection.send_command("dawloop.ping", {"request_id": request_id}, timeout=3.0)
    except Exception as error:
        print(json.dumps({"status": "STOP", "stage": "send", "error_code": type(error).__name__}))
        return 1
    finally:
        connection.disconnect()

    result = {
        "request_id": request_id,
        "midi_port": args.midi_port,
        "midi_trigger_sent": not str(response.get("error", "")).startswith("Failed to send MIDI trigger"),
        "midi_event_received": response.get("stage") == "midi_callback" and response.get("request_id") == request_id,
        "response": response,
    }
    result["status"] = "PASS" if result["midi_event_received"] and response.get("status") == "PASS" else "STOP"
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
