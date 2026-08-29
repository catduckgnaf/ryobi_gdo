"""Test the Ryobi camera platform."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from custom_components.ryobi_gdo.camera import RyobiCamera, async_setup_entry


class FakeResponse:
    """Minimal asynchronous camera response."""

    status = 200

    async def read(self) -> bytes:
        """Return a fake image payload."""
        return b"fake-jpeg"


class FakeRequest:
    """Minimal asynchronous request context manager."""

    async def __aenter__(self) -> FakeResponse:
        """Enter the request context."""
        return FakeResponse()

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        """Exit the request context."""


class FakeSession:
    """Minimal HTTP session for camera image tests."""

    def get(self, url: str, timeout: int) -> FakeRequest:
        """Return a fake HTTP request."""
        return FakeRequest()


@pytest.fixture
def coordinator():
    """Return a coordinator with a camera module."""
    value = MagicMock()
    value.device_id = "fakedeviceID02"
    value.data = {
        "device_name": "Test GDO",
        "camera_image_url": "https://camera.example/snapshot.jpg",
    }
    value.client.modules = {"camera": "camera_0"}
    value.client.session = FakeSession()
    return value


@pytest.mark.asyncio
async def test_camera_setup_adds_camera_entity(coordinator):
    """Set up one camera entity when a camera module is present."""
    entities = []
    entry = SimpleNamespace(runtime_data=coordinator)

    await async_setup_entry(None, entry, entities.extend)

    assert len(entities) == 1
    assert isinstance(entities[0], RyobiCamera)
    assert entities[0].unique_id == "fakedeviceID02_security_camera"
    assert entities[0].device_info["name"] == "Test GDO"


@pytest.mark.asyncio
async def test_camera_image_fetch_returns_image_payload(coordinator):
    """Fetch and return the camera image bytes."""
    entity = RyobiCamera(coordinator)

    assert await entity.async_camera_image() == b"fake-jpeg"
