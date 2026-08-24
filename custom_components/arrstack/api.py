"""HTTP-Clients für Sonarr, Radarr, SABnzbd und Jellyseerr/Seerr.

Bewusst eigene, schlanke Clients statt `aiopyarr`: dessen Queue-Abruf hat einen
bekannten `timeleft`-Fehler (tkdrob/aiopyarr#60), und die Integration braucht
ohnehin Endpunkte, die die Bibliothek nicht abdeckt (`manualimport`,
`queue`-Löschen mit Flags, Seerr komplett). Der HTTP-Client kommt von Home
Assistant selbst — deshalb steht in `manifest.json` `"requirements": []`.

Jeder Client kennt nur seinen eigenen Dienst. Es gibt keine Aufrufe zwischen
den Clients; ein fehlender Dienst kann hier also gar nichts kaputtmachen.
"""

from __future__ import annotations

import json
from typing import Any

import aiohttp
from yarl import URL

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    QUEUE_PAGE_SIZE,
    RECENT_PAGE_SIZE,
    REQUEST_TIMEOUT,
    SERVICE_SONARR,
)


class ArrstackError(Exception):
    """Basisfehler aller vier Clients."""


class ArrstackAuthError(ArrstackError):
    """API-Schlüssel abgelehnt (401/403 bzw. SABnzbds Klartextmeldung)."""


class ArrstackConnectionError(ArrstackError):
    """Dienst nicht erreichbar — Netz, DNS, Zeitüberschreitung, TLS."""


def normalize_url(url: str) -> str:
    """Auf ein `schema://host:port[/unterordner]` ohne Schrägstrich am Ende.

    Ein Unterordner (`urlBase`, etwa `http://host/sonarr`) bleibt erhalten — er
    gehört zur Adresse und wird jedem API-Pfad vorangestellt.
    """
    cleaned = (url or "").strip().rstrip("/")
    if cleaned and "://" not in cleaned:
        cleaned = f"http://{cleaned}"
    return cleaned


class _BaseClient:
    """Gemeinsames Anfragegerüst: eine Sitzung, ein Basispfad, ein Zeitlimit."""

    def __init__(
        self,
        hass: HomeAssistant,
        url: str,
        api_key: str,
        verify_ssl: bool = True,
    ) -> None:
        """Die Sitzung kommt von Home Assistant, damit sie mitverwaltet wird."""
        self._session: aiohttp.ClientSession = async_get_clientsession(
            hass, verify_ssl
        )
        self._base = normalize_url(url)
        self._api_key = api_key

    @property
    def base_url(self) -> str:
        """Die normalisierte Basisadresse — auch die Grundlage der unique_id."""
        return self._base

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        """Eine Anfrage; Fehler werden in die drei Klassen oben übersetzt."""
        url = URL(f"{self._base}/{path.lstrip('/')}", encoded=False)
        try:
            response = await self._session.request(
                method,
                url,
                params=_stringify(params),
                json=json,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            )
        except aiohttp.ClientError as err:
            raise ArrstackConnectionError(f"{url.host}: {err}") from err
        except TimeoutError as err:
            raise ArrstackConnectionError(
                f"{url.host}: keine Antwort nach {REQUEST_TIMEOUT} s"
            ) from err

        async with response:
            if response.status in (401, 403):
                raise ArrstackAuthError(
                    f"API-Schlüssel abgelehnt (HTTP {response.status})."
                )
            if response.status >= 400:
                body = (await response.text())[:200]
                raise ArrstackError(f"HTTP {response.status}: {body}")
            if response.status == 204 or not response.content_length:
                # 204 und leere Antworten kommen bei POST/DELETE regelmäßig vor.
                text = await response.text()
                if not text.strip():
                    return None
                return _loads(text)
            return _loads(await response.text())


def _stringify(params: dict[str, Any] | None) -> dict[str, str] | None:
    """aiohttp nimmt keine bools/ints als Query-Werte — hier umgewandelt."""
    if params is None:
        return None
    out: dict[str, str] = {}
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, bool):
            out[key] = "true" if value else "false"
        else:
            out[key] = str(value)
    return out


def _loads(text: str) -> Any:
    """JSON entpacken; leerer Text wird zu None statt zu einem Fehler."""
    if not text.strip():
        return None
    try:
        return json.loads(text)
    except ValueError as err:
        raise ArrstackError(f"Antwort war kein JSON: {text[:120]}") from err


