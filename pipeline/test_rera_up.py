"""Tests for UP RERA evidence rules; no network requests or real claims."""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import rera_up


def test_portal_claim_is_not_verification(tmp_path):
    path = tmp_path / "noida.json"
    path.write_text(json.dumps({"projects": []}))
    rows = [{"id": "a", "name": "Example Towers", "locality": "Sector 10, Noida",
             "rera_id": "UPRERAPRJ12345"}]
    stats = rera_up.annotate(rows, path)
    assert stats["verified"] == 0
    assert rows[0]["rera_verification"]["status"] == "not_checked"


def test_verified_requires_official_evidence_and_matching_project(tmp_path):
    path = tmp_path / "noida.json"
    path.write_text(json.dumps({"projects": [{
        "registration_id": "UPRERAPRJ12345",
        "official_name": "Example Towers", "locality": "Sector 10",
        "official_url": "https://www.up-rera.in/",
        "checked_on": "2026-11-24"
    }]}))
    rows = [{"id": "a", "name": "Example Towers", "locality": "Sector 10, Noida",
             "rera_id": "UPRERAPRJ12345"},
            {"id": "b", "name": "Different Towers", "locality": "Sector 10, Noida",
             "rera_id": "UPRERAPRJ12345"}]
    rera_up.annotate(rows, path)
    assert rows[0]["rera_verification"]["status"] == "verified"
    assert rows[1]["rera_verification"]["status"] == "conflict"


def test_non_official_source_is_rejected(tmp_path):
    path = tmp_path / "noida.json"
    path.write_text(json.dumps({"projects": [{
        "registration_id": "UPRERAPRJ12345",
        "official_name": "Example Towers", "locality": "Sector 10",
        "official_url": "https://other.example.com/",
        "checked_on": "2026-11-24"
    }]}))
    try:
        rera_up.annotate([], path)
    except ValueError:
        pass
    else:
        raise AssertionError("An unofficial source must never establish UP RERA verification")
