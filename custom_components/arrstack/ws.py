"""WebSocket-Kommandos — alles, was eine Karte braucht, läuft hier serverseitig.

**Warum überhaupt.** Jellyseerr setzt keine CORS-Header. Ein `fetch` aus der
Lovelace-Karte auf `http://seerr:5055/api/v1/search` bricht der Browser ab,
bevor die Anfrage rausgeht. Bei Sonarr/Radarr käme dazu, dass der API-Schlüssel
im Browser läge. Also geht **jeder** Aufruf über `hass.callWS` und von dort
über die Clients dieser Integration.

**Instanzauflösung.** Jedes Kommando nimmt `entry_id` oder `service`. Bei genau
einer passenden Instanz darf beides fehlen; bei mehreren antwortet das Kommando
mit `ambiguous_instance`, statt sich eine auszusuchen.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, callback

from .api import ArrstackAuthError, ArrstackError
from .const import (
    ARR_SERVICES,
    CONF_SERVICE,
    CONF_URL,
    DOMAIN,
    ERR_AMBIGUOUS,
    ERR_API,
    ERR_NOT_FOUND,
    ERR_UNSUPPORTED,
    RECENT_PAGE_SIZE,
    SERVICE_SABNZBD,
    SERVICE_SEERR,
    WS_HISTORY,
    WS_IMPORT_PROBLEMS,
    WS_INSTANCES,
    WS_MANUAL_IMPORT,
    WS_QUEUE,
    WS_QUEUE_REMOVE,
    WS_RECENT,
    WS_REQUEST,
    WS_REQUESTS,
    WS_SEARCH,
    WS_TV_SEASONS,
)
from .coordinator import (
    ArrstackRuntime,
    classify_candidates,
    media_status_name,
    seerr_poster,
)


class _Unresolved(Exception):
    """Keine (oder keine eindeutige) Instanz — trägt den Fehlercode mit."""

    def __init__(self, code: str, message: str) -> None:
        """Code und Klartext; beides geht an die Karte."""
        super().__init__(message)
        self.code = code


def _loaded_entries(hass: HomeAssistant) -> list[ConfigEntry]:
    """Alle arrstack-Einträge, die gerade laufen."""
    return [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state is ConfigEntryState.LOADED
        and getattr(entry, "runtime_data", None) is not None
    ]


def _resolve(
    hass: HomeAssistant, msg: dict[str, Any], allowed: tuple[str, ...]
) -> ArrstackRuntime:
    """Die gemeinte Instanz finden — oder sagen, warum das nicht geht."""
    entries = [
        entry for entry in _loaded_entries(hass) if entry.data[CONF_SERVICE] in allowed
    ]

    entry_id = msg.get("entry_id")
    if entry_id:
        for entry in entries:
            if entry.entry_id == entry_id:
                return entry.runtime_data
        raise _Unresolved(
            ERR_NOT_FOUND,
            f"Keine laufende arrstack-Instanz mit der Id {entry_id} "
            f"(zulässig hier: {', '.join(allowed)}).",
        )

    service = msg.get("service")
    if service:
        if service not in allowed:
            raise _Unresolved(
                ERR_UNSUPPORTED,
                f"{service} kann dieses Kommando nicht — "
                f"zulässig sind {', '.join(allowed)}.",
            )
        entries = [entry for entry in entries if entry.data[CONF_SERVICE] == service]

    if not entries:
        raise _Unresolved(
            ERR_NOT_FOUND,
            "Kein passender arrstack-Dienst eingerichtet "
            f"({', '.join(allowed)}).",
        )
    if len(entries) > 1:
        raise _Unresolved(
            ERR_AMBIGUOUS,
            "Mehrere passende Instanzen — bitte `entry_id` angeben: "
            + ", ".join(f"{entry.title} ({entry.entry_id})" for entry in entries),
        )
    return entries[0].runtime_data


def _handle(func):
    """Fehler einheitlich beantworten, statt die Verbindung abstürzen zu lassen."""

    async def wrapper(
        hass: HomeAssistant,
        connection: websocket_api.ActiveConnection,
        msg: dict[str, Any],
    ) -> None:
        try:
            await func(hass, connection, msg)
        except _Unresolved as err:
            connection.send_error(msg["id"], err.code, str(err))
        except ArrstackAuthError as err:
            connection.send_error(msg["id"], ERR_API, f"API-Schlüssel: {err}")
        except ArrstackError as err:
            connection.send_error(msg["id"], ERR_API, str(err))

    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


_INSTANCE_KEYS = {
    vol.Optional("entry_id"): str,
    vol.Optional("service"): str,
}


@callback
def async_register_websocket_api(hass: HomeAssistant) -> None:
    """Alle Kommandos anmelden. Wird genau einmal aufgerufen."""
    for command in (
        ws_instances,
        ws_queue,
        ws_recent,
        ws_history,
        ws_import_problems,
        ws_manual_import,
        ws_queue_remove,
        ws_search,
        ws_tv_seasons,
        ws_request,
        ws_requests,
    ):
        websocket_api.async_register_command(hass, command)


# --- Übersicht --------------------------------------------------------------


@websocket_api.websocket_command({vol.Required("type"): WS_INSTANCES})
@callback
def ws_instances(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Welche Dienste laufen — die Karten-Editoren bauen daraus ihre Auswahl."""
    connection.send_result(
        msg["id"],
        {
            "instances": [
                {
                    "entry_id": entry.entry_id,
                    "title": entry.title,
                    "service": entry.data[CONF_SERVICE],
                    "url": entry.data.get(CONF_URL),
                }
                for entry in _loaded_entries(hass)
            ]
        },
    )


