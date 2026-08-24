"""Ein DataUpdateCoordinator je Dienst — und die Aufbereitung der Rohdaten.

Hier steckt die eigentliche Fachlogik: was „heruntergeladen, aber nicht
importiert" heißt, welche Felder eine Karte braucht, und was ein Sensor als
Zahl bekommt. Die Clients in `api.py` liefern nur JSON.

**Kein Coordinator kennt einen anderen.** Jede Config-Entry richtet genau einen
ein; fehlt ein Dienst, fehlt schlicht dieser Coordinator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    ArrClient,
    ArrstackAuthError,
    ArrstackError,
    SabClient,
    SeerrClient,
)
from .const import (
    CONF_API_KEY,
    CONF_SCAN_INTERVAL,
    CONF_SERVICE,
    CONF_URL,
    CONF_VERIFY_SSL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    IMPORT_PROBLEM_STATES,
    SEERR_COUNT_KEYS,
    SEERR_MEDIA_STATUS,
    SERVICE_SABNZBD,
    SERVICE_SEERR,
    SERVICE_SONARR,
    SLOW_REFRESH_EVERY,
    STATE_DOWNLOADING,
    UNSAFE_REJECTION_MARKERS,
)

_LOGGER = logging.getLogger(__name__)

# Zuweisung statt `type ...` (PEP 695), damit die Datei auch unter Python 3.11
# noch parst — sie wird hier nur syntaktisch geprüft, nicht ausgeführt.
ArrstackConfigEntry = ConfigEntry["ArrstackRuntime"]

TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w300"


@dataclass(slots=True)
class ArrstackRuntime:
    """Was eine Config-Entry besitzt: ihren Dienst und ihren Coordinator."""

    service: str
    coordinator: DataUpdateCoordinator[dict[str, Any]]
    client: Any = field(repr=False)


def _setting(entry: ConfigEntry, key: str, default: Any) -> Any:
    """Optionen schlagen Daten — Optionen sind das, was später editiert wird."""
    return entry.options.get(key, entry.data.get(key, default))


def is_import_problem(record: dict[str, Any]) -> bool:
    """„Heruntergeladen, aber nicht importiert" nach dem Datenvertrag (§5).

    Drei Bedingungen zusammen, nicht einzeln:
    fertig heruntergeladen · Warnung oder Fehler · Import hängt.
    """
    if str(record.get("status") or "").lower() != "completed":
        return False
    if str(record.get("trackedDownloadStatus") or "").lower() not in (
        "warning",
        "error",
    ):
        return False
    return record.get("trackedDownloadState") in IMPORT_PROBLEM_STATES


def rejection_is_unsafe(reason: str) -> bool:
    """Ist dieser Ablehnungsgrund einer, bei dem Auto-Import schadet?"""
    lowered = str(reason or "").lower().replace("_", "")
    return any(marker in lowered for marker in UNSAFE_REJECTION_MARKERS)


def classify_candidates(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """Entscheidet, ob ein Ein-Klick-Import angeboten werden darf.

    Angeboten wird er nur, wenn **jede** gefundene Datei zugeordnet ist und
    **keine** Ablehnung mit einem der heiklen Gründe dabei ist. Sonst bleibt
    es beim Anzeigen des Grundes — blind zu importieren ordnet Dateien der
    falschen Serie zu, und das wieder auseinanderzusortieren ist Handarbeit.
    """
    reasons: list[str] = []
    unsafe = False
    for candidate in candidates:
        for rejection in candidate.get("rejections") or []:
            reason = rejection.get("reason") if isinstance(rejection, dict) else rejection
            reason = str(reason or "").strip()
            if reason:
                reasons.append(reason)
            if rejection_is_unsafe(reason):
                unsafe = True
        # Ohne Zuordnung (Serie/Film fehlt) weiß die App nicht, wohin damit.
        if not candidate.get("series") and not candidate.get("movie"):
            unsafe = True
            reasons.append("Keine Serie/kein Film zugeordnet")
    return {
        "can_auto_import": bool(candidates) and not unsafe,
        "reasons": sorted(set(reasons)),
    }


def _poster_url(item: dict[str, Any] | None) -> str | None:
    """Poster-Adresse aus `images[]` einer *arr-App.

    `remoteUrl` zeigt direkt zu TMDB/Fanart und ist ohne API-Schlüssel
    abrufbar — die Karte kann es also unverändert in ein `<img>` schreiben.
    """
    for image in (item or {}).get("images") or []:
        if image.get("coverType") == "poster":
            return image.get("remoteUrl") or image.get("url")
    return None


def _episode_label(record: dict[str, Any]) -> str | None:
    """`S02E05` aus einem Queue- oder History-Eintrag, wenn ableitbar."""
    episode = record.get("episode") or {}
    if not episode:
        episodes = record.get("episodes") or []
        episode = episodes[0] if episodes else {}
    season = episode.get("seasonNumber")
    number = episode.get("episodeNumber")
    if season is None or number is None:
        return None
    return f"S{int(season):02d}E{int(number):02d}"


def normalize_queue_record(record: dict[str, Any], is_sonarr: bool) -> dict[str, Any]:
    """Ein Queue-Eintrag in der Form, die Sensoren und Karte brauchen.

    Die Feldnamen `sizeleft`/`timeleft` sind so falsch geschrieben, wie die
    API sie liefert — das ist Absicht und darf nicht „korrigiert" werden.
    """
    size = float(record.get("size") or 0)
    sizeleft = float(record.get("sizeleft") or 0)
    progress = 0.0
    if size > 0:
        progress = max(0.0, min(100.0, (size - sizeleft) / size * 100))

    parent = record.get("series") if is_sonarr else record.get("movie")
    messages: list[str] = []
    for entry in record.get("statusMessages") or []:
        title = str(entry.get("title") or "").strip()
        for message in entry.get("messages") or []:
            messages.append(f"{title}: {message}".strip(": ").strip())
        if title and not entry.get("messages"):
            messages.append(title)
    if record.get("errorMessage"):
        messages.append(str(record["errorMessage"]))

    return {
        "id": record.get("id"),
        "download_id": record.get("downloadId"),
        "title": record.get("title") or "",
        "parent_title": (parent or {}).get("title"),
        "episode": _episode_label(record) if is_sonarr else None,
        "poster": _poster_url(parent),
        "size": size,
        "sizeleft": sizeleft,
        "timeleft": record.get("timeleft"),
        "progress": round(progress, 1),
        "status": record.get("status"),
        "tracked_status": record.get("trackedDownloadStatus"),
        "tracked_state": record.get("trackedDownloadState"),
        "protocol": record.get("protocol"),
        "indexer": record.get("indexer"),
        "download_client": record.get("downloadClient"),
        "messages": messages,
        # Unbekannte Serien/Filme haben keinen Elterneintrag — genau die sind
        # der häufigste Grund für einen hängenden Import.
        "unknown": parent is None,
        "is_problem": is_import_problem(record),
    }


class _ArrstackCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Gemeinsames Verhalten: Intervall, Fehlerübersetzung, langsamer Takt."""

    config_entry: ArrstackConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ArrstackConfigEntry) -> None:
        """Intervall aus den Optionen; der Name enthält den Dienst."""
        interval = int(_setting(entry, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
        self.service: str = entry.data[CONF_SERVICE]
        self._cycle = 0
        self._slow: dict[str, Any] = {}
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {self.service}",
            update_interval=timedelta(seconds=interval),
        )

    @property
    def _slow_due(self) -> bool:
        """Große Abfragen nur beim ersten und jedem n-ten Durchlauf."""
        return not self._slow or self._cycle % SLOW_REFRESH_EVERY == 0

    async def _async_update_data(self) -> dict[str, Any]:
        """Ein Durchlauf; Auth-Fehler lösen den Reauth-Dialog aus."""
        try:
            data = await self._fetch()
        except ArrstackAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except ArrstackError as err:
            raise UpdateFailed(str(err)) from err
        self._cycle += 1
        return data

    async def _fetch(self) -> dict[str, Any]:
        """Von den Unterklassen gefüllt."""
        raise NotImplementedError


class ArrCoordinator(_ArrstackCoordinator):
    """Sonarr oder Radarr."""

    client: ArrClient

    def __init__(
        self, hass: HomeAssistant, entry: ArrstackConfigEntry, client: ArrClient
    ) -> None:
        """Der Client bringt den Dienst schon mit."""
        super().__init__(hass, entry)
        self.client = client
        self.is_sonarr = client.is_sonarr

    @property
    def major_version(self) -> int:
        """Hauptversion aus `system/status` — 0, solange nichts gelesen wurde.

        Daran hängt, ob `skipRedownload` mitgeschickt werden darf: das Feld
        gibt es erst ab v4.
        """
        version = str((self.data or {}).get("version") or self._slow.get("version") or "")
        head = version.split(".")[0]
        return int(head) if head.isdigit() else 0

    async def _fetch(self) -> dict[str, Any]:
        """Queue in jedem Durchlauf, der teure Rest im langsamen Takt."""
        queue_raw = await self.client.queue()
        records = [
            normalize_queue_record(record, self.is_sonarr)
            for record in (queue_raw.get("records") or [])
        ]

        if self._slow_due:
            status = await self.client.system_status()
            health = await self.client.health()
            diskspace = await self.client.diskspace()
            wanted = await self.client.wanted_missing()
            library = await self.client.library()
            self._slow = {
                "version": status.get("version"),
                "app_name": status.get("appName"),
                "health": [
                    {
                        "type": item.get("type"),
                        "source": item.get("source"),
                        "message": item.get("message"),
                    }
                    for item in health
                ],
                "diskspace": _sum_diskspace(diskspace),
                "wanted": wanted,
                "library_count": len(library),
                # Sonarr kennt keine dienstweite Episodendatei-Liste
                # (`/episodefile` verlangt eine `seriesId`), deshalb kommt
                # „zuletzt hinzugefügt" dort aus der History. Radarr liefert
                # `movieFile.dateAdded` im Bestand gleich mit.
                "recent": self._recent_from_history(
                    await self.client.history_imported()
                )
                if self.is_sonarr
                else self._recent_from(library),
            }

        problems = [record for record in records if record["is_problem"]]
        health_items = self._slow.get("health") or []
        return {
            **self._slow,
            "queue": records,
            "queue_total": int(queue_raw.get("totalRecords") or len(records)),
            "downloading": sum(
                1 for record in records if record["status"] == STATE_DOWNLOADING
            ),
            "import_problems": problems,
            "import_problem_count": len(problems),
            "health_errors": sum(
                1 for item in health_items if item.get("type") == "error"
            ),
            "health_warnings": sum(
                1 for item in health_items if item.get("type") == "warning"
            ),
        }

    def _recent_from(self, library: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Radarr: `movieFile.dateAdded` ist „liegt seit wann da"."""
        if self.is_sonarr:
            return []
        entries = []
        for movie in library:
            movie_file = movie.get("movieFile") or {}
            added = movie_file.get("dateAdded")
            if not added:
                continue
            entries.append(
                {
                    "id": movie.get("id"),
                    "title": movie.get("title"),
                    "subtitle": str(movie.get("year") or ""),
                    "added": added,
                    "poster": _poster_url(movie),
                    "quality": (movie_file.get("quality") or {})
                    .get("quality", {})
                    .get("name"),
                }
            )
        entries.sort(key=lambda item: item["added"], reverse=True)
        return entries[:30]

    def _recent_from_history(
        self, records: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Sonarr: importierte Folgen aus der History (`eventType=3`)."""
        entries = []
        for record in records:
            series = record.get("series") or {}
            entries.append(
                {
                    "id": record.get("id"),
                    "title": series.get("title") or record.get("sourceTitle"),
                    "subtitle": _episode_label(record) or "",
                    "added": record.get("date"),
                    "poster": _poster_url(series),
                    "quality": (record.get("quality") or {})
                    .get("quality", {})
                    .get("name"),
                }
            )
        return entries


def _sum_diskspace(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Alle Laufwerke zusammenzählen — ein Sensor, nicht zwölf.

    Doppelte Pfade (dieselbe Platte über mehrere Mountpunkte) werden über den
    Pfad entdoppelt, sonst zählt derselbe Platz mehrfach.
    """
    seen: dict[str, dict[str, Any]] = {}
    for entry in entries:
        path = str(entry.get("path") or entry.get("label") or "")
        seen.setdefault(path, entry)
    free = sum(float(item.get("freeSpace") or 0) for item in seen.values())
    total = sum(float(item.get("totalSpace") or 0) for item in seen.values())
    return {
        "free": free,
        "total": total,
        "used_percent": round((total - free) / total * 100, 1) if total else None,
        "drives": [
            {
                "path": item.get("path"),
                "label": item.get("label"),
                "free": item.get("freeSpace"),
                "total": item.get("totalSpace"),
            }
            for item in seen.values()
        ],
    }


class SabCoordinator(_ArrstackCoordinator):
    """SABnzbd."""

    client: SabClient

    def __init__(
        self, hass: HomeAssistant, entry: ArrstackConfigEntry, client: SabClient
    ) -> None:
        """Nur Queue und History; beides ist klein genug für jeden Durchlauf."""
        super().__init__(hass, entry)
        self.client = client

    async def _fetch(self) -> dict[str, Any]:
        """Kopfwerte plus Einzelposten für die Karte."""
        queue = await self.client.queue()
        if self._slow_due:
            self._slow = {"version": await self.client.version()}

        slots = [
            {
                "id": slot.get("nzo_id"),
                "title": slot.get("filename") or slot.get("nzbname"),
                "category": slot.get("cat"),
                "status": slot.get("status"),
                "percentage": _to_float(slot.get("percentage")),
                "mb": _to_float(slot.get("mb")),
                "mbleft": _to_float(slot.get("mbleft")),
                "timeleft": slot.get("timeleft"),
                "priority": slot.get("priority"),
            }
            for slot in queue.get("slots") or []
        ]

        return {
            **self._slow,
            "status": queue.get("status"),
            "paused": bool(queue.get("paused")),
            "speed": _to_float(queue.get("kbpersec")) * 1024,
            "sizeleft": _to_float(queue.get("mbleft")) * 1024 * 1024,
            "size": _to_float(queue.get("mb")) * 1024 * 1024,
            "queue_count": int(queue.get("noofslots") or len(slots)),
            "timeleft": queue.get("timeleft"),
            "speedlimit": _to_float(queue.get("speedlimit")),
            "speedlimit_abs": _to_float(queue.get("speedlimit_abs")),
            "diskspace_free": _to_float(queue.get("diskspace1")) * 1024**3,
            "diskspace_total": _to_float(queue.get("diskspacetotal1")) * 1024**3,
            "warnings": int(queue.get("have_warnings") or 0),
            "queue": slots,
        }


def _to_float(value: Any) -> float:
    """SABnzbd liefert Zahlen als Text, teils mit Tausenderpunkt oder leer."""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    try:
        return float(text)
    except ValueError:
        return 0.0


class SeerrCoordinator(_ArrstackCoordinator):
    """Jellyseerr/Seerr."""

    client: SeerrClient

    def __init__(
        self, hass: HomeAssistant, entry: ArrstackConfigEntry, client: SeerrClient
    ) -> None:
        """Die Zähler sind ein einziger, billiger Aufruf."""
        super().__init__(hass, entry)
        self.client = client

    async def _fetch(self) -> dict[str, Any]:
        """`request/count` in jedem Durchlauf, `status` im langsamen Takt."""
        counts = await self.client.request_count()
        if self._slow_due:
            status = await self.client.status()
            self._slow = {"version": status.get("version")}
        return {
            **self._slow,
            **{key: counts.get(key) for key in SEERR_COUNT_KEYS},
            "counts": counts,
        }


def media_status_name(value: Any) -> str:
    """Zahl aus Seerrs Status-Enum in einen lesbaren Namen (D1)."""
    try:
        return SEERR_MEDIA_STATUS.get(int(value), "unknown")
    except (TypeError, ValueError):
        return "unknown"


def build_client(hass: HomeAssistant, entry: ArrstackConfigEntry) -> Any:
    """Passenden Client zur Config-Entry bauen."""
    service = entry.data[CONF_SERVICE]
    url = _setting(entry, CONF_URL, "")
    api_key = _setting(entry, CONF_API_KEY, "")
    verify_ssl = bool(_setting(entry, CONF_VERIFY_SSL, True))

    if service == SERVICE_SABNZBD:
        return SabClient(hass, url, api_key, verify_ssl)
    if service == SERVICE_SEERR:
        return SeerrClient(hass, url, api_key, verify_ssl)
    return ArrClient(hass, url, api_key, service, verify_ssl)


def build_coordinator(
    hass: HomeAssistant, entry: ArrstackConfigEntry, client: Any
) -> _ArrstackCoordinator:
    """Passenden Coordinator zur Config-Entry bauen."""
    service = entry.data[CONF_SERVICE]
    if service == SERVICE_SABNZBD:
        return SabCoordinator(hass, entry, client)
    if service == SERVICE_SEERR:
        return SeerrCoordinator(hass, entry, client)
    return ArrCoordinator(hass, entry, client)


def seerr_poster(path: str | None) -> str | None:
    """`posterPath` von Seerr zu einer vollständigen TMDB-Bildadresse."""
    if not path:
        return None
    return f"{TMDB_IMAGE_BASE}{path}"


def service_is_sonarr(service: str) -> bool:
    """Kleiner Helfer, damit Plattformdateien `const` nicht importieren müssen."""
    return service == SERVICE_SONARR
