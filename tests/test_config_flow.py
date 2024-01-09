"""Test config flow."""

from unittest.mock import patch

import pytest

from custom_components.ryobi_gdo.const import DOMAIN
from homeassistant import config_entries, setup
from homeassistant.data_entry_flow import FlowResultType


@pytest.mark.parametrize(
    "input_1,step_id_1,input_2,step_id_2,title,data",
    [
        (
            {
                "username": "TestUser",
                "password": "FakePassword",
            },
            "user",
            {
                "device_id": "fakedeviceID02",
            },
            "user_2",
            "TestUser",
            {
                "username": "TestUser",
                "password": "FakePassword",
                "device_id": "fakedeviceID02",
            },
        ),
    ],
)
async def test_form_user(
    input_1,
    step_id_1,
    input_2,
    step_id_2,
    title,
    data,
    hass,
    mock_api_key,
    mock_devices,
):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}
    assert result["step_id"] == step_id_1

    with patch(
        "custom_components.ryobi_gdo.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_1
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == step_id_2
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_2
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == title
        assert result["data"] == data

        await hass.async_block_till_done()
        assert len(mock_setup_entry.mock_calls) == 1
