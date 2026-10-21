"""Binäre Sensoren: Import-Problem, Health, Erreichbarkeit.

`health` schließt eine echte Lücke — die Core-`sonarr` hat keinen
Health-Sensor. `offline` ist der einzige Sensor, der auch dann noch antwortet,
wenn der Dienst weg ist (siehe `available` unten).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ARR_SERVICES, SERVICE_SABNZBD
from .coordinator import ArrstackConfigEntry
from .entity import ArrstackEntity


@dataclass(frozen=True, kw_only=True)
class ArrstackBinaryDescription(BinarySensorEntityDescription):
    """Beschreibung mit Zustandsfunktion; `None` heißt „unbekannt"."""

    is_on_fn: Callable[[dict[str, Any]], bool | None]
    attrs_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None
    #: Bleibt verfügbar, auch wenn die letzte Abfrage scheiterte.
    survives_outage: bool = False


_OFFLINE = ArrstackBinaryDescription(
    key="offline",
    translation_key="offline",
    device_class=BinarySensorDeviceClass.PROBLEM,
    entity_category=EntityCategory.DIAGNOSTIC,
    # Wird in der Entität überschrieben — der Zustand hängt nicht an den Daten,
    # sondern daran, ob die Abfrage überhaupt durchkam.
    is_on_fn=lambda data: None,
    survives_outage=True,
)

_ARR: tuple[ArrstackBinaryDescription, ...] = (
    ArrstackBinaryDescription(
        key="import_problem",
        translation_key="import_problem",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=lambda data: bool(data.get("import_problem_count")),
        attrs_fn=lambda data: {
            "count": data.get("import_problem_count"),
            "titles": [
                item.get("parent_title") or item.get("title")
                for item in data.get("import_problems") or []
            ][:20],
        },
    ),
    ArrstackBinaryDescription(
        key="health",
        translation_key="health",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=lambda data: bool(
            data.get("health_errors") or data.get("health_warnings")
        ),
        attrs_fn=lambda data: {
            "errors": data.get("health_errors"),
            "warnings": data.get("health_warnings"),
            "messages": [
                f"{item.get('type')}: {item.get('message')}"
                for item in data.get("health") or []
            ][:20],
        },
    ),
    _OFFLINE,
)

_SAB: tuple[ArrstackBinaryDescription, ...] = (
    ArrstackBinaryDescription(
        key="warnings",
        translation_key="warnings",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=lambda data: bool(data.get("warnings")),
        attrs_fn=lambda data: {"count": data.get("warnings")},
    ),
    ArrstackBinaryDescription(
        key="paused",
        translation_key="paused",
        is_on_fn=lambda data: bool(data.get("paused")),
    ),
    _OFFLINE,
)

_SEERR: tuple[ArrstackBinaryDescription, ...] = (_OFFLINE,)


def descriptions_for(service: str) -> tuple[ArrstackBinaryDescription, ...]:
    """Welche binären Sensoren ein Dienst bekommt."""
    if service in ARR_SERVICES:
        return _ARR
    if service == SERVICE_SABNZBD:
        return _SAB
    return _SEERR


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ArrstackConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Binäre Sensoren des Dienstes anlegen."""
    runtime = entry.runtime_data
    async_add_entities(
        ArrstackBinarySensor(runtime.coordinator, description)
        for description in descriptions_for(runtime.service)
    )


class ArrstackBinarySensor(ArrstackEntity, BinarySensorEntity):
    """Ein binärer Sensor."""

    entity_description: ArrstackBinaryDescription

    @property
    def available(self) -> bool:
        """Der Offline-Sensor bleibt verfügbar, sonst könnte er nichts melden.

        `CoordinatorEntity.available` ist `last_update_success` — genau dann
        also falsch, wenn dieser Sensor gebraucht wird.
        """
        if self.entity_description.survives_outage:
            return True
        return super().available

    @property
    def is_on(self) -> bool | None:
        """Offline hängt am Abfrageerfolg, alles andere an den Daten."""
        if self.entity_description.key == "offline":
            return not self.coordinator.last_update_success
        return self.entity_description.is_on_fn(self._data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Nur, wo die Beschreibung Attribute vorsieht."""
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self._data)
