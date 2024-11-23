# -*- coding: utf-8 -*-
import os, sys, xbmc, xbmcplugin, xbmcgui, xbmcaddon, requests, six, json, threading, urllib3
from six.moves.urllib.parse import parse_qsl, urlparse
from resources.lib import tools, settings
from resources.lib.gui.gui import cGui
settings.init()
sourcesFolder = os.path.join(xbmcaddon.Addon("plugin.video.xstream").getAddonInfo("path"), "sites")
sys.path.append(sourcesFolder)
session = requests.session()
dialog = xbmcgui.DialogProgress()
urllib3.disable_warnings()

def showFailedNotification(msg="Keine Streams gefunden"):
	tools.logger.info(msg)
	xbmc.executebuiltin("Notification(%s,%s,%s,%s)" % ("xStream Scraper",msg,5000,tools.addonInfo("icon")))
	o = xbmcgui.ListItem(xbmc.getInfoLabel("ListItem.Label"))
	xbmcplugin.setResolvedUrl(int(sys.argv[1]), False, o)

def cleantitle(title):
	a = tools.cParser.replace("(s\d\de\d\d|staffel \d+-\d+|\((\d{4})\))", "", title.lower())
	return tools.cParser.replace("( |-|:)", "", a)

def get_episodes(sources, s, e):
	episoden = []
	for count, source in enumerate(sources, 1):
		try:
			site = source["site"]
			dialog.update(int(count * 25 /len(sources)+50), "Filtere Seite %s..." % site)
			if dialog.iscanceled(): return showFailedNotification("Abgebrochen")
			tools.logger.info("Filtere %s" % site)
			for result in plugin(source):
				if "pisode" in result.keys() or result.get("mediaType") == "episode":
					for a in result.keys():
						if "pisode" in a:
							episode = tools.cParser.replace("[^0-9]", "", result[a])
							if episode and int(episode) == int(e):
								episoden.append(result)
				else:
					season = result.get("season")
					if season and int(season) == int(s):
						for results in plugin(result):
							if "pisode" in results.keys() or results.get("mediaType") == "episode":
								for b in results.keys():
									if "pisode" in b:
										episode = tools.cParser.replace("[^0-9]", "", results[b])
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
	sources = []; aPlugins = []; threads = []; oGui = cGui(); settings.collectMode = True; ntitle =""
	for w in [str(filename[:-3]) for filename in os.listdir(sourcesFolder) if not " vod" in filename and not filename.startswith('__') and filename.endswith('.py')]:
		if xbmcaddon.Addon().getSetting(w) == "true" :
			if isSerie: aPlugins.append({'id': w, 'name': w.capitalize()})
			else:
				if w != "serienstream": aPlugins.append({'id': w, 'name': w.capitalize()})
	dialog.create("xStream Scraper Suche gestartet ...", "Suche ...")
	for count, pluginEntry in enumerate(aPlugins):
		t = threading.Thread(target=_pluginSearch, args=(pluginEntry, sSearchText, isSerie, oGui), name=pluginEntry["name"])
		threads += [t]
		t.start()
	for count, t in enumerate(threads):
		tools.logger.info("Searching for %s at %s" % (sSearchText, t.name))
		dialog.update(int(count * 25 / len(threads)), "%s %s" % (t.name, " Suche abgeschlossen"))
		if dialog.iscanceled(): return showFailedNotification("Abgebrochen")
		t.join()
	settings.collectMode = False
	total = len(oGui.searchResults)
	if total == 0: return showFailedNotification("Nichts gefunden")
	for count, result in enumerate(oGui.searchResults, 1):
		settings.skip = "Ok"
		
		def set_skip(msg):
			if settings.skip == "Ok":
				settings.skip = msg
				
		title, originaltitle, language, quality, mediaType, year = cleantitle(result.get("title")), result.get("title"), result.get("language"), result.get("quality"), result.get("mediaType"), result.get("year")
		if not year and (' (19' in title or ' (20' in title):
			isMatch, aYear = tools.cParser.parse(title, '(.*?)\(((19\d{2}|20\d{2}))\)')
			if isMatch:
				title = aYear[0][0].strip()
				year = aYear[0][1]
		if not year and ('*19' in title or '*20' in title):
			isMatch, aYear = tools.cParser.parse(title, '(.*?)\*((19\d{2}|20\d{2}))\*')
			if isMatch:
				title = aYear[0][0].strip()
				year = aYear[0][1]
		if dialog.iscanceled(): return showFailedNotification("Abgebrochen")
		if language and language.lower() not in ["ger", "de", "deutsch"]: set_skip(" Wrong Language")
		if isSerie and mediaType == "movie": set_skip(" Wrong Media")
		if isSerie:
			isMatch, found = tools.cParser.parseSingleResult(title, "(season\d+|staffel\d+)")
			if isMatch:
				title = title.replace(found, "")
				ok, aMatches = tools.cParser.parseSingleResult(found, "\d+")
				if ok and int(season) != int(aMatches) : set_skip(" Wrong Season")
		if not isSerie and mediaType and mediaType  in ["tvshow", "series", "episode", "season"] : set_skip(" Wrong Media")
		if not isSerie and year and int(searchYear) !=0 and int(year) != int(searchYear): set_skip(" Wrong Year")
		if not isSerie and year and int(searchYear) !=0 and int(year) == int(searchYear): pass
		else:
			if tools.api_key:
				if cleantitle(title) not in searchtitles: set_skip(" Wrong Name")
			elif cleantitle(title) not in cleantitle(sSearchText): set_skip(" Wrong Name")
		if "filmpalast" in result.get("site"):
			if ntitle == title: set_skip(" Duplicate")
			else: ntitle = title
		dialog.update(int(count*multi/total + 25), "%s von %s\n%s: %s" % (count, total, settings.skip, originaltitle))
		if settings.skip == "Ok": sources.append(result)
	return sources

