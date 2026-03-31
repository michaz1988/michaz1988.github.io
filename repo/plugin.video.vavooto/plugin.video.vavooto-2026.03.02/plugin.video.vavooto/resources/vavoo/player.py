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
        #log(cConfig().getLocalizedString(30166) + ' -> [player]: player instance created', LOGNOTICE)

    def onPlayBackStarted(self):
        log(cConfig().getLocalizedString(30166) + ' -> [player]: starting Playback')
        try:
            self.totalTime = self.getTotalTime()
        except:
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
                   # log(cConfig().getLocalizedString(30166) + ' -> [player]: Detected Global Search context', LOGNOTICE)
        except:
            pass

    def onPlayBackStopped(self):
        #log(cConfig().getLocalizedString(30166) + ' -> [player]: Playback stopped', LOGNOTICE)
        if self.playedTime == 0 and self.totalTime == 999999:
            self.streamSuccess = False
            #log(cConfig().getLocalizedString(30166) + ' -> [player]: Kodi failed to open stream', LOGERROR)
        self.streamFinished = True

        # After playback ends, if we came from Global Search → return to main menu
        if self.from_global_search:
            try:
                execute('Container.Update(plugin://plugin.video.xstream/)')
                log('xStream -> [player]: Returning to addon main menu after Global Search')
            except: log(format_exc())

    def onPlayBackEnded(self):
        #log(cConfig().getLocalizedString(30166) + ' -> [player]: Playback completed', LOGNOTICE)
        self.onPlayBackStopped()


class cPlayer:
    def clearPlayList(self):
        oPlaylist = self.__getPlayList()
        oPlaylist.clear()

    def __getPlayList(self):
        return xbmc.PlayList(xbmc.PLAYLIST_VIDEO)

    #def addItemToPlaylist(self, oGuiElement):
        #oListItem = cGui().createListItem(oGuiElement)
        #self.__addItemToPlaylist(oGuiElement, oListItem)

    #def __addItemToPlaylist(self, oGuiElement, oListItem):
        #oPlaylist = self.__getPlayList()
        #oPlaylist.add(oGuiElement.getMediaUrl(), oListItem)

    def startPlayer(self):
        #log(cConfig().getLocalizedString(30166) + ' -> [player]: start player', LOGNOTICE)
        xbmcPlayer = XstreamPlayer()
        while (not monitor.abortRequested()) & (not xbmcPlayer.streamFinished):
            if xbmcPlayer.isPlayingVideo():
                xbmcPlayer.playedTime = xbmcPlayer.getTime()
            monitor.waitForAbort(10)
        return xbmcPlayer.streamSuccess