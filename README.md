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
