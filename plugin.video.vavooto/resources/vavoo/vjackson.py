# -*- coding: utf-8 -*-
from vavoo.utils import *

urllib3.disable_warnings()
BASEURL = "https://vavoo.to/ccapi/"

def menu(params):
	set_content("files")
	addDir2("Live", "DefaultAddonPVRClient", "live")
	addDir2("Filme", "DefaultMovies", "indexMovie")
	addDir2("Serien", "DefaultTVShows", "indexSerie")
	end()

def indexMovie(params):
	set_content("movies")
	addDir2("Beliebte Filme", "DefaultMovies", "show", id="movie.popular")
	addDir2("Angesagte Filme", "DefaultMovies", "show", id="movie.trending")
	addDir2("Genres", "DefaultGenre", "genres", id="movie.popular")
	addDir2("Suche", "DefaultAddonsSearch", "search", id="movie.popular")
	end()

def indexSerie(params):
	set_content("tvshows")
	addDir2("Beliebte Serien", "DefaultTVShows", "show", id="series.popular")
	addDir2("Angesagte Serien", "DefaultTVShows", "show", id="series.trending")
	addDir2("Genres", "DefaultGenre", "genres", id="series.popular")
	addDir2("Suche", "DefaultAddonsSearch", "search", id="series.popular")
	end()

def live(params):
	try: lines = json.loads(getSetting("favs"))
	except (TypeError, ValueError):
		lines = []
	if len(lines)>0: addDir2("Live - Favoriten", "DefaultAddonPVRClient", "favchannels")
	addDir2("Live - Alle", "DefaultAddonPVRClient", "channels")
	addDir2("Live - A bis Z", "DefaultAddonPVRClient", "a_z_tv")
	addDir2("Live - Gruppen", "DefaultAddonPVRClient", "group_tv")
	end()

def group_tv(params):
	if params.get("type")=="vavoo":
		from vavoo.vavoo_tv import vavoo_groups
		gruppen, hash = vavoo_groups()
		for group in gruppen: 
			addDir2(group.encode().decode("ascii", errors="ignore"), "DefaultAddonPVRClient", "channels", type="vavoo", group=group)
	elif params.get("type")=="stalker":
		from vavoo.stalker import StalkerPortal
		portal = StalkerPortal(get_cache_or_setting("stalkerurl"), get_cache_or_setting("mac"))
		gruppen = portal.genres()
		for title, groupid in  gruppen.items():
			addDir2(title.encode().decode("ascii", errors="ignore"), "DefaultAddonPVRClient", "channels", type="stalker", group=groupid)
	else:
		active_sources = []
		if getSetting("vavoo") == "true":
			active_sources.append(("VAVOO - GRUPPEN", "vavoo"))
		if getSetting("stalker") == "true":
			active_sources.append(("STALKER - GRUPPEN", "stalker"))

		if len(active_sources) > 1:
			for title, stype in active_sources:
				addDir2(title, "DefaultAddonPVRClient", "group_tv", type=stype)
		elif len(active_sources) == 1:
			group_tv({"type": active_sources[0][1]})
		else:
			return
	end()

def a_z_tv(params):
	from collections import defaultdict
	from vavoo import vjlive
	results = vjlive.getchannels()
	res = defaultdict(dict)
	for key, val in results.items():
		prefix, number = key[:1].upper() if key[:1].isalpha() else "#", key
		res[prefix][number] = val
	res = dict(sorted(res.items()))
	for key, val in res.items():
		addDir2(key, "DefaultAddonPVRClient", "channels", items=json.dumps(val))
	end()

