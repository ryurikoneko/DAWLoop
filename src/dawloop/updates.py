# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 ryurikoneko
"""发布提醒与本地版本观察；不执行升级或宿主操作。"""

from __future__ import annotations

import ast
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
from urllib.request import Request, urlopen

REPOSITORY = "https://github.com/ryurikoneko/DAWLoop"
RELEASES_API = "https://api.github.com/repos/ryurikoneko/DAWLoop/releases?per_page=100"
CACHE_SECONDS = 86400
MAX_RESPONSE_BYTES = 1024 * 1024


def version_key(value: str) -> tuple[int, int, int, int, int, int, int] | None:
    """比较项目采用的 PEP 440 / SemVer 预发布格式；未知格式不猜顺序。"""
    match = re.fullmatch(
        r"v?(\d+)\.(\d+)\.(\d+)(?:[-.]?(a|alpha|b|beta|rc)[.-]?(\d*))?(?:\.dev(\d+))?", value
    )
    if not match:
        return None
    major, minor, patch, stage, number, dev = match.groups()
    rank = {"a": 0, "alpha": 0, "b": 1, "beta": 1, "rc": 2, None: 3}[stage]
    if stage is None and dev is not None:
        rank = -1
    return int(major), int(minor), int(patch), rank, int(number or 0), int(dev is None), int(dev or 0)


def select_release(data: object, channel: str) -> dict | None:
    if not isinstance(data, list):
        raise ValueError("INVALID_RELEASE_RESPONSE")
    candidates = []
    for item in data:
        if not isinstance(item, dict) or item.get("draft") is not False:
            continue
        tag, url = item.get("tag_name"), item.get("html_url")
        if not isinstance(tag, str) or not isinstance(url, str):
            continue
        key = version_key(tag)
        if key is None or not re.fullmatch(re.escape(REPOSITORY) + r"/releases/tag/[A-Za-z0-9._-]+", url):
            continue
        if channel == "stable" and (item.get("prerelease") is not False or key[3] != 3):
            continue
        candidates.append((key, {"tag": tag, "url": url}))
    return max(candidates, key=lambda pair: pair[0])[1] if candidates else None


def fetch_releases() -> object:
    request = Request(RELEASES_API, headers={"Accept": "application/vnd.github+json", "User-Agent": "DAWLoop-update-check"})
    with urlopen(request, timeout=3) as response:
        # 限制异常响应大小，且不持久化远端 release 正文或任意字段。
        content = response.read(MAX_RESPONSE_BYTES + 1)
    if len(content) > MAX_RESPONSE_BYTES:
        raise ValueError("RELEASE_RESPONSE_TOO_LARGE")
    return json.loads(content)