def callApi(action, params, method="GET", headers=None, **kwargs):
	tools.logger.debug("Action:%s params: %s" % (action,json.dumps(params)))
	if not headers: headers = dict()
	headers["auth-token"] = tools.getAuthSignature()
	resp = session.request(method, ("https://www2.vavoo.to/ccapi/" + action), params=params, headers=headers, **kwargs)
	resp.raise_for_status()
	data = resp.json()
	tools.logger.debug("callApi res: %s" % json.dumps(data))
	return data

def callApi2(action, params):
	res = callApi(action, params, verify=False)
	while True:
		if type(res) is not dict or "id" not in res or "data" not in res: return res
		data = res["data"]
		if type(data) is dict and data.get("type") == "fetch":
			params = data["params"]
			body = params.get("body")
			headers = params.get("headers")
			try: resp = session.request(params.get("method", "GET").upper(), data["url"], headers={k:v[0] if type(v) in (list, tuple) else v for k, v in headers.items()} if headers else None, data=body.decode("base64") if body else None, allow_redirects=params.get("redirect", "follow") == "follow")
			except: return
			headers = dict(resp.headers)
			resData = {"status": resp.status_code, "url": resp.url, "headers": headers, "data": b64encode(resp.content).decode("utf-8").replace("\n", "") if data["body"] else None}
			tools.logger.debug(json.dumps(resData))
			tools.logger.debug(resp.text)
			res = callApi("res", {"id": res["id"]}, method="POST", json=resData, verify=False)
		elif type(data) is dict and data.get("error"):
			tools.logger.error(data.get("error"))
			return
		else: return data
	return