class ArrClient(_BaseClient):
    """Sonarr und Radarr — dieselbe API `/api/v3`, andere Substantive."""

    def __init__(
        self,
        hass: HomeAssistant,
        url: str,
        api_key: str,
        service: str,
        verify_ssl: bool = True,
    ) -> None:
        """`service` entscheidet über Feldnamen, Kommandos und Endpunkte."""
        super().__init__(hass, url, api_key, verify_ssl)
        self.service = service
        self.is_sonarr = service == SERVICE_SONARR

    async def _get(self, path: str, **params: Any) -> Any:
        return await self._request(
            "GET",
            f"api/v3/{path}",
            params=params,
            headers={"X-Api-Key": self._api_key},
        )

    async def _post(self, path: str, payload: Any) -> Any:
        return await self._request(
            "POST",
            f"api/v3/{path}",
            json=payload,
            headers={"X-Api-Key": self._api_key},
        )

    async def _delete(self, path: str, **params: Any) -> Any:
        return await self._request(
            "DELETE",
            f"api/v3/{path}",
            params=params,
            headers={"X-Api-Key": self._api_key},
        )

    # -- lesen ---------------------------------------------------------------

    async def system_status(self) -> dict[str, Any]:
        """`version` und `urlBase`; wird schon im Config-Flow als Test benutzt."""
        return await self._get("system/status") or {}

    async def health(self) -> list[dict[str, Any]]:
        """Health-Checks; Sonarr hat dafür in Core keinen Sensor."""
        return await self._get("health") or []

    async def diskspace(self) -> list[dict[str, Any]]:
        """Alle von der App gesehenen Laufwerke."""
        return await self._get("diskspace") or []

    async def queue(self, page_size: int = QUEUE_PAGE_SIZE) -> dict[str, Any]:
        """Die Queue samt Titeln.

        `includeUnknownSeriesItems` bzw. `includeUnknownMovieItems` ist der
        entscheidende Schalter: **ohne ihn fehlen genau die Einträge**, um die
        es beim „heruntergeladen, aber nicht importiert" geht.
        """
        params: dict[str, Any] = {
            "page": 1,
            "pageSize": page_size,
            "sortKey": "timeleft",
            "sortDirection": "ascending",
        }
        if self.is_sonarr:
            params["includeUnknownSeriesItems"] = True
            params["includeSeries"] = True
            params["includeEpisode"] = True
        else:
            params["includeUnknownMovieItems"] = True
            params["includeMovie"] = True
        return await self._get("queue", **params) or {}

    async def wanted_missing(self) -> int:
        """Nur die Gesamtzahl — `pageSize=1` hält die Antwort klein."""
        data = await self._get(
            "wanted/missing", page=1, pageSize=1, includeSeries=False
        )
        return int((data or {}).get("totalRecords") or 0)

    async def library(self) -> list[dict[str, Any]]:
        """Serien- bzw. Filmbestand. Groß — deshalb nur im langsamen Takt."""
        return await self._get("series" if self.is_sonarr else "movie") or []

    async def history_imported(
        self, page_size: int = RECENT_PAGE_SIZE
    ) -> list[dict[str, Any]]:
        """Zuletzt erfolgreich importiert (`eventType=3`).

        Für Radarr liefert `movieFile.dateAdded` aus dem Bestand die genauere
        Antwort auf „liegt seit wann in der Bibliothek" — die nimmt der
        Coordinator auch. Für **Sonarr** gibt es keinen Weg, Episodendateien
        über alle Serien hinweg zu listen (`/episodefile` verlangt eine
        `seriesId`), deshalb ist hier die History die Quelle.
        """
        params: dict[str, Any] = {
            "page": 1,
            "pageSize": page_size,
            "eventType": 3,
            "sortKey": "date",
            "sortDirection": "descending",
        }
        if self.is_sonarr:
            params["includeSeries"] = True
            params["includeEpisode"] = True
        else:
            params["includeMovie"] = True
        data = await self._get("history", **params) or {}
        return data.get("records") or []

    async def manual_import_candidates(
        self, download_id: str
    ) -> list[dict[str, Any]]:
        """Was die App in diesem Download findet — mit `rejections`.

        `filterExistingFiles=false`, damit auch bereits bekannte Dateien
        auftauchen; sonst sieht man bei „existing file better" gar nichts und
        könnte den Grund nicht anzeigen.
        """
        return await self._get(
            "manualimport", downloadId=download_id, filterExistingFiles=False
        ) or []

    # -- schreiben -----------------------------------------------------------

    async def command(self, name: str, **payload: Any) -> Any:
        """`POST /command` — Rescan, RefreshMonitoredDownloads, ManualImport."""
        return await self._post("command", {"name": name, **payload})

    async def manual_import(
        self, files: list[dict[str, Any]], import_mode: str = "auto"
    ) -> Any:
        """Der moderne Weg (`POST /manualimport`), wie ihn die Web-UI geht."""
        payload = [{**item, "importMode": import_mode} for item in files]
        return await self._post("manualimport", payload)

    async def queue_delete(
        self,
        item_id: int,
        *,
        remove_from_client: bool = True,
        blocklist: bool = False,
        skip_redownload: bool | None = None,
        change_category: bool | None = None,
    ) -> Any:
        """Eintrag aus der Queue werfen.

        `skipRedownload` und `changeCategory` gibt es **erst ab v4**; wer sie
        an ein v3 schickt, bekommt einen Fehler. Der Aufrufer entscheidet
        anhand der gelesenen Version, ob er sie mitgibt (None = weglassen).
        """
        params: dict[str, Any] = {
            "removeFromClient": remove_from_client,
            "blocklist": blocklist,
        }
        if skip_redownload is not None:
            params["skipRedownload"] = skip_redownload
        if change_category is not None:
            params["changeCategory"] = change_category
        return await self._delete(f"queue/{item_id}", **params)


