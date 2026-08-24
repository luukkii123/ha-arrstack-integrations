"""Konstanten der arrstack-Integration.

Vier Dienste, eine Domain: Sonarr, Radarr, SABnzbd und Jellyseerr/Seerr werden
je als **eigene Config-Entry** eingerichtet. Kein Dienst setzt einen anderen
voraus — was hier steht, ist deshalb nach Dienst getrennt und nirgends
verschränkt.
"""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "arrstack"

# --- Konfigurationsschlüssel ------------------------------------------------

CONF_SERVICE: Final = "service"
CONF_URL: Final = "url"
CONF_API_KEY: Final = "api_key"
CONF_VERIFY_SSL: Final = "verify_ssl"
CONF_SCAN_INTERVAL: Final = "scan_interval"

# --- Dienste ----------------------------------------------------------------

SERVICE_SONARR: Final = "sonarr"
SERVICE_RADARR: Final = "radarr"
SERVICE_SABNZBD: Final = "sabnzbd"
SERVICE_SEERR: Final = "seerr"

SERVICES: Final = (SERVICE_SONARR, SERVICE_RADARR, SERVICE_SABNZBD, SERVICE_SEERR)

#: Sonarr und Radarr teilen sich die *arr-API (`/api/v3`) und werden überall
#: symmetrisch behandelt — nur die Feld- und Kommandonamen unterscheiden sich.
ARR_SERVICES: Final = (SERVICE_SONARR, SERVICE_RADARR)

SERVICE_LABELS: Final = {
    SERVICE_SONARR: "Sonarr",
    SERVICE_RADARR: "Radarr",
    SERVICE_SABNZBD: "SABnzbd",
    SERVICE_SEERR: "Jellyseerr/Seerr",
}

DEFAULT_PORTS: Final = {
    SERVICE_SONARR: 8989,
    SERVICE_RADARR: 7878,
    SERVICE_SABNZBD: 8080,
    SERVICE_SEERR: 5055,
}

# --- Abfrage ----------------------------------------------------------------

DEFAULT_SCAN_INTERVAL: Final = 60
MIN_SCAN_INTERVAL: Final = 15
MAX_SCAN_INTERVAL: Final = 3600

REQUEST_TIMEOUT: Final = 20

#: Bestand (Serien/Filme), Plattenplatz, Health und Version ändern sich selten,
#: kosten aber die mit Abstand größte Antwort. Sie werden nur bei jedem n-ten
#: Durchlauf geholt; die Queue kommt in jedem.
SLOW_REFRESH_EVERY: Final = 10

QUEUE_PAGE_SIZE: Final = 200
RECENT_PAGE_SIZE: Final = 30

# --- Queue-Zustände der *arr-Apps -------------------------------------------
# `trackedDownloadState` laut API-Vertrag (§5 des Plans). `importBlocked`
# existiert erst ab v4 — v3 meldet stattdessen `importPending` mit
# `trackedDownloadStatus: warning`.

STATE_DOWNLOADING: Final = "downloading"
STATE_IMPORT_PENDING: Final = "importPending"
STATE_IMPORT_BLOCKED: Final = "importBlocked"
STATE_IMPORTING: Final = "importing"
STATE_IMPORTED: Final = "imported"
STATE_FAILED_PENDING: Final = "failedPending"
STATE_FAILED: Final = "failed"
STATE_IGNORED: Final = "ignored"

#: „Heruntergeladen, aber nicht importiert": Der Download ist fertig, aber der
#: Import hängt. Zusätzlich muss `trackedDownloadStatus` warning/error sein —
#: siehe `is_import_problem()` in `coordinator.py`.
IMPORT_PROBLEM_STATES: Final = frozenset(
    {STATE_IMPORT_PENDING, STATE_IMPORT_BLOCKED, STATE_FAILED_PENDING}
)

#: Ablehnungsgründe, bei denen ein automatischer Import **nicht** angeboten
#: wird. Die *arr-Apps liefern 35 `rejections[].reason`-Werte; das hier sind
#: die, bei denen ein blinder Import Schaden anrichtet (falsche Zuordnung,
#: Sample statt Folge, schlechtere Datei über eine bessere). Verglichen wird
#: kleingeschrieben und als Teilzeichenkette, weil die Apps mal den Enum-Namen
#: (`unknownSeries`) und mal einen Satz (`Unknown series`) schicken.
UNSAFE_REJECTION_MARKERS: Final = (
    "unknownseries",
    "unknown series",
    "unknownmovie",
    "unknown movie",
    "unknownartist",
    "sample",
    "notqualityupgrade",
    "not a quality upgrade",
    "quality cutoff",
    "existingfile",
    "existing file",
    "nofileseligible",
    "no files eligible",
    "pathdoesnotexist",
    "path does not exist",
    "unknowndownloadclient",
)

# --- Seerr ------------------------------------------------------------------
# Jellyseerr/Seerr-Enum (D1). Overseerr kennt 6/7 nicht — es wird hier auch
# nicht unterstützt, deshalb keine Fallbacklogik.

SEERR_MEDIA_STATUS: Final = {
    1: "unknown",
    2: "pending",
    3: "processing",
    4: "partially_available",
    5: "available",
    6: "blocklisted",
    7: "deleted",
}

SEERR_STATUS_AVAILABLE: Final = 5

#: Zähler aus `GET /api/v1/request/count`, jeder wird ein Sensor.
SEERR_COUNT_KEYS: Final = (
    "pending",
    "approved",
    "declined",
    "processing",
    "available",
    "failed",
    "completed",
    "total",
)

# --- WebSocket-Kommandos ----------------------------------------------------
# Jedes Kommando trägt `entry_id` (oder `service`), weil mehrere Instanzen
# desselben Dienstes erlaubt sind. Bei genau einer passenden Instanz ist die
# Angabe optional.

WS_INSTANCES: Final = f"{DOMAIN}/instances"
WS_QUEUE: Final = f"{DOMAIN}/queue"
WS_RECENT: Final = f"{DOMAIN}/recent"
WS_HISTORY: Final = f"{DOMAIN}/history"
WS_IMPORT_PROBLEMS: Final = f"{DOMAIN}/import_problems"
WS_MANUAL_IMPORT: Final = f"{DOMAIN}/manual_import"
WS_QUEUE_REMOVE: Final = f"{DOMAIN}/queue_remove"
WS_SEARCH: Final = f"{DOMAIN}/search"
WS_TV_SEASONS: Final = f"{DOMAIN}/tv_seasons"
WS_REQUEST: Final = f"{DOMAIN}/request"
WS_REQUESTS: Final = f"{DOMAIN}/requests"

#: Fehlercodes, die die Karten auswerten (`error.code` aus `hass.callWS`).
ERR_NOT_FOUND: Final = "not_found"
ERR_AMBIGUOUS: Final = "ambiguous_instance"
ERR_UNSUPPORTED: Final = "unsupported_service"
ERR_API: Final = "api_error"
