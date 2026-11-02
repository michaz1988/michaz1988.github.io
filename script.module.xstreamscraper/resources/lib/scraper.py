# -*- coding: utf-8 -*-
import os, socket, sys, time, xbmc, xbmcplugin, xbmcgui, xbmcaddon, concurrent.futures, urllib3
from resources.lib import settings, streamTest
from resources.lib.streamTest import Cancelled, StreamTimeout
from resources.lib.xstreamBridge import sourcesFolder
from resources.lib import streamHistory
from resources.lib.gui.gui import cGui
from resources.lib.handler.requestHandler import cRequestHandler, quietWindows
from resources.lib.logger import logger
from resources.lib.tools import cParser
settings.init()
api_key = "86dd18b04874d9c94afadde7993d94e3"
PRIORITY_SITE = "serienstream"

class ProgressDialog:
	"""Fortschritt als normales Fenster oder, je nach Einstellung, im Hintergrund.
	Das Hintergrund-Fenster kennt keinen Abbrechen-Knopf und zeigt nur eine Zeile."""
	def __init__(self):
		self._dialog = None
		self._background = False
		self._heading = ""

	def create(self, heading, message=""):
		self.close()
		self._background = xbmcaddon.Addon().getSetting("progress_background") == "true"
		self._heading = heading
		self._dialog = xbmcgui.DialogProgressBG() if self._background else xbmcgui.DialogProgress()
		self._dialog.create(heading, message)

	def update(self, percent, message=""):
		if not self._dialog: return
		if self._background: self._dialog.update(percent, self._heading, message.replace("\n", " | "))
		else: self._dialog.update(percent, message)

	def iscanceled(self):
		return bool(self._dialog) and not self._background and self._dialog.iscanceled()

	def close(self):
		if self._dialog: self._dialog.close()
		self._dialog = None

dialog = ProgressDialog()
urllib3.disable_warnings()

def showFailedNotification(msg="Keine Streams gefunden"):
	logger.info(msg)
	xbmc.executebuiltin("Notification(%s,%s,%s,%s)" % ("xStream Scraper",msg,5000,xbmcaddon.Addon().getAddonInfo("icon")))
	o = xbmcgui.ListItem(xbmc.getInfoLabel("ListItem.Label"))
	xbmcplugin.setResolvedUrl(int(sys.argv[1]), False, o)

def cleantitle(title):
	a = cParser.replace(r"(s\d\de\d\d|staffel \d+-\d+|\((\d{4})\))", "", title.lower())
	return cParser.replace("( |-|:)", "", a)

def _episode_number(result):
	for key, value in result.items():
		if "pisode" in key.lower():
			episode = cParser.replace("[^0-9]", "", str(value))
			if episode:
				return episode
	if result.get("mediaType") == "episode":
		for value in (result.get("sUrl"), result.get("url"), result.get("title")):
			if not value:
				continue
			is_match, episode = cParser.parseSingleResult(str(value), r"(?:episode|folge)[\s_-]*(\d+)")
			if is_match:
				return episode
	return None

def get_episodes(sources, s, e):
	episoden = []
	for count, source in enumerate(sources, 1):
		try:
			site = source["site"]
			dialog.update(int(count * 25 /len(sources)+50), "Filtere Seite %s..." % site)
			if dialog.iscanceled(): raise Cancelled()
			logger.info("Filtere %s" % site)
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
			logger.error(e)
			import traceback
			logger.error(traceback.format_exc())
	return episoden
	
def get_hosters(sources, isSerie, season, episode):
	newsources, hosters, temp = sources, [], []
	if isSerie: newsources = get_episodes(sources, season, episode)
	for count, source in enumerate(newsources, 1):
		site = source["site"]
		if dialog.iscanceled(): raise Cancelled()
		dialog.update(int(count * 25 /len(newsources)+75), "Suche nach Hostern auf %s" % source["site"])
		p = plugin(source, True)
		if p:
			function = p[-1]
			del p[-1]
			for a in p:
				# Die Seite liefert jede Folge auch auf Englisch und als Ger-Sub, unter demselben Hosternamen.
				if site == PRIORITY_SITE and a.get("languageCode") != "(DE)": continue
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
		logger.error(pluginEntry["name"] + ": search failed, Error = %s" % e)
		import traceback
		logger.error(traceback.format_exc())

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
		logger.error(traceback.format_exc())

