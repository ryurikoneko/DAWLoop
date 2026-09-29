from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class TargetIdentity:
    project_id: str
    pattern_id: str
    channel_index: int
    channel_name: str
    fl_studio_version: str
    pattern_number: int | None = None
    ppq: int | None = None
    safe_to_edit: bool | None = None
    api_version: int | None = None
    channel_index_type: str = "global"
    observed_at_utc: str | None = None

    def __post_init__(self) -> None:
        if not all((self.project_id, self.pattern_id, self.channel_name, self.fl_studio_version)):
            raise ValueError("工程、Pattern、Channel 和 FL Studio 版本必须明确")
        if type(self.channel_index) is not int or self.channel_index < 0:
            raise ValueError("channel_index 必须为非负整数")

    def to_dict(self) -> dict[str, str | int | bool | None]:
        return asdict(self)


def identity_from_response(response: dict) -> TargetIdentity:
    if not isinstance(response, dict) or response.get("success") is not True:
        raise ValueError("PATTERN_IDENTITY_UNAVAILABLE")
    target = response.get("target")
    if not isinstance(target, dict) or target.get("source") != "fl_studio_midi_scripting":
        raise ValueError("PATTERN_IDENTITY_UNAVAILABLE")
    number, index, ppq = (target.get(key) for key in ("pattern_number", "channel_index", "ppq"))
    if type(number) is not int or number < 1:
        raise ValueError("PATTERN_IDENTITY_UNAVAILABLE")
    if type(index) is not int or index < 0 or target.get("channel_index_type") != "global":
        raise ValueError("CHANNEL_IDENTITY_UNAVAILABLE")
    if type(ppq) is not int or ppq <= 0:
        raise ValueError("PPQ_UNAVAILABLE")
    if type(target.get("safe_to_edit")) is not bool:
        raise ValueError("FL_SAFE_TO_EDIT_UNAVAILABLE")
    if type(target.get("api_version")) is not int or target["api_version"] < 1:
        raise ValueError("FL_API_VERSION_UNAVAILABLE")
    for key in ("project_title", "pattern_name", "channel_name", "fl_studio_version"):
        if not isinstance(target.get(key), str) or not target[key].strip():
            raise ValueError(f"{key.upper()}_UNAVAILABLE")
    return TargetIdentity(
        project_id=target["project_title"], pattern_id=target["pattern_name"],
        channel_index=index, channel_name=target["channel_name"],
        fl_studio_version=target["fl_studio_version"], pattern_number=number,
        ppq=ppq, safe_to_edit=target["safe_to_edit"],
        api_version=target["api_version"], channel_index_type="global",
        observed_at_utc=datetime.now(timezone.utc).isoformat(),
    )


def _connection_for_port(port_name: str):
    from fl_studio_mcp.utils.midi_connection import MIDIConnection

    if not isinstance(port_name, str) or not port_name.strip():
        raise ValueError("MIDI_PORT_REQUIRED")

    class ExactPortConnection(MIDIConnection):
        def connect(self) -> bool:
            if self.is_connected:
                return True
            import mido

            if port_name not in mido.get_output_names():
                raise ValueError("MIDI_PORT_UNAVAILABLE")
            self._port = mido.open_output(port_name)
            self._port_name = port_name
            self._connected = True
            self._error = None
            return True

    return ExactPortConnection()


async def read_current_target(port_name: str) -> TargetIdentity:
    import asyncio

    def query():
        connection = _connection_for_port(port_name)
        try:
            return connection.send_command("dawloop.getTargetIdentity", timeout=3.0)
        finally:
            connection.disconnect()

    response = await asyncio.to_thread(query)
    return identity_from_response(response)


def require_same_target(expected: TargetIdentity, actual: TargetIdentity) -> None:
    if type(expected.pattern_number) is not int or expected.pattern_number < 1:
        raise ValueError("PATTERN_IDENTITY_UNAVAILABLE")
    if type(expected.ppq) is not int or expected.ppq <= 0:
        raise ValueError("PPQ_UNAVAILABLE")
    if actual.safe_to_edit is not True:
        raise ValueError("FL_NOT_SAFE_TO_EDIT")
    if type(actual.pattern_number) is not int or actual.pattern_number < 1:
        raise ValueError("PATTERN_IDENTITY_UNAVAILABLE")
    if type(actual.ppq) is not int or actual.ppq <= 0:
        raise ValueError("PPQ_UNAVAILABLE")
    if actual.channel_index_type != "global":
        raise ValueError("CHANNEL_INDEX_TYPE_MISMATCH")
    if expected.channel_index_type != "global":
        raise ValueError("CHANNEL_INDEX_TYPE_MISMATCH")
    if type(actual.api_version) is not int or actual.api_version < 1:
        raise ValueError("FL_API_VERSION_UNAVAILABLE")
    for field, code in (
        ("project_id", "PROJECT_TITLE_MISMATCH"),
        ("pattern_number", "PATTERN_NUMBER_MISMATCH"),
        ("pattern_id", "PATTERN_NAME_MISMATCH"),
        ("channel_index", "CHANNEL_INDEX_MISMATCH"),
        ("channel_name", "CHANNEL_NAME_MISMATCH"),
        ("ppq", "PPQ_MISMATCH"),
        ("fl_studio_version", "FL_STUDIO_VERSION_MISMATCH"),
    ):
        if getattr(expected, field) != getattr(actual, field):
            raise ValueError(code)