def show(params):
	is_catalog_search = params["id"] in ("tmdb.movie", "tmdb.series")
	data = catalog_list(params)
	content, next = "seasons", data["next"]
	data = data["data"]
	cat = params.get("genre") or ("Suchergebnisse" if is_catalog_search else ("Beliebte Serien" if "popular" in params["id"] else "Angesagte Serien"))
	if params["id"].startswith("movie") or params["id"] == "tmdb.movie":
		cat = cat.replace("Serien", "Filme")
		content = "movies"
	set_content(content)
	set_category(cat)
	paramslist = [{"action": "get" if e["id"].startswith("movie") else "seasons" ,"id":e["id"], "n":e["name"]} for e in data]
	with ThreadPoolExecutor(max_workers=min(10, max(len(paramslist), 1))) as executor:
		future_to_url = {executor.submit(createListItem, urlparams):urlparams for urlparams in paramslist}
		for future in as_completed(future_to_url):
			urlparams = future_to_url[future]
			o = future.result()
			if o:
				isFolder = False if o.getProperty("IsPlayable") == "true" else True
				if not isFolder: o.addContextMenuItems([("Manuelle Stream Auswahl", "RunPlugin(%s&manual=true)" % url_for(urlparams))])
				add(urlparams, o, isFolder)
	if next is not None:
		next_params = dict(params)
		next_params.update({"action": "show", "cursor": next})
		addDir(">>> Weiter", next_params)
	end()

def catalog_list(params):
	catalog_id = params["id"]
	request_id = catalog_id
	sort = ""
	filters = {}
	if catalog_id not in ("tmdb.movie", "tmdb.series"):
		media_type = "series" if catalog_id.startswith("series") else "movie"
		catalog_id = "tmdb.%s" % media_type
		request_id = params["id"].replace(".", "/", 1)
		sort = "trendingDay" if "trending" in params["id"] else "popularity"
	if params.get("genre"):
		filters["genre"] = [params["genre"]]
	cursor = params.get("cursor")
	if cursor in (None, "", "None"):
		cursor = None
	elif isinstance(cursor, str) and cursor.isdigit():
		cursor = int(cursor)
	_headers = {
		"user-agent": "MediaHubMX/2",
		"accept": "application/json",
		"content-type": "application/json; charset=utf-8",
		"accept-encoding": "gzip",
		"mediahubmx-signature": getAuthSignature()
	}
	_data = {
		"language": "de",
		"region": "AT",
		"catalogId": catalog_id,
		"id": request_id,
		"adult": False,
		"search": params.get("search", ""),
		"sort": sort,
		"filter": filters,
		"cursor": cursor,
		"clientVersion": "3.1.0"
	}
	req = request_json("POST", "https://vavoo.to/mediahubmx-catalog.json", json=_data, headers=_headers, timeout=10, retries=1)
	items = req.get("items", req.get("data", []))
	media_type = "series" if catalog_id == "tmdb.series" else "movie"
	result = []
	for item in items:
		item = dict(item)
		ids = item.get("ids") or {}
		item_type = item.get("type") or media_type
		if item_type not in ("movie", "series"):
			item_type = media_type
		item_id = str(item.get("id") or ids.get("tmdb_id") or item.get("tmdbId") or item.get("tmdb_id") or "")
		for prefix in ("tmdb.movie.", "tmdb.series.", "tmdb:movie:", "tmdb:series:"):
			if item_id.startswith(prefix):
				item_id = item_id[len(prefix):]
				break
		if item_id.isdigit():
			item_id = "%s.%s" % (item_type, item_id)
		if not item_id.startswith(("movie.", "series.")):
			continue
		item["id"] = item_id
		item["name"] = item.get("name", item.get("title", ""))
		result.append(item)
	return {"data": result, "next": req.get("nextCursor")}