def searchGlobal(sSearchText, searchtitles, isSerie, _type, _id, season, episode, searchYear, siteFilter=None):
    multi = 25 if isSerie else 50
    sources = []
    aPlugins = []
    oGui = cGui()
    settings.collectMode = True
    ntitle = ""

    for w in [str(filename[:-3]) for filename in os.listdir(sourcesFolder) if " vod" not in filename and not filename.startswith('__') and filename.endswith('.py')]:
        if xbmcaddon.Addon().getSetting(w) == "true" and (not siteFilter or siteFilter(w)):
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
                logger.info("Searching for %s at %s" % (sSearchText, plugin_name))
                dialog.update(int(count * 25 / len(aPlugins)), "%s %s" % (plugin_name, " Suche abgeschlossen"))
                if dialog.iscanceled():
                    raise Cancelled()
            except Exception as e:
                logger.error(f"Fehler bei Plugin {pluginEntry['name']}: {e}")

    settings.collectMode = False
    total = len(oGui.searchResults)
    if total == 0:
        return []

    for count, result in enumerate(oGui.searchResults, 1):
        settings.skip = "Ok"

        def set_skip(msg):
            if settings.skip == "Ok":
                settings.skip = msg

        title, originaltitle, language, quality, mediaType, year = cleantitle(result.get("title")), result.get("title"), result.get("language"), result.get("quality"), result.get("mediaType"), result.get("year")

        if not year and (' (19' in title or ' (20' in title):
            isMatch, aYear = cParser.parse(title, r'(.*?)\(((19\d{2}|20\d{2}))\)')
            if isMatch:
                title = aYear[0][0].strip()
                year = aYear[0][1]

        if not year and ('*19' in title or '*20' in title):
            isMatch, aYear = cParser.parse(title, r'(.*?)\*((19\d{2}|20\d{2}))\*')
            if isMatch:
                title = aYear[0][0].strip()
                year = aYear[0][1]

        if dialog.iscanceled():
            raise Cancelled()

        if language and language.lower() not in ["ger", "de", "deutsch"]:
            set_skip(" Wrong Language")

        if isSerie and mediaType == "movie":
            set_skip(" Wrong Media")

        if isSerie:
            isMatch, found = cParser.parseSingleResult(title, r"(season\d+|staffel\d+)")
            if isMatch:
                title = title.replace(found, "")
                ok, aMatches = cParser.parseSingleResult(found, r"\d+")
                if ok and int(season) != int(aMatches):
                    set_skip(" Wrong Season")

        if not isSerie and mediaType and mediaType in ["tvshow", "series", "episode", "season"]:
            set_skip(" Wrong Media")

        if not isSerie and year and int(searchYear) != 0 and int(year) != int(searchYear):
            set_skip(" Wrong Year")

        if not isSerie and year and int(searchYear) != 0 and int(year) == int(searchYear):
            pass
        else:
            if api_key:
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

def get_details(_type, _id):
	url = "https://api.themoviedb.org/3/%s/%s?api_key=%s&language=de&region=DE&append_to_response=alternative_titles" % (_type, _id, api_key)
	oRequest = cRequestHandler(url)
	oRequest.cacheTime = 60 * 60 * 24 * 14
	return oRequest.requestJson()

def play(_type, _id, season, episode):
	# Keine blockierenden Fehlerfenster von xStream, solange der Scraper automatisch sucht.
	with quietWindows():
		try:
			return _search_and_play(_type, _id, season, episode)
		except Cancelled:
			dialog.close()
			return showFailedNotification("Abgebrochen")

def _cancelled():
	return dialog.iscanceled() or xbmc.Monitor().abortRequested()

def _vavoo_param(_type, _id, name, season, episode):
	if _type == "movie": return {"id": "movie.%s" %_id, "n":name, "find":"true"}
	return {"id": "series.%s" %_id, "n":name, "s": season, "e": episode, "find":"true"}

def _vavoo_mirrors(param):
	from vavoo import vjackson
	try:
		mirrors = streamTest.runLimited(lambda: vjackson.get_mirrors(param), cancelled=_cancelled) or []
	except Exception as e:
		logger.error("VAVOO: %s" % e)
		return []
	return [{"site": "vavoo", "name": a["hoster"], "link": a["url"], "mirror": a} for a in mirrors]

def _manual_vavoo():
	# Stream-Auswahl von Hand in den VAVOO-Einstellungen: dann entscheidet der Nutzer, nicht die Reihenfolge.
	return xbmcaddon.Addon("plugin.video.vavooto").getSetting("stream_select") == "0"

def _resolve(candidate):
	if candidate.get("mirror"):
		from vavoo import vjackson
		return vjackson.resolve(candidate["mirror"])
	if candidate.get("resolved"): return candidate["link"]
	stream = plugin(candidate, True)[0]
	if stream.get("resolved"): return stream["streamUrl"]
	import resolveurl as resolver
	return resolver.resolve(stream["streamUrl"])

