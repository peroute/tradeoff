import json
from pathlib import Path

import httpx
import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def pytest_addoption(parser):
    parser.addoption(
        "--run-live",
        action="store_true",
        default=False,
        help="run @pytest.mark.live tests that hit the real OECD/BLS network APIs",
    )


def pytest_collection_modifyitems(config, items):
    """Skip live tests unless --run-live is passed (default run is fully offline)."""
    if config.getoption("--run-live"):
        return
    skip_live = pytest.mark.skip(reason="needs --run-live (hits real network APIs)")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)


class FakeResponse:
    """Minimal stand-in for httpx.Response used to mock module-level httpx calls."""

    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPError(f"mocked HTTP {self.status_code}")

    def json(self):
        return self._payload


@pytest.fixture
def fake_response():
    return FakeResponse


@pytest.fixture
def load_fixture():
    def _load(name):
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))

    return _load
