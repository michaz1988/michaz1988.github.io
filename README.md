# Michaz Kodi Add-on-Quellen

Diese Branch enthält die Quellen der Kodi-Add-ons. Die veröffentlichte
Repository-Webseite und ihr Workflow liegen in der Branch `main` desselben
Git-Repositories.

Der Workflow **Repository, EPG und Listen aktualisieren** lädt diese Branch,
erstellt die versionsgebundenen ZIP-Dateien, aktualisiert `addons.xml` und
`addons.xml.md5` und erzeugt die Verzeichnis-Indizes neu.

Lokale Änderungen können mit dem mitgelieferten Skript commitet und gepusht
werden:

```sh
sh push_addons.sh
```

Optional kann eine eigene Commit-Nachricht angegeben werden:

```sh
sh push_addons.sh "Add-ons aktualisiert"
```

Pro Add-on bleiben die zwei neuesten ZIP-Versionen erhalten.
