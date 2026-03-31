# -*- coding: utf-8 -*-
import xbmcgui, xbmcaddon, sys, xbmc, os, time, json, xbmcplugin, requests, re
import urllib3, resolveurl, base64, random, string, xbmcvfs
from datetime import datetime
from hashlib import md5, sha256, sha1
from dateutil.parser import parse
from traceback import format_exc
from zlib import compress, decompress
from xbmcgui import ListItem, Dialog, DialogProgress, Window
from urllib.parse import urlencode, urlparse, parse_qsl, quote_plus, urlsplit, quote
from concurrent.futures import ThreadPoolExecutor, as_completed
try:
	from infotagger.listitem import ListItemInfoTag
	tagger = True
except: tagger = False

def translatePath(*args):
	return xbmcvfs.translatePath(*args)

def exists(*args):
	return os.path.exists(translatePath(*args))

addon = xbmcaddon.Addon("plugin.video.vavooto")
addonInfo = addon.getAddonInfo
addonID = "plugin.video.vavooto"
addonprofile = translatePath(addonInfo('profile'))
addonpath = translatePath(addonInfo('path'))
cachepath = os.path.join(addonprofile, "cache")
if not exists(cachepath): os.makedirs(cachepath)
home = Window(10000)
session = requests.Session()
progress = DialogProgress()
dialog = Dialog()
monitor = xbmc.Monitor()
player = xbmc.Player
getInfoLabel = xbmc.getInfoLabel
getSetting = addon.getSetting
setSetting = addon.setSetting
openSettings = addon.openSettings
execute = xbmc.executebuiltin
getCondV = xbmc.getCondVisibility

def clear(auto=False):
	for a in os.listdir(cachepath):
		file = os.path.join(cachepath, a)
		key = a.replace(".json", "")
		if auto:
			m = open(file, "rb").read()
			try: data = decompress(m)
			except: data = m
			r = json.loads(data)
			sigValidUntil = r.get('sigValidUntil', 0)
			if sigValidUntil != False and sigValidUntil < int(time.time()):
				os.remove(file)
				home.clearProperty(key)
		else: 
			os.remove(file)
			home.clearProperty(key)
		
clear(auto=True)

def getAuthSignature():
	i = 0
	while i < 5:
		i+=1
		try:
			_headers={"user-agent": "okhttp/4.11.0", "accept": "application/json", "content-type": "application/json; charset=utf-8", "content-length": "1106", "accept-encoding": "gzip"}
			_data = {"token":"ldCvE092e7gER0rVIajfsXIvRhwlrAzP6_1oEJ4q6HH89QHt24v6NNL_jQJO219hiLOXF2hqEfsUuEWitEIGN4EaHHEHb7Cd7gojc5SQYRFzU3XWo_kMeryAUbcwWnQrnf0-","reason":"app-blur","locale":"de","theme":"dark","metadata":{"device":{"type":"Handset","brand":"google","model":"Nexus","name":"21081111RG","uniqueId":"d10e5d99ab665233"},"os":{"name":"android","version":"7.1.2","abis":["arm64-v8a"],"host":"android"},"app":{"platform":"android","version":"1.1.0","buildId":"97215000","engine":"hbc85","signatures":["6e8a975e3cbf07d5de823a760d4c2547f86c1403105020adee5de67ac510999e"],"installer":"com.android.vending"},"version":{"package":"app.lokke.main","binary":"1.1.0","js":"1.1.0"},"platform":{"isAndroid":True,"isIOS":False,"isTV":False,"isWeb":False,"isMobile":True,"isWebTV":False,"isElectron":False}},"appFocusTime":0,"playerActive":False,"playDuration":0,"devMode":True,"hasAddon":True,"castConnected":False,"package":"app.lokke.main","version":"1.1.0","process":"app","firstAppStart":1772388338206,"lastAppStart":1772388338206,"ipLocation":None,"adblockEnabled":False,"proxy":{"supported":["ss","openvpn"],"engine":"openvpn","ssVersion":1,"enabled":False,"autoServer":True,"id":"fi-hel"},"iap":{"supported":True}}
			req = requests.post('https://www.lokke.app/api/app/ping', json=_data, headers=_headers).json()
			return req.get("addonSig")
		except: continue

