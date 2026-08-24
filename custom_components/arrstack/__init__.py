"""arrstack — Radarr, Sonarr, Jellyseerr/Seerr und SABnzbd in Home Assistant.

Die Core-Integrationen `sonarr`/`radarr`/`sabnzbd` bleiben daneben aktiv. Diese
hier ergänzt, was ihnen fehlt: Stück-Listen statt bloßer Zählwerte, ein Signal
für „heruntergeladen, aber nicht importiert" samt Reparatur, Health für Sonarr,
und Jellyseerr — das die Core-`overseerr` ausdrücklich nicht unterstützt.

Jeder Dienst ist eine eigene Config-Entry und für sich allein lauffähig. Es
gibt **keine** Stelle, an der ein Dienst einen anderen voraussetzt.
"""

from __future__ import annotations

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import (
    ARR_SERVICES,
    CONF_SERVICE,
    DOMAIN,
    SERVICE_SABNZBD,
    SERVICE_SEERR,
)
from .coordinator import (
    ArrstackConfigEntry,
    ArrstackRuntime,
    build_client,
    build_coordinator,
)
from .ws import async_register_websocket_api

_LOGGER = logging.getLogger(__name__)

#: Welche Plattformen ein Dienst mitbringt. Wer nur SABnzbd einrichtet, lädt
#: auch nur dessen Plattformen — `sensor.py` & Co. fragen den Dienst ab und
#: legen für fremde Dienste nichts an.
PLATFORMS_BY_SERVICE: dict[str, list[Platform]] = {
    SERVICE_SABNZBD: [
        Platform.BINARY_SENSOR,
        Platform.BUTTON,
        Platform.NUMBER,
        Platform.SENSOR,
    ],
    SERVICE_SEERR: [Platform.BINARY_SENSOR, Platform.SENSOR],
}

_ARR_PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SENSOR,
]

_WS_REGISTERED = "websocket_registered"


def platforms_for(service: str) -> list[Platform]:
    """Plattformliste eines Dienstes; Sonarr und Radarr teilen sich eine."""
    if service in ARR_SERVICES:
        return _ARR_PLATFORMS
    return PLATFORMS_BY_SERVICE[service]


async def async_setup_entry(hass: HomeAssistant, entry: ArrstackConfigEntry) -> bool:
    """Einen Dienst einrichten: Client, Coordinator, erste Abfrage, Plattformen.

    Der erste Abruf darf scheitern, ohne die anderen Einträge zu berühren —
    Home Assistant wiederholt ihn dann für genau diesen Eintrag.
    """
    service = entry.data[CONF_SERVICE]
    client = build_client(hass, entry)
    coordinator = build_coordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = ArrstackRuntime(
        service=service, coordinator=coordinator, client=client
    )

    # Die WS-Kommandos hängen an keiner einzelnen Entry — sie suchen sich die
    # passende zur Laufzeit. Registriert wird deshalb genau einmal.
    domain_data = hass.data.setdefault(DOMAIN, {})
    if not domain_data.get(_WS_REGISTERED):
        async_register_websocket_api(hass)
        domain_data[_WS_REGISTERED] = True

    await hass.config_entries.async_forward_entry_setups(
        entry, platforms_for(service)
    )
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ArrstackConfigEntry) -> bool:
    """Nur die Plattformen dieses Dienstes abräumen.

    Die WS-Kommandos bleiben registriert — Home Assistant kann sie nicht wieder
    abmelden, und sie antworten ohne passende Entry sauber mit `not_found`.
    """
    return await hass.config_entries.async_unload_platforms(
        entry, platforms_for(entry.data[CONF_SERVICE])
    )


async def async_reload_entry(hass: HomeAssistant, entry: ArrstackConfigEntry) -> None:
    """Nach einer Optionsänderung (Intervall, Schlüssel) neu laden."""
    await hass.config_entries.async_reload(entry.entry_id)