def search(params):
	type = "SERIEN" if params["id"].startswith("serie") else "FILM"
	cacheOk, history = get_cache("seriesearch" if type == "SERIEN" else "moviesearch")
	if not cacheOk: history = {}
	if not history or params.get("newsearch"):
		a = list(history.keys())[-1] if history else ""
		heading="VAVOO.TO - %s SUCHE" % type
		kb = xbmc.Keyboard(a, heading, False)
		kb.doModal()
		if (kb.isConfirmed()):
			query = kb.getText().strip()
			if not query:
				return
			para = {"id": "tmdb.series" if type == "SERIEN" else "tmdb.movie", "search": query}
			history[query] = para
			set_cache("seriesearch" if type == "SERIEN" else "moviesearch", history, False)
			show(para)
		else: return
	else:
		addDir2("Neue Suche", "DefaultAddonsSearch", "search", id=params["id"], newsearch=True)
		for a in history:
			cm = [("Suchverlauf löschen", "RunPlugin(%s?action=delete_search&id=%s)" % (sys.argv[0], params["id"])), ("Suche löschen", "RunPlugin(%s?action=delete_search&id=%s&single=%s)" % (sys.argv[0], params["id"], a))]
			search_params = history[a]
			if isinstance(search_params, dict):
				addDir2(a, "DefaultAddonsSearch", "show", context=cm, **search_params)
			else:
				addDir2(a, "DefaultAddonsSearch", "show", context=cm, id=search_params)
		end()

def genres(params):
	serie_genrelist = [
		{"genre": "Action & Adventure", "icon":"Adventure"}, {"genre": "Animation", "icon":"Animation"}, {"genre": "Komödie", "icon":"Comedy"}, {"genre": "Krimi", "icon":"Crime"},
		{"genre": "Dokumentarfilm", "icon":"Documentary"}, {"genre": "Drama", "icon":"Drama"}, {"genre": "Familie", "icon":"Family"}, {"genre": "Kids", "icon":"Children"},
		{"genre": "Mystery", "icon":"Mystery"}, {"genre": "News", "icon":"News"}, {"genre": "Reality", "icon":"Reality-TV"}, {"genre": "Sci-Fi & Fantasy", "icon":"Sci-Fi"},	# edit Reality by kasi
		{"genre": "Soap", "icon":"Sitcom"}, {"genre": "Talk", "icon":"Biography"}, {"genre": "War & Politics", "icon":"War"}, {"genre": "Western", "icon":"Western"}]			# edit Soap by kasi
	movie_genrelist = [
		{"genre": "Action", "icon":"Action"}, {"genre": "Abenteuer", "icon":"Adventure"}, {"genre": "Animation", "icon":"Animation"}, {"genre": "Komödie", "icon":"Comedy"},
		{"genre": "Krimi", "icon":"Crime"}, {"genre": "Dokumentarfilm", "icon":"Documentary"}, {"genre": "Drama", "icon":"Drama"}, {"genre": "Familie", "icon":"Family"},
		{"genre": "Fantasy", "icon":"Fantasy"}, {"genre": "Historie", "icon":"History"}, {"genre": "Horror", "icon":"Horror"}, {"genre": "Musik", "icon":"Music"},
		{"genre": "Mystery", "icon":"Mystery"}, {"genre": "Liebesfilm", "icon":"Romance"}, {"genre": "Science Fiction", "icon":"Sci-Fi"}, {"genre": "TV-Film", "icon":"Mini-Series"},
		{"genre": "Thriller", "icon":"Thriller"}, {"genre": "Kriegsfilm", "icon":"War"}, {"genre": "Western", "icon":"Western"}]
	genrelist= serie_genrelist if params["id"].startswith("serie") else movie_genrelist
	for genre in genrelist: addDir2(genre["genre"], genre["icon"], "show", id=params["id"], genre=genre["genre"])
	end()

def seasons(params):
	set_content("seasons")
	set_category("Staffeln")
	_seasons = get_meta(params)["seasons"]
	if len(_seasons) == 1:
		params["s"] = "1"
		return episodes(params)
	params["action"] = "episodes"
	for season in _seasons:
		params["s"] = str(season["season_number"])
		o = createListItem(params)
		add(params, o, True)
	end()
	