def gettsSignature():
	i = 0
	while i < 5:
		i+=1
		try:
			vec = {"vec": "9frjpxPjxSNilxJPCJ0XGYs6scej3dW/h/VWlnKUiLSG8IP7mfyDU7NirOlld+VtCKGj03XjetfliDMhIev7wcARo+YTU8KPFuVQP9E2DVXzY2BFo1NhE6qEmPfNDnm74eyl/7iFJ0EETm6XbYyz8IKBkAqPN/Spp3PZ2ulKg3QBSDxcVN4R5zRn7OsgLJ2CNTuWkd/h451lDCp+TtTuvnAEhcQckdsydFhTZCK5IiWrrTIC/d4qDXEd+GtOP4hPdoIuCaNzYfX3lLCwFENC6RZoTBYLrcKVVgbqyQZ7DnLqfLqvf3z0FVUWx9H21liGFpByzdnoxyFkue3NzrFtkRL37xkx9ITucepSYKzUVEfyBh+/3mtzKY26VIRkJFkpf8KVcCRNrTRQn47Wuq4gC7sSwT7eHCAydKSACcUMMdpPSvbvfOmIqeBNA83osX8FPFYUMZsjvYNEE3arbFiGsQlggBKgg1V3oN+5ni3Vjc5InHg/xv476LHDFnNdAJx448ph3DoAiJjr2g4ZTNynfSxdzA68qSuJY8UjyzgDjG0RIMv2h7DlQNjkAXv4k1BrPpfOiOqH67yIarNmkPIwrIV+W9TTV/yRyE1LEgOr4DK8uW2AUtHOPA2gn6P5sgFyi68w55MZBPepddfYTQ+E1N6R/hWnMYPt/i0xSUeMPekX47iucfpFBEv9Uh9zdGiEB+0P3LVMP+q+pbBU4o1NkKyY1V8wH1Wilr0a+q87kEnQ1LWYMMBhaP9yFseGSbYwdeLsX9uR1uPaN+u4woO2g8sw9Y5ze5XMgOVpFCZaut02I5k0U4WPyN5adQjG8sAzxsI3KsV04DEVymj224iqg2Lzz53Xz9yEy+7/85ILQpJ6llCyqpHLFyHq/kJxYPhDUF755WaHJEaFRPxUqbparNX+mCE9Xzy7Q/KTgAPiRS41FHXXv+7XSPp4cy9jli0BVnYf13Xsp28OGs/D8Nl3NgEn3/eUcMN80JRdsOrV62fnBVMBNf36+LbISdvsFAFr0xyuPGmlIETcFyxJkrGZnhHAxwzsvZ+Uwf8lffBfZFPRrNv+tgeeLpatVcHLHZGeTgWWml6tIHwWUqv2TVJeMkAEL5PPS4Gtbscau5HM+FEjtGS+KClfX1CNKvgYJl7mLDEf5ZYQv5kHaoQ6RcPaR6vUNn02zpq5/X3EPIgUKF0r/0ctmoT84B2J1BKfCbctdFY9br7JSJ6DvUxyde68jB+Il6qNcQwTFj4cNErk4x719Y42NoAnnQYC2/qfL/gAhJl8TKMvBt3Bno+va8ve8E0z8yEuMLUqe8OXLce6nCa+L5LYK1aBdb60BYbMeWk1qmG6Nk9OnYLhzDyrd9iHDd7X95OM6X5wiMVZRn5ebw4askTTc50xmrg4eic2U1w1JpSEjdH/u/hXrWKSMWAxaj34uQnMuWxPZEXoVxzGyuUbroXRfkhzpqmqqqOcypjsWPdq5BOUGL/Riwjm6yMI0x9kbO8+VoQ6RYfjAbxNriZ1cQ+AW1fqEgnRWXmjt4Z1M0ygUBi8w71bDML1YG6UHeC2cJ2CCCxSrfycKQhpSdI1QIuwd2eyIpd4LgwrMiY3xNWreAF+qobNxvE7ypKTISNrz0iYIhU0aKNlcGwYd0FXIRfKVBzSBe4MRK2pGLDNO6ytoHxvJweZ8h1XG8RWc4aB5gTnB7Tjiqym4b64lRdj1DPHJnzD4aqRixpXhzYzWVDN2kONCR5i2quYbnVFN4sSfLiKeOwKX4JdmzpYixNZXjLkG14seS6KR0Wl8Itp5IMIWFpnNokjRH76RYRZAcx0jP0V5/GfNNTi5QsEU98en0SiXHQGXnROiHpRUDXTl8FmJORjwXc0AjrEMuQ2FDJDmAIlKUSLhjbIiKw3iaqp5TVyXuz0ZMYBhnqhcwqULqtFSuIKpaW8FgF8QJfP2frADf4kKZG1bQ99MrRrb2A="}
			url = 'https://www.vavoo.tv/api/box/ping2'
			req = requests.post(url, data=vec).json()
			return req['response'].get('signed')
		except: continue

