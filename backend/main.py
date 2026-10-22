from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.scenario_engine import ScenarioEngine


BASE_DIR = Path(__file__).resolve().parents[1]

DATA_FILE = BASE_DIR / "data" / "call_scenarios.json"
SMS_DATA_FILE = BASE_DIR / "data" / "sms_scenarios.json"
QR_DATA_FILE = BASE_DIR / "data" / "qr_scenarios.json"
VIBER_DATA_FILE = BASE_DIR / "data" / "viber_takeover_scenario.json"

FRONTEND_DIR = BASE_DIR / "frontend"
STATIC_DIR = BASE_DIR / "static"


engine = ScenarioEngine(DATA_FILE)


app = FastAPI(
    title="FRAUD LAB – Fraud Exhibition System",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
)


app.mount(
    "/static",
    StaticFiles(directory=STATIC_DIR),
    name="static",
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "mode": "offline-first",
    }


@app.get("/api/scenarios")
def list_scenarios():
    return JSONResponse(
        content=engine.list_scenarios(),
        media_type="application/json; charset=utf-8"
    )


@app.get("/api/scenarios/{scenario_id}")
def get_scenario(scenario_id: str) -> dict:
    try:
        return engine.get_scenario(scenario_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/sms-challenge")
def get_sms_challenge() -> dict:
    try:
        return json.loads(
            SMS_DATA_FILE.read_text(encoding="utf-8")
        )
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=500,
            detail="SMS challenge data unavailable",
        ) from exc


@app.get("/api/viber-scenario")
def get_viber_scenario() -> dict:
    try:
        return json.loads(VIBER_DATA_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail="Viber scenario data unavailable") from exc


@app.get("/api/qr-challenge")
def get_qr_challenge() -> dict:
    try:
        return json.loads(
            QR_DATA_FILE.read_text(encoding="utf-8")
        )
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=500,
            detail="QR challenge data unavailable",
        ) from exc


@app.get("/")
def root() -> FileResponse:
    return FileResponse(
        FRONTEND_DIR / "home" / "index.html"
    )


@app.get("/call")
def call_booth() -> FileResponse:
    return FileResponse(
        FRONTEND_DIR / "call" / "index.html"
    )


@app.get("/sms")
def sms_challenge_page() -> FileResponse:
    return FileResponse(
        FRONTEND_DIR / "sms" / "index.html"
    )


@app.get("/qr")
def qr_challenge_page() -> FileResponse:
    return FileResponse(
        FRONTEND_DIR / "qr" / "index.html"
    )

@app.get("/viber")
def viber_station_page() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "viber" / "index.html")


CALL_AUDIO_MANIFEST_FILE = BASE_DIR / "data" / "call_audio_manifest.json"


@app.get("/api/call-audio-manifest")
def get_call_audio_manifest() -> dict:
    try:
        return json.loads(
            CALL_AUDIO_MANIFEST_FILE.read_text(encoding="utf-8")
        )
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=500,
            detail="Call audio manifest unavailable",
        ) from exc

def _load_data_object(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("file unavailable or invalid UTF-8/JSON") from exc
    if not isinstance(data, dict):
        raise ValueError("root must be a JSON object")
    return data


def _validate_challenge_items(data: dict) -> None:
    items = data.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("nonempty items list required")
    identifiers = set()
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"]:
            raise ValueError("item id missing")
        if item["id"] in identifiers:
            raise ValueError("duplicate item id")
        identifiers.add(item["id"])
        choices = item.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("item choices missing")
        if any(not isinstance(choice, dict) or not isinstance(choice.get("label"), str)
               or not choice["label"] or not isinstance(choice.get("feedback"), str)
               or not isinstance(choice.get("score"), (int, float))
               or isinstance(choice["score"], bool) for choice in choices):
            raise ValueError("item choice invalid")


def _validate_viber_data(data: dict) -> None:
    nodes = data.get("nodes")
    endings = data.get("endings")
    variants = data.get("variants")
    if not isinstance(nodes, dict) or not nodes or data.get("start_node") not in nodes:
        raise ValueError("invalid Viber start or nodes")
    if not isinstance(endings, dict) or not endings:
        raise ValueError("Viber endings missing")
    if not isinstance(variants, list) or not variants or not all(isinstance(v, str) for v in variants):
        raise ValueError("Viber variants missing")
    if data.get("default_variant") not in variants:
        raise ValueError("invalid Viber default variant")
    for node in nodes.values():
        if not isinstance(node, dict):
            raise ValueError("invalid Viber node")
        links = []
        if "choices" in node:
            choices = node["choices"]
            if not isinstance(choices, list) or not choices:
                raise ValueError("invalid Viber choices")
            if any(not isinstance(c, dict) for c in choices):
                raise ValueError("invalid Viber choice")
            links.extend(c.get("next_node") for c in choices)
        if "next_node" in node:
            links.append(node["next_node"])
        if "next_by_variant" in node:
            dispatch = node["next_by_variant"]
            if not isinstance(dispatch, dict) or set(dispatch) != set(variants):
                raise ValueError("invalid Viber variant dispatch")
            links.extend(dispatch.values())
        if any(target not in nodes for target in links):
            raise ValueError("missing Viber linked node")
        if "outcome" in node and node["outcome"] not in endings:
            raise ValueError("invalid Viber ending reference")
        if not links and "outcome" not in node:
            raise ValueError("Viber node has no continuation")


def station_readiness() -> dict[str, str]:
    """Read-only, deterministic station data checks. Called on demand, not by watchdog."""
    result = {}
    checks = (
        ("telephone", lambda: ScenarioEngine(DATA_FILE)),
        ("sms", lambda: _validate_challenge_items(_load_data_object(SMS_DATA_FILE))),
        ("qr", lambda: _validate_challenge_items(_load_data_object(QR_DATA_FILE))),
        ("viber", lambda: _validate_viber_data(_load_data_object(VIBER_DATA_FILE))),
    )
    for station, check in checks:
        try:
            check()
            result[station] = "ready"
        except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError):
            # Never expose local file paths or scenario contents to visitors.
            result[station] = "unavailable"
    try:
        if not _load_data_object(CALL_AUDIO_MANIFEST_FILE):
            raise ValueError("empty audio manifest")
        result["call_audio"] = "ready"
    except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError):
        result["call_audio"] = "unavailable"
    return result


@app.get("/api/readiness")
def readiness() -> JSONResponse:
    """503 if station data is not ready; independent of /api/health liveness."""
    stations = station_readiness()
    ready = all(value == "ready" for value in stations.values())
    return JSONResponse(
        content={"status": "ready" if ready else "not_ready", "stations": stations},
        status_code=200 if ready else 503,
        headers={"Cache-Control": "no-store"},
    )
