"""现场研究入口必须显式指定本机安装目录，公开仓库不猜维护者路径。"""

import os
from pathlib import Path


def fl_executable():
    value = os.environ.get('DAWLOOP_FL_EXECUTABLE')
    if not value:
        raise ValueError('EXPLICIT_FL_EXECUTABLE_REQUIRED')
    path = Path(value)
    if not path.is_absolute() or not path.is_file():
        raise ValueError('FL_EXECUTABLE_INVALID')
    return str(path)


def controller_settings(override=None):
    value = override or os.environ.get('DAWLOOP_CONTROLLER_SETTINGS')
    if not value:
        raise ValueError('EXPLICIT_CONTROLLER_SETTINGS_REQUIRED')
    path = Path(value)
    if not path.is_absolute() or not path.is_dir():
        raise ValueError('CONTROLLER_SETTINGS_INVALID')
    return path
