"""HA service registration, response data and permission contracts."""
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from homeassistant.core import Context
from homeassistant.exceptions import Unauthorized
from custom_components.arrstack.const import DOMAIN

@pytest.mark.parametrize('action,data', [
    ('refresh_import_queue', {}), ('inspect_import', {'queue_item_id': 7}),
    ('import_item', {'queue_item_id': 7, 'candidate_id': 'explicit'}),
    ('import_ready', {}), ('import_selected', {'queue_item_ids': [7,8]})])
async def test_service_response(hass, monkeypatch, action, data):
    from custom_components.arrstack.services import async_register_import_services
    manager = SimpleNamespace(refresh=AsyncMock(return_value=[{'queue_item_id': 7}]), inspect=AsyncMock(return_value={'queue_item_id': 7}), import_item=AsyncMock(return_value={'queue_item_id': 7,'status':'submitted'}), import_ready=AsyncMock(return_value=[{'queue_item_id':7,'status':'submitted'}]), import_selected=AsyncMock(return_value=[{'queue_item_id':7,'status':'submitted'}]))
    runtime = SimpleNamespace(service='sonarr', imports=manager, coordinator=SimpleNamespace(async_request_refresh=AsyncMock()))
    monkeypatch.setattr('custom_components.arrstack.services._resolve', lambda *args: runtime)
    async_register_import_services(hass)
    response = await hass.services.async_call(DOMAIN, action, data, blocking=True, return_response=True)
    assert isinstance(response, dict)
    assert response['service'] == 'sonarr'
    if action.startswith('import_'):
        assert runtime.coordinator.async_request_refresh.await_count == 1

async def test_user_permissions(hass, monkeypatch):
    from custom_components.arrstack.services import async_register_import_services
    async_register_import_services(hass)
    monkeypatch.setattr(hass.auth, 'async_get_user', AsyncMock(return_value=SimpleNamespace(is_admin=False)))
    with pytest.raises(Unauthorized):
        await hass.services.async_call(DOMAIN, 'import_ready', {}, context=Context(user_id='non-admin'), blocking=True, return_response=True)

async def test_action_unresolved_instance_is_service_error(hass):
    from custom_components.arrstack.services import async_register_import_services
    from homeassistant.exceptions import ServiceValidationError
    async_register_import_services(hass)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, 'inspect_import', {'queue_item_id':7}, blocking=True, return_response=True)

async def test_websocket_transport_contract(hass, hass_ws_client, monkeypatch):
    from custom_components.arrstack.ws import async_register_websocket_api
    runtime = SimpleNamespace(service='radarr', imports=SimpleNamespace(refresh=AsyncMock(return_value=[{'queue_item_id':9,'import_state':'ready','candidate_count':1}]), import_item=AsyncMock(return_value={'queue_item_id':9,'status':'submitted'})), coordinator=SimpleNamespace(async_request_refresh=AsyncMock()))
    monkeypatch.setattr('custom_components.arrstack.services._resolve', lambda *args: runtime)
    async_register_websocket_api(hass)
    client = await hass_ws_client(hass)
    await client.send_json({'id':1,'type':'arrstack/refresh_import_queue','service':'radarr'})
    response = await client.receive_json()
    assert response['success']
    assert response['result']['items'][0]['candidate_count'] == 1
    await client.send_json({'id':2,'type':'arrstack/import_item','queue_item_id':9,'candidate_id':'selected'})
    response = await client.receive_json()
    assert response['result']['status'] == 'submitted'

async def test_service_schema_rejects_unsafe_parameters(hass):
    import voluptuous as vol
    from custom_components.arrstack.services import async_register_import_services
    async_register_import_services(hass)
    for data in [{'queue_item_id':0}, {'queue_item_id':7, 'force':True}, {'queue_item_id':7,'service':'seerr'}]:
        with pytest.raises(vol.Invalid):
            await hass.services.async_call(DOMAIN, 'import_item', data, blocking=True, return_response=True)

async def test_websocket_non_admin_cannot_import(hass, hass_ws_client, hass_access_token, hass_admin_user):
    from custom_components.arrstack.ws import async_register_websocket_api
    async_register_websocket_api(hass)
    hass_admin_user.groups = []
    client = await hass_ws_client(hass, access_token=hass_access_token)
    await client.send_json({'id':1,'type':'arrstack/import_ready'})
    result = await client.receive_json()
    assert not result['success']
    assert result['error']['code'] == 'unauthorized'
