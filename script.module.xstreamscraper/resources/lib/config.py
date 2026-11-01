# -*- coding: utf-8 -*-
# Python 3

import xbmcaddon
import resolveurl as resolver

from resources.lib import common
from six.moves.urllib.parse import urlparse
from xbmc import LOGINFO as LOGNOTICE, LOGERROR, LOGWARNING, log, executebuiltin, getCondVisibility, getInfoLabel

class cConfig:
	def __init__(self, addon_id=None):
		self.__addon = xbmcaddon.Addon(addon_id or common.addonID)
		self.__aLanguage = self.__addon.getLocalizedString

	def showSettingsWindow(self):
		self.__addon.openSettings()

	def getSetting(self, sName, default=''):
		result = self.__addon.getSetting(sName)
		if result:
			return result
		else:
			return default

	def getSettingString(self, sName, default=''):
		return str(self.getSetting(sName, default))

	def getAddonInfo(self, sName):
		return self.__addon.getAddonInfo(sName) or ''

	def setSetting(self, id, value):
		if id and value is not None:
			self.__addon.setSetting(id, value)

	def getLocalizedString(self, sCode):
		return self.__aLanguage(sCode)
		
	def isBlockedHoster(self, domain, checkResolver=True ):
		return False, domain