class SabClient(_BaseClient):
    """SABnzbd — eine einzige Adresse `/api`, alles über `mode=`.

    **Der Schlüssel geht als Query-Wert `apikey`**, nicht als `X-Api-Key`.
    Das weicht vom Plan (§5, „alle vier: X-Api-Key") ab; SABnzbd liest den
    Header nicht, und ein Header-only-Aufruf käme als „API Key Incorrect"
    zurück. Der Header wird zusätzlich mitgeschickt, schadet nicht.
    """

    async def _call(self, mode: str, **params: Any) -> dict[str, Any]:
        data = await self._request(
            "GET",
            "api",
            params={
                "mode": mode,
                "output": "json",
                "apikey": self._api_key,
                **params,
            },
            headers={"X-Api-Key": self._api_key},
        )
        if isinstance(data, dict):
            # SABnzbd antwortet auf einen falschen Schlüssel mit HTTP 200 und
            # `{"status": false, "error": "API Key Incorrect"}`. Ohne diese
            # Prüfung liefe die Integration mit leeren Werten weiter.
            error = data.get("error")
            if error and data.get("status") is False:
                if "key" in str(error).lower():
                    raise ArrstackAuthError(str(error))
                raise ArrstackError(str(error))
        return data or {}

    async def version(self) -> str:
        """Wird auch im Config-Flow als Erreichbarkeitstest benutzt."""
        data = await self._call("version")
        return str(data.get("version") or "")

    async def queue(self) -> dict[str, Any]:
        """Queue samt Kopfwerten: Tempo, Restgröße, Platte, Pausenzustand."""
        data = await self._call("queue")
        return data.get("queue") or {}

    async def history(self, limit: int = RECENT_PAGE_SIZE) -> dict[str, Any]:
        """Abgeschlossene und fehlgeschlagene Downloads."""
        data = await self._call("history", limit=limit)
        return data.get("history") or {}

    async def pause(self) -> None:
        """Alles anhalten."""
        await self._call("pause")

    async def resume(self) -> None:
        """Weiterlaufen lassen."""
        await self._call("resume")

    async def set_speedlimit(self, value: float) -> None:
        """Tempolimit in Prozent der Leitung (SABnzbds eigene Einheit)."""
        await self._call("config", name="speedlimit", value=value)


class SeerrClient(_BaseClient):
    """Jellyseerr/Seerr — `/api/v1`, Standardport 5055.

    Overseerr wird **nicht** unterstützt (D1). Der Unterschied, der hier zählt,
    steckt im Status-Enum: 6 = BLOCKLISTED, 7 = DELETED.
    """

    async def _get(self, path: str, **params: Any) -> Any:
        return await self._request(
            "GET",
            f"api/v1/{path}",
            params=params,
            headers={"X-Api-Key": self._api_key},
        )

    async def status(self) -> dict[str, Any]:
        """Version und Update-Zustand; im Config-Flow der Test."""
        return await self._get("status") or {}

    async def request_count(self) -> dict[str, Any]:
        """Zähler je Zustand — die Grundlage aller Seerr-Sensoren."""
        return await self._get("request/count") or {}

    async def search(self, query: str, page: int = 1) -> dict[str, Any]:
        """Titelsuche. Ergebnis trägt `mediaType`, `id` (TMDB), `posterPath`."""
        return await self._get("search", query=query, page=page) or {}

    async def tv(self, tmdb_id: int) -> dict[str, Any]:
        """Serie samt `seasons[]` und `mediaInfo.seasons[].status`."""
        return await self._get(f"tv/{tmdb_id}") or {}

    async def movie(self, tmdb_id: int) -> dict[str, Any]:
        """Film samt `mediaInfo.status`."""
        return await self._get(f"movie/{tmdb_id}") or {}

    async def requests(
        self,
        *,
        take: int = RECENT_PAGE_SIZE,
        skip: int = 0,
        filter_: str = "all",
        sort: str = "added",
    ) -> dict[str, Any]:
        """Bestehende Requests, absteigend nach Anlage."""
        return await self._get(
            "request",
            take=take,
            skip=skip,
            filter=filter_,
            sort=sort,
            sortDirection="desc",
        ) or {}

    async def create_request(
        self,
        *,
        media_type: str,
        media_id: int,
        seasons: list[int] | str | None = None,
        is_4k: bool = False,
    ) -> dict[str, Any]:
        """Request anlegen.

        **Bei `mediaType == "tv"` ist `seasons` Pflicht** — fehlt es, antwortet
        Seerr mit HTTP 500. Erlaubt ist eine Liste von Staffelnummern oder der
        Text `"all"`.
        """
        payload: dict[str, Any] = {
            "mediaType": media_type,
            "mediaId": int(media_id),
            "is4k": is_4k,
        }
        if media_type == "tv":
            payload["seasons"] = seasons if seasons is not None else "all"
        return await self._request(
            "POST",
            "api/v1/request",
            json=payload,
            headers={"X-Api-Key": self._api_key},
        ) or {}
