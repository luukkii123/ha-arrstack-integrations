# arrstack

Eine Home-Assistant-Integration für **Radarr**, **Sonarr**, **SABnzbd** und
**Jellyseerr/Seerr** — mit dem, was die eingebauten Integrationen nicht können:
Stück-Listen statt bloßer Zählwerte, ein Signal für „heruntergeladen, aber
nicht importiert" samt Reparatur, ein Health-Sensor für Sonarr und
Jellyseerr-Unterstützung.

Die passenden Dashboard-Karten liegen in einem eigenen Repository:
[**ha-arrstack-cards**](https://github.com/luukkii123/ha-arrstack-cards).
Beides funktioniert unabhängig voneinander — die Integration braucht die
Karten nicht.

## Jeder Dienst ist optional

Jeder Dienst wird als **eigener Eintrag** hinzugefügt und läuft für sich
allein. Nur Radarr? Geht. Nur SABnzbd? Geht. Radarr und Sonarr ohne Seerr?
Geht auch — dann entfällt schlicht das Anfragen, alles andere bleibt.
Mehrere Instanzen desselben Dienstes sind erlaubt.

Es gibt **keine** Stelle im Code, an der ein Dienst einen anderen voraussetzt.

## Neben den eingebauten Integrationen

`sonarr`, `radarr` und `sabnzbd` von Home Assistant können weiterlaufen. Die
Entitäten kollidieren nicht: arrstack hat eine eigene Domain, und jede
`unique_id` trägt zusätzlich die Id des Eintrags. Doppelte Sensoren sind
gewollt — arrstack liefert das, was dort fehlt:

| | eingebaut | arrstack |
| --- | --- | --- |
| Queue als Zahl | ja | ja |
| Queue als **Liste** mit Fortschritt und Grund | nein | ja |
| „heruntergeladen, aber nicht importiert" | nein | Sensor + Reparatur |
| Health-Sensor für Sonarr | nein | ja |
| Rescan/Refresh/Aufräumen als Knopf | nein | ja |
| Jellyseerr | nein (`overseerr` bricht damit) | ja |
| mehrere Instanzen je Dienst | teils | ja |

## Installation

1. In HACS **Custom Repository** hinzufügen: dieses Repo, Kategorie
   **Integration**.
2. Installieren, Home Assistant neu starten.
3. *Einstellungen → Geräte & Dienste → Integration hinzufügen* → **arrstack**,
   Dienst wählen, Adresse und API-Schlüssel eintragen. Für jeden weiteren
   Dienst noch einmal.

Den API-Schlüssel findest du in Sonarr/Radarr unter *Einstellungen →
Allgemein*, in SABnzbd unter *Konfiguration → Allgemein*, in Jellyseerr unter
*Einstellungen → Allgemein*.

Zugangsdaten stehen nur im Config-Flow — nichts davon liegt in einer Datei
dieses Repositories.

Jedes Feld des Dialogs trägt seinen eigenen Hilfetext (deutsch und englisch, je
nach Spracheinstellung von Home Assistant). Was dort steht, in Kurzform:

| Feld | Standard | Bedeutung |
| --- | --- | --- |
| Adresse | `http://localhost:<Standardport>` | Basisadresse des Dienstes mit Protokoll, Host und Port; der Vorschlag trägt bereits den Standardport |
| API-Schlüssel | — | der Schlüssel aus den Einstellungen des Dienstes selbst; er wird einmal ausprobiert, bevor der Eintrag entsteht |
| Zertifikat prüfen | an | prüft das TLS-Zertifikat bei https-Adressen; nur bei einem selbst signierten Zertifikat abschalten |
| Abfrageintervall | 60 s | Sekunden zwischen zwei Abfragen des Dienstes; erlaubt 15 bis 3600 |

Über **Konfigurieren** lassen sich Schlüssel, Zertifikatsprüfung und Intervall
später ändern; ein leeres Schlüsselfeld behält den bisherigen Schlüssel.

### Wenn der API-Schlüssel nicht mehr gilt

Antwortet ein Dienst mit 401 oder 403 — weil der Schlüssel in Sonarr, Radarr,
SABnzbd oder Jellyseerr neu erzeugt wurde —, startet die Integration die
**erneute Anmeldung**: Home Assistant zeigt beim betroffenen Eintrag „Erneut
anmelden" und öffnet ein einziges Feld für den neuen Schlüssel. Adresse und
Dienst bleiben, wie sie sind; der neue Schlüssel wird gegen den Dienst geprüft,
bevor er den alten ersetzt, und zugleich aus den Optionen entfernt, damit kein
alter Schlüssel aus einem früheren „Konfigurieren" gewinnt.

*English:* add this repository to HACS as a **custom repository** of category
**Integration**, install it, restart Home Assistant, then go to Settings →
Devices & Services → **Add integration** → *arrstack* and pick a service. Every
field carries its own helper text. If a service later rejects its API key, Home
Assistant asks you to sign in again and only the key has to be re-entered.

## Entitäten

**Sonarr und Radarr** (je Eintrag): `queue`, `downloading`, `import_problems`,
`wanted`, `series` bzw. `movies`, `diskspace_free`, `version`;
`binary_sensor` für Importproblem, Health und Erreichbarkeit; Knöpfe für
Bibliothek neu einlesen, Downloads neu prüfen und Warteschlange aufräumen.

**SABnzbd**: Tempo, Rest, Warteschlange, Status, freier Speicher, Version;
`binary_sensor` für Warnungen, Pausiert und Erreichbarkeit; Knöpfe Anhalten
und Fortsetzen; ein Regler für das Tempolimit.

**Jellyseerr/Seerr**: die Zähler aus `request/count` (offen, freigegeben,
abgelehnt, in Arbeit, verfügbar, fehlgeschlagen, erledigt, gesamt) und
Erreichbarkeit.

### Woran man den Dienst erkennt

Ein Eintrag zeigt in Home Assistant immer das Zeichen seiner **Domain** — also
`arrstack` für alle vier. Damit man einer Liste trotzdem ansieht, welcher
Eintrag Radarr ist und welcher Sonarr, trägt **die Hauptentität jedes Dienstes
das echte Logo** (`queue` bei Sonarr/Radarr, `status` bei SABnzbd). Es wird von
`brands.home-assistant.io` geladen — Home Assistants eigener Sammlung — und
liegt nicht in diesem Repo; es sind fremde Marken. Alle übrigen Entitäten
haben ein passendes MDI-Zeichen.

**Für Jellyseerr gibt es dort kein Zeichen.** Die Adresse antwortet mit
HTTP 200 und liefert ein Bild mit der Aufschrift „icon not available" —
nachgemessen: Pixel für Pixel dasselbe wie für einen erfundenen Namen. Seerr
bekommt deshalb `mdi:jellyfish` statt eines geborgten Logos.

Die **Einzellisten** — welcher Titel gerade lädt, welcher feststeckt — sind
bewusst keine Entitäten. Bei ein paar hundert Einträgen wären das hunderte
Entitäten in der Datenbank. Sie kommen über WebSocket-Kommandos.

## WebSocket-Kommandos

Alle Kommandos laufen **serverseitig**. Das ist keine Bequemlichkeit: Seerr
setzt keine CORS-Header, ein Aufruf direkt aus dem Browser würde abgebrochen —
und der API-Schlüssel hätte im Browser ohnehin nichts zu suchen.

| Typ | Zweck | Dienste |
| --- | --- | --- |
| `arrstack/instances` | eingerichtete Instanzen auflisten | alle |
| `arrstack/queue` | Warteschlange als Liste | Sonarr · Radarr · SABnzbd |
| `arrstack/recent` | zuletzt in die Bibliothek aufgenommen | Sonarr · Radarr |
| `arrstack/history` | abgeschlossen und fehlgeschlagen | SABnzbd |
| `arrstack/import_problems` | hängende Importe samt Grund | Sonarr · Radarr |
| `arrstack/manual_import` | Kandidaten prüfen oder importieren | Sonarr · Radarr |
| `arrstack/queue_remove` | Eintrag entfernen | Sonarr · Radarr |
| `arrstack/search` | Titelsuche | Seerr |
| `arrstack/tv_seasons` | Staffeln samt Verfügbarkeit | Seerr |
| `arrstack/request` | Anfrage anlegen | Seerr |
| `arrstack/requests` | bestehende Anfragen | Seerr |

Schreibende Kommandos verlangen Administratorrechte. Jedes Kommando nimmt
`entry_id` oder `service`; gibt es genau eine passende Instanz, darf beides
fehlen. Bei mehreren antwortet es mit `ambiguous_instance`, statt sich eine
auszusuchen.

## „Heruntergeladen, aber nicht importiert"

Der häufigste Fall im Alltag: Der Download ist fertig, die Datei liegt da, aber
die App ordnet sie nicht zu — meist, weil die Serie nicht angelegt ist. Erkannt
wird das an drei Bedingungen **zusammen**: `status == completed`,
`trackedDownloadStatus` ist `warning` oder `error`, und `trackedDownloadState`
ist `importPending`, `importBlocked` oder `failedPending`.

Unbekannte Serien und Filme tauchen nur auf, wenn die Warteschlange mit
`includeUnknownSeriesItems` bzw. `includeUnknownMovieItems` abgefragt wird —
genau das tut diese Integration.

**Der Ein-Klick-Import wird nur angeboten, wenn er ungefährlich ist.** Sobald
eine Datei keiner Serie zugeordnet ist oder die App einen der heiklen Gründe
nennt (`unknownSeries`, `sample`, „existing file better", „not a quality
upgrade", „path does not exist" …), bleibt der Knopf gesperrt und der Grund
steht daneben. Blind zu importieren ordnet Dateien der falschen Serie zu, und
das wieder auseinanderzusortieren ist Handarbeit.

Der Knopf *Warteschlange aufräumen* ist aus demselben Grund eng gefasst: Er
entfernt **nur** endgültig fehlgeschlagene Einträge und blocklistet nichts.

## Abfrage

Standard sind 60 Sekunden, einstellbar zwischen 15 und 3600. Die Warteschlange
wird in jedem Durchlauf geholt; Bestand, Plattenplatz, Health und Version nur
bei jedem zehnten — das sind die großen Antworten und sie ändern sich selten.

## Getestet

- `hassfest` grün.
- Alle Module gegen Home Assistant **2026.8.3** importiert.
- **46 Prüfungen** in `tests/smoke_test.py` gegen einen nachgebauten
  Sonarr-/Radarr-/SABnzbd-/Seerr-Server — Zustandserkennung, Sperren des
  Auto-Imports, Versionsverzweigung (`skipRedownload` erst ab v4), SABnzbds
  Klartextfehler bei falschem Schlüssel, Seerrs Staffelpflicht. Aufruf steht
  oben in der Datei; es braucht dafür keinen echten Media-Stack.

**Was noch aussteht:** ein Lauf in einem echten Home Assistant mit echten
Diensten. Alles oben ist gegen nachgebaute Antworten geprüft, nicht gegen
einen laufenden Radarr.

## Entfernen

**Je Eintrag, nicht je Integration** — vier Dienste bedeuten vier Einträge.

1. Einstellungen → Geräte & Dienste → **arrstack** → beim gewünschten Eintrag
   ⋮ → **Löschen**. Damit endet dessen Abfrage sofort; das Gerät und alle
   seine Entitäten verschwinden, der gespeicherte API-Schlüssel wird mit dem
   Eintrag gelöscht.
2. Sind alle Einträge weg: in HACS **arrstack** → ⋮ → **Entfernen**, danach
   Home Assistant neu starten. Das löscht `custom_components/arrstack`.

**Was zurückbleibt:** nichts von der Integration selbst — keine Datei
außerhalb der Config-Entries. Was im Verlauf (Recorder) und in den
Langzeitstatistiken der gelöschten Sensoren steht, bleibt bis zum nächsten
Aufräumen des Recorders erhalten; wer es sofort los sein will, löscht es unter
*Entwicklerwerkzeuge → Statistiken*. In Sonarr, Radarr, SABnzbd oder
Jellyseerr wird **nichts** geändert: die API-Schlüssel dort bleiben gültig und
müssen bei Bedarf dort widerrufen werden. Dashboard-Karten aus
`ha-arrstack-cards` bleiben liegen und zeigen dann fehlende Entitäten — die
gehören in ein eigenes HACS-Paket und werden hier nicht mitentfernt.

*English:* delete each entry under Settings → Devices & Services (one per
service; this removes its device, entities and stored API key), then remove
*arrstack* in HACS and restart. Recorder history and long-term statistics of
the deleted sensors remain until the recorder purges them. Nothing is changed
inside Sonarr, Radarr, SABnzbd or Jellyseerr — revoke the API keys there
yourself if you want to.

## Lizenz

MIT


## Lokale Qualitätsprüfung – 05.10.2026

HA-Bibliothekstests ohne eigenen HA-Server: Home Assistant 2026.7.0 mit
pytest-homeassistant-custom-component 0.13.344 sowie HA 2026.9.2 mit
0.13.365. `tests_ha/test_config_flow.py` prüft den vollständigen Config-Flow,
Optionen und vorhandene Reauth-/Reconfigure-Schritte, Fehler-Recovery und
Dubletten. Gemessene Zeilen- **und** Zweigabdeckung: **100 %**; der
CI-Befehl erzwingt dies mit `--cov-branch --cov-fail-under=100`.
Die HA-Suite umfasst 25 bestandene Tests je Matrixversion.

Die bestehende isolierte API-/Logikprüfung besteht zusätzlich mit 46 Prüfungen.

Die aktuelle Bronze-Checkliste mit 20 Regeln ist in `quality_scale.yaml`
belegt beziehungsweise mit begründeten Ausnahmen geführt. Das Manifest
beansprucht weiterhin keine Stufe, solange die Auslieferungsabnahme nicht
vorbereitet und abgeschlossen ist.

Dies sind lokale Quellcode- und Bibliotheksnachweise; sie ersetzen keine
Live-Abnahme und behaupten weder Veröffentlichung noch HACS-Installation.
Aufruf und Testumgebung: [`tests_ha`](tests_ha/).

## Import-Actions und kompakte Karten — 0.4.0

Karten und Automationen verwenden dieselbe serverseitige Prüfung. Neue
WebSocket-Kommandos und gleichnamige HA-Actions:

| Action (`arrstack.`) / WS (`arrstack/`) | Parameter / Ergebnis |
| --- | --- |
| `refresh_import_queue` | `entry_id` oder `service`, optional `queue_item_id`; `{service, items}` |
| `inspect_import` | `queue_item_id`; geprüftes Item |
| `import_item` | `queue_item_id`, optional ausdrücklich gewählte `candidate_id`; Item mit `status` |
| `import_ready` | alle Items prüfen; `{service, results}` |
| `import_selected` | `queue_item_ids` als Liste; `{service, results}` je eindeutiger ID |

Bei mehreren passenden Instanzen muss `entry_id` angegeben werden. Actions
liefern mit `response_variable` strukturierte Antworten und sind auch ohne
Antwortvariable aufrufbar. Aufrufe durch Benutzer verlangen Administratorrechte;
Automationen ohne Benutzerkontext dürfen die Actions ausführen.

Items ergänzen die Queuefelder um `queue_item_id`, `download_complete`,
`import_state`, `candidate_count`, `candidates`, `last_checked`, `last_error`.
Zustände sind `not_applicable`, `ready`, `no_match`, `selection_required`,
`error`. Kandidaten enthalten stabile `candidate_id`, `valid`, Dateiname/Pfad,
Größe, Quality, Languages, Release Group, Custom Formats und Ablehnungsgründe.
`candidate_count` zählt nur valide Kandidaten; ungeprüfte aktive Downloads
haben `null`, keine Kandidaten und keinen zusätzlichen Importwarnstatus.

Der Download muss `completed` sein und explizit `sizeleft == 0` liefern;
zusätzlich muss ein bestehendes Importproblem vorliegen. Keine Zuordnung wird
anhand von Dateinamen geraten. Jede Ablehnung, falsche Download-/Serien-/Film-
oder Episodenzuordnung sowie fehlende Ziel-IDs sperrt den Kandidaten.
Ohne ausdrückliche Kandidatenwahl wird nur genau ein valider Kandidat importiert.
Die Queue wird vollständig über alle Seiten gelesen und vor jedem Import
erneut geprüft. Sammelaktionen überspringen unvollständige, leere und
mehrdeutige Items und liefern Ergebnisse einzeln.

`status: submitted` bedeutet: Der Dienst hat den Importauftrag angenommen;
es behauptet keinen bereits abgeschlossenen Dateiimport. Der Coordinator
wird danach aktualisiert. Gleichzeitige und wiederholte Aufträge für dieselbe
Download-/Dateizuordnung werden innerhalb der laufenden Integration gesperrt,
auch wenn mehrere Queuezeilen denselben Download darstellen. Bei einer
bestätigten 4xx-Ablehnung (außer 408) bleibt ein frisch geprüfter erneuter Versuch möglich.
Bei Verbindungsabbruch/Timeout, 5xx/408 oder unlesbarer Antwort ist der Ausgang ungewiss: Die Reservierung
bleibt bis zum Verschwinden des Downloads aus der Queue erhalten. Nach einem
HA-Neustart sind diese flüchtigen Reservierungen nicht mehr vorhanden; deshalb
bei ungewissem Ausgang zuerst den Dienststatus prüfen. Der historische
`manual_import`-Force-Schalter ist gesperrt; explizite Auswahl erfolgt über
`import_item`, ohne die Sicherheitsprüfung zu umgehen.

Automationsbeispiel (IDs aus `arrstack/instances` übernehmen):

```yaml
sequence:
  - action: arrstack.import_ready
    data:
      entry_id: YOUR_CONFIG_ENTRY_ID
    response_variable: import_result
```

Die Seerr-Suche kodiert freien Text einmal mit striktem Percent-Encoding,
einschließlich Leerzeichen als `%20`; ein eingegebenes `%20` bleibt wörtlicher
Text. API-Schlüssel und private Dienstadressen bleiben im Config-Entry.

### Geprüft — 08.10.2026, 0.4.0

Lokale HA-Bibliotheksmatrizen 2026.7.0 und 2026.9.2: jeweils 35 Tests,
ConfigFlow-Zeilen und -Zweige 100 %. Zehn neue Tests prüfen echte HA-Service-
und WebSocket-Registrierung, Antwortdaten, Schemas und Benutzerrechte.
Die 46 bisherigen API-/Logikprüfungen bleiben grün. Zusätzlich prüft
`tests/import_test.py` den tatsächlichen HTTP-Querytext für 13 Sonderzeichenfälle,
20/50/99-Prozent-Downloads, abgeschlossenes Nichtproblem, 0/1/mehrere Kandidaten,
explizite Auswahl, Sonarr/Radarr-Zuordnung, Fehler, frische Revalidierung,
mehrseitige Queue, doppelte IDs/Downloadzeilen, gleichzeitige Aufrufe und
bestätigte Ablehnung gegenüber ungewissem Verbindungsfehler. Der statische
UI-Regelprüfer meldet 0 Verstöße.

Dies sind isolierte HA-/Diensttests, keine Veröffentlichung, Installation oder
produktive Medienänderung. Die Live-Abnahme und Karten-Browserprüfung wird
im gemeinsamen HACS-Abnahmebericht ergänzt; native HA-Formulare wurden hier
nicht per Tastatur/Mobile/Screenreader geprüft.

## Importkorrektur und Tabellenfelder — 0.4.1

Die bisherige Importfunktion nutzte `POST /manualimport`. Das war ein
Vertragsfehler: Sonarr und Radarr prüfen dort eine Zuordnung erneut, führen
aber keinen Dateiimport aus. Ein HTTP-200 dieser Prüfung durfte daher nicht
als angenommener Importauftrag behandelt werden. Einzel-, Auswahl-, Bulk-
und historischer WS-Import benutzen jetzt `POST /api/v3/command` mit
`name: ManualImport`, `files` und `importMode` auf Command-Ebene. Die API muss
eine positive ganzzahlige Command-ID und `name: ManualImport` bestätigen;
fehlgeschlagene, abgebrochene oder unpassende Antworten erzeugen kein
`submitted`. Der akzeptierte Auftrag liefert zusätzlich `command_id`.
Die Dateien übernehmen vorhandenen `releaseType` aus der API; Targets werden
weiterhin ausschließlich frisch aus deren Kandidaten gelesen.

Vertrag anhand der tatsächlich laufenden Versionen geprüft: Sonarr
4.0.20.3014 und Radarr 6.4.4.10685. Öffentliche Originalquellen:
[Sonarr Reprocess-Controller](https://github.com/Sonarr/Sonarr/blob/v4.0.20.3014/src/Sonarr.Api.V3/ManualImport/ManualImportController.cs),
[Sonarr Import-Command](https://github.com/Sonarr/Sonarr/blob/v4.0.20.3014/src/NzbDrone.Core/MediaFiles/EpisodeImport/Manual/ManualImportCommand.cs),
[Radarr Reprocess-Controller](https://github.com/Radarr/Radarr/blob/v6.4.4.10685/src/Radarr.Api.V3/ManualImport/ManualImportController.cs),
[Radarr Import-Command](https://github.com/Radarr/Radarr/blob/v6.4.4.10685/src/NzbDrone.Core/MediaFiles/MovieImport/Manual/ManualImportCommand.cs).

Neue optionale Queuefelder: `episode_title`, `episode_air_date`, `languages`
(Namenliste), `quality` (Name), `custom_formats` (Namenliste),
`custom_format_score` (Zahl) und `output_path`. Nicht gelieferte/ungültige
Werte bleiben `null`; eine tatsächlich gelieferte Formatpunktzahl `0` bleibt
`0`. Vorhandene `messages` enthalten bereits die fachlichen Queuegründe.
Pfadwerte gehören ausschließlich in die private Laufzeitanzeige, niemals
in öffentliche Abnahmeberichte oder Screenshots.

Importfehler liefern `last_error` mit verständlichem nächsten Schritt,
`last_error_code` und kontrollierte `last_error_details` (Phase, gegebenenfalls
Endpoint/HTTP-Status). Die Details übernehmen keine Rohantwort, Dateinamen,
Adressen oder Zugangsdaten des Dienstes. Unbestätigte Command-Antworten und
ungewisse Übermittlungen behalten den vorhandenen Duplikatschutz. Der
Neustart beziehungsweise ein neu aufgebauter Integrationslauf nach dem Update
entfernt die flüchtigen Reservierungen aus 0.4.0, die durch den falschen
Reprocess-Aufruf entstanden sein können. Bei real ungewissem Auftrag zuerst
im Dienst prüfen; `submitted` bestätigt weiterhin keinen abgeschlossenen
Dateiimport.

### Geprüft — 08.10.2026, 0.4.1

`tests/import_command_test.py` wurde vor der Korrektur gegen einen lokalen
HTTP-Server rot: Er beobachtete `/manualimport` statt des vorgeschriebenen
`/command`. Jetzt bestehen beide Dienstverträge samt echten Client-/Manager-
Aufrufen, Command-Payload, akzeptierter ID, unpassenden Antworten und sieben
optionalen Feldern einschließlich fehlender und strukturwidriger Werte.
Die alten Smoke-Fixtures wurden von der falschen Importannahme auf den
Command-Vertrag korrigiert. In beiden HA-Testimages sind HTTP-Vertrag und
Sicherheitsregressionen grün. Die komplette HA-Suite besteht jeweils mit
35 Tests und 100 % ConfigFlow-Zeilen-/Zweigabdeckung, die Smoke-Suite auf
HA 2026.9.2 mit 46 Prüfungen. Ein paralleler Coverage-Lauf kollidierte zunächst
auf derselben lokalen `.coverage`-Datei; der Wiederholungslauf mit isolierter
Coverage-Datei bestand. Dies war ein Prüfwerkzeugfehler, kein bestandener
Abnahmelauf.

Die Live-Diagnose nutzte ausschließlich lesende Queue-/Kandidatenaufrufe.
Der frühere genaue HTTP-Fehlercode ist nicht belegt. Kein produktiver Import
wurde zum Test ausgelöst; Veröffentlichung, Installation und anschließende
Live-Abnahme erfolgen getrennt durch die gemeinsame HACS-Sitzung.
