import xbmcaddon, xbmcvfs

def starter2():
	pass

def translatePath(*args):
	return xbmcvfs.translatePath(*args)

addonID = 'plugin.video.xstream'
addon = xbmcaddon.Addon(addonID)
addonInfo = addon.getAddonInfo
profilePath = translatePath(addonInfo('profile'))
addonPath = translatePath(addonInfo('path'))
addonName = addonInfo('name')