# --- Sonarr / Radarr / SABnzbd ---------------------------------------------


@websocket_api.websocket_command({vol.Required("type"): WS_QUEUE, **_INSTANCE_KEYS})
@websocket_api.async_response
@_handle
async def ws_queue(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Was gerade läuft. Für die *arr-Apps und für SABnzbd.

    Die Liste kommt aus dem Coordinator, nicht aus einer frischen Anfrage —
    die Karte soll den Dienst nicht bei jedem Aufschlagen zusätzlich belasten.
    """
    runtime = _resolve(hass, msg, ARR_SERVICES + (SERVICE_SABNZBD,))
    data = runtime.coordinator.data or {}
    connection.send_result(
        msg["id"],
        {
            "service": runtime.service,
            "items": data.get("queue") or [],
            "total": data.get("queue_total", data.get("queue_count")),
            "paused": data.get("paused"),
            "speed": data.get("speed"),
        },
    )


@websocket_api.websocket_command({vol.Required("type"): WS_RECENT, **_INSTANCE_KEYS})
@websocket_api.async_response
@_handle
async def ws_recent(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Zuletzt erfolgreich in die Bibliothek aufgenommen."""
    runtime = _resolve(hass, msg, ARR_SERVICES)
    data = runtime.coordinator.data or {}
    connection.send_result(
        msg["id"], {"service": runtime.service, "items": data.get("recent") or []}
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_HISTORY,
        vol.Optional("limit", default=RECENT_PAGE_SIZE): vol.All(
            int, vol.Range(min=1, max=200)
        ),
        **_INSTANCE_KEYS,
    }
)
@websocket_api.async_response
@_handle
async def ws_history(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """SABnzbd-History — abgeschlossen und fehlgeschlagen, frisch geholt."""
    runtime = _resolve(hass, msg, (SERVICE_SABNZBD,))
    history = await runtime.client.history(msg["limit"])
    connection.send_result(
        msg["id"],
        {
            "items": [
                {
                    "id": slot.get("nzo_id"),
                    "title": slot.get("name"),
                    "category": slot.get("category"),
                    "status": slot.get("status"),
                    "size": slot.get("bytes"),
                    "completed": slot.get("completed"),
                    "fail_message": slot.get("fail_message"),
                    "download_time": slot.get("download_time"),
                }
                for slot in history.get("slots") or []
            ]
        },
    )


@websocket_api.websocket_command(
    {vol.Required("type"): WS_IMPORT_PROBLEMS, **_INSTANCE_KEYS}
)
@websocket_api.async_response
@_handle
async def ws_import_problems(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """„Heruntergeladen, aber nicht importiert" — die Liste hinter dem Sensor."""
    runtime = _resolve(hass, msg, ARR_SERVICES)
    data = runtime.coordinator.data or {}
    connection.send_result(
        msg["id"],
        {
            "service": runtime.service,
            "items": data.get("import_problems") or [],
        },
    )


def _import_payload(
    candidates: list[dict[str, Any]], is_sonarr: bool, download_id: str
) -> list[dict[str, Any]]:
    """Aus den Kandidaten die Nutzlast für `POST /manualimport` bauen.

    Nur Felder, die die App selbst geliefert hat — nichts geraten. Fehlt die
    Zuordnung (`series`/`movie`), wird der Kandidat übersprungen; ohne Ziel
    hätte der Import keine Bedeutung.
    """
    payload: list[dict[str, Any]] = []
    for candidate in candidates:
        parent = candidate.get("series") if is_sonarr else candidate.get("movie")
        if not parent:
            continue
        item: dict[str, Any] = {
            "path": candidate.get("path"),
            "folderName": candidate.get("folderName"),
            "quality": candidate.get("quality"),
            "languages": candidate.get("languages"),
            "releaseGroup": candidate.get("releaseGroup"),
            "downloadId": candidate.get("downloadId") or download_id,
            "indexerFlags": candidate.get("indexerFlags", 0),
        }
        if is_sonarr:
            item["seriesId"] = parent.get("id")
            item["episodeIds"] = [
                episode.get("id") for episode in candidate.get("episodes") or []
            ]
        else:
            item["movieId"] = parent.get("id")
        payload.append(item)
    return payload


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_MANUAL_IMPORT,
        vol.Required("download_id"): str,
        vol.Optional("action", default="candidates"): vol.In(("candidates", "import")),
        vol.Optional("import_mode", default="auto"): vol.In(("auto", "move", "copy")),
        vol.Optional("force", default=False): bool,
        **_INSTANCE_KEYS,
    }
)
@websocket_api.async_response
@_handle
async def ws_manual_import(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Kandidaten eines Downloads holen — oder importieren.

    Importiert wird **nur**, wenn `classify_candidates` grünes Licht gibt.
    `force: true` übergeht das bewusst; die Karte setzt es nie von allein,
    sondern erst nach einer zweiten Bestätigung des Nutzers.
    """
    runtime = _resolve(hass, msg, ARR_SERVICES)
    client = runtime.client
    download_id = msg["download_id"]
    candidates = await client.manual_import_candidates(download_id)
    verdict = classify_candidates(candidates)

    if msg["action"] == "candidates":
        connection.send_result(
            msg["id"],
            {
                "service": runtime.service,
                "can_auto_import": verdict["can_auto_import"],
                "reasons": verdict["reasons"],
                "candidates": [
                    {
                        "path": candidate.get("path"),
                        "name": candidate.get("name") or candidate.get("relativePath"),
                        "size": candidate.get("size"),
                        "quality": (candidate.get("quality") or {})
                        .get("quality", {})
                        .get("name"),
                        "parent": (
                            (candidate.get("series") or candidate.get("movie") or {})
                        ).get("title"),
                        "episodes": [
                            f"S{int(episode.get('seasonNumber', 0)):02d}"
                            f"E{int(episode.get('episodeNumber', 0)):02d}"
                            for episode in candidate.get("episodes") or []
                        ],
                        "rejections": [
                            rejection.get("reason")
                            if isinstance(rejection, dict)
                            else str(rejection)
                            for rejection in candidate.get("rejections") or []
                        ],
                    }
                    for candidate in candidates
                ],
            },
        )
        return

    if not verdict["can_auto_import"] and not msg["force"]:
        connection.send_error(
            msg["id"],
            "unsafe_import",
            "Automatischer Import wäre riskant: "
            + ("; ".join(verdict["reasons"]) or "keine Zuordnung gefunden"),
        )
        return

    payload = _import_payload(candidates, client.is_sonarr, download_id)
    if not payload:
        connection.send_error(
            msg["id"],
            "unsafe_import",
            "Keine zuordenbare Datei in diesem Download — nichts zu importieren.",
        )
        return

    await client.manual_import(payload, msg["import_mode"])
    await runtime.coordinator.async_request_refresh()
    connection.send_result(
        msg["id"], {"imported": len(payload), "import_mode": msg["import_mode"]}
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_QUEUE_REMOVE,
        vol.Required("item_id"): int,
        vol.Optional("remove_from_client", default=True): bool,
        vol.Optional("blocklist", default=False): bool,
        **_INSTANCE_KEYS,
    }
)
@websocket_api.async_response
@_handle
async def ws_queue_remove(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Einen Queue-Eintrag entfernen, wahlweise mit Blocklist."""
    runtime = _resolve(hass, msg, ARR_SERVICES)
    coordinator = runtime.coordinator
    # `skipRedownload` existiert erst ab v4 (D5).
    skip_redownload = False if coordinator.major_version >= 4 else None
    await runtime.client.queue_delete(
        msg["item_id"],
        remove_from_client=msg["remove_from_client"],
        blocklist=msg["blocklist"],
        skip_redownload=skip_redownload,
    )
    await coordinator.async_request_refresh()
    connection.send_result(msg["id"], {"removed": msg["item_id"]})


# --- Jellyseerr / Seerr -----------------------------------------------------


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_SEARCH,
        vol.Required("query"): str,
        vol.Optional("page", default=1): vol.All(int, vol.Range(min=1, max=20)),
        **_INSTANCE_KEYS,
    }
)
@websocket_api.async_response
@_handle
async def ws_search(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Seerr-Suche als Stellvertreter — der Browser käme wegen CORS nicht hin."""
    runtime = _resolve(hass, msg, (SERVICE_SEERR,))
    data = await runtime.client.search(msg["query"], msg["page"])
    results = []
    for item in data.get("results") or []:
        media_type = item.get("mediaType")
        if media_type not in ("tv", "movie"):
            continue  # `person` interessiert hier nicht
        media_info = item.get("mediaInfo") or {}
        results.append(
            {
                "id": item.get("id"),
                "media_type": media_type,
                "title": item.get("name") or item.get("title"),
                "date": item.get("firstAirDate") or item.get("releaseDate"),
                "overview": item.get("overview"),
                "poster": seerr_poster(item.get("posterPath")),
                "status": media_status_name(media_info.get("status")),
                "status_code": media_info.get("status"),
            }
        )
    connection.send_result(
        msg["id"],
        {
            "results": results,
            "page": data.get("page"),
            "total_pages": data.get("totalPages"),
        },
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TV_SEASONS,
        vol.Required("tmdb_id"): int,
        **_INSTANCE_KEYS,
    }
)
@websocket_api.async_response
@_handle
async def ws_tv_seasons(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Staffeln einer Serie samt Verfügbarkeit.

    `seasons[]` kommt von TMDB, `mediaInfo.seasons[].status` von Seerr — beides
    zusammengeführt, damit die Karte vorhandene Staffeln ausgrauen kann.
    Staffel 0 (Specials) bleibt drin, aber als solche markiert.
    """
    runtime = _resolve(hass, msg, (SERVICE_SEERR,))
    show = await runtime.client.tv(msg["tmdb_id"])
    media_info = show.get("mediaInfo") or {}
    by_number = {
        season.get("seasonNumber"): season
        for season in media_info.get("seasons") or []
    }
    seasons = []
    for season in show.get("seasons") or []:
        number = season.get("seasonNumber")
        known = by_number.get(number) or {}
        seasons.append(
            {
                "season": number,
                "name": season.get("name"),
                "episodes": season.get("episodeCount"),
                "air_date": season.get("airDate"),
                "specials": number == 0,
                "status": media_status_name(known.get("status")),
                "status_code": known.get("status"),
            }
        )
    connection.send_result(
        msg["id"],
        {
            "id": show.get("id"),
            "title": show.get("name"),
            "poster": seerr_poster(show.get("posterPath")),
            "overview": show.get("overview"),
            "status": media_status_name(media_info.get("status")),
            "seasons": seasons,
        },
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_REQUEST,
        vol.Required("media_type"): vol.In(("tv", "movie")),
        vol.Required("media_id"): int,
        vol.Optional("seasons"): vol.Any([int], "all"),
        vol.Optional("is_4k", default=False): bool,
        **_INSTANCE_KEYS,
    }
)
@websocket_api.async_response
@_handle
async def ws_request(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Request anlegen — der „Download"-Knopf der Karte.

    Bei `tv` **muss** `seasons` mit; fehlt es, antwortet Seerr mit HTTP 500.
    Wird nichts übergeben, gilt `"all"`.
    """
    runtime = _resolve(hass, msg, (SERVICE_SEERR,))
    seasons = msg.get("seasons")
    if msg["media_type"] == "tv" and not seasons:
        seasons = "all"
    result = await runtime.client.create_request(
        media_type=msg["media_type"],
        media_id=msg["media_id"],
        seasons=seasons,
        is_4k=msg["is_4k"],
    )
    await runtime.coordinator.async_request_refresh()
    connection.send_result(
        msg["id"],
        {
            "request_id": result.get("id"),
            "status": result.get("status"),
            "media_status": media_status_name(
                (result.get("media") or {}).get("status")
            ),
        },
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_REQUESTS,
        vol.Optional("filter", default="all"): str,
        vol.Optional("take", default=RECENT_PAGE_SIZE): vol.All(
            int, vol.Range(min=1, max=100)
        ),
        **_INSTANCE_KEYS,
    }
)
@websocket_api.async_response
@_handle
async def ws_requests(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Bestehende Requests, neueste zuerst."""
    runtime = _resolve(hass, msg, (SERVICE_SEERR,))
    data = await runtime.client.requests(take=msg["take"], filter_=msg["filter"])
    items = []
    for request in data.get("results") or []:
        media = request.get("media") or {}
        items.append(
            {
                "id": request.get("id"),
                "media_type": media.get("mediaType"),
                "tmdb_id": media.get("tmdbId"),
                "status_code": request.get("status"),
                "media_status": media_status_name(media.get("status")),
                "created": request.get("createdAt"),
                "requested_by": (request.get("requestedBy") or {}).get(
                    "displayName"
                ),
                "seasons": [
                    season.get("seasonNumber") for season in request.get("seasons") or []
                ],
            }
        )
    connection.send_result(
        msg["id"], {"items": items, "total": (data.get("pageInfo") or {}).get("results")}
    )
