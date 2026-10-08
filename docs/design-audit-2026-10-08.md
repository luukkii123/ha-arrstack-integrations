# Design-Audit vom 08.10.2026 — ha-arrstack-integrations

Kanonische Quelle: `/mnt/user/Data/Claude Projekte/DESIGN_GUIDELINES.md`.
Umfang: Agent-Einstieg, fachliche Benennung und statische Quellenprüfung. Keine App-Codeänderung, kein Deploy und kein Upload.

## Plattform und Nachweise

Home-Assistant-Integration; sichtbare Config-/Options-/Reauth-Formulare rendert HA. Keine eigenständige PWA.

Lesereihenfolge: gemeinsame `AGENTS.md` und `CLAUDE.md`, zentrale Richtlinien, Audit-/Glossarvorlage und Todo-Regel; lokale `AGENTS.md`/`CLAUDE.md`; lokale AGENTS.md → HACS AGENTS/CLAUDE und docs/ui-regeln.md; gezielte README-/Flow-/Übersetzungsquellen.

Tatsächlich: `git status`, Dateibestand mit `rg --files`, gezielte `rg -n`-/Quelltextprüfung, Todoabruf/-Übernahme und Dokumentenprüfung. Kein Browser gestartet, keine echten Viewports (360/390 px, Tablet, Desktop) geprüft, keine echte Keyboard-/Escape-/Back-/Forward-Prüfung, keine PWA-Installation oder Offline-Geräteprobe, kein Screenreader, keine Kontrast-/Zoom-/Touchmessung, keine Web-Vitals-Feldmessung. Vorhandene Tests/ältere Abnahmen sind Quellenhinweise und wurden hier nicht erneut ausgeführt. `teilweise` meint belegte Teilstruktur; es bedeutet keine bestandene Laufzeitabnahme.

### Quellen

- **E01**: `custom_components/arrstack/config_flow.py`: ConfigFlow, OptionsFlow, Fehler-/Formzweige und Unique ID.
- **E02**: `custom_components/arrstack/strings.json`, `translations/de.json`, `translations/en.json`: Feldlabel/-erklärung und Fehler; `manifest.json`/`quality_scale.yaml`.
- **E03**: `custom_components/arrstack/` und README.md: Integrationsbestand; eigene Browseroberfläche nicht implementiert, Formrendering gehört zu Home Assistant.
- **E04**: `../scripts/ui-regeln-pruefen.py`: tatsächlich von HACS-Wurzel ausgeführt, dieses Unterrepo 0 statische Verstöße, Exit 0; deckt die globale Laufzeitmatrix nicht ab.

## Alle 26 Regeln

