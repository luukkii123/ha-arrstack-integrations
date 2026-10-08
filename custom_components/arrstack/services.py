"""Import actions and WebSocket commands share the same execution path."""
from __future__ import annotations
from typing import Any
import voluptuous as vol
from homeassistant.core import HomeAssistant, SupportsResponse, callback
from homeassistant.exceptions import ServiceValidationError, Unauthorized
from .api import ArrstackError
from .const import ARR_SERVICES, DOMAIN
from .ws import _resolve, _Unresolved

IMPORT_ACTIONS = ('refresh_import_queue', 'inspect_import', 'import_item', 'import_ready', 'import_selected')
INSTANCE_SCHEMA = {vol.Optional('entry_id'): str, vol.Optional('service'): vol.In(ARR_SERVICES)}
ITEM_ID = vol.All(int, vol.Range(min=1))

def action_schema(action: str) -> dict:
    """Stable schemas for both transports."""
    schema = dict(INSTANCE_SCHEMA)
    if action == 'refresh_import_queue':
        schema[vol.Optional('queue_item_id')] = ITEM_ID
    if action in ('inspect_import', 'import_item'):
        schema[vol.Required('queue_item_id')] = ITEM_ID
    if action == 'import_item':
        schema[vol.Optional('candidate_id')] = str
    if action == 'import_selected':
        schema[vol.Required('queue_item_ids')] = vol.All([ITEM_ID], vol.Length(min=1, max=200))
    return schema

async def execute_import_action(hass: HomeAssistant, action: str, data: dict[str, Any]) -> dict[str, Any]:
    """Resolve a single instance and use the authoritative backend manager."""
    runtime = _resolve(hass, data, ARR_SERVICES)
    manager = runtime.imports
    if action == 'refresh_import_queue':
        result = {'items': await manager.refresh(data.get('queue_item_id'))}
    elif action == 'inspect_import':
        result = await manager.inspect(data['queue_item_id'])
    elif action == 'import_item':
        result = await manager.import_item(data['queue_item_id'], data.get('candidate_id'))
    elif action == 'import_ready':
        result = {'results': await manager.import_ready()}
    else:
        result = {'results': await manager.import_selected(data['queue_item_ids'])}
    if action.startswith('import_'):
        await runtime.coordinator.async_request_refresh()
    return {'service': runtime.service, **result}

@callback
def async_register_import_services(hass: HomeAssistant) -> None:
    """Register actions once, with structured optional response data."""
    for action in IMPORT_ACTIONS:
        async def handler(call, action=action):
            if call.context.user_id:
                user = await hass.auth.async_get_user(call.context.user_id)
                if user is None or not user.is_admin:
                    raise Unauthorized()
            try:
                return await execute_import_action(hass, action, call.data)
            except (_Unresolved, ArrstackError) as err:
                raise ServiceValidationError('Instanz oder Warteschlange konnte nicht geprüft werden. Auswahl prüfen und erneut aktualisieren.') from err
        hass.services.async_register(DOMAIN, action, handler, schema=vol.Schema(action_schema(action)), supports_response=SupportsResponse.OPTIONAL)