def append_headers(headers):
	return '|%s' % '&'.join(['%s=%s' % (key, quote_plus(headers[key])) for key in headers])
    
def delete_search(params):
	if params["id"] == "all":
		set_cache("seriesearch", {}, False)
		set_cache("moviesearch", {}, False)
		execute("Container.Refresh")
	else:
		type = "SERIEN" if params["id"].startswith("serie") else "FILM"
		cacheOk, history = get_cache("seriesearch" if type == "SERIEN" else "moviesearch")
		if not cacheOk: history = {}
		if params.get("single"):
			history.pop(params.get("single"))
			set_cache("seriesearch" if type == "SERIEN" else "moviesearch", history, False)
			if not history: execute("Action(ParentDir)")
			else: execute("Container.Refresh")
		else:
			set_cache("seriesearch" if type == "SERIEN" else "moviesearch", {}, False)
			execute("Action(ParentDir)")

def selectDialog(list, heading=None, multiselect = False, preselect=False):
	if heading == 'default' or heading is None: heading = addonInfo('name')
	if multiselect: 
		if preselect==False: preselect=[]
		return dialog.multiselect(str(heading), list, preselect=preselect)
	return dialog.select(str(heading), list, preselect=preselect)

def set_cache(key, value, timeout=False):
	path = convertPluginParams(key)
	data=json.dumps({"sigValidUntil": False if timeout == False else int(time.time()) +(timeout*3600),"value": value})
	home.setProperty(path, data)
	file = os.path.join(cachepath, path)
	if addon.getSetting("comp") == "true":
		data = compress(data.encode())
		k = open(file, "wb")
	else: k = open(file, "w")
	k.write(data)
	k.close()

def get_cache(key):
	path = convertPluginParams(key)
	keyfile = home.getProperty(path)
	if keyfile:
		r = json.loads(keyfile)
		sigValidUntil = r.get('sigValidUntil', 0)
		if sigValidUntil == False or sigValidUntil > int(time.time()):
			log(f"{key} from cache")
			return True, r.get('value')
		home.clearProperty(path)
	else:
		file = os.path.join(cachepath, path)
		if os.path.isfile(file):
			k = open(file, "rb").read()
			try: data = decompress(k)
			except: data = k
			r = json.loads(data)
			sigValidUntil = r.get('sigValidUntil', 0) 
			if sigValidUntil == False or sigValidUntil > int(time.time()):
				value = r.get('value')
				data=json.dumps({"sigValidUntil": sigValidUntil,"value": value})
				home.setProperty(path, data)
				log(f"{key} from cache")
				return True, value
			os.remove(file)
	return False, None

def get_cache_or_setting(setting):
	cacheOk, a = get_cache(setting)
	if not cacheOk : 
		a = addon.getSetting(setting)
		set_cache(setting, a)
	return a
	
def del_cache(key):
	path = convertPluginParams(key)
	try:
		file = os.path.join(cachepath, f"{path}.json")
		if not os.path.isfile(file):
			file = os.path.join(cachepath, path)
		home.clearProperty(path)
		os.remove(file)
		log(f"Delete {key}")
	except: pass

