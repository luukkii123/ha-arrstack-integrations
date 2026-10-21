# HA-Bibliothekstests ohne eigene HA-Instanz

Die Tests nutzen echte Home-Assistant-Flowmanager in pytest. Sie starten
keinen HA-Server, installieren keine eigene Instanz und berühren keine
Produktionsdaten. HTTP-/SSH-Abfragen werden an der Transportgrenze ersetzt;
Eintrags-Setup und -Unload werden in den Flowtests isoliert.

Im Repository ausführen:

```sh
docker build -f tests_ha/Dockerfile -t integration-tests .
docker run --rm --network none -v "$PWD:/repo" -w /repo integration-tests python -m pytest -c tests_ha/pytest.ini tests_ha --cov=custom_components.arrstack.config_flow --cov-branch --cov-fail-under=100 -q
```

CI prüft HA 2026.7.0 mit Testplugin 0.13.344 und HA 2026.9.2 mit
0.13.365. Die Grenze 100 % gilt für Config-, Options-, Reauth- und
Reconfigure-Flows einschließlich Recovery nach jedem erwarteten Fehler.
Sie behauptet keine 100-%-Abdeckung der gesamten Integration.
