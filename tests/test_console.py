"""The in-browser console: the only place the server starts processes."""

import pytest

from f1_ml.server import create_app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("PITWALL_DISABLE_CONSOLE", raising=False)
    return create_app().test_client()


def run(client, command, addr="127.0.0.1"):
    return client.post("/api/command", json={"command": command},
                       environ_base={"REMOTE_ADDR": addr})


def test_console_refuses_other_machines(client):
    assert run(client, "info", addr="192.168.1.20").status_code == 403
    assert run(client, "info").status_code == 200
