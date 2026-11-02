# -*- coding: utf-8 -*-
import hashlib, json, os, xbmc, xbmcaddon, xbmcvfs

XSTREAM_ID = "plugin.video.xstream"

def md5(fname):
	hash_md5 = hashlib.md5()
	with open(fname, "rb") as f:
		for chunk in iter(lambda: f.read(4096), b""):
			hash_md5.update(chunk)
	return hash_md5.hexdigest()

def setup_tmdb_helper():
	helper = xbmcaddon.Addon("plugin.video.themoviedb.helper")
	helper.setSetting("players_url", "https://michaz1988.github.io/players.zip")
	xbmc.executebuiltin('RunScript(plugin.video.themoviedb.helper, update_players)')
	helper.setSetting("default_player_movies", "xstream.json play_movie")
	helper.setSetting("default_player_episodes", "xstream.json play_episode")

def repair(force=False):
	addon = xbmcaddon.Addon()
	new_xml = [
		'<settings>',
		' <category label="Einrichten">',
		'  <setting label="TMDB-HELPER einrichten" type="action" action="RunPlugin(plugin://script.module.xstreamscraper/?action=true)"/>',
		' </category>',
		' <category label="VIDEO">',
		'  <setting default="1" id="stream_select" label="Stream Auswahl" type="enum" values="Hoster|Automatisch"/>',
		'  <setting default="true" id="auto_try_next_stream" type="bool" subsetting="true" visible="eq(-1,0)" label="Automatisch nächsten ähnlichen Stream versuchen"/>',
		'  <setting default="false" id="progress_background" type="bool" label="Fortschritt im Hintergrund anzeigen"/>',
		' </category>',
		' <category label="VAVOO">',
		'  <setting default="true" id="vavoo" label="Vavoo" type="bool"/>',
		' </category>',
		' <category label="Scraper">']
	firststart = False
	settingsxml = os.path.join(xbmcvfs.translatePath(addon.getAddonInfo("path")), "resources", "settings.xml")
	profilepath = xbmcvfs.translatePath(addon.getAddonInfo("profile"))
	if not os.path.exists(profilepath): os.makedirs(profilepath)
	xstreampluginDB = os.path.join(xbmcvfs.translatePath(xbmcaddon.Addon(XSTREAM_ID).getAddonInfo("profile")), "pluginDB")
	scraperpluginDB = os.path.join(profilepath, "pluginDB")
	if not os.path.exists(scraperpluginDB) or not os.path.exists(settingsxml):
		firststart = True
		with open(scraperpluginDB, "w") as k: json.dump({}, k)
	if md5(scraperpluginDB) != md5(xstreampluginDB):
		with open(xstreampluginDB) as k: plugins = json.load(k)
		for key, value in plugins.items():
			if not "vod_" in value.get("identifier"): new_xml.append('  <setting default="%s" id="%s" label="%s" type="bool"/>' % (value.get("globalsearch"), value.get("identifier"), value.get("name")))
		new_xml.append(' </category>')
		new_xml.append('</settings>')
		with open(settingsxml, 'w', encoding='utf-8') as f: f.write('\n'.join(new_xml))
	if firststart or force:
		setup_tmdb_helper()