def filterout(name):
	if addon.getSetting("filter") == "true":
		name = name.encode().decode("ascii", errors="ignore")
		for r in(("   ", " "), ("  ", " "), ("SPORT1", "SPORT 1"), ("BIBELTV", "BIBEL TV"), ("DIGITALL", "DIGITAL"), ("EINS", "1"), ("ZWEI", "2"), ("DREI", "3"), ("SIEBEN", "7"), ("III", "3"), ("II", "2"), ("BR TV", "BR"), ("ʜᴅ", "")): name = name.replace(*r).strip()
		if "BLACK" in name: return "AXN BLACK"
		if "E!" in name: return "E! ENTERTAINMENT"
		elif "AXN" in name or "WHITE" in name: return "AXN WHITE"
		elif "SONY" in name: return "AXN BLACK"
		elif "WARNER" in name or "TNT" in name:
			if "SERIE" in name: return "WARNER TV SERIE"
			elif "FILM" in name: return "WARNER TV FILM"
			elif "COMEDY" in name: return "WARNER TV COMEDY"
		elif all(ele in name for ele in ["1", "2", "3"]): return "1-2-3 TV"
		elif "CENTRAL" in name or "VIVA" in name: return "COMEDY CENTRAL"
		elif "NICK" in name:
			if "EON" in name: return "NICKELODEON"
			elif "TOONS" in name: return "NICKTOONS"
			elif "J" in name: return "NICK JUNIOR"
		elif "ANIXE" in name: return "ANIXE+" if "+" in name else "ANIXE"
		elif "ERSTE" in name and "DAS" in name: return "ARD"
		elif "ZDF" in name:
			if "INFO" in name: return "ZDF INFO"
			elif "NEO" in name: return "ZDF NEO"
			else: return "ZDF"
		elif "FERNSEHEN" in name: 
			if "BR" in name or "BAY" in name: return "BR"
			elif "HR" in name: return "HR"
		elif "DISNEY" in name:
			if "CHANNEL" in name: return "DISNEY CHANNEL"
			elif "J" in name: return "DISNEY JUNIOR"
		elif "SPIEGEL" in name or "CURIOSITY" in name:
			return "SPIEGEL GESCHICHTE" if "GESCHICHTE" in name else "CURIOSITY CHANNEL"
		elif "INVESTIGATION" in name or "A&E" in name: return "CRIME + INVESTIGATION"
		elif "WELT" in name: return "WELT DER WUNDER" if "WUNDER" in name else "WELT"
		elif "GEO" in name:
			if "WILD" in name: return "NAT GEO WILD"
			return "NATIONAL GEOGRAPHIC" if "NAT" in name else "GEO TV"
		elif "N-TV" in name or "NTV" in name: return "NTV"
		elif "PLANET" in name: 
			 return "ANIMAL PLANET" if "ANIMAL" in name else "PLANET"
		elif "TELE" in name and "5" in name: return "TELE 5"
		elif "VOX" in name:
			if "UP" in name or "+" in name: return "VOX UP"
			else: return "VOX"
		if "ORF" in name:
			if "SPORT" in name: return "ORF SPORT"
			if "3" in name: return "ORF 3"
			if "2" in name: return "ORF 2"
			if "1" in name: return "ORF 1"
			if "I" in name: return "ORF 1"
		elif "RTL" in name:
			if "SPORT" in name or "LUXE" in name: name=name
			elif "CRIME" in name: return "RTL CRIME"
			elif "SUPER" in name: return "SUPER RTL"
			elif "PLUS" in name or "UP" in name: return "RTL UP"
			elif "PASSION" in name: return "RTL PASSION"
			elif "LIVING" in name: return "RTL LIVING"
			elif "2" in name: return "RTL 2"
			elif "TOTALLY" in name: return "TOTALLY TURTLES"
			else: return "RTL"
		elif "KABE" in name:
			if "CLA" in name: return "KABEL 1 CLASSICS"
			return "KABEL 1 DOKU" if "DO" in name else "KABEL 1"
		elif "PRO" in name:
			if "FUN" in name: return "PRO 7 FUN"
			return "PRO 7 MAXX" if "MAXX" in name else "PRO 7"
		elif "EUROSPORT" in name:
			if "1" in name: return "EUROSPORT 1"
			if "2" in name: return "EUROSPORT 2"
		elif "ATV" in name:
			return "ATV 2" if "2" in name else "ATV"
		elif "SAT" in name:
			if "3" in name: return "3 SAT"
			elif "1" in name:
				if "GOLD" in name: return "SAT 1 GOLD"
				if "EMOT" in name: return "SAT 1 EMOTIONS"
				else: return "SAT 1"
		elif "SKY" in name:
			if not any(ele in name for ele in ["BUNDES", "SPORT", "SELECT", "BOX"]):
				if "DO" in name: return "SKY DOCUMENTARIES"
				elif "REPLAY" in name: return "SKY REPLAY"
				elif "CASE" in name: return "SKY SHOWCASE"
				elif "ATLANTIC" in name: return "SKY ATLANTIC"
				elif "ACTION" in name: return "SKY CINEMA ACTION"
				elif "HIGHLIGHT" in name or "BEST" in name: return "SKY CINEMA HIGHLIGHTS"
				elif "COMEDY" in name: return "SKY COMEDY"
				elif "FAMI" in name: return "SKY CINEMA FAMILY"
				elif "CLASS" in name or "NOSTALGIE" in name: return "SKY CINEMA CLASSICS"
				elif "KRIM" in name: return "SKY KRIMI"
				elif "CRIME" in name: return "SKY CRIME"
				elif "NATURE" in name: return "SKY NATURE"
				elif "SHOWS" in name: return "SKY SERIEN & SHOWS"
				elif "SPECIAL" in name: return "SKY CINEMA SPECIAL"
				elif "PREMIE" in name: return "SKY CINEMA PREMIEREN +24" if "24" in name else "SKY CINEMA PREMIEREN"
				elif ("ONE" in name or "1" in name) and not "CINEMA" in name: return "SKY ONE"
		elif "PULS" in name:
			if "24" in name: return "PULS 24"
			elif "4" in name: return "PULS 4"
		elif "DO" in name and "24" in name: return "N24 DOKU"
		for keyword in  [("ALLGAU" ,"ALLGAU TV"), ("HEIMA" ,"HEIMATKANAL"), ("ALPHA", "ARD ALPHA"), ("UNIVERSAL" ,"UNIVERSAL TV"), ("SERVUS" ,"SERVUS TV"), ("FOXI", "FIX & FOXI"), ("FOX" ,"SKY REPLAY"), ("STREET" ,"13TH STREET"), ("ZEE" ,"ZEE ONE"), ("DELUX" ,"DELUXE MUSIC"), ("DISCO" ,"DISCOVERY"), ("TAGESSCHAU" ,"TAGESSCHAU 24"), ("VISION" ,"MOTORVISION"), ("AUTO" ,"AUTO MOTOR SPORT"), ("ROMANCE" ,"ROMANCE TV"), "SIXX", "SWR", "EURONEWS", "ARTE", "MTV", "ARD", "MDR", "NDR", "RBB", "PHOENIX", "KIKA", "WDR", "TLC", "DMAX", "HISTORY", "SYFY", "NITRO", "JUKEBOX", "KINOWELT", "WAIDWERK"]:
			if isinstance(keyword, tuple):
				if keyword[0] in name: return keyword[1]
			elif keyword in name: return keyword
		if name == "SR FERNSEHEN" or name == "SR" or "SRF" in name: return "SRF"
	return re.sub(r"(^(DE|AT|CH) ?(:|\||-)| (\|\w|(F|Q|U)?HD\+?|(2|4|8)K|(720|1080|2160)p?|AUSTRIA|GERMANY|DEUTSCHLAND|HEVC|H265|RAW|SD|YOU)|(\(|\[).*?(\)|\])| (DE|\.\D)$)", "", name).strip()

