import json
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def manifest():
    return json.loads((ROOT / "release_notification.json").read_text(encoding="utf-8"))

def test_version_scoped_owner_approval():
    g = manifest()
    assert g["schema_version"] == 2
    assert g["product"] == "dawloop-desktop"
    assert g["notification_enabled"] is True
    assert g["approved_by_owner"] is True
    assert g["approved_owner"] == "ryurikoneko"
    assert g["approval_command"] == "ENABLE_PUBLIC_UPDATE_NOTIFICATION"
    assert (g["version"], g["release_id"], g["channel"]) == ("v0.5.6-alpha.2", 412979500, "preview")
    assert len(g["approvals"]) == 1

def test_approval_identity_and_expiration():
    g = manifest()
    a = g["approvals"][0]
    assert a["approval_id"] == g["active_approval_id"]
    for field in ("product", "version", "release_id", "channel"):
        assert a[field] == g[field]
    assert a["owner"] == g["approved_owner"]
    assert a["command"] == g["approval_command"]
    assert a["content_url"] == "https://github.com/ryurikoneko/DAWLoop/releases/tag/v0.5.6-alpha.2"
    assert a["release_form"] == "prerelease"
    duration = datetime.fromisoformat(a["expires_at"]) - datetime.fromisoformat(a["approved_at"])
    assert timedelta(0) < duration <= timedelta(days=30)
    assert isinstance(g["revocations"], list)

def test_approval_record_matches_embedded_record():
    a = json.loads((ROOT / "release_notifications/approvals/alpha2-preview-20261015.json").read_text(encoding="utf-8"))
    assert a == manifest()["approvals"][0]
    assert a["stable"] == "DISABLED"
    assert a["other_versions"] == "DISABLED"
    assert a["automatic_download_install"] is False

def test_manual_acceptance_has_honest_provenance():
    a = manifest()["approvals"][0]
    assert a["acceptance"]["status"] == "MAINTAINER_CONFIRMED"
    assert a["acceptance"]["agent_direct_observation"] is False
    assert a["acceptance"]["per_case_results"] == "NOT_SEPARATELY_REPORTED"
    assert set(a["requested_content"]) == {"zh-CN", "en-US"}