def _test(candidate):
	"""Aufloesen und pruefen teilen sich dasselbe Zeitlimit. Liefert die spielbare URL oder None."""
	deadline = time.monotonic() + streamTest.LIMIT
	url = _resolve(candidate)
	if not isinstance(url, str) or not url: return None
	streamTest.check(url, deadline)
	return url

def _first_working(candidates, tried):
	"""Testet die Kandidaten der Reihe nach und liefert (Kandidat, URL) des ersten funktionierenden."""
	total = len(candidates)
	if not total: return None, None
	dialog.create("Suche gestartet ...", "Teste Streams")
	import resolveurl # Der erste Import dauert und soll nicht vom Limit des ersten Streams abgehen.
	timeout = socket.getdefaulttimeout()
	socket.setdefaulttimeout(streamTest.LIMIT) # Damit auch aufgegebene Tests von selbst enden.
	try:
		for count, candidate in enumerate(candidates, 1):
			tried.append(candidate)
			dialog.update(int(count/total*100), "Teste Stream %s/%s\nSeite: %s\nLink: %s" % (count, total, candidate["site"], candidate["link"]))
			if _cancelled(): raise Cancelled()
			try:
				url = streamTest.runLimited(lambda c=candidate: _test(c), cancelled=_cancelled)
			except StreamTimeout as e:
				logger.info("Stream uebersprungen (%s): %s" % (e, candidate["link"]))
				continue
			except Exception as e:
				logger.info("Stream defekt (%s): %s" % (e, candidate["link"]))
				continue
			if url: return candidate, url
	finally:
		socket.setdefaulttimeout(timeout)
		dialog.close()
	return None, None

def _search_and_play(_type, _id, season, episode):
	data = get_details(_type, _id)
	if not data: return showFailedNotification("TMDB nicht erreichbar")
	if _type == "tv": isSerie, name, releaseDate = True, data["name"], data["first_air_date"]
	else: isSerie, name, releaseDate = False, data["title"], data["release_date"]
	mirrors = []
	if xbmcaddon.Addon().getSetting('vavoo') == 'true':
		param = _vavoo_param(_type, _id, name, season, episode)
		if _manual_vavoo():
			from vavoo import vjackson
			url = vjackson.get(param)
			if url: return _play(url)
		else:
			mirrors = _vavoo_mirrors(param)
	# Pro Film bzw. Folge: nur wer genau denselben Titel noch einmal startet, bekommt einen anderen Stream.
	key = "tv.%s.%s.%s" % (_id, season, episode) if isSerie else "movie.%s" % _id
	usedStreams = streamHistory.used(key)
	tried = []
	results = data.get("alternative_titles", {}).get("results")
	searchtitles = [a["title"] for a in results] if results else []
	searchtitles.append(name)
	# Der deutsche TMDb-Titel kann einen Zusatz haben ("MobLand: Familie bis aufs Blut"), die Seite fuehrt das Original.
	original = data.get("original_name") or data.get("original_title")
	if original: searchtitles.append(original)
	titles = [cleantitle(a) for a in searchtitles]
	def find(siteFilter):
		sources = searchGlobal(name.split(":")[0], titles, isSerie, _type, _id, season, episode, int(releaseDate[:4]), siteFilter)
		hosters = get_hosters(sources, isSerie, season, episode) if sources else []
		dialog.close()
		return sources, hosters
	def fresh(candidates):
		return [c for c in candidates if streamHistory.streamId(c) not in usedStreams]
	hasPriority = isSerie and xbmcaddon.Addon().getSetting(PRIORITY_SITE) == "true"
	priority = find(lambda site: site == PRIORITY_SITE)[1] if hasPriority else []
	# Erst die ungespielten Streams der Vorrang-Seite und von VAVOO, das spart die langsame Suche auf allen Seiten.
	candidate, url = _first_working(fresh(priority) + fresh(mirrors), tried)
	if not url:
		sources, hosters = find((lambda site: site != PRIORITY_SITE) if hasPriority else None)
		candidates = hosters + [c for c in priority + mirrors if c not in tried]
		if not candidates:
			return showFailedNotification("keine Hoster" if sources else "keine Quellen")
		candidate, url = _first_working(streamHistory.order(candidates, usedStreams), tried)
	if not url: return showFailedNotification()
	logger.info("Spiele :%s" % url)
	_play(url)
	streamHistory.remember(key, candidate)

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
