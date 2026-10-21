"""Feste Sensorlisten je Dienst.

Die **Stück-Listen** (welcher Titel lädt gerade, welcher steckt fest) sind
bewusst *keine* Entitäten: bei ein paar hundert Queue-Einträgen wären das
hunderte Entitäten, die HA in jedem Neustart anlegt. Sie gehen über die
WS-Kommandos an die Karte (`ws.py`).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfDataRate, UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    SERVICE_SABNZBD,
    SERVICE_SEERR,
    SERVICE_SONARR,
)
from .coordinator import ArrstackConfigEntry
from .entity import ArrstackEntity


@dataclass(frozen=True, kw_only=True)
class ArrstackSensorDescription(SensorEntityDescription):
    """Sensorbeschreibung mit dem Griff in die Coordinator-Daten."""

    value_fn: Callable[[dict[str, Any]], Any]
    attrs_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None


def _diskspace(data: dict[str, Any], key: str) -> Any:
    return (data.get("diskspace") or {}).get(key)


#: Sonarr und Radarr sind bis auf den Bestandssensor identisch.
_ARR_COMMON: tuple[ArrstackSensorDescription, ...] = (
    ArrstackSensorDescription(
        key="queue",
        translation_key="queue",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("queue_total"),
    ),
    ArrstackSensorDescription(
        key="downloading",
        translation_key="downloading",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("downloading"),
    ),
    ArrstackSensorDescription(
        key="import_problems",
        translation_key="import_problems",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("import_problem_count"),
        # Die Titel als Attribut, damit eine Automatisierung sie ohne
        # WS-Kommando lesen kann. Bewusst nur Titel und Grund, nicht der ganze
        # Eintrag — Attribute landen in der Datenbank.
        attrs_fn=lambda data: {
            "titles": [
                item.get("parent_title") or item.get("title")
                for item in data.get("import_problems") or []
            ][:20],
        },
    ),
    ArrstackSensorDescription(
        key="wanted",
        translation_key="wanted",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("wanted"),
    ),
    ArrstackSensorDescription(
        key="diskspace_free",
        translation_key="diskspace_free",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
        suggested_display_precision=0,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: _diskspace(data, "free"),
        attrs_fn=lambda data: {"drives": _diskspace(data, "drives") or []},
    ),
    ArrstackSensorDescription(
        key="version",
        translation_key="version",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("version"),
    ),
)

_SONARR_ONLY: tuple[ArrstackSensorDescription, ...] = (
    ArrstackSensorDescription(
        key="series",
        translation_key="series",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("library_count"),
    ),
)

_RADARR_ONLY: tuple[ArrstackSensorDescription, ...] = (
    ArrstackSensorDescription(
        key="movies",
        translation_key="movies",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("library_count"),
    ),
)

_SAB: tuple[ArrstackSensorDescription, ...] = (
    ArrstackSensorDescription(
        key="speed",
        translation_key="speed",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
        suggested_unit_of_measurement=UnitOfDataRate.MEGABYTES_PER_SECOND,
        suggested_display_precision=1,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("speed"),
    ),
    ArrstackSensorDescription(
        key="sizeleft",
        translation_key="sizeleft",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("sizeleft"),
    ),
    ArrstackSensorDescription(
        key="queue_count",
        translation_key="queue_count",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("queue_count"),
    ),
    ArrstackSensorDescription(
        key="status",
        translation_key="status",
        value_fn=lambda data: data.get("status"),
        attrs_fn=lambda data: {"timeleft": data.get("timeleft")},
    ),
    ArrstackSensorDescription(
        key="diskspace_free",
        translation_key="diskspace_free",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
        suggested_display_precision=0,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("diskspace_free"),
        attrs_fn=lambda data: {"total": data.get("diskspace_total")},
    ),
    ArrstackSensorDescription(
        key="version",
        translation_key="version",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("version"),
    ),
)


def _seerr_count(key: str) -> ArrstackSensorDescription:
    """Ein Zähler aus `request/count` — alle nach demselben Muster."""
    return ArrstackSensorDescription(
        key=f"requests_{key}",
        translation_key=f"requests_{key}",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data, key=key: (data.get("counts") or {}).get(key),
    )


_SEERR: tuple[ArrstackSensorDescription, ...] = (
    _seerr_count("pending"),
    _seerr_count("approved"),
    _seerr_count("declined"),
    _seerr_count("processing"),
    _seerr_count("available"),
    _seerr_count("failed"),
    _seerr_count("completed"),
    _seerr_count("total"),
    ArrstackSensorDescription(
        key="version",
        translation_key="version",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("version"),
    ),
)


def descriptions_for(service: str) -> tuple[ArrstackSensorDescription, ...]:
    """Welche Sensoren ein Dienst bekommt."""
    if service == SERVICE_SABNZBD:
        return _SAB
    if service == SERVICE_SEERR:
        return _SEERR
    extra = _SONARR_ONLY if service == SERVICE_SONARR else _RADARR_ONLY
    return _ARR_COMMON + extra


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ArrstackConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Sensoren des Dienstes anlegen, den diese Entry vertritt."""
    runtime = entry.runtime_data
    async_add_entities(
        ArrstackSensor(runtime.coordinator, description)
        for description in descriptions_for(runtime.service)
    )


class ArrstackSensor(ArrstackEntity, SensorEntity):
    """Ein Sensor; der Wert kommt aus `value_fn` der Beschreibung."""

    entity_description: ArrstackSensorDescription

    @property
    def native_value(self) -> Any:
        """Fehlende Werte bleiben None — HA zeigt dann „unbekannt"."""
        return self.entity_description.value_fn(self._data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Nur, wo die Beschreibung Attribute vorsieht."""
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self._data)
