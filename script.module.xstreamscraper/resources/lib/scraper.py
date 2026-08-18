# -*- coding: utf-8 -*-
import os, sys, xbmc, xbmcplugin, xbmcgui, xbmcaddon, requests, json, concurrent.futures, urllib3
from six.moves.urllib.parse import parse_qsl, urlparse
from resources.lib import tools, settings
from resources.lib.gui.gui import cGui
import resources
import resources.lib
import resources.lib.gui
import resources.lib.handler
settings.init()
xstreamFolder = xbmcaddon.Addon("plugin.video.xstream").getAddonInfo("path")
sourcesFolder = os.path.join(xstreamFolder, "sites")
sys.path.append(sourcesFolder)
sys.path.append(xstreamFolder)

# The scraper ships compatibility replacements in its own resources package.
# Keep those first, but also expose modules added by newer xStream versions.
for package, folder in (
	(resources, os.path.join(xstreamFolder, "resources")),
	(resources.lib, os.path.join(xstreamFolder, "resources", "lib")),
	(resources.lib.gui, os.path.join(xstreamFolder, "resources", "lib", "gui")),
	(resources.lib.handler, os.path.join(xstreamFolder, "resources", "lib", "handler")),
):
	if folder not in package.__path__:
		package.__path__.append(folder)
session = requests.session()
dialog = xbmcgui.DialogProgress()
urllib3.disable_warnings()

def showFailedNotification(msg="Keine Streams gefunden"):
	tools.logger.info(msg)
	xbmc.executebuiltin("Notification(%s,%s,%s,%s)" % ("xStream Scraper",msg,5000,tools.addonInfo("icon")))
	o = xbmcgui.ListItem(xbmc.getInfoLabel("ListItem.Label"))
	xbmcplugin.setResolvedUrl(int(sys.argv[1]), False, o)

def cleantitle(title):
	a = tools.cParser.replace(r"(s\d\de\d\d|staffel \d+-\d+|\((\d{4})\))", "", title.lower())
	return tools.cParser.replace("( |-|:)", "", a)

def _episode_number(result):
	for key, value in result.items():
		if "pisode" in key.lower():
			episode = tools.cParser.replace("[^0-9]", "", str(value))
			if episode:
				return episode
	if result.get("mediaType") == "episode":
		for value in (result.get("sUrl"), result.get("url"), result.get("title")):
			if not value:
				continue
			is_match, episode = tools.cParser.parseSingleResult(str(value), r"(?:episode|folge)[\s_-]*(\d+)")
			if is_match:
				return episode
	return None

def get_episodes(sources, s, e):
	episoden = []
	for count, source in enumerate(sources, 1):
		try:
			site = source["site"]
			dialog.update(int(count * 25 /len(sources)+50), "Filtere Seite %s..." % site)
			if dialog.iscanceled(): return showFailedNotification("Abgebrochen")
			tools.logger.info("Filtere %s" % site)
			for result in plugin(source) or []:
				if "pisode" in result.keys() or result.get("mediaType") == "episode":
					episode = _episode_number(result)
					if episode and int(episode) == int(e):
						episoden.append(result)
				else:
					season = result.get("season")
					if season and int(season) == int(s):
						for results in plugin(result) or []:
							if "pisode" in results.keys() or results.get("mediaType") == "episode":
								episode = _episode_number(results)
								if episode and int(episode) == int(e):
									episoden.append(results)
		except Exception as e:
			tools.logger.error(e)
			import traceback
			tools.logger.debug(traceback.format_exc())
	return episoden
	
def get_hosters(sources, isSerie, season, episode):
	newsources, hosters, temp = sources, [], []
	if isSerie: newsources = get_episodes(sources, season, episode)
	for count, source in enumerate(newsources, 1):
		site = source["site"]
		if dialog.iscanceled(): return showFailedNotification("Abgebrochen")
		dialog.update(int(count * 25 /len(newsources)+75), "Suche nach Hostern auf %s" % source["site"])
		p = plugin(source, True)
		if p:
			function = p[-1]
			del p[-1]
			for a in p:
				a["site"] = site
				a["function"] = function
				if a["link"] not in temp:
					temp.append(a["link"])
					hosters.append(a)
	dialog.close()
	return hosters

