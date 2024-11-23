# -*- coding: utf-8 -*-
# Python 3

from resources.lib.tools import cParser, cUtil
from resources.lib.config import cConfig
from resources.lib.common import addon
from resources.lib.tools import logger
from os import path

LOGMESSAGE = cConfig().getLocalizedString(30166)
class cGuiElement:
	'''
	This class "abstracts" a xbmc listitem.
	Kwargs:
		sTitle	(str): title/label oft the GuiElement/listitem
		sSite	 (str): siteidentifier of the siteplugin, which is called if the GuiElement is selected
		sFunction (str): name of the function, which is called if the GuiElement is selected
		These arguments are mandatory. If not given on init, they have to be set by their setter-methods, before the GuiElement is added to the Gui.
	'''
	DEFAULT_FOLDER_ICON = 'DefaultFolder.png'
	DEFAULT_FANART = path.join(addon.getAddonInfo('path'), 'fanart.jpg')
	MEDIA_TYPES = ['movie', 'tvshow', 'season', 'episode']

	def __init__(self, sTitle='', sSite=None, sFunction=None):
		self.__sType = 'video'
		self.__sMediaUrl = ''
		self.__sTitle = cUtil.cleanse_text(sTitle)
		self.__sTitleSecond = ''
		self.__sDescription = ''
		self.__sThumbnail = ''
		self.__sIcon = self.DEFAULT_FOLDER_ICON
		self.__aItemValues = {}
		self.__aProperties = {}
		self.__aContextElements = []
		self.__sFanart = self.DEFAULT_FANART
		self.__sSiteName = sSite
		self.__sFunctionName = sFunction
		self._sLanguage = ''
		self._sSubLanguage = ''
		self._sYear = ''
		self._sQuality = ''
		self._mediaType = ''
		self._season = ''
		self._episode = ''
		self._tmdbID = ''
		self._rating = ''
		self._isMetaSet = False

	def setType(self, sType):
		self.__sType = sType

	def getType(self):
		return self.__sType

	def setMediaUrl(self, sMediaUrl):
		self.__sMediaUrl = sMediaUrl

	def getMediaUrl(self):
		return self.__sMediaUrl

	def setSiteName(self, sSiteName):
		self.__sSiteName = sSiteName

	def getSiteName(self):
		return self.__sSiteName

	def setFunction(self, sFunctionName):
		self.__sFunctionName = sFunctionName

	def getFunction(self):
		return self.__sFunctionName

	def setTitle(self, sTitle):
		self.__sTitle = cUtil.cleanse_text(sTitle)

	def getTitle(self):
		if ' (19' in self.__sTitle or ' (20' in self.__sTitle:
			isMatch, aYear = cParser.parse(self.__sTitle, '(.*?)\(((19\d{2}|20\d{2}))\)')
			if isMatch:
				self.__sTitle = aYear[0][0]
				self.setYear(aYear[0][1])
		if '*19' in self.__sTitle or '*20' in self.__sTitle:
			isMatch, aYear = cParser.parse(self.__sTitle, '(.*?)\*((19\d{2}|20\d{2}))\*')
			if isMatch:
				self.__sTitle = aYear[0][0]
				self.setYear(aYear[0][1])
		if '*english*' in self.__sTitle.lower():
			isMatch, aLang = cParser.parse(self.__sTitle, '(.*?)\*(.*?)\*')
			if isMatch:
				self.__sTitle = aLang[0][0]
				self.setLanguage('Englisch')
		if 'English:' in self.__sTitle:
			self.__sTitle = self.__sTitle.replace('English:', '')
			self.setLanguage('Englisch')
		if '(omu)' in self.__sTitle.lower():
			self.__sTitle = self.__sTitle.replace('(OmU) ', '').replace('(Omu) ', '')
			self.setLanguage('OmU')
		if self._sYear: self.__sTitle = self.__sTitle.strip() + ' (' + self._sYear + ')'
		return self.__sTitle.strip()

	def setMediaType(self, mediaType):
		'''
		Set mediatype for GuiElement
		Args:
			mediaType(str): 'movie'/'tvshow'/'season'/'episode'
		'''
		mediaType = mediaType.lower()
		if mediaType in self.MEDIA_TYPES:
			self._mediaType = mediaType
		else:
			logger.error(LOGMESSAGE + ' -> [guiElement]: Unknown MediaType given for %s' % self.getTitle())

	def setSeason(self, season):
		self._season = season
		self.__aItemValues['season'] = str(season)

	def setEpisode(self, episode):
		self._episode = episode
		self.__aItemValues['episode'] = str(episode)

	def setTVShowTitle(self, tvShowTitle):
		self.__aItemValues['TVShowTitle'] = str(tvShowTitle)

	def setYear(self, year):
		try:
			year = int(year)
		except:
			logger.error(LOGMESSAGE + ' -> [guiElement]: Year given for %s seems not to be a valid number' % self.getTitle())
			return False
		if len(str(year)) != 4:
			logger.error(LOGMESSAGE + ' -> [guiElement]: Year given for %s has %s digits, required 4 digits' % (self.getTitle(), len(str(year))))
			return False
		if year > 0:
			self._sYear = str(year)
			self.__aItemValues['year'] = year
			return True
		else:
			logger.error(LOGMESSAGE + ' -> [guiElement]: Year given for %s must be greater than 0' % self.getTitle())
			return False

	def setQuality(self, quality):
		self._sQuality = quality
		
	def getQuality(self):
		return self._sQuality
	
	def setTitleSecond(self, sTitleSecond):
		self.__sTitleSecond = cUtil.cleanse_text(str(sTitleSecond))

	def getTitleSecond(self):
		return self.__sTitleSecond

	def setDescription(self, sDescription):
		sDescription = cUtil.cleanse_text(sDescription)
		self.__sDescription = sDescription
		self.__aItemValues['plot'] = sDescription

	def getDescription(self):
		if 'plot' not in self.__aItemValues:
			return self.__sDescription
		else:
			return self.__aItemValues['plot']

	def setThumbnail(self, sThumbnail):
		self.__sThumbnail = sThumbnail
		if cConfig().getSetting('replacefanart') == 'true' and sThumbnail.startswith('http'):
			self.__sFanart = sThumbnail

	def getThumbnail(self):
		return self.__sThumbnail

	def setIcon(self, sIcon):
		self.__sIcon = sIcon

	def getIcon(self):
		return self.__sIcon

	def setFanart(self, sFanart):
		self.__sFanart = sFanart

	def getFanart(self):
		return self.__sFanart

	def addItemValue(self, sItemKey, sItemValue):
		self.__aItemValues[sItemKey] = sItemValue

	def setItemValues(self, aValueList):
		self.__aItemValues = aValueList

	def getItemValues(self):
		self.__aItemValues['title'] = self.getTitle()
		if self.getDescription():
			self.__aItemValues['plot'] = self.getDescription()
		for sPropertyKey in self.__aProperties.keys():
			self.__aItemValues[sPropertyKey] = self.__aProperties[sPropertyKey]
		return self.__aItemValues

	def addItemProperties(self, sPropertyKey, sPropertyValue):
		self.__aProperties[sPropertyKey] = sPropertyValue

	def getItemProperties(self):
		for sItemValueKey in self.__aItemValues.keys():
			if not self.__aItemValues[sItemValueKey] == '':
				try:
					self.__aProperties[sItemValueKey] = str(self.__aItemValues[sItemValueKey])
				except:
					pass
		return self.__aProperties

	def addContextItem(self, oContextElement):
		self.__aContextElements.append(oContextElement)

	def getContextItems(self):
		return self.__aContextElements

	def setLanguage(self, sLang):
		self._sLanguage = str(sLang)

	def setSubLanguage(self, sLang):
		self._sSubLanguage = str(sLang)

	def getMeta(self, mediaType, tmdbID='', TVShowTitle='', season='', episode='', mode='add'):
		'''
		Fetch metainformations for GuiElement.
		Args:
			mediaType(str): 'movie'/'tvshow'/'season'/'episode'
		Kwargs:
			tmdbID (str)		:
			TVShowTitle (str)   :
			mode (str)		  : 'add'/'replace' defines if fetched metainformtions should be added to existing informations, or if they should replace them.
		'''
		if cConfig().getSetting('TMDBMETA') == 'false':
			return False
		if not self._mediaType:
			self.setMediaType(mediaType)
		if mode not in ['add', 'replace']:
			logger.error(LOGMESSAGE + ' -> [guiElement]: Wrong meta set mode')
		if not season and self._season:
			season = self._season
		if not episode and self._episode:
			episode = self._episode
		if not self._mediaType:
			logger.error(LOGMESSAGE + ' -> [guiElement]: Could not get MetaInformations for %s, mediaType not defined' % self.getTitle())
			return False
		from tmdb import cTMDB
		oMetaget = cTMDB()
		if not oMetaget:
			return False

		if self._mediaType == 'movie':
			if self._sYear:
				meta = oMetaget.get_meta(self._mediaType, self.getTitle(), year=self._sYear, advanced=cConfig().getSetting('advanced'))
			else:
				meta = oMetaget.get_meta(self._mediaType, self.getTitle(), advanced=cConfig().getSetting('advanced'))
		elif self._mediaType == 'tvshow':
			if self._sYear:
				meta = oMetaget.get_meta(self._mediaType, self.getTitle(), year=self._sYear, advanced=cConfig().getSetting('advanced'))
			else:
				meta = oMetaget.get_meta(self._mediaType, self.getTitle(), advanced=cConfig().getSetting('advanced'))
		elif self._mediaType == 'season':
			meta = {}
		elif self._mediaType == 'episode':
			meta = oMetaget.get_meta_episodes(self._mediaType, TVShowTitle, tmdbID, str(season), str(episode))
		else:
			return False

		if not meta:
			return False

		if self._mediaType == 'season':
			meta = meta[0]

		if mode == 'replace':
			self.setItemValues(meta)
			if 'cover_url' in meta:
				self.setThumbnail(meta['cover_url'])
			if 'backdrop_url' in meta:
				self.setFanart(meta['backdrop_url'])
			if 'title' in meta and episode:
				self.setTitle(str(episode) + '. ' + meta['title'])

		else:
			meta.update(self.__aItemValues)
			meta.update(self.__aProperties)
			if 'cover_url' in meta != '' and self.__sThumbnail == '':
				self.setThumbnail(meta['cover_url'])

			if 'backdrop_url' in meta and self.__sFanart == self.DEFAULT_FANART:
				self.setFanart(meta['backdrop_url'])
			self.setItemValues(meta)
		if 'tmdb_id' in meta:
			self._tmdbID = meta['tmdb_id']
		self._isMetaSet = True
		return meta