| Regel | Status | Beleg, Anwendbarkeit und nächste Prüfung |
| --- | --- | --- |
| R01 · Konsistenz | teilweise | E01/E02: ein Config-/OptionsFlow, deutsche und englische Übersetzung; Labels fachlich vergleichen. |
| R02 · Mehrfachauswahl | nicht anwendbar | Keine eigene Liste mit fachlicher Sammelaktion; HA-Entitäts-/Konfigurationsverwaltung gehört zum Host. Bei zukünftiger eigener Liste erneut prüfen. |
| R03 · Keyboard | ungeprüft | E01/E02/E03: Home-Assistant-Formoberfläche und fachliche Wirkung dieser Integration real prüfen; Quellstruktur allein genügt nicht. |
| R04 · Modale Dialoge | ungeprüft | E01/E02/E03: Home-Assistant-Formoberfläche und fachliche Wirkung dieser Integration real prüfen; Quellstruktur allein genügt nicht. |
| R05 · Navigation | ungeprüft | E01/E02/E03: Home-Assistant-Formoberfläche und fachliche Wirkung dieser Integration real prüfen; Quellstruktur allein genügt nicht. |
| R06 · Responsive Mobile | ungeprüft | E01/E02/E03: Home-Assistant-Formoberfläche und fachliche Wirkung dieser Integration real prüfen; Quellstruktur allein genügt nicht. |
| R07 · PWA | nicht anwendbar | Integration hat keine eigene Webapp/PWA; Installation/Manifest/Offline gehören zu Home Assistant. Integration muss eigene Datenverfügbarkeit ehrlich melden. |
| R08 · Wiederverwendung | teilweise | E01: zentrale Flows/Validierung und Hostformular; Reconfigure/Reauth/Optionspfade fachlich vergleichen. |
| R09 · Designsystem | teilweise | E02/E03: Hostschema statt eigenem Designsystem; keine neue Markenoberfläche. Host-Rendering nicht aktuell geprüft. |
| R10 · Formulare | teilweise | E01/E02/E04: Schema/Fehler und alle geprüften Feldbeschreibungen; Datenerhalt/Keyboard real prüfen. |
| R11 · Feedback | teilweise | E01: asynchrone Verbindungsprüfung und Fehlerzweige; echter langsamer Host-/Dienstfall ungeprüft. |
| R12 · Fehlerbehebung | teilweise | E01/E02: Fehlerkeys und lokalisierte Meldungen; reale Auth-/Timeout-/Datenfehler mit nächster Aktion prüfen. |
| R13 · Destruktive Aktionen | ungeprüft | E01/E02/E03: Home-Assistant-Formoberfläche und fachliche Wirkung dieser Integration real prüfen; Quellstruktur allein genügt nicht. |
| R14 · Große Datenmengen | ungeprüft | E01/E02/E03: Home-Assistant-Formoberfläche und fachliche Wirkung dieser Integration real prüfen; Quellstruktur allein genügt nicht. |
| R15 · Drag&Drop | nicht anwendbar | Kein eigener Drag&Drop-Pfad im Integrationsbestand E03. |
| R16 · Accessibility | ungeprüft | E01/E02/E03: Home-Assistant-Formoberfläche und fachliche Wirkung dieser Integration real prüfen; Quellstruktur allein genügt nicht. |
| R17 · Interaktionszustände | teilweise | E01/E02: Formularfehler/Hostzustände statisch vorhanden; Disabled/Busy/Fokus nicht real geprüft. |
| R18 · Ansichtszustände | teilweise | E01/E03: API-/Coordinator-Datenverfügbarkeit und Hostfehler; reale offline/forbidden/partial-Fälle ungeprüft. |
| R19 · Berechtigungen | nicht anwendbar | Keine Browser-Kamera-/Mikrofon-/Push-/Standortberechtigung in E01–E03; konfigurierte Datenquellen/Tracker sind keine browserseitige Geolocation-Anfrage. |
| R20 · Performance | ungeprüft | E01/E02/E03: Home-Assistant-Formoberfläche und fachliche Wirkung dieser Integration real prüfen; Quellstruktur allein genügt nicht. |
| R21 · UI-Präferenzen | ungeprüft | E01/E02/E03: Home-Assistant-Formoberfläche und fachliche Wirkung dieser Integration real prüfen; Quellstruktur allein genügt nicht. |
| R22 · Auffindbarkeit | ungeprüft | E01/E02/E03: Home-Assistant-Formoberfläche und fachliche Wirkung dieser Integration real prüfen; Quellstruktur allein genügt nicht. |
| R23 · Responsive Komponenten | ungeprüft | E01/E02/E03: Home-Assistant-Formoberfläche und fachliche Wirkung dieser Integration real prüfen; Quellstruktur allein genügt nicht. |
| R24 · Ausnahmen | teilweise | R07/R15/R19 fachlich begrenzte Nichtanwendbarkeit oben; Risiko falscher HA-Hostdelegation, Ersatz: reale Config-/Options-/Reauth- und Verfügbarkeitsprüfung. Kein pauschales Backend-Bestehen. |
| R25 · Menüs/Settings | ungeprüft | E01/E02/E03: Home-Assistant-Formoberfläche und fachliche Wirkung dieser Integration real prüfen; Quellstruktur allein genügt nicht. |
| R26 · Sprache/Fachvokabular | teilweise | E02/E04: deutsche Texte und englische Variante vorhanden; Fachbegriffe in design-glossar.md. Komplette Laufzeitanzeige ungeprüft. |

## Ausnahmen und Folgearbeit

Kein Integrationstest, keine HA-Hostprüfung und kein Schaltversuch ausgeführt. R03/R04/R05/R06/R16 bleiben für Hostdialoge ungeprüft, auch wenn Code an HA delegiert. Die historische Bronze-/Liveabnahme wird hier nicht als aktuelle Designabnahme verwendet. Weiterarbeit über HACS-Audit #139.

## Backend-Nachprüfung — Todos #181/#182, Version 0.4.0

Änderungen: HTTP-Query-Encoding, zentraler ImportManager, HA-Actions und
WS-Kommandos, zweisprachige Action-Feldbeschreibungen. Keine eigene
Browseroberfläche implementiert. Die vorhandenen Host-Formulare bleiben
unter ihrer bisherigen Laufzeitgrenze; keine Tastatur-/Mobile-Abnahme behauptet.

Tatsächlich ausgeführt am 08.10.2026:

- Beide vorhandenen HA-Testimages `hacs-bronze-tests:2026.7.0` und
  `hacs-bronze-tests:2026.9.2`: komplette `tests_ha`-Suite, je 35 bestanden;
  ConfigFlow-Zeilen-/Zweigabdeckung 100 %.
- Zehn neue HA-Tests in `tests_ha/test_import_actions.py`: echte
  ServiceRegistry-/WebSocket-Aufrufe, optionale strukturierte Antworten,
  Schemafehler und Admin-/Nichtadmin-Zugriff. Externe Dienste dabei isoliert.
- `tests/import_test.py` gegen lokalen HTTP-Server und Dienstfixtures in
  beiden Images grün: 13 Encodingfälle, komplette/aktive Downloads, Kandidaten
  0/1/mehrere, explizite Auswahl, falsche Zuordnung, Sonarr und Radarr,
  Fehler pro Item, Retry/Timeout, stale candidate, vollständige Pagination,
  doppelte Downloadzeilen und gleichzeitig ausgelöste Importaufträge.
