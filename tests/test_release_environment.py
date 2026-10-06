"""发布不能因为丢弃私有证据而重新开放已关闭的现场入口。"""

import importlib
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from release_environment import fl_executable


def test_missing_installation_never_guesses_maintainer_path(monkeypatch):
    monkeypatch.delenv('DAWLOOP_FL_EXECUTABLE', raising=False)
    with pytest.raises(ValueError, match='EXPLICIT_FL_EXECUTABLE_REQUIRED'):
        fl_executable()


def test_missing_route_state_refuses_before_installer(tmp_path, monkeypatch):
    guard = importlib.import_module('_runtime_v2_file_route')
    monkeypatch.setattr(guard, '__file__', str(tmp_path/'scripts/guard.py'))
    with pytest.raises(RuntimeError, match='拒绝安装'):
        guard.require_open_file_snapshot_route()
