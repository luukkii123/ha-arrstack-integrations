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