- Bisherige `tests/smoke_test.py`: 46 bestandene Prüfungen auf HA 2026.9.2.
- `python3 ../scripts/ui-regeln-pruefen.py --repo ha-arrstack-integrations`:
  0 Verstöße. Quell-/Schema-Check, keine native Browserprüfung.

| Regel | Status dieses Eingriffs | Konkreter Beleg / Grenze |
| --- | --- | --- |
| R01 | erfüllt für Backend | Cards/Actions benutzen `execute_import_action` und denselben ImportManager; Service-/WS-Antworttests. Native Labels nicht visuell geprüft. |
| R02 | erfüllt für Backend | `import_selected` verarbeitet ausgewählte stabile IDs und liefert Einzelresultate; Duplicate-ID-Test. Keine eigene Auswahllistenoberfläche. |
| R03 | ungeprüft für Host | Keine Keyboardimplementierung verändert; HA-Actionformular real prüfen. |
| R04 | ungeprüft für Host | Keine eigenen modalen Dialoge; nativer HA-Host nicht per Scrim/Escape getestet. |
| R05 | ungeprüft für Host | Keine eigene Navigation; Host-Back/Forward nicht getestet. |
| R06 | ungeprüft für Host | Keine eigene Ansicht; Actionfelder mobil nicht im Browser getestet. |
| R07 | nicht anwendbar | HA-Integration ohne eigene PWA; HA-Host bleibt zuständig. |
| R08 | erfüllt für Backend | Ein Manager und eine Action-Ausführung für zwei Transporte und beide ARR-Dienste. |
| R09 | teilweise | HA-Service-Schemas/Selektoren statt eigener Komponenten; statischer Regelprüfer grün, Hostdarstellung offen. |
| R10 | teilweise | Stabile IDs, Schema-Fehlerprüfung, deutsche/englische Action-Label und Feldbeschreibungen; Host-Datenerhalt offen. |
| R11 | erfüllt für Backend | Itemstatus `submitted/skipped/error`, keine Abschlussbehauptung bei angenommener Submission; Lock und Duplikat-/Paralleltests. |
| R12 | erfüllt für Backend | Konkrete sichere Meldungen mit erneutem Prüfschritt; HTTP-Ablehnung retrybar, ungewisser Verbindungsabbruch ausdrücklich benannt; Fehlerfälle getestet. |
| R13 | erfüllt für Backend | Kein erzwungener unsicherer Import; jede Schreibaktion frisch validiert, aktive/mehrdeutige/fehlzugeordnete Items gesperrt. Auswahl ist ausdrücklich und ersetzt keine Prüfung. |
| R14 | erfüllt für Backend | Vollständige Queue-Pagination und per Item strukturierter Bulk-Status; Zweitseiten-Test. |
| R15 | nicht anwendbar | Backend ohne Drag&Drop. |
| R16 | ungeprüft für Host | Keine eigene Browseroberfläche; kein Screenreader/Zoom/Kontrastlauf. |
| R17 | erfüllt für Datenvertrag | `not_applicable/ready/no_match/selection_required/error`, nullable count vor Prüfung, safe valid-Flags; Sicherheitsmatrix getestet. Darstellung im Kartenrepo. |
| R18 | erfüllt für Datenvertrag | Keine Kandidatenwarnung für aktive/ungeprüfte Downloads; leere/error-Zustände explizit, keine Raw-JSON-Meldung in neuen Itemfehlern. |
| R19 | nicht anwendbar | Keine Browserpermission eingeführt; bestehende Benutzerrechte werden real per HA-API geprüft. |
| R20 | teilweise | Kandidatenabruf nur für explizit vollständige Importprobleme; Test 20/50/99 % ohne Kandidatenrequests. Keine Feldmessung/Web Vitals. |
| R21 | nicht anwendbar | Backend speichert keine UI-Präferenzen. Flüchtige Reservierungen dienen Aktionssicherheit, nicht Navigation. |
| R22 | teilweise | Fünf benannte Actions samt HA-Feldbeschreibungen registriert; Auffindbarkeit im nativen UI nicht visuell geprüft. |
| R23 | nicht anwendbar | Backend enthält keine responsiven Komponenten; gemeinsamer fachlicher Vertrag durch R08 getestet. |
| R24 | erfüllt | Begrenzung HA-Host versus API und fehlende echte Browserabnahme oben ausdrücklich dokumentiert; keine Ersatzbehauptung. |
| R25 | teilweise | Fünf abgegrenzte Actions mit stabilen Feldern; keine Settings-Neugestaltung, native mobile Formhierarchie offen. |
| R26 | erfüllt für neue Metadaten | Deutsche/englische Actions und Feldbeschreibungen, etablierte Sonarr/Radarr/Queue/Import-Begriffe erhalten. Hostrendering nicht geprüft. |

Sicherheitsgrenze: Reservierungen sind flüchtig. Nach HA-Neustart zuerst den
Dienststatus eines zuvor ungewissen Importauftrags prüfen. Die reine
Lokalprüfung veröffentlicht/installiert nichts und verändert keine echten
Mediendateien. Release-/Live-Abnahme erfolgt durch die übergeordnete Sitzung;
Todos #181/#182 werden erst mit deren belegtem Abschluss erledigt.
