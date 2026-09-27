from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class TargetIdentity:
    project_id: str
    pattern_id: str
    channel_index: int
    channel_name: str
    fl_studio_version: str

    def __post_init__(self) -> None:
        if not all((self.project_id, self.pattern_id, self.channel_name, self.fl_studio_version)):
            raise ValueError("工程、Pattern、Channel 和 FL Studio 版本必须明确")
        if type(self.channel_index) is not int or self.channel_index < 0:
            raise ValueError("channel_index 必须为非负整数")

    def to_dict(self) -> dict[str, str | int]:
        return asdict(self)


def require_same_target(expected: TargetIdentity, actual: TargetIdentity) -> None:
    if expected != actual:
        raise ValueError("FL Studio 当前目标与计划目标不一致；操作已停止")
