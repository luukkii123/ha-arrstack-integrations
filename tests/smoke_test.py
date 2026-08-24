#!/usr/bin/env python3
"""Funktionstest gegen einen nachgebauten Sonarr/Radarr/SABnzbd/Seerr-Server.

Kein echter Media-Stack nötig und keine Zugangsdaten: Das Skript startet einen
kleinen aiohttp-Server auf `127.0.0.1`, der die Antworten liefert, die im Plan
als Datenvertrag festgehalten sind — samt der Fälle, um die es wirklich geht
(`trackedDownloadState`, `rejections`, Seerrs Staffelpflicht, SABnzbds
Klartextfehler bei falschem Schlüssel).

Ausführen (Home Assistant muss importierbar sein, deshalb im Container):

    docker run --rm -v "$PWD:/repo:ro" ghcr.io/home-assistant/home-assistant:stable \\
        python3 /repo/tests/smoke_test.py

Ausgabe: eine Zeile je Prüfung, am Ende die Zahl der bestandenen Prüfungen.
Ein fehlgeschlagenes `assert` beendet das Skript mit Rückgabewert 1.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

from aiohttp import ClientSession, web

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components"))

from arrstack import api as api_module  # noqa: E402
from arrstack.api import (  # noqa: E402
    ArrClient,
    ArrstackAuthError,
    SabClient,
    SeerrClient,
    normalize_url,
)
from arrstack.coordinator import (  # noqa: E402
    _sum_diskspace,
    classify_candidates,
    is_import_problem,
    media_status_name,
    normalize_queue_record,
    seerr_poster,
)
from arrstack.ws import _import_payload  # noqa: E402

API_KEY = "test-key"
PASSED = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    """Eine Prüfung protokollieren und bei Fehlschlag hart abbrechen."""
    global PASSED
    if not condition:
        print(f"FEHLGESCHLAGEN: {label} {detail}")
        raise SystemExit(1)
    PASSED += 1
    print(f"ok   {label}{(' — ' + detail) if detail else ''}")


# --- Nachgebaute Antworten --------------------------------------------------

SONARR_QUEUE = {
    "page": 1,
    "totalRecords": 3,
    "records": [
        {
            "id": 1,
            "title": "Serie.A.S01E01.1080p",
            "series": {
                "id": 10,
                "title": "Serie A",
                "images": [{"coverType": "poster", "remoteUrl": "https://x/p1.jpg"}],
            },
            "episode": {"seasonNumber": 1, "episodeNumber": 1},
            "size": 1000.0,
            "sizeleft": 250.0,
            "timeleft": "00:12:30",
            "status": "downloading",
            "trackedDownloadStatus": "ok",
            "trackedDownloadState": "downloading",
            "downloadId": "abc",
            "protocol": "usenet",
        },
        {
            # Der Fall, um den es geht: fertig geladen, aber nicht importiert,
            # und die Serie kennt Sonarr gar nicht (kein `series`-Objekt).
            "id": 2,
            "title": "Unbekannte.Serie.S02E05.1080p",
            "size": 2000.0,
            "sizeleft": 0.0,
            "timeleft": None,
            "status": "completed",
            "trackedDownloadStatus": "warning",
            "trackedDownloadState": "importPending",
            "downloadId": "def",
            "statusMessages": [
                {"title": "Unbekannte.Serie.S02E05.1080p", "messages": ["Unknown series"]}
            ],
        },
        {
            "id": 3,
            "title": "Serie.C.S01E02",
            "series": {"id": 12, "title": "Serie C", "images": []},
            "size": 500.0,
            "sizeleft": 0.0,
            "status": "completed",
            "trackedDownloadStatus": "ok",
            "trackedDownloadState": "imported",
            "downloadId": "ghi",
        },
    ],
}

SONARR_CANDIDATES_UNSAFE = [
    {
        "path": "/downloads/Unbekannte.Serie.S02E05.1080p.mkv",
        "folderName": "Unbekannte.Serie.S02E05.1080p",
        "name": "Unbekannte.Serie.S02E05",
        "size": 2000,
        "quality": {"quality": {"name": "WEBDL-1080p"}},
        "languages": [{"id": 1, "name": "English"}],
        "rejections": [{"reason": "unknownSeries", "type": "permanent"}],
        "episodes": [],
    }
]

SONARR_CANDIDATES_SAFE = [
    {
        "path": "/downloads/Serie.A.S01E03.mkv",
        "folderName": "Serie.A.S01E03",
        "series": {"id": 10, "title": "Serie A"},
        "episodes": [{"id": 501, "seasonNumber": 1, "episodeNumber": 3}],
        "quality": {"quality": {"name": "WEBDL-1080p"}},
        "languages": [{"id": 1, "name": "English"}],
        "releaseGroup": "GRP",
        "downloadId": "jkl",
        "indexerFlags": 0,
        "rejections": [],
    }
]

RADARR_LIBRARY = [
    {
        "id": 1,
        "title": "Film Alt",
        "year": 2001,
        "images": [{"coverType": "poster", "remoteUrl": "https://x/m1.jpg"}],
        "movieFile": {
            "dateAdded": "2026-01-01T10:00:00Z",
            "quality": {"quality": {"name": "Bluray-1080p"}},
        },
    },
    {
        "id": 2,
        "title": "Film Neu",
        "year": 2026,
        "images": [],
        "movieFile": {"dateAdded": "2026-08-20T10:00:00Z", "quality": {}},
    },
    {"id": 3, "title": "Film ohne Datei", "year": 2020, "images": []},
]

SEERR_TV = {
    "id": 1399,
    "name": "Beispielserie",
    "posterPath": "/poster.jpg",
    "seasons": [
        {"seasonNumber": 0, "name": "Specials", "episodeCount": 3},
        {"seasonNumber": 1, "name": "Staffel 1", "episodeCount": 10},
        {"seasonNumber": 2, "name": "Staffel 2", "episodeCount": 10},
    ],
    "mediaInfo": {"status": 4, "seasons": [{"seasonNumber": 1, "status": 5}]},
}


def build_app() -> web.Application:
    """Die vier Dienste auf einem Server; der Pfad entscheidet, wer antwortet."""
    app = web.Application()
    seen: dict[str, Any] = {}
    app["seen"] = seen

    def require_key(request: web.Request) -> None:
        if request.headers.get("X-Api-Key") != API_KEY:
            raise web.HTTPUnauthorized(text="bad key")

    async def sonarr_status(request: web.Request) -> web.Response:
        require_key(request)
        return web.json_response({"version": "4.0.10.2544", "appName": "Sonarr"})

    async def sonarr_queue(request: web.Request) -> web.Response:
        require_key(request)
        seen["queue_query"] = dict(request.query)
        return web.json_response(SONARR_QUEUE)

    async def sonarr_manualimport(request: web.Request) -> web.Response:
        require_key(request)
        if request.method == "POST":
            seen["import_payload"] = await request.json()
            return web.json_response([])
        seen["manualimport_query"] = dict(request.query)
        download_id = request.query.get("downloadId")
        return web.json_response(
            SONARR_CANDIDATES_SAFE if download_id == "jkl" else SONARR_CANDIDATES_UNSAFE
        )

    async def queue_delete(request: web.Request) -> web.Response:
        require_key(request)
        seen["delete_query"] = dict(request.query)
        seen["delete_id"] = request.match_info["item_id"]
        return web.json_response({})

    async def radarr_movies(request: web.Request) -> web.Response:
        require_key(request)
        return web.json_response(RADARR_LIBRARY)

    async def diskspace(request: web.Request) -> web.Response:
        require_key(request)
        return web.json_response(
            [
                {"path": "/data", "freeSpace": 100, "totalSpace": 400},
                {"path": "/data", "freeSpace": 100, "totalSpace": 400},
                {"path": "/other", "freeSpace": 50, "totalSpace": 100},
            ]
        )

    async def sab(request: web.Request) -> web.Response:
        mode = request.query.get("mode")
        if request.query.get("apikey") != API_KEY:
            # Genau so antwortet SABnzbd: HTTP 200 mit einem Fehlertext.
            return web.json_response({"status": False, "error": "API Key Incorrect"})
        if mode == "version":
            return web.json_response({"version": "4.3.1"})
        if mode == "queue":
            return web.json_response(
                {
                    "queue": {
                        "status": "Downloading",
                        "paused": False,
                        "kbpersec": "5120.5",
                        "mb": "2048.0",
                        "mbleft": "512.0",
                        "noofslots": 2,
                        "timeleft": "0:03:20",
                        "speedlimit": "80",
                        "speedlimit_abs": "8192000",
                        "diskspace1": "1024.5",
                        "diskspacetotal1": "4096.0",
                        "have_warnings": "1",
                        "slots": [
                            {
                                "nzo_id": "SABnzbd_nzo_1",
                                "filename": "Datei eins",
                                "cat": "tv",
                                "status": "Downloading",
                                "percentage": "75",
                                "mb": "1024.0",
                                "mbleft": "256.0",
                                "timeleft": "0:01:40",
                            }
                        ],
                    }
                }
            )
        if mode == "config":
            seen["sab_config"] = dict(request.query)
            return web.json_response({"status": True})
        return web.json_response({"status": True})

    async def seerr_count(request: web.Request) -> web.Response:
        require_key(request)
        return web.json_response(
            {"pending": 2, "approved": 5, "available": 3, "total": 10}
        )

    async def seerr_tv(request: web.Request) -> web.Response:
        require_key(request)
        return web.json_response(SEERR_TV)

    async def seerr_request(request: web.Request) -> web.Response:
        require_key(request)
        payload = await request.json()
        seen["request_payload"] = payload
        if payload.get("mediaType") == "tv" and "seasons" not in payload:
            # Seerrs echtes Verhalten: fehlende Staffeln → 500.
            return web.json_response({"message": "seasons required"}, status=500)
        return web.json_response({"id": 77, "status": 2, "media": {"status": 3}})

    app.add_routes(
        [
            web.get("/api/v3/system/status", sonarr_status),
            web.get("/api/v3/queue", sonarr_queue),
            web.get("/api/v3/manualimport", sonarr_manualimport),
            web.post("/api/v3/manualimport", sonarr_manualimport),
            web.delete("/api/v3/queue/{item_id}", queue_delete),
            web.get("/api/v3/movie", radarr_movies),
            web.get("/api/v3/diskspace", diskspace),
            web.get("/api", sab),
            web.get("/api/v1/request/count", seerr_count),
            web.get("/api/v1/tv/{tmdb_id}", seerr_tv),
            web.post("/api/v1/request", seerr_request),
        ]
    )
    return app


def make_client(cls, session: ClientSession, base: str, *args: Any):
    """Client bauen, ohne ein echtes `hass` zu brauchen.

    `async_get_clientsession` wird für die Dauer des Tests durch die Sitzung
    des Tests ersetzt — geprüft wird dadurch derselbe Code, den HA auch nutzt.
    """
    original = api_module.async_get_clientsession
    api_module.async_get_clientsession = lambda hass, verify=True: session
    try:
        return cls(None, base, *args)
    finally:
        api_module.async_get_clientsession = original


async def main() -> None:
    """Alle Prüfungen; jede belegt eine Aussage aus dem Plan."""
    # --- reine Funktionen, ohne Server ------------------------------------
    check(
        "normalize_url hängt fehlendes Schema an",
        normalize_url("host:8989/sonarr/") == "http://host:8989/sonarr",
        normalize_url("host:8989/sonarr/"),
    )
    check(
        "is_import_problem: fertig + Warnung + importPending",
        is_import_problem(SONARR_QUEUE["records"][1]) is True,
    )
    check(
        "is_import_problem: laufender Download ist kein Problem",
        is_import_problem(SONARR_QUEUE["records"][0]) is False,
    )
    check(
        "is_import_problem: sauber importiert ist kein Problem",
        is_import_problem(SONARR_QUEUE["records"][2]) is False,
    )

    record = normalize_queue_record(SONARR_QUEUE["records"][0], True)
    check(
        "Fortschritt aus size/sizeleft",
        record["progress"] == 75.0,
        f"{record['progress']} %",
    )
    check("Episodenkürzel", record["episode"] == "S01E01", record["episode"])
    check("Poster aus images[]", record["poster"] == "https://x/p1.jpg")

    unknown = normalize_queue_record(SONARR_QUEUE["records"][1], True)
    check("unbekannte Serie erkannt", unknown["unknown"] is True)
    check(
        "Grund aus statusMessages übernommen",
        unknown["messages"] == ["Unbekannte.Serie.S02E05.1080p: Unknown series"],
        str(unknown["messages"]),
    )

    verdict_unsafe = classify_candidates(SONARR_CANDIDATES_UNSAFE)
    check(
        "unknownSeries verbietet Auto-Import",
        verdict_unsafe["can_auto_import"] is False,
        str(verdict_unsafe["reasons"]),
    )
    verdict_safe = classify_candidates(SONARR_CANDIDATES_SAFE)
    check(
        "sauberer Kandidat erlaubt Auto-Import",
        verdict_safe["can_auto_import"] is True,
    )
    check(
        "leere Kandidatenliste erlaubt keinen Import",
        classify_candidates([])["can_auto_import"] is False,
    )

    payload = _import_payload(SONARR_CANDIDATES_SAFE, True, "jkl")
    check("Import-Nutzlast: eine Datei", len(payload) == 1)
    check("Import-Nutzlast: seriesId gesetzt", payload[0]["seriesId"] == 10)
    check("Import-Nutzlast: episodeIds gesetzt", payload[0]["episodeIds"] == [501])
    check(
        "Import-Nutzlast: unzuordenbare Datei fällt raus",
        _import_payload(SONARR_CANDIDATES_UNSAFE, True, "def") == [],
    )

    disks = _sum_diskspace(
        [
            {"path": "/data", "freeSpace": 100, "totalSpace": 400},
            {"path": "/data", "freeSpace": 100, "totalSpace": 400},
            {"path": "/other", "freeSpace": 50, "totalSpace": 100},
        ]
    )
    check(
        "doppelte Laufwerke zählen einmal",
        disks["free"] == 150 and disks["total"] == 500,
        f"{disks['free']} von {disks['total']}",
    )

    check("Seerr-Enum 6 = blocklisted", media_status_name(6) == "blocklisted")
    check("Seerr-Enum 7 = deleted", media_status_name(7) == "deleted")
    check("Seerr-Enum unbekannt bleibt unknown", media_status_name(None) == "unknown")
    check(
        "Poster-Adresse wird vervollständigt",
        seerr_poster("/p.jpg") == "https://image.tmdb.org/t/p/w300/p.jpg",
    )

    # --- gegen den nachgebauten Server ------------------------------------
    runner = web.AppRunner(build_app())
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = runner.addresses[0][1]
    base = f"http://127.0.0.1:{port}"
    seen = runner.app["seen"]

    async with ClientSession() as session:
        sonarr = make_client(ArrClient, session, base, API_KEY, "sonarr")
        radarr = make_client(ArrClient, session, base, API_KEY, "radarr")
        sab = make_client(SabClient, session, base, API_KEY)
        sab_bad = make_client(SabClient, session, base, "falsch")
        seerr = make_client(SeerrClient, session, base, API_KEY)
        sonarr_bad = make_client(ArrClient, session, base, "falsch", "sonarr")

        status = await sonarr.system_status()
        check("system/status liefert Version", status["version"].startswith("4."))

        await sonarr.queue()
        check(
            "Queue fragt unbekannte Serien mit ab",
            seen["queue_query"].get("includeUnknownSeriesItems") == "true",
            str(seen["queue_query"]),
        )
        await radarr.queue()
        check(
            "Radarr fragt unbekannte Filme mit ab",
            seen["queue_query"].get("includeUnknownMovieItems") == "true",
        )

        await sonarr.manual_import_candidates("def")
        check(
            "Kandidaten ohne Vorfilterung geholt",
            seen["manualimport_query"].get("filterExistingFiles") == "false",
        )
        await sonarr.manual_import(payload, "auto")
        check(
            "importMode geht mit",
            seen["import_payload"][0]["importMode"] == "auto",
        )

        await sonarr.queue_delete(2, remove_from_client=True, blocklist=False)
        check(
            "Löschen ohne skipRedownload (v3-tauglich)",
            "skipRedownload" not in seen["delete_query"],
            str(seen["delete_query"]),
        )
        await sonarr.queue_delete(2, skip_redownload=False)
        check(
            "Löschen mit skipRedownload, wenn v4",
            seen["delete_query"].get("skipRedownload") == "false",
        )

        try:
            await sonarr_bad.system_status()
        except ArrstackAuthError:
            check("falscher *arr-Schlüssel wird als Auth-Fehler erkannt", True)
        else:
            check("falscher *arr-Schlüssel wird als Auth-Fehler erkannt", False)

        check("SABnzbd-Version gelesen", await sab.version() == "4.3.1")
        queue = await sab.queue()
        check("SABnzbd-Queue hat Einträge", len(queue["slots"]) == 1)
        await sab.set_speedlimit(50)
        check(
            "Tempolimit wird als config-Aufruf gesetzt",
            seen["sab_config"].get("name") == "speedlimit"
            and seen["sab_config"].get("value") == "50",
            str(seen["sab_config"]),
        )
        try:
            await sab_bad.version()
        except ArrstackAuthError:
            check("SABnzbds Klartextfehler wird als Auth-Fehler erkannt", True)
        else:
            check("SABnzbds Klartextfehler wird als Auth-Fehler erkannt", False)

        counts = await seerr.request_count()
        check("Seerr-Zähler gelesen", counts["pending"] == 2)
        show = await seerr.tv(1399)
        check("Seerr-Serie hat drei Staffeln", len(show["seasons"]) == 3)

        result = await seerr.create_request(media_type="tv", media_id=1399, seasons=[2])
        check("Seerr-Request angelegt", result["id"] == 77)
        check(
            "Staffeln gehen bei TV zwingend mit",
            seen["request_payload"].get("seasons") == [2],
            str(seen["request_payload"]),
        )
        await seerr.create_request(media_type="tv", media_id=1399, seasons=None)
        check(
            "ohne Angabe wird 'all' geschickt, nie gar nichts",
            seen["request_payload"].get("seasons") == "all",
        )
        await seerr.create_request(media_type="movie", media_id=42)
        check(
            "bei Filmen bleibt seasons weg",
            "seasons" not in seen["request_payload"],
        )

    await runner.cleanup()
    print(f"\n{PASSED} Prüfungen bestanden.")


if __name__ == "__main__":
    asyncio.run(main())
