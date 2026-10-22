"""Readiness failure must not change watchdog liveness semantics."""
from io import BytesIO
from urllib.error import HTTPError
from unittest.mock import patch

from scripts import exhibition_launcher as launcher


class FakeResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return b'{"status":"ready","stations":{"telephone":"ready","sms":"ready"}}'


def test_launcher_readiness_pass():
    with patch.object(launcher, "urlopen", return_value=FakeResponse()):
        ready, payload, error = launcher.readiness_check()
    assert ready and error is None and payload["status"] == "ready"


def test_launcher_readiness_503_does_not_trigger_liveness_restart():
    body = b'{"status":"not_ready","stations":{"telephone":"ready","sms":"unavailable"}}'
    err = HTTPError(launcher.READINESS_URL, 503, "not ready", {}, BytesIO(body))
    with patch.object(launcher, "urlopen", side_effect=err):
        ready, payload, error = launcher.readiness_check()
    assert not ready
    assert payload["stations"]["sms"] == "unavailable"
    assert error == "Station data not ready: sms"


def test_launcher_refuses_kiosk_when_data_unready():
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    patches = [
        patch.object(launcher, "os", SimpleNamespace(name="nt")),
        patch.object(launcher, "acquire_mutex", return_value=123),
        patch.object(launcher, "release_mutex"),
        patch.object(launcher, "validate_project_files", return_value=[]),
        patch.object(launcher, "read_state", return_value={"schema": 1}),
        patch.object(launcher, "health_check", return_value=(True, {"status":"ok", "mode":"offline-first"}, None)),
        patch.object(launcher, "readiness_check", return_value=(False, {"status":"not_ready"}, "Station data not ready: sms")),
        patch.object(launcher, "ensure_watchdog"),
        patch.object(launcher, "write_state"),
        patch.object(launcher, "process_matches", return_value=False),
    ]
    from contextlib import ExitStack
    with ExitStack() as stack:
        mocks = [stack.enter_context(p) for p in patches]
        assert launcher.start(gui=False, no_browser=True) == 1
        mocks[7].assert_not_called()  # no watchdog started for invalid station data
        mocks[8].assert_not_called()  # no normal startup state written


def test_launcher_cleans_up_new_backend_when_data_unready():
    from types import SimpleNamespace
    from contextlib import ExitStack
    from unittest.mock import Mock
    process = Mock()
    process.poll.return_value = None
    record = {"owned": True, "pid": 12345}
    patch_specs = [
        ("os", SimpleNamespace(name="nt")),
        ("acquire_mutex", Mock(return_value=123)),
        ("release_mutex", Mock()),
        ("validate_project_files", Mock(return_value=[])),
        ("read_state", Mock(return_value={"schema": 1})),
        ("health_check", Mock(return_value=(False, None, "not responding"))),
        ("port_open", Mock(return_value=False)),
        ("launch_backend", Mock(return_value=(process, record))),
        ("wait_for_health", Mock(return_value=(True, "started"))),
        ("readiness_check", Mock(return_value=(False, None, "Station data not ready: viber"))),
        ("process_matches", Mock(side_effect=lambda record: bool(record))),
        ("terminate_owned_process", Mock(return_value=True)),
        ("clear_state", Mock()),
        ("write_state", Mock()),
        ("ensure_watchdog", Mock()),
    ]
    with ExitStack() as stack:
        mocks = {name: stack.enter_context(patch.object(launcher, name, value)) for name, value in patch_specs}
        assert launcher.start(gui=False, no_browser=True) == 1
        mocks["terminate_owned_process"].assert_called_once_with(record, "backend")
        mocks["clear_state"].assert_called_once()
        mocks["ensure_watchdog"].assert_not_called()


def test_launcher_readiness_missing_route_fails_closed():
    err = HTTPError(launcher.READINESS_URL, 404, "not found", {}, BytesIO(b''))
    with patch.object(launcher, "urlopen", side_effect=err):
        ready, payload, error = launcher.readiness_check()
    assert not ready and payload is None
    assert error == "Station readiness could not be checked"
