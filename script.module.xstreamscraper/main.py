# -*- coding: utf-8 -*-
import sys, xbmcaddon, xbmcplugin
from xbmcgui import ListItem
from resources.lib import addonTools

def main():
	if not xbmcaddon.Addon().getSetting("firststart") == "true":
		addonTools.repair(True)
		xbmcaddon.Addon().setSetting("firststart", "true")
	else: addonTools.repair()
	from urllib.parse import parse_qsl
	params = dict(parse_qsl(sys.argv[2][1:]))
	tmdb_id = params.get("id")
	title = params.get("title", "")
	action = params.get("action")
	repair = params.get("repair")
	season = int(params.get("season", 0))
	episode = int(params.get("episode", 0))
	type = "tv" if season !=0 and episode !=0 else "movie"
	if tmdb_id:
		from resources.lib import scraper
		scraper.play(type, tmdb_id, season, episode)
	elif repair:
		addonTools.repair(True)
	elif action:
		addonTools.setup_tmdb_helper()
	else: 
		xbmcplugin.setContent(int(sys.argv[1]), "files")
		xbmcplugin.addDirectoryItem(int(sys.argv[1]), "%s?action=true" %sys.argv[0], ListItem("TMDB-HELPER einrichten"), False)
		xbmcplugin.endOfDirectory(int(sys.argv[1]), succeeded=True, cacheToDisc=True)

if __name__ == '__main__':
    sys.exit(main())