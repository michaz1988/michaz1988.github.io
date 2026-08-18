# -*- coding: utf-8 -*-
# Python 3

import xbmcaddon
import resolveurl as resolver

from resources.lib import common
from six.moves.urllib.parse import urlparse
from xbmc import LOGINFO as LOGNOTICE, LOGERROR, LOGWARNING, log, executebuiltin, getCondVisibility, getInfoLabel

class cConfig:
	def __init__(self):
		self.__addon = xbmcaddon.Addon(common.addonID)
		self.__aLanguage = self.__addon.getLocalizedString

	def showSettingsWindow(self):
		self.__addon.openSettings()

	def getSetting(self, sName, default=''):
		result = self.__addon.getSetting(sName)
		if result:
			return result
		else:
			return default

	def setSetting(self, id, value):
		if id and value:
			self.__addon.setSetting(id, value)

	def getLocalizedString(self, sCode):
		return self.__aLanguage(sCode)
		
	def isBlockedHoster(self, domain, checkResolver=True ):
		return False, domain