# Michaz Kodi Add-ons

Dieses Repository enthält die Quellen der Kodi-Add-ons.

Jeder Push auf den Branch `main` startet automatisch die GitHub Action
**Kodi-Repository aktualisieren**. Sie aktualisiert das bestehende Repository
`michaz1988/michaz1988.github.io`.

Lokale Änderungen können mit dem mitgelieferten Skript commitet und gepusht
werden:

```sh
sh push_addons.sh
```

Optional kann eine eigene Commit-Nachricht angegeben werden:

```sh
sh push_addons.sh "Add-ons aktualisiert"
```

Der Workflow erstellt fehlende versionsgebundene ZIP-Dateien, aktualisiert
`addons.xml` und `addons.xml.md5`, erzeugt die Verzeichnis-Indizes neu und
behält pro Add-on die zwei neuesten ZIP-Versionen.
