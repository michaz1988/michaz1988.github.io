# -*- coding: utf-8 -*-
import sys, xbmcaddon, xbmcplugin
from xbmcgui import ListItem
from resources.lib import tools

def main():
	if not xbmcaddon.Addon().getSetting("firststart") == "true":
		tools.repair(True)
		xbmcaddon.Addon().setSetting("firststart", "true")
	else: tools.repair()
	from six.moves.urllib.parse import parse_qsl
	params = dict(parse_qsl(sys.argv[2][1:]))
	tmdb_id = params.get("id")
	action = params.get("action")
	repair = params.get("repair")
	season = int(params.get("season", 0))
	episode = int(params.get("episode", 0))
	type = "tv" if season !=0 and episode !=0 else "movie"
	if tmdb_id:
		from resources.lib import scraper
		scraper.play(type, tmdb_id, season, episode)
	elif repair:
		tools.repair(True)
	elif action:
		xbmcaddon.Addon("plugin.video.themoviedb.helper").setSetting("players_url", "https://michaz1988.github.io/players.zip")
		xbmc.executebuiltin('RunScript(plugin.video.themoviedb.helper, update_players)')
		xbmcaddon.Addon("plugin.video.themoviedb.helper").setSetting("default_player_movies", "xstream.json play_movie")
		xbmcaddon.Addon("plugin.video.themoviedb.helper").setSetting("default_player_episodes", "xstream.json play_episode")
	else: 
		xbmcplugin.setContent(int(sys.argv[1]), "files")
		xbmcplugin.addDirectoryItem(int(sys.argv[1]), "%s?action=true" %sys.argv[0], ListItem("TMDB-HELPER einrichten"), False)
		xbmcplugin.addDirectoryItem(int(sys.argv[1]), "%s?repair=true" %sys.argv[0], ListItem("xStream reparieren"), False)
		xbmcplugin.endOfDirectory(int(sys.argv[1]), succeeded=True, cacheToDisc=True)

if __name__ == '__main__':
    sys.exit(main())