def _get(_type, _id, season, episode):
	import resolveurl as resolver
	mirrors = callApi2("links", {"id": "movie.%s" % _id, "language": "de"}) if _type.startswith("movie") else callApi2("links", {"id": "series.%s.%s.%s" % (_id, season, episode), "language": "de"})
	if not mirrors: return
	newurllist = []
	for i ,a in enumerate(mirrors, 1):
		try:
			a['hoster'] = urlparse(a['url']).netloc
			if 'streamz' in a['hoster']: continue # den hoster kann man vergessen
			if 'language' in a:
				if 'de' in a['language'] :
					if "1080p" in a['name']:
						a['name'] = "%s %s" %(a['hoster'], '1080p')
						a['weight'] = 1080+i
					elif "720p" in a['name']:
						a['name'] = "%s %s" %(a['hoster'], '720p')
						a['weight'] = 720+i
					elif "480p" in a['name']:
						a['name'] = "%s %s" %(a['hoster'], '480p')
						a['weight'] = 480+i
					elif "360p" in a['name']:
						a['name'] = "%s %s" %(a['hoster'], '360p')
						a['weight'] = 360+i
					else:
						#a['name'] = "%s %s" %(a['hoster'], 'SD')
						a['name'] = a['hoster']
						a['weight'] = i
					newurllist.append(a)
			else:
				a['name'] = a['hoster']
				a['weight'] = i
				newurllist.append(a)
		except: pass
	mirrors = list(sorted(newurllist, key=lambda x: x['weight'], reverse=True))
	# Nummerierung neu
	for i, a in enumerate(mirrors, 1):
		a['name'] = "%s. %s" % (i, a['name'])
	if xbmcaddon.Addon().getSetting('stream_select') == '0':
		captions = [ mirror['name'] for mirror in mirrors ]
		index = xbmcgui.Dialog().select("VAVOO", captions)
		if index == -1: return # xbmc.executebuiltin('Action(ParentDir)')
		mirrors = [mirrors[index]] if xbmcaddon.Addon().getSetting('auto_try_next_stream') !="true" else mirrors[index:]
	dialog.create("Suche gestartet ...", "Teste Streams")
	for count, mirror in enumerate(mirrors, 1):
		dialog.update(int(count/len(mirrors)*100), "Teste Stream %s/%s" % (count, len(mirrors)))
		if dialog.iscanceled(): return showFailedNotification("Abgebrochen")
		try:
			if resolver and resolver.relevant_resolvers(urlparse(mirror['url']).hostname):
				url = resolver.resolve(mirror['url'])
			elif 'hd-stream' in mirror['url']:
				id = mirror['url'].split('/')[-1]
				posturl = 'https://hd-stream.to/api/source/%s' % id
				data = {'r': 'https://kinoger.to/', 'd': 'hd-stream.to'}
				response = session.post(posturl, data)
				if response.status_code != 200: continue
				links = response.json()['data']
				links = sorted(links, key=lambda x: int(x['label'].replace('p', '')), reverse=True)
				url = links[0]['file']
			else:
				res = callApi2('open', {'link': mirror['url']})
				url = res[-1].get('url')
			if url:
				headers = {}; params = {}
				newurl = url
				if "|" in newurl:
					newurl, headers = newurl.split("|")
					headers = dict(parse_qsl(headers))
				if "?" in newurl:
					newurl, params = newurl.split("?")
					params = dict(parse_qsl(params))
				res = session.get(newurl, headers=headers, params=params, stream=True)
				if not res.ok: continue
				if "text" in res.headers.get("Content-Type","text"): continue
				else:
					tools.logger.info("Spiele :%s" % url)
					return url
		except: continue
	return False

def play(_type, _id, season, episode):
	if xbmcaddon.Addon().getSetting('vavoo') == 'true':
		from lib import vjackson
		#url = xbmc.executebuiltin('RunPlugin(plugin://plugin.video.vavooto/?action=get&id=movie.%s&find=true)' % _id) if _type == "movie" else xbmc.executebuiltin('RunPlugin(plugin://plugin.video.vavooto/?action=get&id=%s.%s&s=%s&e=%s&find=true)' %(_type, _id,season, episode))
		param = {"id": "movie.%s" %_id,  "find":"true"} if _type == "movie" else {"id": "series.%s" %_id, "s": season, "e": episode,  "find":"true"}
		url = vjackson._get(param)
		if url: return _play(url)
	data = tools.get_data({"id":"%s.%s" % (_type, _id)})
	if _type == "tv": isSerie, name, releaseDate = True, data["name"], data["first_air_date"]
	else: isSerie, name, releaseDate = False, data["title"], data["release_date"]
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
		dialog.update(int(count/total*100), "Teste Stream %s/%s" % (count, total))
		if dialog.iscanceled(): return showFailedNotification("Abgebrochen")
		import resolveurl as resolver
		try:
			if k.get("resolved"): url = k["link"]
			else:
				stream = plugin(k, True)[0]
				url =  resolver.resolve(stream["streamUrl"])
			if not isinstance(url, str): raise Exception("kein Link")
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
			else:
				tools.logger.info("Spiele :%s" % url)
				return _play(url)
		except Exception as e:
			tools.logger.error(e)
			import traceback
			tools.logger.debug(traceback.format_exc())
		finally: del resolver
	dialog.close()
	return showFailedNotification()

def _play(url):
	try:dialog.close()
	except: pass
	o = xbmcgui.ListItem(xbmc.getInfoLabel("ListItem.Label"))
	o.setPath(url)
	o.setProperty("IsPlayable", "true")
	if ".m3u8" in url:
		if six.PY2: o.setProperty("inputstreamaddon", "inputstream.adaptive")
		else: o.setProperty("inputstream", "inputstream.adaptive")
		o.setProperty("inputstream.adaptive.manifest_type", "hls")
	xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, o)