def getGenresFromIDs(genresID):
	tmdb_genres = {12: "Abenteuer", 14: "Fantasy", 16: "Animation", 18: "Drama", 27: "Horror", 28: "Action", 35: "Komödie", 36: "Historie", 37: "Western", 53: "Thriller", 80: "Krimi", 99: "Dokumentarfilm", 878: "Science Fiction", 9648: "Mystery", 10402: "Musik", 10749: "Liebesfilm", 10751: "Familie", 10752: "Kriegsfilm", 10759: "Action & Adventure", 10762: "Kids", 10763: "News", 10764: "Reality", 10765: "Sci-Fi & Fantasy", 10766: "Soap", 10767: "Talk", 10768: "War & Politics", 10770: "TV-Film"}
	sGenres = []
	for gid in genresID:
		genre = tmdb_genres.get(gid)
		if genre: sGenres.append(genre)
	return sGenres

def get_meta(param):
	media_type, tmdb_id = param["id"].replace("series", "tv").split(".")
	_meta, _art, _property, _cast, _episodes= {}, {}, {}, [], []
	_meta["writer"],_meta["director"] = [],[]
	trailer_url = "plugin://plugin.video.youtube/play/?video_id=%s"
	lang = "de-DE" #Addon().getSetting("tmdb_lang")
	api_key = "86dd18b04874d9c94afadde7993d94e3"
	append_to_response = "credits,videos,external_ids,content_ratings,keywords,translations"
	if media_type == "movie": append_to_response = append_to_response.replace("content_ratings", "release_dates")
	poster = "https://image.tmdb.org/t/p/%s" % "w342" #Addon().getSetting("poster_tmdb")
	fanart = "https://image.tmdb.org/t/p/%s" % "w1280" #Addon().getSetting("backdrop_tmdb")
	tmdb_url = "https://api.themoviedb.org/3/%s/%s" % (media_type, tmdb_id)
	url_params = {"language":lang, "api_key":api_key, "append_to_response":append_to_response}
	_meta["mediatype"] = media_type.replace("tv", "tvshow")
	
	def setInfo(key, value):
		if value: _meta[key] = value

	def setproperties(key, value):
		if value: _property[key] = value

	cacheOk, meta = get_cache({"id": param["id"]})
	if not cacheOk:
		meta = requests.get(tmdb_url, params=url_params).json()
		if "success" in meta and meta["success"] == False: return
		set_cache({"id": param["id"]}, meta, 75600)
	_seasons = [i for i in meta["seasons"] if i["season_number"] != 0] if meta.get("seasons") else []
	_ids = {"tmdb": tmdb_id}
	external_ids = meta.get("external_ids")
	if external_ids and  external_ids.get("imdb_id"):
		_ids["imdb"] = external_ids["imdb_id"]
		setInfo("imdbnumber", external_ids["imdb_id"])
	if external_ids and  external_ids.get("tvdb_id"): _ids["tvdb"] = external_ids["tvdb_id"]
	setproperties("homepage", meta.get("homepage"))
	setInfo("title", meta.get("title", meta.get("name")))
	setInfo("tvshowtitle", meta.get("name"))
	setInfo("rating", meta.get("vote_average"))
	setInfo("votes", meta.get("vote_count"))
	belongs_to_collection = meta.get("belongs_to_collection")
	if belongs_to_collection:
		setInfo("setid", belongs_to_collection.get("id"))
		setInfo("set", belongs_to_collection.get("name"))
	setInfo("duration", meta.get("runtime", 0)*60)
	setInfo("originaltitle", meta.get("originalName", meta.get("original_title", meta.get("original_name"))))
	if meta.get("genres"): setInfo("genre", [i["name"] for i in meta["genres"]])
	elif meta.get("genre_ids"): setInfo("genre", getGenresFromIDs(meta["genre_ids"]))
	if meta.get('translations') and len(meta['translations']['translations']) > 0:
		overviews = meta['translations']['translations']
		for overview in overviews:
			if overview['data']['overview']:
				if overview['name'] == "Deutsch" or  overview['iso_639_1'] == "de": #  or  overview['name'] == "English":
					setInfo("plot", overview['data']['overview'])
					break
				if overview['name'] == "English":
					setInfo("plot", overview['data']['overview'])
	setInfo("premiered", meta.get("release_date", meta.get("first_air_date", meta.get("releaseDate"))))
	if len(_meta.get("premiered", "0")) == 10: _meta["year"] = int(_meta["premiered"][:4])
	setInfo("status", meta.get("status"))
	setInfo("tagline", meta.get("tagline"))
	keywords = meta.get("keywords", {})
	tags = keywords.get("results", keywords.get("keywords",{}))
	if tags: setInfo("tag", [i["name"] for i in tags])
	results = meta.get("release_dates", meta.get("content_ratings", {})).get("results")
	results = [i for i in results if i["iso_3166_1"] == "DE"] if results else []
	if results:
		for release in results:
			if release["iso_3166_1"] == "DE":
				if release.get("rating"): setInfo("mpaa", release.get("rating"))
				else:
					for release_date in release["release_dates"]:
						if release_date["type"] == 3: setInfo("mpaa", release_date.get("certification"))
	if meta.get("backdrop_path"): _art["banner"] = fanart + meta["backdrop_path"]
	if meta.get("poster_path"): _art["poster"] = poster + meta["poster_path"]
	if meta.get('budget') and meta['budget'] !=0: setproperties("Budget", '${:,}'.format(meta['budget']))
	if meta.get('revenue') and meta['revenue'] !=0: setproperties("Revenue", '${:,}'.format(meta['revenue']))
	setproperties("TotalSeasons", meta.get("number_of_seasons"))
	setproperties("TotalEpisodes", meta.get("number_of_episodes"))
	if meta.get("production_countries"): _meta["country"] = [i["name"] for i in meta["production_countries"]]
	if meta.get("production_companies"): _meta["studio"] = [i["name"] for i in meta["production_companies"]]
	if meta.get("trailers") and "youtube" in meta["trailers"]:
		for t in meta["trailers"]["youtube"]:
			if t["type"] == "Trailer": setInfo("trailer", trailer_url % t["source"])
	elif meta.get("videos",{}).get("results"):
		for t in meta["videos"]["results"]:
			if t["type"] == "Trailer" and t["site"] == "YouTube": setInfo("trailer", trailer_url % t["key"])
	if param.get("s"):
		_meta["mediatype"] = "season"
		_meta["season"] = param["s"]
		season = [i for i in _seasons if i["season_number"] == int(param["s"])][0]
		_meta["title"] = season["name"]
		if season.get("overview"): 
			setInfo("plot", season.get("overview"))
		else:
			cacheOk, seasonmeta = get_cache({"id": param["id"], "s":param["s"]})
			if not cacheOk:
				tmdb_url+="/season/%s" % param["s"]
				seasonmeta = requests.get(tmdb_url, params=url_params).json()
				set_cache({"id": param["id"], "s":param["s"]}, seasonmeta, 75600)
			if seasonmeta.get('translations') and len(seasonmeta['translations']['translations']) > 0:
				overviews = seasonmeta['translations']['translations']
				for overview in overviews:
					if overview['data']['overview']:
						if overview['name'] == "Deutsch" or  overview['iso_639_1'] == "de": #  or  overview['name'] == "English":
							setInfo("plot", overview['data']['overview'])
							break
						if overview['name'] == "English":
							setInfo("plot", overview['data']['overview'])
		_meta["sortepisode"] = season["episode_count"]
		setproperties("TotalEpisodes", season["episode_count"])
		setInfo("aired", season.get("air_date"))
		if _meta.get("aired")  and len(_meta["aired"]) == 10: _meta["year"] = int(_meta["aired"][:4])
		if season.get("poster_path"): _art["poster"] = poster + season["poster_path"]
	if param.get("s") and param.get("e"):
		_meta["mediatype"] = "episode"
		_meta["episode"] = int(param.get("e"))
		cacheOk, meta = get_cache({"id": param["id"], "s":param["s"]})
		if not cacheOk:
			tmdb_url+="/season/%s" % param["s"]
			meta = requests.get(tmdb_url, params=url_params).json()
			set_cache({"id": param["id"], "s":param["s"]}, meta, 75600)
		_episodes = meta["episodes"]
		episode = [i for i in _episodes if i["episode_number"] == int(param["e"])][0]
		_meta["title"] = episode["name"] if episode.get("name") else "Staffel:%s Episode:%s" % (param["s"], param["e"])
		if episode.get("overview") and episode.get("name"):
			_meta["plot"] = episode.get("overview")
		else:
			cacheOk, episodemeta = get_cache({"id": param["id"], "s":param["s"], "e":param["e"]})
			if not cacheOk:
				tmdb_url+="/season/%s/episode/%s" % (param["s"], param["e"])
				episodemeta = requests.get(tmdb_url, params=url_params).json()
				set_cache({"id": param["id"], "s":param["s"], "e": param["e"]}, episodemeta, 75600)
			if episodemeta.get('translations') and len(episodemeta['translations']['translations']) > 0:
				overviews = episodemeta['translations']['translations']
				for overview in overviews:
					if overview['data']['overview']:
						if overview['name'] == "Deutsch" or  overview['iso_639_1'] == "de": #  or  overview['name'] == "English":
							setInfo("plot", overview['data']['overview'])
							break
						if overview['name'] == "English":
							setInfo("plot", overview['data']['overview'])
				for overview in overviews:
					if overview['data']['name']:
						if overview['name'] == "Deutsch" or  overview['iso_639_1'] == "de":
							setInfo("title", overview['data']['name'])
							break
						if overview['name'] == "English":
							setInfo("title", overview['data']['name'])				
		_meta["aired"] = episode.get("air_date")
		setInfo("rating", episode.get("vote_average"))
		setInfo("votes", episode.get("vote_count"))
		if _meta.get("aired")  and len(_meta["aired"]) == 10: _meta["year"] = int(_meta["aired"][:4])
		setInfo("code", episode.get("production_code"))
		if episode.get("runtime"): _meta["duration"] = episode["runtime"]*60
		if episode.get("still_path"): _art["thumb"] = poster + episode["still_path"]
		if episode.get("crew"):
			for crew in episode["crew"]:
				if crew["department"] == "Directing": _meta["director"].append(crew["name"])
				elif crew["department"] == "Writing": _meta["writer"].append(crew["name"])
		if episode.get("guest_stars"):
			for i in episode["guest_stars"]:
				if i.get("profile_path"): _cast.append({"name":i["name"], "role":i["character"], "thumbnail": poster + i["profile_path"], "order": i["order"]})
				else:
					if i.get("name"): _cast.append({"name":i.get("name", ""), "role":i.get("character", ""), "order": i.get("order", 0)})
	if _meta["mediatype"] in ["movie", "episode"]: _property["IsPlayable"] = "true"
	casts = meta.get("credits",{}).get("cast")
	crews = meta.get("credits",{}).get("crew")
	if crews:
		for crew in crews:
			if crew["job"] == "Director": _meta["director"].append(crew["name"])
			if crew["department"] == "Writing": _meta["writer"].append(crew["name"])
	created_by =  meta.get("created_by")
	if created_by:
		for i in created_by:
			_meta["director"].append(i["name"])
	if casts:
		for a in casts:
			cast = {"name":a["name"], "role":a["character"], "order": a["order"]}
			if a.get("profile_path"): cast["thumbnail"] = poster + a["profile_path"]
			_cast.append(cast)
	return {"infos":_meta, "art":_art, "properties":_property, "cast":_cast, "ids":_ids, "seasons":_seasons, "episodes":_episodes}