def _pluginSearch(pluginEntry, sSearchText, isSerie, oGui):
	try:
		plugin = __import__(pluginEntry["id"], globals(), locals())
		#if "vod" in pluginEntry["id"]: searchfunction = "_searchSeries" if isSerie else "_searchMovies"
		#else: searchfunction = "_search"
		searchfunction = "_search"
		function = getattr(plugin, searchfunction)(oGui, sSearchText)
	except Exception as e:
		tools.logger.error(pluginEntry["name"] + ": search failed, Error = %s" % e)
		import traceback
		tools.logger.debug(traceback.format_exc())

def plugin(source, force = False):
	settings.aDirectory = []
	link = source.get("link")
	site = source.get("site")
	function = source.get("function")
	settings.urlparams = source
	try:
		b = __import__(site)
		if link:
			return getattr(b, function)(link)
		else: function = getattr(b, function)()
		if not force and not function: function = settings.aDirectory
		return function
	except Exception as e:
		import traceback
		tools.logger.error(traceback.format_exc())

def searchGlobal(sSearchText, searchtitles, isSerie, _type, _id, season, episode, searchYear):
    multi = 25 if isSerie else 50
    sources = []
    aPlugins = []
    oGui = cGui()
    settings.collectMode = True
    ntitle = ""

    for w in [str(filename[:-3]) for filename in os.listdir(sourcesFolder) if " vod" not in filename and not filename.startswith('__') and filename.endswith('.py')]:
        if xbmcaddon.Addon().getSetting(w) == "true":
            if isSerie:
                aPlugins.append({'id': w, 'name': w.capitalize()})
            elif w != "serienstream":
                aPlugins.append({'id': w, 'name': w.capitalize()})

    dialog.create("xStream Scraper Suche gestartet ...", "Suche ...")

    def _wrapped_pluginSearch(pluginEntry):
        _pluginSearch(pluginEntry, sSearchText, isSerie, oGui)
        return pluginEntry["name"]

    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_to_plugin = {executor.submit(_wrapped_pluginSearch, pluginEntry): pluginEntry for pluginEntry in aPlugins}
        for count, future in enumerate(concurrent.futures.as_completed(future_to_plugin)):
            pluginEntry = future_to_plugin[future]
            try:
                plugin_name = future.result()
                tools.logger.info("Searching for %s at %s" % (sSearchText, plugin_name))
                dialog.update(int(count * 25 / len(aPlugins)), "%s %s" % (plugin_name, " Suche abgeschlossen"))
                if dialog.iscanceled():
                    return showFailedNotification("Abgebrochen")
            except Exception as e:
                tools.logger.error(f"Fehler bei Plugin {pluginEntry['name']}: {e}")

    settings.collectMode = False
    total = len(oGui.searchResults)
    if total == 0:
        return showFailedNotification("Nichts gefunden")

    for count, result in enumerate(oGui.searchResults, 1):
        settings.skip = "Ok"

        def set_skip(msg):
            if settings.skip == "Ok":
                settings.skip = msg

        title, originaltitle, language, quality, mediaType, year = cleantitle(result.get("title")), result.get("title"), result.get("language"), result.get("quality"), result.get("mediaType"), result.get("year")

        if not year and (' (19' in title or ' (20' in title):
            isMatch, aYear = tools.cParser.parse(title, r'(.*?)\(((19\d{2}|20\d{2}))\)')
            if isMatch:
                title = aYear[0][0].strip()
                year = aYear[0][1]

        if not year and ('*19' in title or '*20' in title):
            isMatch, aYear = tools.cParser.parse(title, r'(.*?)\*((19\d{2}|20\d{2}))\*')
            if isMatch:
                title = aYear[0][0].strip()
                year = aYear[0][1]

        if dialog.iscanceled():
            return showFailedNotification("Abgebrochen")

        if language and language.lower() not in ["ger", "de", "deutsch"]:
            set_skip(" Wrong Language")

        if isSerie and mediaType == "movie":
            set_skip(" Wrong Media")

        if isSerie:
            isMatch, found = tools.cParser.parseSingleResult(title, r"(season\d+|staffel\d+)")
            if isMatch:
                title = title.replace(found, "")
                ok, aMatches = tools.cParser.parseSingleResult(found, r"\d+")
                if ok and int(season) != int(aMatches):
                    set_skip(" Wrong Season")

        if not isSerie and mediaType and mediaType in ["tvshow", "series", "episode", "season"]:
            set_skip(" Wrong Media")

        if not isSerie and year and int(searchYear) != 0 and int(year) != int(searchYear):
            set_skip(" Wrong Year")

        if not isSerie and year and int(searchYear) != 0 and int(year) == int(searchYear):
            pass
        else:
            if tools.api_key:
                if cleantitle(title) not in searchtitles:
                    set_skip(" Wrong Name")
            elif cleantitle(title) not in cleantitle(sSearchText):
                set_skip(" Wrong Name")

        if "filmpalast" in result.get("site"):
            if ntitle == title:
                set_skip(" Duplicate")
            else:
                ntitle = title

        dialog.update(int(count * multi / total + 25), "%s von %s\n%s: %s" % (count, total, settings.skip, originaltitle))
        if settings.skip == "Ok":
            sources.append(result)

    return sources