def episodes(params):
	set_content("episodes")
	set_category("Staffel %s/Episoden" %params["s"])
	_episodes = get_meta(params)["infos"]["sortepisode"]
	params["action"], i = "get", 1
	while i <= _episodes:
		params["e"] = str(i)
		o = createListItem(params)
		o.addContextMenuItems([("Manuelle Stream Auswahl", "RunPlugin(%s&manual=true)" % url_for(params))])
		add(params, o)
		i+=1
	end()

def resolve(mirror):
	log(mirror, header="Try to resolve:")
	try: 
		resolved = resolveurl.resolve(mirror["url"])
		return resolved
	except Exception:
		pass
	try:
		_headers={"user-agent": "MediaHubMX/2", "content-type": "application/json; charset=utf-8", "content-length": "102", "accept-encoding": "gzip", "mediahubmx-signature": getAuthSignature()}
		_data = {"language":"de","region":"AT","url":mirror["url"],"clientVersion":"3.0.2"}
		url = request_json("POST", "https://vavoo.to/mediahubmx-resolve.json", json=_data, headers=_headers, timeout=10, retries=1)["data"]["url"]
		resolved = resolveurl.resolve(url)
		return resolved
	except Exception:
		pass
	try:
		res = callApi2('open', {'link': mirror["url"]})[-1]
		headers = res.get('headers', {})
		resolved = request("GET", res['url'], headers=headers, stream=True, timeout=10, retries=1).url
		return resolved
	except Exception:
		return

def checkstream(url):
	if not url: return
	log(url, header="Checking Stream:")
	try:
		newurl, headers, params = url, {}, {}
		if "|" in newurl:
			newurl, headers = newurl.split("|")
			headers = dict(parse_qsl(headers))
		if "?" in newurl:
			newurl, params = newurl.split("?")
			params = dict(parse_qsl(params))
		res = request("GET", newurl, headers=headers, params=params, stream=True, timeout=10, retries=0)
		res.raise_for_status()
		if "text" in res.headers.get("Content-Type","text"): raise Exception("Keine Videodatei")
	except Exception:
		log(format_exc())
		return
	else: return url

