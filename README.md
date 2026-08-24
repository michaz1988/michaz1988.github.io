# Michaz Kodi Add-on-Quellen

Dieser Branch enthält die Quellen der Kodi-Add-ons. Die veröffentlichte
Repository-Webseite liegt in der Branch `main` desselben Git-Repositories.

Ein Push auf `addons` startet den Workflow **Add-ons nach main
veröffentlichen**. Er testet den Generator, erstellt die versionsgebundenen
ZIP-Dateien, aktualisiert `addons.xml` und `addons.xml.md5` und erzeugt die
Verzeichnis-Indizes neu. Pro Add-on bleibt nur die aktuelle ZIP-Version
erhalten.
