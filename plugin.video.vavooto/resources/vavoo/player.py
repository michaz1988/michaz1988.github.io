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

    def onPlayBackEnded(self):
        self.ended = True

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

    def wait_for_failure(self, stall_seconds=8, startup_seconds=12):
        started = time.time()
        last_progress = started
        last_time = None
        progressed = False          # getTime() ist mindestens einmal echt weitergelaufen

        while not monitor.abortRequested():
            if self.stopped or self.ended:
                # Stop/End OHNE dass je ein Bild lief -> Quelle taugt nicht, naechste probieren.
                # (Kodi feuert onPlayBackStopped auch, wenn ffmpeg selbst abbricht.)
                if not progressed:
                    return "startup_failed"
                return "ended" if self.ended else "stopped"

            if self.isPlayingVideo():
                try:
                    current = self.getTime()
                    if last_time is None:
                        last_time = current
                    elif current - last_time > 0.25:
                        last_time = current
                        last_progress = time.time()
                        progressed = True
                    elif progressed and self._speed() != 0 and time.time() - last_progress >= stall_seconds:
                        return "stalled"
                    elif not progressed and time.time() - started >= startup_seconds:
                        return "startup_failed"
                except Exception:
                    if time.time() - started >= startup_seconds:
                        return "startup_failed"
            elif progressed:
                # lief schon, Bild jetzt ohne Event weg
                if time.time() - last_progress >= stall_seconds:
                    return "stalled"
            elif time.time() - started >= startup_seconds:
                return "startup_failed"

            monitor.waitForAbort(1)
        return "abort"