def get(params):
	manual = True if params.get("manual") == "true" else False
	find = True if params.get("find") == "true" else False
	params["site"] = "vavoo"
	cacheOk, mirrors = get_cache(params)
	_headers={"user-agent": "MediaHubMX/2", "content-type": "application/json; charset=utf-8", "content-length": "1898", "accept-encoding": "gzip", "mediahubmx-signature": getAuthSignature()}
	if not cacheOk:
		name = params.get("n")
		if not name:
			b = get_meta(params)
			if params.get("e"):
				name = b["infos"]["tvshowtitle"] if params.get("e") else b["infos"]["title"]
		if params.get("e"):_data={"language":"de","region":"AT","type":"series","ids":{"tmdb_id":params["id"].split(".")[1]},"name":name,"episode":{"season":params["s"],"episode":params["e"]},"clientVersion":"3.0.2"}
		else: _data={"language":"de","region":"AT","type":"movie","ids":{"tmdb_id":params["id"].split(".")[1]},"name":name,"episode":{},"clientVersion":"3.0.2"}
		url = "https://vavoo.to/mediahubmx-source.json"
		mirrors = request_json("POST", url, json=_data, headers=_headers, timeout=10, retries=1)
		set_cache(params, mirrors, 1)
	if not mirrors:
		log("Keine Mirrors gefunden")
		if not find: showFailedNotification()
		return
	else:
		newurllist, streamurl =[], None
		for i ,a in enumerate(mirrors, 1):
			if not "de" in a.get('languages', []): continue
			a["hoster"] = urlparse(a["url"]).netloc
			if "streamz" in a["hoster"]: continue # den hoster kann man vergessen
			quali = a.get("tag", "SD")
			if quali == "1080p" or quali == "FHD":
				if int(getSetting("stream_quali") or 0) > 0: continue
				a["name"], a["weight"] = "%s %s" %(a["hoster"], "1080p"), 1080+random.randint(0, 9)
			elif quali == "720p" or quali == "HD":
				if int(getSetting("stream_quali") or 0) > 1: continue
				a["name"], a["weight"] = "%s %s" %(a["hoster"], "720p"), 720+random.randint(0, 9)
			else: a["name"], a["weight"] = a["hoster"], random.randint(0, 9)
			newurllist.append({"name":a["name"], "weight":a["weight"], "hoster": a["hoster"], "url":a["url"]})
		mirrors = list(sorted(newurllist, key=lambda x: x["weight"], reverse=True)) if newurllist else None
		if not mirrors:
			log("Keine Mirrors gefunden")
			if not find: showFailedNotification()
			return
		for i, a in enumerate(mirrors, 1): a["name"] = "%s. %s" % (i, a["name"])
		log(mirrors)
		if getSetting("stream_select") == "0" or manual:
			index = dialog.select("VAVOO", [ mirror["name"] for mirror in mirrors ])
			if index == -1: return
			if getSetting("auto_try_next_stream") !="true": mirrors = [mirrors[index]]
			else: mirrors = mirrors[index:]
		for mirror in mirrors:
			streamurl = checkstream(resolve(mirror)) if getSetting("stream_check") == "true" else resolve(mirror)
			if streamurl: break
		if find and streamurl: return streamurl
		elif not streamurl:
			if find: return
			return showFailedNotification("Stream not resolvable or down")
		else:
			log("Spiele :%s" % streamurl)
			o = ListItem(getInfoLabel("ListItem.Title"))
			o.setProperty("IsPlayable", "true")
			if ".m3u8" in streamurl:
				o.setProperty("inputstream", "inputstream.adaptive")
				o.setProperty('inputstream.adaptive.config', '{"ssl_verify_peer":false}')
				if "|" in streamurl: 
					streamurl, headers = streamurl.split("|")
					o.setProperty('inputstream.adaptive.common_headers', headers)
					o.setProperty('inputstream.adaptive.stream_headers', headers)
			o.setPath(streamurl)
			if int(sys.argv[1]) > 0: set_resolved(o)
			else:
				from vavoo.player import cPlayer
				player().play(streamurl, o)
				return cPlayer().startPlayer()

def callApi(action, params, method="GET", headers=None, **kwargs):
	log(params, header="Action:%s params:" % action)
	if not headers: headers = dict()
	headers["auth-token"] = getAuthSignature()
	resp = request(method, (BASEURL + action), params=params, headers=headers, retries=1, timeout=10, **kwargs)
	resp.raise_for_status()
	data = resp.json()
	log(data, header="callApi res:")
	return data

def callApi2(action, params):
	res = callApi(action, params, verify=False)
	while True:
		if type(res) is not dict or "id" not in res or "data" not in res:
			return res
		data = res["data"]
		if type(data) is dict and data.get("type") == "fetch":
			fetch_params = data.get("params", {})
			body = fetch_params.get("body")
			headers = fetch_params.get("headers")
			decoded_body = base64.b64decode(body) if body else None
			try:
				resp = request(
					fetch_params.get("method", "GET").upper(),
					data["url"],
					headers={k: v[0] if type(v) in (list, tuple) else v for k, v in headers.items()} if headers else None,
					data=decoded_body,
					allow_redirects=fetch_params.get("redirect", "follow") == "follow",
					timeout=10,
					retries=1
				)
			except Exception:
				log(format_exc())
				return
			headers = dict(resp.headers)
			resData = {"status": resp.status_code, "url": resp.url, "headers": headers, "data": base64.b64encode(resp.content).decode("utf-8").replace("\n", "") if body else None}
			log(resData)
			res = callApi("res", {"id": res["id"]}, method="POST", json=resData, verify=False)
		elif type(data) is dict and data.get("error"):
			log(data.get("error"))
			return
		else: return data
