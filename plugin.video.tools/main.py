# -*- coding: utf-8 -*-
import sys, xbmc

if __name__ == "__main__":
	if sys.version_info[1] >=12:
		if not xbmc.getCondVisibility("System.HasAddon(script.module.asyn)"):
			xbmc.executebuiltin('InstallAddon(script.module.asyn)')
			xbmc.executebuiltin('SendClick(11)')
	from resources.lib import tools
	
	