def log(msg, header=""):
	try: msg = json.dumps(msg, indent=4)
	except: pass
	if header: header+="\n"
	out = "\n####VAVOOTO####\n%s%s\n########" % (header, msg)
	mode = xbmc.LOGINFO if addon.getSetting("debug") == "true" else xbmc.LOGDEBUG
	xbmc.log(out, mode)

def showFailedNotification(msg="Keine Streams gefunden"):
	log(msg)
	execute("Notification(VAVOO.TO,%s,5000,%s)" % (msg,addonInfo("icon")))
	sys.exit()
	
def addDir(name, params, iconimage="DefaultFolder.png", isFolder=True, context=[]):
	liz = ListItem(name)
	liz.setArt({"icon":iconimage, "thumb":iconimage})
	plot = " "
	if not context: context.append(("Einstellungen", "RunPlugin(%s?action=settings)" % sys.argv[0]))
	if name == "TV Favoriten (Live)":
		plot = "[COLOR gold]Liste der eigenen Live Favoriten[/COLOR]"
		context.append(("Alle Favoriten entfernen", "RunPlugin(%s?action=delallTvFavorit)" % sys.argv[0]))
	liz.addContextMenuItems(context)
	infoLabels={"title": name, "plot": plot}
	info_tag = ListItemInfoTag(liz, 'video')
	info_tag.set_info(infoLabels)
	add(params, liz, isFolder)

