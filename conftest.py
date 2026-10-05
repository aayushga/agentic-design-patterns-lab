"""Shared offline fixtures for the pattern test suites."""
import socket
import sys
import types

import pytest


@pytest.fixture(autouse=True)
def offline_environment(monkeypatch):
    """Tests never use real credentials or open network connections."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

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

        client = types.SimpleNamespace(responses=types.SimpleNamespace(create=create))
        monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=lambda **kwargs: client))
        monkeypatch.setenv("OPENAI_API_KEY", "offline-test-placeholder")
        return client, requests

    return install
