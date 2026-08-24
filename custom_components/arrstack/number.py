"""SABnzbds Tempolimit als Zahl-Entität.

SABnzbd rechnet das Limit in **Prozent der Leitung** (`speedlimit`), nicht in
kB/s — der absolute Wert steht daneben als `speedlimit_abs` und wird als
Attribut mitgegeben. 0 heißt „kein Limit".
"""

from __future__ import annotations

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import ArrstackError
from .const import SERVICE_SABNZBD
from .coordinator import ArrstackConfigEntry
from .entity import ArrstackEntity

SPEEDLIMIT = NumberEntityDescription(
    key="speedlimit",
    translation_key="speedlimit",
    device_class=NumberDeviceClass.POWER_FACTOR,
    native_unit_of_measurement=PERCENTAGE,
    native_min_value=0,
    native_max_value=100,
    native_step=1,
    mode=NumberMode.SLIDER,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ArrstackConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Nur SABnzbd bekommt diese Plattform überhaupt."""
    runtime = entry.runtime_data
    if runtime.service != SERVICE_SABNZBD:
        return
    async_add_entities([SabSpeedLimit(runtime.coordinator, SPEEDLIMIT)])


class SabSpeedLimit(ArrstackEntity, NumberEntity):
    """Tempolimit in Prozent."""

    @property
    def native_value(self) -> float | None:
        """Aktueller Wert aus der Queue-Antwort."""
        return self._data.get("speedlimit")

    @property
    def extra_state_attributes(self) -> dict[str, float | None]:
        """Der absolute Wert (kB/s), den SABnzbd daraus errechnet."""
        return {"speedlimit_abs": self._data.get("speedlimit_abs")}

    async def async_set_native_value(self, value: float) -> None:
        """Setzen und sofort zurücklesen, damit der Regler nicht springt."""
        try:
            await self.coordinator.client.set_speedlimit(value)
        except ArrstackError as err:
            raise HomeAssistantError(f"arrstack: {err}") from err
        await self.coordinator.async_request_refresh()
