"""Regression coverage for the five-station exhibition validator (C5a)."""
from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_exhibition as validator


def test_c5a_required_assets_match_current_five_stations():
    assert len(validator.MAIN_PAGE_CSS) == 5
    assert set(validator.MAIN_PAGE_CSS) == {"home", "call", "sms", "qr", "viber"}
    assert all(asset[1:] in validator.REQUIRED_FRONTEND_FILES
               for asset in validator.MAIN_PAGE_CSS.values())
    assert {"/viber", "/api/viber-scenario", "/api/readiness"}.issubset(
        validator.CRITICAL_ROUTES)
    assert "static/css/base.css" not in validator.REQUIRED_FRONTEND_FILES
    assert "static/js/viber.js" in validator.REQUIRED_FRONTEND_FILES


def _mock_frontend(root: Path) -> None:
    for rel in validator.REQUIRED_FRONTEND_FILES:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("", encoding="utf-8")
    for station, css in validator.MAIN_PAGE_CSS.items():
        (root / "frontend" / station / "index.html").write_text(
            f'<html><head><link rel="stylesheet" href="{css}?v=test"></head></html>',
            encoding="utf-8",
        )


def test_c5a_main_page_css_validation_accepts_versioned_local_links(tmp_path, monkeypatch):
    _mock_frontend(tmp_path)
    monkeypatch.setattr(validator, "ROOT", tmp_path)
    report = validator.Report()
    validator.check_frontend_assets(report)
    assert not report.errors
    assert sum("active parity stylesheet linked" in item for item in report.passes) == 5


def test_c5a_detects_legacy_css_substitution(tmp_path, monkeypatch):
    _mock_frontend(tmp_path)
    page = tmp_path / "frontend" / "sms" / "index.html"
    page.write_text('<link rel="stylesheet" href="/static/css/sms.css">', encoding="utf-8")
    (tmp_path / "static/css/sms.css").write_text("", encoding="utf-8")
    monkeypatch.setattr(validator, "ROOT", tmp_path)
    report = validator.Report()
    validator.check_frontend_assets(report)
    assert any("sms: expected active stylesheet missing" in error for error in report.errors)


def test_c5a_detects_missing_parity_asset(tmp_path, monkeypatch):
    _mock_frontend(tmp_path)
    (tmp_path / "static/css/screens/viber-parity.css").unlink()
    monkeypatch.setattr(validator, "ROOT", tmp_path)
    report = validator.Report()
    validator.check_frontend_assets(report)
    assert any("Missing required frontend file: static/css/screens/viber-parity.css" in error
               for error in report.errors)


def test_c5a_readiness_contract_is_checked(monkeypatch):
    monkeypatch.setattr(validator, "import_exhibition_app", lambda report: object())
    correct = {"status": "ready", "stations": {
        "telephone": "ready", "sms": "ready", "qr": "ready", "viber": "ready", "call_audio": "ready"}}

    async def fake_get(app, path):
        data = correct if path == "/api/readiness" else {"status": "ok", "mode": "offline-first"}
        return (200, json.dumps(data).encode("utf-8"), {})

    monkeypatch.setattr(validator, "asgi_get", fake_get)
    report = validator.Report()
    validator.check_fastapi_routes(report)
    assert not report.errors
    assert "/api/readiness -> 200" in report.passes
    assert "/api/viber-scenario -> 200" in report.passes

    broken = {"status": "ready", "stations": {**correct["stations"], "viber": "unavailable"}}

    async def broken_get(app, path):
        data = broken if path == "/api/readiness" else {"status": "ok", "mode": "offline-first"}
        return (200, json.dumps(data).encode("utf-8"), {})

    monkeypatch.setattr(validator, "asgi_get", broken_get)
    report = validator.Report()
    validator.check_fastapi_routes(report)
    assert any("/api/readiness: station status is not fully ready" in item for item in report.errors)
