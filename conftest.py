"""Shared offline fixtures for the pattern test suites."""
import socket
import sys
import types

import pytest


_collection_guard = pytest.MonkeyPatch()


def _block_network(*args, **kwargs):
    raise AssertionError("Network access is forbidden in the offline test suite")


def pytest_sessionstart(session):
    """Protect module import/collection as well as individual test execution."""
    for name in ("OPENAI_API_KEY", "OPENAI_MODEL", "OPENAI_ECONOMY_MODEL"):
        _collection_guard.delenv(name, raising=False)
    _collection_guard.setattr(socket.socket, "connect", _block_network)
    _collection_guard.setattr(socket.socket, "connect_ex", _block_network)


def pytest_sessionfinish(session, exitstatus):
    # Also safe when pytest is invoked programmatically in a long-lived process.
    _collection_guard.undo()


@pytest.fixture(autouse=True)
def offline_environment(monkeypatch):
    """Tests never use real credentials or open network connections."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_ECONOMY_MODEL", raising=False)

    def block_network(*args, **kwargs):
        raise AssertionError("Network access is forbidden in the offline test suite")

    monkeypatch.setattr(socket.socket, "connect", block_network)
    monkeypatch.setattr(socket.socket, "connect_ex", block_network)


@pytest.fixture
def fake_openai(monkeypatch):
    """Install a fake SDK and record requests without requiring the real package."""
    def install(*outputs, status="completed", error=None):
        requests = []
        remaining = iter(outputs)

        def create(**kwargs):
            requests.append(kwargs)
            if error is not None:
                raise error
            return types.SimpleNamespace(output_text=next(remaining), status=status)

        class Client:
            def __init__(self):
                self.responses = types.SimpleNamespace(create=create)
                self.closed = False
                self.options = None
            def __enter__(self):
                return self
            def __exit__(self, *args):
                self.closed = True
        client = Client()
        def factory(**kwargs):
            client.options = kwargs
            return client
        monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=factory))
        monkeypatch.setenv("OPENAI_API_KEY", "offline-test-placeholder")
        return client, requests

    return install
