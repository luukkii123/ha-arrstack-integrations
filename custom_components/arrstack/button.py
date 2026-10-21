"""Knöpfe: Rescan, Downloads neu prüfen, Queue aufräumen, SABnzbd steuern.

Der Aufräum-Knopf ist der einzige, der etwas löscht — und deshalb der
zurückhaltendste: er fasst **nur** endgültig fehlgeschlagene Einträge an.
Hängende Importe bleiben liegen, weil sie sich oft von selbst lösen, sobald
die Serie angelegt ist.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import ArrstackError
from .const import ARR_SERVICES, SERVICE_SABNZBD, STATE_FAILED, STATE_FAILED_PENDING
from .coordinator import ArrCoordinator, ArrstackConfigEntry, SabCoordinator
from .entity import ArrstackEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class ArrstackButtonDescription(ButtonEntityDescription):
    """Beschreibung mit der Aktion, die der Knopf auslöst."""

    press_fn: Callable[[Any], Awaitable[None]]


async def _rescan(coordinator: ArrCoordinator) -> None:
    """Bibliothek neu einlesen — ohne Id gilt das für alles."""
    name = "RescanSeries" if coordinator.is_sonarr else "RescanMovie"
    await coordinator.client.command(name)


async def _refresh_downloads(coordinator: ArrCoordinator) -> None:
    """Die App die Download-Clients sofort neu abfragen lassen."""
    await coordinator.client.command("RefreshMonitoredDownloads")


async def _cleanup_queue(coordinator: ArrCoordinator) -> None:
    """Endgültig fehlgeschlagene Einträge aus der Queue werfen.

    Absichtlich eng gefasst: `failed`/`failedPending`. Nicht angefasst werden
    `importPending`/`importBlocked` — die verschwinden meist von allein, sobald
    die fehlende Serie angelegt oder die Datei zugeordnet ist. Der Client
    behält seine Dateien nicht (`removeFromClient=True`), aber es wird
    **nichts geblocklistet** — das wäre eine Entscheidung des Nutzers.
    """
    records = (coordinator.data or {}).get("queue") or []
    victims = [
        record
        for record in records
        if record.get("tracked_state") in (STATE_FAILED, STATE_FAILED_PENDING)
        or str(record.get("status") or "").lower() == "failed"
    ]
    if not victims:
        return
    # `skipRedownload` gibt es erst ab v4 — an v3 geschickt quittiert die App
    # den Aufruf mit einem Fehler.
    skip_redownload = False if coordinator.major_version >= 4 else None
    for record in victims:
        await coordinator.client.queue_delete(
            int(record["id"]),
            remove_from_client=True,
            blocklist=False,
            skip_redownload=skip_redownload,
        )
    _LOGGER.info(
        "arrstack: %d fehlgeschlagene Queue-Einträge entfernt (%s)",
        len(victims),
        coordinator.service,
    )
    await coordinator.async_request_refresh()


async def _sab_pause(coordinator: SabCoordinator) -> None:
    """Alles anhalten."""
    await coordinator.client.pause()
    await coordinator.async_request_refresh()


async def _sab_resume(coordinator: SabCoordinator) -> None:
    """Weiterlaufen lassen."""
    await coordinator.client.resume()
    await coordinator.async_request_refresh()


_ARR: tuple[ArrstackButtonDescription, ...] = (
    ArrstackButtonDescription(
        key="rescan", translation_key="rescan", press_fn=_rescan
    ),
    ArrstackButtonDescription(
        key="refresh_downloads",
        translation_key="refresh_downloads",
        press_fn=_refresh_downloads,
    ),
    ArrstackButtonDescription(
        key="cleanup_queue",
        translation_key="cleanup_queue",
        press_fn=_cleanup_queue,
    ),
)

_SAB: tuple[ArrstackButtonDescription, ...] = (
    ArrstackButtonDescription(key="pause", translation_key="pause", press_fn=_sab_pause),
    ArrstackButtonDescription(
        key="resume", translation_key="resume", press_fn=_sab_resume
    ),
)


def descriptions_for(service: str) -> tuple[ArrstackButtonDescription, ...]:
    """Welche Knöpfe ein Dienst bekommt; Seerr bekommt keine."""
    if service in ARR_SERVICES:
        return _ARR
    if service == SERVICE_SABNZBD:
        return _SAB
    return ()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ArrstackConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Knöpfe des Dienstes anlegen."""
    runtime = entry.runtime_data
    async_add_entities(
        ArrstackButton(runtime.coordinator, description)
        for description in descriptions_for(runtime.service)
    )


class ArrstackButton(ArrstackEntity, ButtonEntity):
    """Ein Knopf."""

    entity_description: ArrstackButtonDescription

    async def async_press(self) -> None:
        """API-Fehler werden zu einer sichtbaren Meldung, nicht zu Stille."""
        try:
            await self.entity_description.press_fn(self.coordinator)
        except ArrstackError as err:
            raise HomeAssistantError(f"arrstack: {err}") from err
