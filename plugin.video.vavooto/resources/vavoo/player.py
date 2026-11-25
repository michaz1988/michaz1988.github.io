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
        self.reset()

    def reset(self):
        """Zustand fuer die naechste Quelle zuruecksetzen."""
        self.ended = False
        self.stopped = False
        self.error = False
        # Pfad des eigenen Streams, festgehalten beim ersten echten Bild. Spielt
        # Kodi danach etwas anderes, hat der Nutzer gewechselt -> nicht eingreifen.
        self.own_file = None

    def _playing_file(self):
        try:
            return self.getPlayingFile()
        except Exception:
            return None

    def _foreign_playback(self):
        if not self.own_file or not self.isPlaying():
            return False
        current = self._playing_file()
        return bool(current) and current != self.own_file

    def stop_and_settle(self, max_wait=20.0):
        """Eigenen Stream stoppen und das Stopp-Event abwarten.

        Ohne das Warten kaeme das Event der alten Quelle erst waehrend der
        naechsten an und wuerde dort als Nutzer-Stopp gewertet. Kodi kann zum
        Schliessen viele Sekunden brauchen und blockiert dabei API-Aufrufe; die
        Wartezeit zaehlt deshalb Abfragerunden (siehe _confirm_stall), nicht Uhrzeit.
        Gibt False zurueck, wenn der Player in der Zeit nicht zur Ruhe kam.
        """
        if self.isPlaying():
            self.stop()
            rounds = max(1, int(round(max_wait / 0.1)))
            while rounds > 0 and not monitor.abortRequested():
                if self.stopped or self.ended or self.error:
                    break
                monitor.waitForAbort(0.1)
                rounds -= 1
        settled = not self.isPlaying()
        self.reset()
        return settled

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

    def _confirm_stall(self, grace, check=None):
        """Vor einem Stillstand-Urteil kurz auf onPlayBackStopped/Ended warten.

        Beim Druck auf Stopp friert getTime() ein bzw. isPlayingVideo() wird False,
        bevor Kodi das Stopp-Event liefert. Ohne diese Wartezeit wuerde ein
        Nutzer-Stopp als Abriss gewertet und die naechste Quelle gestartet.

        Die Frist zaehlt Abfragerunden statt Uhrzeit: Waehrend Kodi den Player
        schliesst, blockieren API-Aufrufe (z.B. getProperty) teils viele Sekunden,
        und das Stopp-Event wird erst danach in waitForAbort zugestellt. Eine
        Uhrzeit-Frist liefe in der Blockade ab, bevor das Event ankommt.
        """
        full = max(1, int(round(grace / 0.1)))
        rounds = full
        while not monitor.abortRequested():
            round_start = time.time()
            if check:
                reason = check()
                if reason:
                    return reason
            if self.stopped:
                return "stopped"
            if self.ended or self.error:
                return "ended"
            if rounds <= 0:
                return "stalled"
            rounds -= 1
            monitor.waitForAbort(0.1)
            if time.time() - round_start > 1.0:
                # Kodi war blockiert (meist: Player wird gerade geschlossen) ->
                # Frist neu beginnen, damit das Stopp-Event noch ankommen kann.
                rounds = full
        return "abort"

    def user_stop_pending(self, wait=0.5):
        """Ausstehende Player-Events abholen; True, wenn darunter ein Stopp war."""
        rounds = max(1, int(round(wait / 0.1)))
        while rounds > 0 and not self.stopped and not monitor.abortRequested():
            monitor.waitForAbort(0.1)
            rounds -= 1
        return self.stopped

    def wait_for_failure(self, stall_seconds=0.5, startup_seconds=12, check=None, on_started=None):
        """Wiedergabe ueberwachen, bis sie endet oder abreisst.

        check: Funktion ohne Argumente; liefert sie einen Grund ("cancelled",
        "replaced"), endet die Ueberwachung sofort mit diesem Ergebnis.
        on_started: wird einmal aufgerufen, sobald das erste echte Bild laeuft.
        """
        started = time.time()
        last_progress = started
        last_time = None
        progressed = False          # getTime() ist mindestens einmal echt weitergelaufen

        while not monitor.abortRequested():
            if check:
                reason = check()
                if reason:
                    return reason
            if self._foreign_playback():
                # Kodi spielt etwas anderes als unseren Stream -> Nutzer hat gewechselt
                return "replaced"
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
                        if not progressed:
                            progressed = True
                            if not self.own_file:
                                self.own_file = self._playing_file()
                            if on_started:
                                try:
                                    on_started()
                                except Exception:
                                    log(format_exc())
                    elif progressed and self._speed() != 0 and time.time() - last_progress >= stall_seconds:
                        result = self._confirm_stall(1.0, check)
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
                    return self._confirm_stall(3.0, check)
            elif time.time() - started >= startup_seconds:
                return "startup_failed"

            monitor.waitForAbort(0.1)
        return "abort"
