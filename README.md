# Michaz Kodi Repository

Dieses Repository stellt Kodi-Add-ons, EPG-Daten und ergänzende Dateien bereit.

## Kodi-Repository installieren

1. In Kodi unter **Einstellungen → Dateimanager → Quelle hinzufügen** die Adresse
   `https://michaz1988.github.io/` eintragen.
2. Unter **Add-ons → Aus ZIP-Datei installieren** die Quelle öffnen.
3. Im Ordner [`repo/repository.michaz`](https://michaz1988.github.io/repo/repository.michaz/)
   die neueste ZIP-Datei installieren.
4. Anschließend **Aus Repository installieren → Michaz Repository** auswählen.

## EPG

- [EPG als XML](https://github.com/michaz1988/michaz1988.github.io/releases/download/EPG/guide.xml)
- [EPG als komprimierte XML.GZ-Datei](https://github.com/michaz1988/michaz1988.github.io/releases/download/EPG/guide.xml.gz)

Die EPG-Dateien werden täglich automatisch aktualisiert.

## Eigenen Fork verwenden

Die Add-on-Quellen liegen in der Branch `addons`. Beim Forken muss die
GitHub-Option **Copy the DEFAULT branch only** deaktiviert werden, damit diese
Branch ebenfalls in den Fork übernommen wird.

Der Workflow **Repository, EPG und Listen aktualisieren** in der Branch `main`
lädt die Quellen aus `addons`, erstellt die ZIP-Dateien und aktualisiert
`repo/addons.xml`, `repo/addons.xml.md5` sowie die Verzeichnis-Indizes. Da kein
fester Repository-Name verwendet wird, arbeitet der Workflow in einem Fork mit
den Branches des jeweiligen Forks.

## Weitere Downloads

- [Players für TMDB Helper](https://michaz1988.github.io/players.zip)
- [M3U-Liste für IPTV Simple](https://michaz1988.github.io/tv.m3u)
- [Michaz Build](https://h1.nu/michazbuild)

## Probleme melden

Fehler und Rückfragen können über die
[GitHub Issues](https://github.com/michaz1988/michaz1988.github.io/issues)
gemeldet werden. Bitte möglichst Kodi-Version, Betriebssystem und relevante
Auszüge aus `kodi.log` angeben.

Die angebotenen Add-ons und Inhalte stammen teilweise von Drittanbietern und
stehen nicht in Verbindung mit dem offiziellen Kodi-Team.
