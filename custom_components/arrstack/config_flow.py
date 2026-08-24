"""Config-Flow: erst den Dienst wählen, dann Adresse und API-Schlüssel.

Eine Config-Entry = **eine Instanz eines Dienstes**. Vier Dienste bedeuten vier
Einträge, zwei Sonarr-Server bedeuten zwei Sonarr-Einträge. Nichts davon setzt
etwas anderes voraus: Wer nur Radarr einrichtet, bekommt eine vollständig
funktionierende Radarr-Integration.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.helpers.selector import (
    BooleanSelector,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import (
    ArrClient,
    ArrstackAuthError,
    ArrstackConnectionError,
    ArrstackError,
    SabClient,
    SeerrClient,
    normalize_url,
)
from .const import (
    CONF_API_KEY,
    CONF_SCAN_INTERVAL,
    CONF_SERVICE,
    CONF_URL,
    CONF_VERIFY_SSL,
    DEFAULT_PORTS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    SERVICE_LABELS,
    SERVICE_SABNZBD,
    SERVICE_SEERR,
    SERVICES,
)
from .coordinator import ArrstackConfigEntry


def _schema(service: str) -> vol.Schema:
    """Formular für einen Dienst; der Standardport steht als Vorschlag drin.

    Als Adresse steht bewusst `localhost` da: ein Vorschlag, der den
    Standardport zeigt, ohne ein fremdes Netz vorwegzunehmen.
    """
    default_url = f"http://localhost:{DEFAULT_PORTS[service]}"
    return vol.Schema(
        {
            vol.Required(CONF_URL, default=default_url): TextSelector(
                TextSelectorConfig(type=TextSelectorType.URL)
            ),
            vol.Required(CONF_API_KEY): TextSelector(
                TextSelectorConfig(type=TextSelectorType.PASSWORD)
            ),
            vol.Optional(CONF_VERIFY_SSL, default=True): BooleanSelector(),
            vol.Optional(
                CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
            ): vol.All(
                vol.Coerce(int),
                vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
            ),
        }
    )


async def validate_connection(
    hass: Any, service: str, url: str, api_key: str, verify_ssl: bool
) -> dict[str, Any]:
    """Einmal anfragen und die Version zurückgeben.

    Das ist zugleich der Beleg, dass Adresse und Schlüssel stimmen — und bei
    Sonarr/Radarr die Stelle, an der die Hauptversion gelesen wird (D5).
    """
    if service == SERVICE_SABNZBD:
        client = SabClient(hass, url, api_key, verify_ssl)
        return {"version": await client.version()}
    if service == SERVICE_SEERR:
        client = SeerrClient(hass, url, api_key, verify_ssl)
        status = await client.status()
        return {"version": status.get("version")}
    arr = ArrClient(hass, url, api_key, service, verify_ssl)
    status = await arr.system_status()
    if not status.get("version"):
        raise ArrstackError(
            "Antwort ohne `version` — zeigt die Adresse wirklich auf "
            f"{SERVICE_LABELS[service]}?"
        )
    return {"version": status.get("version"), "url_base": status.get("urlBase")}


class ArrstackConfigFlow(ConfigFlow, domain=DOMAIN):
    """Dienstauswahl, Zugangsdaten, Reauth."""

    VERSION = 1

    def __init__(self) -> None:
        """Der gewählte Dienst überlebt den Schritt zwischen Menü und Formular."""
        self._service: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Menü mit den vier Diensten — jeder für sich einrichtbar."""
        return self.async_show_menu(step_id="user", menu_options=list(SERVICES))

    async def async_step_sonarr(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Sonarr."""
        return await self._async_step_service("sonarr", user_input)

    async def async_step_radarr(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Radarr."""
        return await self._async_step_service("radarr", user_input)

    async def async_step_sabnzbd(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """SABnzbd."""
        return await self._async_step_service("sabnzbd", user_input)

    async def async_step_seerr(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Jellyseerr/Seerr."""
        return await self._async_step_service("seerr", user_input)

    async def _async_step_service(
        self, service: str, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        """Ein Formular für alle vier — es unterscheidet sich nur im Port."""
        self._service = service
        errors: dict[str, str] = {}

        if user_input is not None:
            url = normalize_url(user_input[CONF_URL])
            api_key = str(user_input[CONF_API_KEY]).strip()
            verify_ssl = bool(user_input.get(CONF_VERIFY_SSL, True))

            await self.async_set_unique_id(f"{service}:{url}")
            self._abort_if_unique_id_configured()

            try:
                info = await validate_connection(
                    self.hass, service, url, api_key, verify_ssl
                )
            except ArrstackAuthError:
                errors["base"] = "invalid_auth"
            except ArrstackConnectionError:
                errors["base"] = "cannot_connect"
            except ArrstackError:
                errors["base"] = "unexpected_response"
            else:
                data = {
                    CONF_SERVICE: service,
                    CONF_URL: url,
                    CONF_API_KEY: api_key,
                    CONF_VERIFY_SSL: verify_ssl,
                    CONF_SCAN_INTERVAL: user_input.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                    ),
                }
                version = info.get("version") or "?"
                return self.async_create_entry(
                    title=f"{SERVICE_LABELS[service]} ({_host(url)})",
                    data=data,
                    description_placeholders={"version": version},
                )

        return self.async_show_form(
            step_id=service,
            data_schema=self.add_suggested_values_to_schema(
                _schema(service), user_input
            ),
            errors=errors,
            description_placeholders={"service": SERVICE_LABELS[service]},
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Der Coordinator hat 401/403 gesehen — neuen Schlüssel erfragen."""
        self._service = entry_data.get(CONF_SERVICE)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Nur der Schlüssel; Adresse und Dienst bleiben, wie sie sind."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            api_key = str(user_input[CONF_API_KEY]).strip()
            service = entry.data[CONF_SERVICE]
            url = entry.data[CONF_URL]
            verify_ssl = bool(entry.data.get(CONF_VERIFY_SSL, True))
            try:
                await validate_connection(
                    self.hass, service, url, api_key, verify_ssl
                )
            except ArrstackAuthError:
                errors["base"] = "invalid_auth"
            except ArrstackConnectionError:
                errors["base"] = "cannot_connect"
            except ArrstackError:
                errors["base"] = "unexpected_response"
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_API_KEY: api_key}
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    )
                }
            ),
            errors=errors,
            description_placeholders={"title": entry.title},
        )

    @staticmethod
    def async_get_options_flow(entry: ArrstackConfigEntry) -> ArrstackOptionsFlow:
        """Intervall, Schlüssel und Zertifikatsprüfung später ändern."""
        return ArrstackOptionsFlow()