def addDir2(name_, icon_, action, context = [], isFolder=True, **params):
	params["action"] = action
	iconimage = getIcon(icon_) if getIcon(icon_) else icon_
	addDir(name_, params, iconimage, isFolder, context)

def createListItem(params):
	data = get_meta(params)
	if not data: return
	infos = data["infos"]
	if params.get("e"):o = ListItem("S%sxE%s %s" %(params["s"], params["e"], infos["title"]) , infos["title"])
	else: o = ListItem('%s (%s)' %(infos["title"], infos["year"])) if 'year' in infos and infos["year"] else ListItem(infos["title"])
	o.setProperties(data["properties"])
	art = data["art"]
	if art.get("poster"): art["icon"] = art["poster"]
	if art.get("thumb"): art["poster"] = art["thumb"]
	o.setArt(art)
	info_tag = ListItemInfoTag(o, 'video')
	info_tag.set_info(infos)
	info_tag.set_cast(data["cast"])
	info_tag.set_unique_ids(data["ids"], "tmdb")
	return o

def yesno(heading, line1, line2='', line3='', nolabel='', yeslabel=''):
	return dialog.yesno(heading, line1+"\n"+line2+"\n"+line3, nolabel, yeslabel)
	
def ok(heading, line1, line2='', line3=''):
	return dialog.ok(heading, line1+"\n"+line2+"\n"+line3)

