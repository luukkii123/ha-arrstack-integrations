"""Gemeinsame Entitätsbasis: ein Gerät je Config-Entry.

Die Core-Integrationen `sonarr`/`radarr`/`sabnzbd` laufen weiter. Damit sich
nichts überschreibt, ist die `unique_id` **doppelt namensraumt**: Domain
`arrstack` plus `entry_id` plus Schlüssel. Zwei Sonarr-Instanzen kollidieren
dadurch ebenso wenig wie arrstack und Core.
"""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    BRAND_ICON_URL,
    CONF_URL,
    DOMAIN,
    ENTITY_ICONS,
    SERVICE_BRAND,
    SERVICE_FALLBACK_ICON,
    SERVICE_LABELS,
    SERVICE_PRIMARY_ENTITY,
)


class ArrstackEntity(CoordinatorEntity):
    """Basis aller arrstack-Entitäten."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: Any, description: EntityDescription) -> None:
        """Gerätekarte aus dem Eintrag; die Version wird nachgetragen."""
        super().__init__(coordinator)
        self.entity_description = description
        entry = coordinator.config_entry
        service = coordinator.service
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_translation_key = description.translation_key or description.key

        # Ein festes Zeichen nur, wo keine Geräteklasse eines liefert —
        # sonst verlöre man die Automatik von Home Assistant (etwa den
        # Füllstand beim Speicherplatz).
        if getattr(description, "device_class", None) is None:
            self._attr_icon = ENTITY_ICONS.get(description.key)

        # Die Hauptentität trägt das echte Logo des Dienstes. Nur so sieht man
        # einer Liste an, welcher Eintrag Radarr ist und welcher Sonarr — das
        # Zeichen des Config-Entry gehört der Domain und ist bei allen gleich.
        if SERVICE_PRIMARY_ENTITY.get(service) == description.key:
            slug = SERVICE_BRAND.get(service)
            if slug:
                self._attr_entity_picture = BRAND_ICON_URL.format(slug=slug)
            elif SERVICE_FALLBACK_ICON.get(service):
                # Ohne Markenbild wenigstens ein passendes Zeichen — sonst
                # sähe die Hauptentität aus wie jede andere.
                self._attr_icon = SERVICE_FALLBACK_ICON[service]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer=SERVICE_LABELS.get(service, service),
            model=SERVICE_LABELS.get(service, service),
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=entry.data.get(CONF_URL),
            sw_version=str((coordinator.data or {}).get("version") or "") or None,
        )

    @property
    def _data(self) -> dict[str, Any]:
        """Die zuletzt geholten Daten, nie None."""
        return self.coordinator.data or {}