def default_cache_path(channel: str) -> Path:
    root = Path(os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return root / "dawloop" / f"updates-{channel}.json"


def _read_cache(path: Path, channel: str, now: float) -> dict | None:
    try:
        if path.stat().st_size > 8192:
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        checked = data.get("checked_at")
        if (data.get("schema") != 1 or data.get("channel") != channel
                or type(checked) not in (int, float) or not 0 <= now - checked
                or data.get("status") not in ("AVAILABLE", "NO_RELEASE", "UNAVAILABLE")):
            return None
        release = data.get("release")
        if data["status"] == "AVAILABLE":
            if not isinstance(release, dict):
                return None
            sanitized = select_release([dict(draft=False, prerelease=False,
                tag_name=release.get("tag"), html_url=release.get("url"))], channel)
            if sanitized != release:
                return None
        elif release is not None:
            return None
        return data
    except (OSError, ValueError, TypeError, AttributeError):
        return None


def _write_cache(path: Path, data: dict) -> bool:
    temporary = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, ensure_ascii=False)
        os.replace(temporary, path)
        return True
    except OSError:
        return False
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def check_updates(installed: str, *, channel: str = "prerelease", disabled: bool = False,
                  refresh: bool = False, cache_path: Path | None = None,
                  now: float | None = None, fetch=None) -> dict:
    if disabled or os.environ.get("DAWLOOP_NO_UPDATE_CHECK", "").lower() in ("1", "true", "yes"):
        return {"status": "DISABLED", "release_status": "CHECK_DISABLED", "update_available": None}
    if channel not in ("stable", "prerelease"):
        raise ValueError("INVALID_UPDATE_CHANNEL")
    now = time.time() if now is None else now
    path = cache_path or default_cache_path(channel)
    cached = _read_cache(path, channel, now)
    from_cache = bool(cached and not refresh and now - cached["checked_at"] < CACHE_SECONDS)
    cache_written = None
    if from_cache:
        result = dict(cached)
    else:
        try:
            release = select_release((fetch or fetch_releases)(), channel)
            status = "AVAILABLE" if release else "NO_RELEASE"
        except Exception:
            # 网络错误文本可能包含代理凭据，只保存固定诊断码。
            release, status = None, "UNAVAILABLE"
        result = dict(schema=1, channel=channel, checked_at=now, status=status, release=release)
        cache_written = _write_cache(path, result)
    latest = version_key(result["release"]["tag"]) if result["release"] else None
    current = version_key(installed)
    if latest is None or current is None:
        release_status = "CHECK_UNAVAILABLE"
    elif current > latest:
        release_status = "AHEAD_OF_RELEASE"
    elif current < latest:
        release_status = "UPDATE_AVAILABLE"
    else:
        release_status = "UP_TO_DATE"
    result.update(from_cache=from_cache, age_seconds=now - result["checked_at"], stale=False,
                  release_status=release_status,
                  cache_written=cache_written,
                  previous_checked_at=cached["checked_at"] if cached and not from_cache else None,
                  update_available=latest > current if latest is not None and current is not None else None)
    return result


def installation_source() -> dict:
    root = Path(__file__).resolve().parents[2]
    if (root / ".git").exists():
        def git(*args):
            return subprocess.run(["git", "-C", str(root), *args], check=True,
                capture_output=True, text=True, timeout=3).stdout.strip()
        try:
            dirty = bool(git("status", "--porcelain"))
            branch = git("symbolic-ref", "--short", "HEAD")
            remote = git("remote", "get-url", "origin")
            trusted = remote in (REPOSITORY, REPOSITORY + ".git", "git@github.com:ryurikoneko/DAWLoop.git")
            ahead, behind = map(int, git("rev-list", "--left-right", "--count", "HEAD...@{upstream}").split())
            return dict(kind="GIT_CHECKOUT", dirty=dirty, branch=branch, ahead=ahead, behind=behind,
                        safe_pull=trusted and not dirty and ahead == 0 and branch == "main")
        except (OSError, subprocess.SubprocessError, ValueError):
            return dict(kind="GIT_CHECKOUT", safe_pull=False, state="UNKNOWN")
    try:
        distribution = importlib.metadata.distribution("dawloop")
        direct = distribution.read_text("direct_url.json")
        if direct:
            data = json.loads(direct)
            kind = "EDITABLE_LOCAL" if data.get("dir_info", {}).get("editable") else "DIRECT_PACKAGE"
            return dict(kind=kind, safe_pull=False)
    except (importlib.metadata.PackageNotFoundError, ValueError, AttributeError):
        pass
    # 缺少 direct_url 不能证明安装源为 PyPI，也可能来自私有索引。
    return dict(kind="INDEX_OR_UNKNOWN", safe_pull=False)


def update_instructions(source: dict) -> list[str]:
    if source.get("safe_pull"):
        return ["Review the release and confirm this checkout is the intended update target.",
                "git pull --ff-only", "python -m pip install -e .",
                "dawloop setup-fl", "Reload the Controller in FL Studio, then run dawloop doctor --probe-fl."]
    return ["Review the release and your installation source before updating.",
            "Git checkouts: inspect branch, local changes and upstream before any pull.",
            "After an explicit package update, run dawloop setup-fl and Reload the Controller in FL Studio."]


