"""Import core modules without constructing the interactive application."""

import sys
import tempfile
import types
from pathlib import Path

import pytest

main = types.ModuleType("heroku.main")
_data = tempfile.TemporaryDirectory(prefix="herokusafe-tests-")
main.BASE_DIR = _data.name
main.BASE_PATH = Path(_data.name)
main.SESSIONS_DIR = str(main.BASE_PATH / "sessions")
main.get_config_key = lambda key: False
sys.modules["heroku.main"] = main


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    import socket

    connect = socket.socket.connect
    connect_ex = socket.socket.connect_ex

    def reject(*args, **kwargs):
        if (
            len(args) > 1
            and isinstance(args[1], tuple)
            and args[1][0] in {"127.0.0.1", "::1"}
        ):
            return connect(*args, **kwargs)
        raise AssertionError("Regression tests must not access the network")

    def reject_ex(*args, **kwargs):
        if (
            len(args) > 1
            and isinstance(args[1], tuple)
            and args[1][0] in {"127.0.0.1", "::1"}
        ):
            return connect_ex(*args, **kwargs)
        raise AssertionError("Regression tests must not access the network")

    monkeypatch.setattr(socket.socket, "connect", reject)
    monkeypatch.setattr(socket.socket, "connect_ex", reject_ex)


class MemoryDB:
    def __init__(self):
        self.data = {}

    def get(self, owner, key, default=None):
        return self.data.get((owner, key), default)

    def set(self, owner, key, value):
        self.data[owner, key] = value
        return True
