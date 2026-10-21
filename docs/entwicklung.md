# Entwicklung

## Aufbau

- Domain `arrstack`, ein Config-Entry je Dienst (Sonarr, Radarr, SABnzbd,
  Seerr); nirgends setzt ein Dienst einen anderen voraus. Sonarr und Radarr
  teilen sich die *arr-API v3 und werden symmetrisch behandelt.
- Dateien in `custom_components/arrstack/`: `api.py` (Clients je Dienst),
  `coordinator.py` (Abfragen; Queue jeden Durchlauf, Bestand/Health/Speicher
  jeden zehnten), `imports.py` (Importprüfung und -ausführung), `ws.py`
  (WebSocket-Kommandos), `services.py`/`services.yaml` (Aktionen), Plattformen
  `sensor`, `binary_sensor`, `button`, `number`.
- SABnzbd erhält den Schlüssel als Query-Wert `apikey`, nicht als
  `X-Api-Key`-Header.
- Versionsverzweigung: `skipRedownload` erst ab Sonarr/Radarr v4.
- Der Importauftrag läuft über `POST /api/v3/command` mit
  `name: ManualImport`, `files` und `importMode`. `POST /manualimport` prüft nur
  erneut und führt nichts aus; ein HTTP 200 dort ist kein Importauftrag. Die
  API muss eine ganzzahlige Command-ID und `name: ManualImport` bestätigen,
  sonst gibt es kein `submitted`.
- Seerr verlangt bei Serien immer eine Staffelliste. Die Suche kodiert Text
  einmal strikt prozentcodiert (Leerzeichen als `%20`).
- Marken-Logos kommen von `brands.home-assistant.io`; für Jellyseerr gibt es
  dort keins (die Adresse liefert trotzdem HTTP 200 mit Platzhalterbild),
  daher `mdi:jellyfish`.
- Fehlerdetails (`last_error`, `last_error_code`, `last_error_details`)
  enthalten keine Rohantworten, Dateinamen, Adressen oder Zugangsdaten. Pfade
  und Dateinamen gehören nicht in Berichte oder Screenshots.

## Tests

Funktionstest ohne echten Media-Stack gegen einen nachgebauten Server
(Aufruf steht im Kopf der Datei):

```bash
docker run --rm -v "$PWD:/repo:ro" ghcr.io/home-assistant/home-assistant:stable \
    python3 /repo/tests/smoke_test.py
```

Weitere Prüfungen: `tests/import_test.py`, `tests/import_command_test.py`
(HTTP-Vertrag des Importkommandos).

HA-Bibliothekstests (kein laufender HA-Server nötig), siehe auch
`tests_ha/README.md`:

```bash
docker build -f tests_ha/Dockerfile -t integration-tests .
docker run --rm --network none -v "$PWD:/repo" -w /repo integration-tests \
  python -m pytest -c tests_ha/pytest.ini tests_ha \
  --cov=custom_components.arrstack.config_flow --cov-branch --cov-fail-under=100 -q
```

CI testet zwei Home-Assistant-Versionen (siehe `.github/workflows/validate.yml`).
Die 100 %-Grenze gilt nur für den Config-Flow. Bei parallelen Läufen jeder Lauf
eine eigene `.coverage`-Datei verwenden.

`custom_components/arrstack/quality_scale.yaml` führt die Bronze-Regeln mit
Begründungen; das Manifest beansprucht keine Stufe.

## Grenzen

Alle Tests laufen gegen nachgebaute Antworten; ein Lauf gegen echte Dienste
ist nicht Teil der Suite. Native HA-Formulare wurden nicht mit Screenreader
geprüft.
