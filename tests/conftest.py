# pylint: disable=protected-access,redefined-outer-name
"""Global fixtures for integration."""
import os
from unittest.mock import patch

from aioresponses import aioresponses
import pytest

from custom_components.ryobi_gdo.api import RyobiApiClient

pytest_plugins = "pytest_homeassistant_custom_component"  # pylint: disable=invalid-name

TEST_URL_API = "https://tti.tiwiconnect.com/api/login"
TEST_URL_DEVICES = "https://tti.tiwiconnect.com/api/devices"
TEST_URL_DEVICE = "https://tti.tiwiconnect.com/api/devices/fakedeviceID02"


# This fixture enables loading custom integrations in all tests.
# Remove to enable selective use of this fixture
@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Automatically enable loading custom integrations in all tests."""
    yield


# This fixture is used to prevent HomeAssistant from attempting to create and dismiss persistent
# notifications. These calls would fail without this fixture since the persistent_notification
# integration is never loaded during a test.
@pytest.fixture(name="skip_notifications", autouse=True)
def skip_notifications_fixture():
    """Skip notification calls."""
    with patch("homeassistant.components.persistent_notification.async_create"), patch(
        "homeassistant.components.persistent_notification.async_dismiss"
    ):
        yield


@pytest.fixture(name="mock_api_key")
def mock_api_key(mock_aioclient):
    """Mock API call for API key endpoint."""
    mock_aioclient.post(
        TEST_URL_API,
        status=200,
        body=load_fixture("api.json"),
        repeat=True,
    )
    return RyobiApiClient(username="TestUser", password="FakePassword")


@pytest.fixture(name="mock_devices")
def mock_devices(mock_aioclient):
    """Mock API call for API key endpoint."""
    mock_aioclient.get(
        TEST_URL_DEVICES,
        status=200,
        body=load_fixture("devices.json"),
        repeat=True,
    )
    return RyobiApiClient(username="TestUser", password="FakePassword")


@pytest.fixture(name="mock_device")
def mock_device(mock_aioclient):
    """Mock API call for API key endpoint."""
    mock_aioclient.get(
        TEST_URL_DEVICE,
        status=200,
        body=load_fixture("device_id.json"),
        repeat=True,
    )
    return RyobiApiClient(
        username="TestUser", password="FakePassword", device_id="fakedeviceID02"
    )


@pytest.fixture
def mock_aioclient():
    """Fixture to mock aioclient calls."""
    with aioresponses() as m:
        yield m


def load_fixture(filename):
    """Load a fixture."""
    path = os.path.join(os.path.dirname(__file__), "fixtures", filename)
    with open(path, encoding="utf-8") as fptr:
        return fptr.read()