def getIcon(name):
	if exists("%s/resources/art/%s.png" % (addonpath ,name)):return "%s/resources/art/%s.png" % (addonpath ,name)
	elif exists("special://skin/extras/videogenre/%s.png" % name): return translatePath("special://skin/extras/videogenre/%s.png" % name)
	else: return  "%s.png" % name

def end(succeeded=True, cacheToDisc=True):
	return xbmcplugin.endOfDirectory(int(sys.argv[1]), succeeded=succeeded, cacheToDisc=cacheToDisc)
	
def add(params, o, isFolder=False):
	return xbmcplugin.addDirectoryItem(int(sys.argv[1]), url_for(params), o, isFolder)

def set_category(cat):
	xbmcplugin.setPluginCategory(int(sys.argv[1]), cat)

def set_content(cont):
	xbmcplugin.setContent(int(sys.argv[1]), cont)
	
def set_resolved(item):
	xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, item)

def sort_method():
	xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_VIDEO_TITLE)

def convertPluginParams(params):
	if isinstance(params, dict):
		p = []
		for key, value in list(params.items()):
			if isinstance(value, int):
				value = str(value)
			p.append(urlencode({key: value}))
		params = '&'.join(p)
	return params

def url_for(params):
	return "%s?%s" % (sys.argv[0], convertPluginParams(params))