def _host(url: str) -> str:
    """`http://host:8989/sonarr` → `host:8989` — nur für den Eintragstitel."""
    without_scheme = url.split("://", 1)[-1]
    return without_scheme.split("/", 1)[0]


class ArrstackOptionsFlow(OptionsFlow):
    """Nachträglich anpassen, was sich ändern darf."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Leerer Schlüssel heißt: den bisherigen behalten."""
        entry = self.config_entry
        if user_input is not None:
            api_key = str(user_input.get(CONF_API_KEY, "")).strip()
            if api_key:
                user_input[CONF_API_KEY] = api_key
            else:
                user_input.pop(CONF_API_KEY, None)
            return self.async_create_entry(data=user_input)

        current_interval = entry.options.get(
            CONF_SCAN_INTERVAL,
            entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        current_verify = entry.options.get(
            CONF_VERIFY_SSL, entry.data.get(CONF_VERIFY_SSL, True)
        )
        schema = vol.Schema(
            {
                vol.Optional(CONF_API_KEY, default=""): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
                vol.Optional(CONF_VERIFY_SSL, default=current_verify): (
                    BooleanSelector()
                ),
                vol.Optional(CONF_SCAN_INTERVAL, default=current_interval): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                ),
            }
        )
        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            description_placeholders={"title": entry.title},
        )