def _constants(path: Path) -> dict:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        return {node.targets[0].id: node.value.value for node in tree.body
                if isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name) and isinstance(node.value, ast.Constant)}
    except (OSError, SyntaxError, UnicodeError):
        return {}


def controller_versions(settings_dir: Path) -> dict:
    from dawloop.controller_runtime import installed_controller_identity, inspect_controller_lifecycle
    from dawloop.setup import configured_scripts
    source = Path(__file__).parent / "fl_scripts" / "device_DAWLoopController.py"
    installed = configured_scripts(settings_dir)["controller"]
    expected = _constants(source)
    installed_constants = _constants(installed)
    disk_build, disk_sha = installed_controller_identity(installed)
    lifecycle = inspect_controller_lifecycle(installed, expected_build_id=disk_build)
    observation = lifecycle["runtime"]
    runtime = observation.payload or {}
    digest = hashlib.sha256(source.read_bytes()).hexdigest()[:16] if source.exists() else None
    disk_match = disk_build.endswith("+controller:" + digest) if disk_build and digest else None
    runtime_fresh = observation.ready and lifecycle["verification"] == "PASS" and disk_build is not None
    protocol = runtime.get("protocol_version") if runtime_fresh else None
    return dict(expected_controller_digest=digest, installed_build=disk_build,
                installed_sha256=disk_sha, installed_matches_package=disk_match,
                runtime_build=runtime.get("build_id"), runtime_status=observation.code,
                installed_protocol=installed_constants.get("PROTOCOL_VERSION"),
                expected_protocol=expected.get("PROTOCOL_VERSION"), runtime_protocol=protocol,
                protocol_match=(protocol == expected.get("PROTOCOL_VERSION")) if protocol is not None else None)


def print_update_status(installed: str, settings_dir: Path, **options) -> None:
    from datetime import datetime, timezone
    report = check_updates(installed, **options)
    print("\nDAWLoop Update Status")
    print(f"CLI version                 {installed}")
    print(f"Release status              {report['release_status']}")
    if report["status"] != "DISABLED":
        checked = datetime.fromtimestamp(report["checked_at"], timezone.utc).isoformat()
        print(f"Checked at (UTC)            {checked}")
        print(f"Cache age / source          {report['age_seconds']:.0f}s / {'cache' if report['from_cache'] else 'network attempt'}")
        if report["cache_written"] is False:
            print("Cache persistence           UNAVAILABLE; next run may retry")
        release = report.get("release")
        print(f"Latest published release    {release['tag'] if release else 'UNKNOWN / none in selected channel'}")
        available = report["update_available"]
        print(f"Update available            {'YES' if available is True else 'NO' if available is False else 'UNKNOWN'}")
        if release:
            print(f"Release notes               {release['url']}")
    source = installation_source()
    print(f"Installation source         {source['kind']}")
    versions = controller_versions(settings_dir)
    for name, key in (("Installed FL Controller", "installed_build"), ("Runtime FL Controller", "runtime_build"),
                      ("Runtime observation", "runtime_status"), ("Expected protocol", "expected_protocol"),
                      ("Installed protocol", "installed_protocol"),
                      ("Fresh runtime protocol", "runtime_protocol")):
        print(f"{name:<28}{versions[key] if versions[key] is not None else 'UNKNOWN'}")
    for name, key in (("Installed build/package", "installed_matches_package"), ("Runtime protocol match", "protocol_match")):
        value = versions[key]
        print(f"{name:<28}{'MATCH' if value is True else 'MISMATCH' if value is False else 'UNKNOWN'}")
    if report["update_available"] or versions["installed_matches_package"] is False or versions["protocol_match"] is False:
        if report["release_status"] == "AHEAD_OF_RELEASE":
            print("Controller action: review local script/protocol compatibility; no package downgrade recommended.")
        else:
            print("Recommended action:")
            for line in update_instructions(source):
                print(f"  {line}")
    if report["release_status"] == "AHEAD_OF_RELEASE":
        print("No update action recommended. This installation is newer than the latest published release.")
