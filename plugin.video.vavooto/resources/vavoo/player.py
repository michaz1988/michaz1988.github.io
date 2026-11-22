# -*- coding: utf-8 -*-
from vavoo.utils import *

class XstreamPlayer(player):
    def __init__(self, *args, **kwargs):
        player.__init__(self, *args, **kwargs)
        self.streamFinished = False
        self.streamSuccess = True
        self.playedTime = 0
        self.totalTime = 999999
        self.from_global_search = False  # Track if started from Global Search

    def onPlayBackStarted(self):
        log('VAVOO.TO -> [player]: starting Playback')
        try:
            self.totalTime = self.getTotalTime()
        except Exception:
            self.totalTime = 999999

        # Detect if playback started from Global Search
        try:
            path = getInfoLabel('Container.FolderPath')
            if path:
                low = path.lower()
                keywords = [
                    'function=globalsearch',
                    'site=globalsearch',
                    'function=searchalter',
                    'function=searchtmdb'
                ]
                if any(kw in low for kw in keywords):
                    self.from_global_search = True
        except Exception:
            pass

    def onPlayBackStopped(self):
        if self.playedTime == 0 and self.totalTime == 999999:
            self.streamSuccess = False
        self.streamFinished = True

        # After playback ends, if we came from Global Search → return to main menu
        if self.from_global_search:
            try:
                execute('Container.Update(plugin://%s/)' % addonID)
                log('VAVOO.TO -> [player]: Returning to addon main menu after Global Search')
            except Exception:
                log(format_exc())

    def onPlayBackEnded(self):
        self.onPlayBackStopped()


class cPlayer:
    def clearPlayList(self):
        oPlaylist = self.__getPlayList()
        oPlaylist.clear()

    def __getPlayList(self):
        return xbmc.PlayList(xbmc.PLAYLIST_VIDEO)

    def startPlayer(self):
        xbmcPlayer = XstreamPlayer()
        while (not monitor.abortRequested()) & (not xbmcPlayer.streamFinished):
            if xbmcPlayer.isPlayingVideo():
                xbmcPlayer.playedTime = xbmcPlayer.getTime()
            monitor.waitForAbort(10)
        return xbmcPlayer.streamSuccess


class LivePlayer(player):
    """Watch live playback and distinguish user stops from stream failures."""

    def __init__(self):
        player.__init__(self)
        self.ended = False
        self.stopped = False
        self.error = False

    def onPlayBackEnded(self):
        self.ended = True

    def onPlayBackError(self):
        self.error = True

    def onPlayBackStopped(self):
        self.stopped = True

    def _speed(self):
        try:
            query = json.dumps({
                "jsonrpc": "2.0",
                "method": "Player.GetProperties",
                "params": {"playerid": 1, "properties": ["speed"]},
                "id": 1,
            })
            result = json.loads(xbmc.executeJSONRPC(query))
            return result.get("result", {}).get("speed", 1)
        except Exception:
            return 1

    def _confirm_stall(self, grace):
        """Vor einem Stillstand-Urteil kurz auf onPlayBackStopped/Ended warten.

        Beim Druck auf Stopp friert getTime() ein bzw. isPlayingVideo() wird False,
        bevor Kodi das Stopp-Event liefert. Ohne diese Wartezeit wuerde ein
        Nutzer-Stopp als Abriss gewertet und die naechste Quelle gestartet.
        """
        deadline = time.time() + grace
        while not monitor.abortRequested():
            if self.stopped:
                return "stopped"
            if self.ended or self.error:
                return "ended"
            if time.time() >= deadline:
                return "stalled"
            monitor.waitForAbort(0.1)
        return "abort"

    def wait_for_failure(self, stall_seconds=0.5, startup_seconds=12):
        started = time.time()
        last_progress = started
        last_time = None
        progressed = False          # getTime() ist mindestens einmal echt weitergelaufen

        while not monitor.abortRequested():
            if self.stopped:
                # onPlayBackStopped kommt nur bei aktivem Stopp (Nutzer) - auch
                # waehrend des Starts kein Wechsel. Quellfehler melden sich ueber
                # onPlayBackError bzw. onPlayBackEnded.
                return "stopped"
            if self.error or self.ended:
                # Fehler/Ende OHNE dass je ein Bild lief -> Quelle taugt nicht, naechste probieren.
                return "ended" if progressed else "startup_failed"

            if self.isPlayingVideo():
                try:
                    current = self.getTime()
                    if last_time is None:
                        last_time = current
                    elif current - last_time > 0.1:
                        last_time = current
                        last_progress = time.time()
                        progressed = True
                    elif progressed and self._speed() != 0 and time.time() - last_progress >= stall_seconds:
                        result = self._confirm_stall(1.0)
                        if result != "stalled" or self.isPlayingVideo():
                            return result
                        # Player waehrend der Wartezeit verschwunden -> wie unten behandeln
                    elif not progressed and time.time() - started >= startup_seconds:
                        return "startup_failed"
                except Exception:
                    if time.time() - started >= startup_seconds:
                        return "startup_failed"
            elif progressed:
                # lief schon, Bild jetzt ohne Event weg -> meist Nutzer-Stopp, dessen
                # Event noch unterwegs ist; daher laenger auf das Event warten.
                if time.time() - last_progress >= stall_seconds:
                    return self._confirm_stall(3.0)
            elif time.time() - started >= startup_seconds:
                return "startup_failed"

            monitor.waitForAbort(0.1)
        return "abort"