def play(_type, _id, season, episode):
	data = tools.get_data({"id":"%s.%s" % (_type, _id)})
	if _type == "tv": isSerie, name, releaseDate = True, data["name"], data["first_air_date"]
	else: isSerie, name, releaseDate = False, data["title"], data["release_date"]
	if xbmcaddon.Addon().getSetting('vavoo') == 'true':
		from vavoo import vjackson
		#url = xbmc.executebuiltin('RunPlugin(plugin://plugin.video.vavooto/?action=get&id=movie.%s&find=true)' % _id) if _type == "movie" else xbmc.executebuiltin('RunPlugin(plugin://plugin.video.vavooto/?action=get&id=%s.%s&s=%s&e=%s&find=true)' %(_type, _id,season, episode))
		param = {"id": "movie.%s" %_id, "n":name, "find":"true"} if _type == "movie" else {"id": "series.%s" %_id, "n":name, "s": season, "e": episode,  "find":"true"}
		url = vjackson.get(param)
		if url: return _play(url)
	searchYear=int(releaseDate[:4])
	results = data.get("alternative_titles", {}).get("results")
	searchtitles = [a["title"] for a in results] if results else []
	searchtitles.append(name)
	titles = [cleantitle(a) for a in searchtitles]
	sources = searchGlobal(name.split(":")[0], titles, isSerie, _type, _id, season, episode, searchYear)
	if not sources: return showFailedNotification("keine Quellen")
	hosters = get_hosters(sources, isSerie, season, episode)
	if not hosters: return showFailedNotification("keine Hoster")
	total = len(hosters)
	dialog.create("Suche gestartet ...", "Teste Streams")
	for count, k in enumerate(hosters, 1):
		dialog.update(int(count/total*100), "Teste Stream %s/%s\nSeite: %s\nLink: %s" % (count, total, k["site"], k["link"]))
		if dialog.iscanceled(): return showFailedNotification("Abgebrochen")
		import resolveurl as resolver
		try:
			if k.get("resolved"): url = k["link"]
			else:
				stream = plugin(k, True)[0]
				url =  resolver.resolve(stream["streamUrl"])
			if not isinstance(url, str): 
				continue
				#raise Exception("kein Link")
			headers = {}; params = {}
			newurl = url
			if "|" in newurl:
				newurl, headers = newurl.split("|")
				headers = dict(parse_qsl(headers))
			if "?" in newurl:
				newurl, params = newurl.split("?")
				params = dict(parse_qsl(params))
			res = session.get(newurl, headers=headers, params=params, stream=True)
			if not res.ok: raise Exception("Kann Seite nicht erreichen")
			if "text" in res.headers.get("Content-Type","text"): raise Exception("Keine Videodatei")
		except Exception as e:
			tools.logger.error(e)
			import traceback
			tools.logger.debug(traceback.format_exc())
			continue
		else:
			tools.logger.info("Spiele :%s" % url)
			del resolver
			dialog.close()
			return _play(url)
	del resolver
	dialog.close()
	return showFailedNotification()

def _play(url):
	o = xbmcgui.ListItem(xbmc.getInfoLabel("ListItem.Label"))
	o.setProperty("IsPlayable", "true")
	if ".m3u8" in url:
		o.setProperty("inputstream", "inputstream.adaptive")
		o.setProperty('inputstream.adaptive.config', '{"ssl_verify_peer":false}')
		if "|" in url:
			url, headers = url.split("|")
			o.setProperty('inputstream.adaptive.common_headers', headers)
			o.setProperty('inputstream.adaptive.stream_headers', headers)
		#if "?" in url:
			#url, params = url.split("?")
			#o.setProperty('inputstream.adaptive.stream_params', params)
	o.setPath(url)
	xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, o)
