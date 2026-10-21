# arrstack

Home-Assistant-Integration für **Sonarr**, **Radarr**, **SABnzbd** und
**Jellyseerr/Seerr**. Sie liefert Warteschlangen als Listen (nicht nur als
Zahl), erkennt „heruntergeladen, aber nicht importiert", kann solche Importe
prüfen und anstoßen, und bietet Sensoren, Knöpfe und Aktionen für die
Dienste.

Passende Dashboard-Karten gibt es separat in
[**ha-arrstack-cards**](https://github.com/luukkii123/ha-arrstack-cards); die
Integration funktioniert auch ohne sie.

## Unterstützte Dienste

| Dienst | Hinweise |
| --- | --- |
| Sonarr | API v3 (`/api/v3`) |
| Radarr | API v3 (`/api/v3`) |
| SABnzbd | |
| Jellyseerr/Seerr | Overseerr wird nicht unterstützt |

Jeder Dienst wird als **eigener Eintrag** eingerichtet und läuft für sich;
kein Dienst setzt einen anderen voraus. Mehrere Instanzen desselben Dienstes
sind möglich. Die eingebauten Integrationen `sonarr`, `radarr` und `sabnzbd`
können parallel weiterlaufen, die Entitäten kollidieren nicht.

## Voraussetzungen

- Home Assistant 2024.11.0 oder neuer.
- Erreichbare Adresse des Dienstes (Protokoll, Host, Port; ggf. mit
  URL-Unterpfad) und sein **API-Schlüssel**:
  - Sonarr/Radarr: *Einstellungen → Allgemein → Sicherheit → API-Schlüssel*
  - SABnzbd: *Konfiguration → Allgemein → API-Schlüssel*
  - Jellyseerr: *Einstellungen → Allgemein → API-Schlüssel*

## Installation

1. In HACS *Benutzerdefinierte Repositories* → dieses Repository hinzufügen,
   Kategorie **Integration**.
2. *arrstack* herunterladen und Home Assistant neu starten.

## Einrichtung

*Einstellungen → Geräte & Dienste → Integration hinzufügen → arrstack*.
Zuerst den Dienst wählen (Sonarr, Radarr, SABnzbd, Jellyseerr/Seerr), dann:

| Feld | Vorgabe | Bedeutung |
| --- | --- | --- |
| Adresse (`url`) | `http://localhost:<Standardport>` (Sonarr 8989, Radarr 7878, SABnzbd 8080, Seerr 5055) | Basisadresse des Dienstes mit Protokoll, Host und Port |
| API-Schlüssel (`api_key`) | – | Schlüssel aus den Einstellungen des Dienstes; wird vor dem Anlegen einmal getestet |
| Zertifikat prüfen (`verify_ssl`) | an | prüft das TLS-Zertifikat bei https; nur bei selbst signiertem Zertifikat abschalten |
| Abfrageintervall (`scan_interval`) | 60 | Sekunden zwischen zwei Abfragen, 15 bis 3600 |

Fehlermeldungen: Dienst nicht erreichbar, Schlüssel abgelehnt (401/403) oder
Antwort passt nicht zum Dienst. Dieselbe Adresse lässt sich pro Dienst nur
einmal einrichten.

Der API-Schlüssel wird nur im Config-Entry von Home Assistant gespeichert.

### Optionen

Über **Konfigurieren** am Eintrag lassen sich ändern: neuer API-Schlüssel
(leer lassen behält den bisherigen), Zertifikatsprüfung und Abfrageintervall.

### Erneute Anmeldung

Weist ein Dienst den Schlüssel ab (z. B. nach dem Neuerzeugen), zeigt Home
Assistant beim Eintrag „Erneut anmelden". Dort wird nur der neue Schlüssel
eingegeben und vor dem Speichern geprüft.

## Entitäten

Die Hauptentität jedes Dienstes (`Queue` bei Sonarr/Radarr, `Status` bei
SABnzbd) trägt das Logo des Dienstes (von `brands.home-assistant.io` geladen);
Seerr nutzt `mdi:jellyfish`. Einzellisten (welcher Titel lädt oder hängt) sind
bewusst keine Entitäten, sondern kommen über die Aktionen und WebSocket-
Kommandos.

| Dienst | Sensoren | Binärsensoren | Knöpfe | Sonstige |
| --- | --- | --- | --- | --- |
| Sonarr, Radarr | Warteschlange, Lädt gerade, Importprobleme, Fehlend, Freier Speicher, Version (Diagnose); Sonarr zusätzlich Serien, Radarr zusätzlich Filme | Importproblem, Health, Nicht erreichbar (Diagnose) | Bibliothek neu einlesen, Downloads neu prüfen, Warteschlange aufräumen | – |
| SABnzbd | Tempo, Rest, Warteschlange, Status, Freier Speicher, Version (Diagnose) | Warnungen, Pausiert, Nicht erreichbar (Diagnose) | Anhalten, Fortsetzen | Zahl: Tempolimit (0–100 %) |
| Jellyseerr/Seerr | Anfragen: offen, freigegeben, abgelehnt, in Arbeit, verfügbar, fehlgeschlagen, erledigt, gesamt; Version (Diagnose) | Nicht erreichbar (Diagnose) | – | – |

*Warteschlange aufräumen* entfernt nur endgültig fehlgeschlagene Einträge
(`failed`/`failedPending`) und setzt nichts auf die Blocklist.

Die Queue wird in jedem Durchlauf abgefragt; Bestand, Speicher, Health und
Version nur bei jedem zehnten Durchlauf.

## „Heruntergeladen, aber nicht importiert"

Als Importproblem gilt ein Queue-Eintrag, wenn zugleich gilt: Status
`completed`, `trackedDownloadStatus` ist `warning` oder `error`, und
`trackedDownloadState` ist `importPending`, `importBlocked` oder
`failedPending`. Unbekannte Serien/Filme werden mit abgefragt.

Importe werden nur angeboten, wenn sie unbedenklich sind: Der Download muss
fertig sein (`sizeleft == 0`), die Zuordnung (Serie/Film/Episode) muss
eindeutig aus den Kandidaten des Dienstes stammen und darf keine Ablehnung
enthalten. Es wird nichts anhand von Dateinamen geraten. Vor jedem Import
wird der Zustand frisch geprüft. Ohne ausdrückliche Kandidatenwahl wird nur
importiert, wenn genau ein gültiger Kandidat existiert.

`status: submitted` bedeutet: Der Dienst hat den Importauftrag (Command
`ManualImport`, Ergebnis enthält `command_id`) angenommen, nicht dass der
Import abgeschlossen ist. Gleichzeitige und wiederholte Aufträge für dieselbe
Download-/Dateizuordnung werden gesperrt; bei ungewissem Ausgang
(Verbindungsabbruch, Timeout, 5xx) zuerst den Dienststatus prüfen. Die
Sperren sind flüchtig und entfallen nach einem Neustart von Home Assistant.

## Aktionen

Nur Sonarr und Radarr. Alle liefern mit `response_variable` eine strukturierte
Antwort; ein Aufruf durch einen Benutzer verlangt Administratorrechte,
Automationen dürfen sie ausführen. `entry_id` (Instanz) oder `service`
(`sonarr`/`radarr`) wählt die Instanz; gibt es mehrere passende, muss
`entry_id` angegeben werden.

| Aktion | Felder | Zweck |
| --- | --- | --- |
| `arrstack.refresh_import_queue` | `entry_id`/`service`, optional `queue_item_id` | Warteschlange lesen und abgeschlossene Importprobleme prüfen |
| `arrstack.inspect_import` | `entry_id`/`service`, `queue_item_id` (Pflicht) | Zustand und Kandidaten eines Eintrags prüfen |
| `arrstack.import_item` | `entry_id`/`service`, `queue_item_id` (Pflicht), optional `candidate_id` | einen Eintrag erneut prüfen und importieren |
| `arrstack.import_ready` | `entry_id`/`service` | alle fertigen Einträge mit genau einem gültigen Kandidaten importieren |
| `arrstack.import_selected` | `entry_id`/`service`, `queue_item_ids` (Liste, Pflicht) | ausgewählte Einträge importieren, Ergebnis je Eintrag |

Ergebniszustände je Eintrag: `not_applicable`, `ready`, `no_match`,
`selection_required`, `error`.

```yaml
action: arrstack.import_ready
data:
  entry_id: YOUR_CONFIG_ENTRY_ID
response_variable: import_result
```

Die Instanz-ID liefert das WebSocket-Kommando `arrstack/instances` oder die
Auswahl im Aktionseditor.

## WebSocket-Kommandos (für Karten und eigene Frontends)

Alle laufen serverseitig; Seerr setzt keine CORS-Header, und der API-Schlüssel
gehört nicht in den Browser. Jedes Kommando nimmt `entry_id` oder `service`;
bei mehreren passenden Instanzen antwortet es mit `ambiguous_instance`.
Schreibende Kommandos verlangen Administratorrechte.

| Typ (`arrstack/…`) | Zweck | Dienste |
| --- | --- | --- |
| `instances` | eingerichtete Instanzen | alle |
| `queue` | Warteschlange als Liste | Sonarr, Radarr, SABnzbd |
| `recent` | zuletzt aufgenommen | Sonarr, Radarr |
| `history` | abgeschlossen/fehlgeschlagen | SABnzbd |
| `import_problems` | hängende Importe mit Grund | Sonarr, Radarr |
| `manual_import` | Kandidaten prüfen/importieren | Sonarr, Radarr |
| `queue_remove` | Eintrag entfernen | Sonarr, Radarr |
| `search`, `tv_seasons`, `request`, `requests` | Suche, Staffeln, Anfrage anlegen, bestehende Anfragen | Seerr |
| `refresh_import_queue`, `inspect_import`, `import_item`, `import_ready`, `import_selected` | wie die gleichnamigen Aktionen | Sonarr, Radarr |

Die Queue-Einträge enthalten u. a. Titel, Fortschritt, Status,
Importzustand und optional Episodentitel, Ausstrahlung, Sprachen, Qualität,
Custom Formats mit Wertung, Protokoll, Indexer, Downloadclient, Release-Titel
und Größe.

## Entfernen

Je Dienst gibt es einen eigenen Eintrag:

1. *Einstellungen → Geräte & Dienste → arrstack* → beim Eintrag ⋮ → *Löschen*.
   Gerät, Entitäten und gespeicherter Schlüssel verschwinden.
2. Sind alle Einträge entfernt: in HACS *arrstack* entfernen und Home
   Assistant neu starten.

In Sonarr, Radarr, SABnzbd und Jellyseerr wird nichts geändert; API-Schlüssel
dort bei Bedarf selbst widerrufen. Verlauf und Langzeitstatistiken der
gelöschten Sensoren bleiben, bis der Recorder sie bereinigt.

## English summary

Add the repository to HACS as a custom repository of category **Integration**,
install, restart Home Assistant, then add *arrstack* under Settings → Devices &
Services and pick a service (Sonarr, Radarr, SABnzbd, Jellyseerr/Seerr). Enter
address and API key; every field has its own help text. Each service is a
separate entry. If a key is rejected, Home Assistant asks for a new one
(re-authentication). Remove each entry under Devices & Services, then remove
the integration in HACS. Nothing is changed inside the media services.

## Entwicklung

Tests, Testumgebung und Hintergründe: [docs/entwicklung.md](docs/entwicklung.md).

## Lizenz

MIT, siehe [LICENSE](LICENSE).
