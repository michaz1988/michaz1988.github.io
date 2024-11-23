# -*- coding: utf-8 -*-
# Python 3

import sys, xbmc, xbmcgui , xbmcplugin
from resources.lib.tools import logger, cParser
from resources.lib import common, settings
from resources.lib.config import cConfig
from resources.lib.gui.guiElement import cGuiElement
from resources.lib.handler.ParameterHandler import ParameterHandler
from six.moves.urllib.parse import quote_plus, urlencode


class cGui:
	# This class "abstracts" a list of xbmc listitems.
	def __init__(self):
		# for globalSearch or alterSearch
		self.globalSearch = False
		self._collectMode = False
		self._isViewSet = False
		self.searchResults = []

	def addFolder(self, oGuiElement, params='', bIsFolder=True, iTotal=0, isHoster=False):
		if xbmc.Monitor().abortRequested():
			self.setEndOfDirectory(False)
			raise RuntimeError('UserAborted')
		import copy
		if settings.collectMode:
			self.searchResults.append(self.__createItemUrl(oGuiElement,bIsFolder, copy.deepcopy(params)) )
			return
		settings.aDirectory.append(self.__createItemUrl(oGuiElement,bIsFolder, copy.deepcopy(params)))

	def addNextPage(self, site, function, params=''):
		pass

	def createListItem(self, oGuiElement):
		pass

	def __createContextMenu(self, oGuiElement, listitem, bIsFolder, sUrl):
		pass

	def setEndOfDirectory(self, success=True):
		pass

	def setView(self, content='movies'):
		pass

	def updateDirectory(self):
		pass

	def __createItemUrl(self, oGuiElement, bIsFolder, params=""):
		if params == "":
			params = ParameterHandler()
		itemValues = oGuiElement.getItemValues()
		if "tmdb_id" in itemValues and itemValues["tmdb_id"]:
			params.setParam("tmdbID", itemValues["tmdb_id"])
		if "TVShowTitle" in itemValues and itemValues["TVShowTitle"]:
			params.setParam("TVShowTitle", itemValues["TVShowTitle"])
		if "season" in itemValues and itemValues["season"] and int(itemValues["season"]) > 0:
			params.setParam("season", itemValues["season"])
		if "episode" in itemValues and itemValues["episode"] and float(itemValues["episode"]) > 0:
			params.setParam("episode", str(int(cParser.replace("[^0-9]", "", itemValues["episode"]))))
		# TODO change this, it can cause bugs it influencec the params for the following listitems
		if oGuiElement._sQuality:
			params.setParam("quality", oGuiElement._sQuality)
		if oGuiElement._sLanguage:
			params.setParam("language", oGuiElement._sLanguage)
		if oGuiElement._sYear:
			params.setParam("year", oGuiElement._sYear)
		if not bIsFolder:
			if not "TVShowTitle" in itemValues:
				params.setParam("MovieTitle", oGuiElement.getTitle())
			if oGuiElement._mediaType:
				params.setParam("mediaType", oGuiElement._mediaType)
			elif "TVShowTitle" in itemValues and itemValues["TVShowTitle"]:
				params.setParam("mediaType", "tvshow")
			if "season" in itemValues and itemValues["season"] and int(itemValues["season"]) > 0:
				params.setParam("mediaType", "season")
			if "episode" in itemValues and itemValues["episode"] and float(itemValues["episode"]) > 0:
				params.setParam("mediaType", "episode")
		params.setParam("site", oGuiElement.getSiteName())
		params.setParam("title", oGuiElement.getTitle())
		if len(oGuiElement.getFunction()) > 0:
			params.setParam("function", oGuiElement.getFunction())
			if not bIsFolder:
				params.setParam("playMode", "play")
		return params.getAllParameters()

	@staticmethod
	def showKeyBoard(sDefaultText=""):
		# Create the keyboard object and display it modal
		oKeyboard = xbmc.Keyboard(sDefaultText)
		oKeyboard.doModal()
		# If key board is confirmed and there was text entered return the text
		if oKeyboard.isConfirmed():
			sSearchText = oKeyboard.getText()
			if len(sSearchText) > 0:
				return sSearchText
		return False

	@staticmethod
	def showNumpad(defaultNum="", numPadTitle=cConfig().getLocalizedString(30251)):
		defaultNum = str(defaultNum)
		dialog = xbmcgui.Dialog()
		num = dialog.numeric(0, numPadTitle, defaultNum)
		return num

	@staticmethod
	def openSettings():
		cConfig().showSettingsWindow()

	@staticmethod
	def showNofication(sTitle, iSeconds=0):
		pass

	@staticmethod
	def showError(sTitle, sDescription, iSeconds=0):
		if iSeconds == 0:
			iSeconds = 1000
		else:
			iSeconds = iSeconds * 1000
		xbmc.executebuiltin("Notification(%s,%s,%s,%s)" % (str(sTitle), (str(sDescription)), iSeconds, common.addon.getAddonInfo('icon')))

	@staticmethod
	def showInfo(sTitle='xStream', sDescription=cConfig().getLocalizedString(30253), iSeconds=0):
		pass

	@staticmethod
	def showLanguage(sTitle='xStream', sDescription=cConfig().getLocalizedString(30403), iSeconds=0):
		if iSeconds == 0:
			iSeconds = 1000
		else:
			iSeconds = iSeconds * 1000
		xbmc.executebuiltin("Notification(%s,%s,%s,%s)" % (str(sTitle), (str(sDescription)), iSeconds, common.addon.getAddonInfo('icon')))
