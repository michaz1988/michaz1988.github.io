import sys, os, xbmc, xbmcaddon
PY3 = sys.version_info[0] == 3
if PY3:
	import xbmcvfs

def starter2():
	pass

def translatePath(*args):
	if PY3: return xbmcvfs.translatePath(*args)
	else: return xbmc.translatePath(*args).decode('utf-8')

addonID = 'plugin.video.xstream'
addon = xbmcaddon.Addon(addonID)
addonInfo = addon.getAddonInfo
profilePath = translatePath(addonInfo('profile'))
addonPath = translatePath(addonInfo('path'))
addonName = addonInfo('name')