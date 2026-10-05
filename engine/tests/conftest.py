"""Release 0.1.0: tests never touch the network.

Every test runs with real socket connections switched off, so a test that forgets its
httpx.MockTransport (a fake network that answers in memory) fails loudly instead of downloading.
Local Unix sockets stay allowed because they never leave the machine.
"""

import socket
from collections.abc import Iterator

import pytest


def _refuse(self: socket.socket, address: object) -> None:
    if self.family == getattr(socket, "AF_UNIX", None):
        return _REAL_CONNECT(self, address)
    raise RuntimeError(f"network is off in tests: refused a connection to {address!r}")


def _refuse_ex(self: socket.socket, address: object) -> int:
    _refuse(self, address)
    return 0


_REAL_CONNECT = socket.socket.connect


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(socket.socket, "connect", _refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", _refuse_ex)
    yield
