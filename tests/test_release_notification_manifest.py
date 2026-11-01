import json
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def manifest():
    return json.loads((ROOT / "release_notification.json").read_text(encoding="utf-8"))

def historical_approval():
    return json.loads((ROOT / "release_notifications/approvals/alpha2-preview-20261015.json").read_text(encoding="utf-8"))

def test_current_version_requires_its_own_approval():
    g = manifest()
    assert g["schema_version"] == 2
    assert g["product"] == "dawloop-desktop"
    assert (g["version"], g["release_id"], g["channel"]) == ("v0.5.8-alpha.1", None, "preview")
    assert g["notification_enabled"] is False
    assert g["approved_by_owner"] is False
    assert g["approved_owner"] is None
    assert g["approval_command"] is None
    assert g["active_approval_id"] is None
    assert g["approvals"] == []
    assert isinstance(g["revocations"], list)

def test_approval_identity_and_expiration():
    a = historical_approval()
    assert a["approval_id"] == "dawloop-alpha2-preview-20261015"
    assert (a["product"], a["version"], a["release_id"], a["channel"]) == ("dawloop-desktop", "v0.5.6-alpha.2", 412979500, "preview")
    assert a["owner"] == "ryurikoneko"
    assert a["command"] == "ENABLE_PUBLIC_UPDATE_NOTIFICATION"
    assert a["content_url"] == "https://github.com/ryurikoneko/DAWLoop/releases/tag/v0.5.6-alpha.2"
    assert a["release_form"] == "prerelease"
    duration = datetime.fromisoformat(a["expires_at"]) - datetime.fromisoformat(a["approved_at"])
    assert timedelta(0) < duration <= timedelta(days=30)

def test_historical_approval_cannot_authorize_other_versions():
    a = historical_approval()
    assert a["version"] != manifest()["version"]
    assert a["stable"] == "DISABLED"
    assert a["other_versions"] == "DISABLED"
    assert a["automatic_download_install"] is False

def test_manual_acceptance_has_honest_provenance():
    a = historical_approval()
    assert a["acceptance"]["status"] == "MAINTAINER_CONFIRMED"
    assert a["acceptance"]["agent_direct_observation"] is False
    assert a["acceptance"]["per_case_results"] == "NOT_SEPARATELY_REPORTED"
    assert set(a["requested_content"]) == {"zh-CN", "en-US"}
