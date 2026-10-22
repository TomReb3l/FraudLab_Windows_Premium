from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_call_scenario_endpoint():
    response = client.get("/api/scenarios/call_account_security_001")
    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "fraud_call"
    assert payload["start_node"] in payload["nodes"]


def test_unknown_scenario_is_404():
    response = client.get("/api/scenarios/does-not-exist")
    assert response.status_code == 404


def test_frontend_is_served():
    response = client.get("/")
    assert response.status_code == 200
    assert "FRAUD LAB" in response.text


def test_readiness_all_four_stations_and_audio():
    response = client.get("/api/readiness")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["stations"] == {
        "telephone": "ready", "sms": "ready", "qr": "ready",
        "viber": "ready", "call_audio": "ready",
    }


def test_readiness_fails_on_missing_sms_without_changing_liveness(tmp_path, monkeypatch):
    import backend.main as main
    missing = tmp_path / "missing-sms.json"
    monkeypatch.setattr(main, "SMS_DATA_FILE", missing)
    response = client.get("/api/readiness")
    assert response.status_code == 503
    assert response.json()["stations"]["sms"] == "unavailable"
    assert client.get("/api/health").json()["status"] == "ok"


def test_readiness_fails_on_corrupt_json(tmp_path, monkeypatch):
    import backend.main as main
    bad_file = tmp_path / "qr.json"
    bad_file.write_text('{"items":', encoding="utf-8")
    monkeypatch.setattr(main, "QR_DATA_FILE", bad_file)
    response = client.get("/api/readiness")
    assert response.status_code == 503
    assert response.json()["stations"]["qr"] == "unavailable"


def test_readiness_fails_on_empty_sms_items(tmp_path, monkeypatch):
    import backend.main as main
    bad_file = tmp_path / "sms.json"
    bad_file.write_text('{"items": []}', encoding="utf-8")
    monkeypatch.setattr(main, "SMS_DATA_FILE", bad_file)
    assert client.get("/api/readiness").status_code == 503


def test_readiness_fails_on_non_object_call_data(tmp_path, monkeypatch):
    import backend.main as main
    bad_file = tmp_path / "call.json"
    bad_file.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(main, "DATA_FILE", bad_file)
    response = client.get("/api/readiness")
    assert response.status_code == 503
    assert response.json()["stations"]["telephone"] == "unavailable"


def test_readiness_fails_on_missing_audio_manifest(tmp_path, monkeypatch):
    import backend.main as main
    monkeypatch.setattr(main, "CALL_AUDIO_MANIFEST_FILE", tmp_path / "not-found.json")
    response = client.get("/api/readiness")
    assert response.status_code == 503
    assert response.json()["stations"]["call_audio"] == "unavailable"


def test_readiness_fails_on_broken_viber_link(tmp_path, monkeypatch):
    import json
    import backend.main as main
    data = json.loads(main.VIBER_DATA_FILE.read_text(encoding="utf-8"))
    data["nodes"]["chat_opening"]["choices"][0]["next_node"] = "missing"
    bad_file = tmp_path / "viber.json"
    bad_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(main, "VIBER_DATA_FILE", bad_file)
    assert client.get("/api/readiness").json()["stations"]["viber"] == "unavailable"
