# ha-arrstack-integrations — Agent-Einstieg

Dieses Verzeichnis ist ein eigenständiges HACS-Repository. Vor Änderungen
`AGENTS.md`, danach `../AGENTS.md` und `../CLAUDE.md` lesen und deren
Lesereihenfolge einschließlich `../docs/ui-regeln.md` beachten. Fehlende
Parent-Dateien bei einem Einzel-Checkout ausdrücklich benennen; das Regelwerk
vor UI-Arbeit bereitstellen lassen. Git-Befehle in diesem Repo ausführen,
keine Nachbarrepos oder fremden Änderungen in einen Commit aufnehmen.

Vor Planung oder Implementierung vollständig
`/mnt/user/Data/Claude Projekte/DESIGN_GUIDELINES.md` lesen, anschließend
[Projektglossar](docs/design-glossar.md) und
[aktuellen Design-Audit](docs/design-audit-2026-10-08.md). Alle 26 Regel-IDs
auf Anwendbarkeit prüfen; R04 hat Vorrang vor älteren pauschalen Scrim-Regeln.
Quellprüfung ersetzt keine echte Keyboard-/Mobile-/Hostabnahme.

Offene Todos über `bash ../../scripts/todo.sh liste hacs` abrufen; zugehörige
Bereichszuordnung steht in der HACS-Weiche. Vor Edit übernehmen, nur belegt
abschließen, Unfertiges freigeben. Gemeinsame Datenschutz- und
Benachrichtigungsregeln gelten weiter. Der Design-Audit-Auftrag vom 08.10.2026
ändert nur lokale Dokumentation: keine App-Codeänderung, kein Deploy und
keine Veröffentlichung oder Netzwerk-Git-Aktion.
