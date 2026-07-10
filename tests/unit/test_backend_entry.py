import importlib.util
from pathlib import Path
from types import SimpleNamespace

ROOT_DIR = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("backend_entry", ROOT_DIR / "backend-entry.py")
assert SPEC is not None
backend_entry = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(backend_entry)

BackendState = backend_entry.BackendState
SidecarHandler = backend_entry.SidecarHandler


def _handler(token: str, header: str | None) -> SidecarHandler:
    handler = object.__new__(SidecarHandler)
    handler.server = SimpleNamespace(
        backend_state=BackendState(
            data_dir=Path("/tmp/devsynapse-test"),
            version="1.0.0",
            auth_token=token,
        )
    )
    handler.headers = {"authorization": header} if header else {}
    return handler


def test_sidecar_handler_requires_bearer_token():
    assert _handler("secret", None)._authorized() is False
    assert _handler("secret", "Bearer wrong")._authorized() is False
    assert _handler("secret", "Bearer secret")._authorized() is True
