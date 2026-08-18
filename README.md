# Michaz Kodi Add-ons

Dieses Repository enthält die Quellen der Kodi-Add-ons.

Über die GitHub Action **Kodi-Repository aktualisieren** kann das bestehende
Repository `michaz1988/michaz1988.github.io` manuell aktualisiert werden:

1. Auf GitHub den Bereich **Actions** öffnen.
2. **Kodi-Repository aktualisieren** auswählen.
3. **Run workflow** starten.

Der Workflow erstellt fehlende versionsgebundene ZIP-Dateien, aktualisiert
`addons.xml` und `addons.xml.md5`, erzeugt die Verzeichnis-Indizes neu und
behält pro Add-on die zwei neuesten ZIP-Versionen.

