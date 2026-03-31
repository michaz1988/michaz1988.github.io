# -*- coding: utf-8 -*-
from vavoo.utils import *

chanicons = ['13thstreet.png', '3sat.png', 'animalplanet.png', 'anixe.png', 'ard.png', 'ardalpha.png', 'arte.png', 'atv.png', 'atv2.png', 'automotorsport.png', 'axnblack.png', 'axnwhite.png', 'br.png', 'cartoonito.png', 'cartoonnetwork.png', 'comedycentral.png', 'curiositychannel.png', 'fix&foxi.png', 'dazn1.png', 'dazn2.png', 'deluxemusic.png', 'nationalgeographic.png', 'dmax.png', 'eurosport1.png', 'eurosport2.png', 'nickjunior.png', 'superrtl.png', 'heimatkanal.png', 'history.png', 'hr.png', 'jukebox.png', 'kabel1doku.png', 'pro7.png', 'pro7maxx.png', 'pro7fun.png', 'rtl2.png', 'kika.png', 'kinowelt.png', 'mdr.png', 'universaltv.png', 'discovery.png', 'mtv.png', 'n24doku.png', 'natgeowild.png', 'sky1.png', 'ndr.png', 'nickelodeon.png', 'nitro.png', 'romancetv.png', 'ntv.png', 'one.png', 'orf1.png', 'orf2.png', 'orf3.png', 'orfsportplus.png', 'phoenix.png', 'geotv.png', 'puls24.png', 'puls4.png', 'rbb.png', 'ric.png', 'motorvision.png', 'rtl.png', 'rtlcrime.png', 'rtlliving.png', 'kabel1.png', 'rtlpassion.png', 'rtlup.png', 'sat1.png', 'sat1emotions.png', 'sat1gold.png', 'servustv.png', 'silverline.png', 'sixx.png', 'skyatlantic.png', 'skycinemaaction.png', 'skycinemaclassics.png', 'skycinemafamily.png', 'skycinemahighlights.png', 'skycinemapremieren.png', 'skycrime.png', 'skydocumentaries.png', 'skykrimi.png', 'skynature.png', 'skyreplay.png', 'skyshowcase.png', 'spiegelgeschichte.png', 'kabel1classics.png', 'sport1.png', 'sportdigital.png', 'swr.png', 'syfy.png', 'tagesschau24.png', 'tele5.png', 'tlc.png', 'toggoplus.png', 'crime+investigation.png', 'vox.png', 'voxup.png', 'warnertvcomedy.png', 'warnertvfilm.png', 'warnertvserie.png', 'wdr.png', 'welt.png', 'weltderwunder.png', 'zdf.png', 'zdfinfo.png', 'zdfneo.png', 'zeeone.png', 'skycinemathriller.png']

def resolve_link(link):
	try:
		if not "vavoo" in link:
			from vavoo.stalker import StalkerPortal
			link, headers = StalkerPortal(get_cache_or_setting("stalkerurl"), get_cache_or_setting("mac")).get_tv_stream_url(link)
			# Wenn 403 erkannt und None zurückkommt: sofort abbrechen
			if not link: return None, None
			status = int(requests.get(link, headers=headers, timeout=10, stream=True).status_code)
			log(f"function resolve_link Staus :{status}")
			if status < 400: return link, "&".join([f"{k}={v}" for k, v in headers.items()])
		#elif getSetting("streammode") == "1":
		else:
			_headers = {"user-agent": "MediaHubMX/2", "accept": "application/json", "content-type": "application/json; charset=utf-8", "content-length": "115", "accept-encoding": "gzip", "mediahubmx-signature": getAuthSignature()}
			_data = {"language": "de", "region": "AT", "url": link, "clientVersion": "3.0.2"}
			url = "https://vavoo.to/mediahubmx-resolve.json"
			streamurl = requests.post(url, json=_data, headers=_headers).json()[0]["url"]
			status = int(requests.get(streamurl, timeout=10, stream=True).status_code)
			log(f"function resolve_link Staus :{status}")
			if status < 400: return streamurl, None
		#else:
			#streamurl = "%s?n=1&b=5&vavoo_auth=%s" % (link.replace("vavoo-iptv", "live2")[0:-12], gettsSignature())
			#log(streamurl)
			#status = int(requests.get(streamurl, headers={"User-Agent": "VAVOO/2.6"}, timeout=10, stream=True).status_code)
			#log(f"function resolve_link Staus :{status}")
			#if status < 400: return streamurl, "User-Agent=VAVOO/2.6"
	except: log(format_exc())
	return None, None

def get_stalker_channels(genres=False):
	if genres == False: cacheOk, genres = get_cache("stalker_groups")
	from vavoo.stalker import StalkerPortal, get_genres, new_mac
	if not genres: genres = get_genres()
	cacheOk, chan = get_cache("sta_channels")
	if not cacheOk:
		url, mac = get_cache_or_setting("stalkerurl"), get_cache_or_setting("mac")
		if not url or not mac:
			dialog.notification('VAVOO.TO', 'Kein Stalkerportal gewählt, deaktiviere Stalker', xbmcgui.NOTIFICATION_ERROR, 2000)
			setSetting("stalker", "false")
			return {}
		portal = StalkerPortal(url, mac)
		check = portal.check()
		if check == True: cacheOk, chan = get_cache("sta_channels")
		elif check == "IP BLOCKED":
			dialog.notification('VAVOO.TO', 'IP BLOCKED anderes Portal auswählen, deaktiviere Stalker', xbmcgui.NOTIFICATION_ERROR, 2000)
			setSetting("stalker", "false")
			return {}
		else:
			m = new_mac(True)
			if m == False:
				dialog.notification('VAVOO.TO', 'Keine funktionierende Mac gefunden, anderes Portal auswählen, deaktiviere Stalker', xbmcgui.NOTIFICATION_ERROR, 2000)
				setSetting("stalker", "false")
				return {}
		cacheOk, chan = get_cache("sta_channels")
		if not cacheOk: return {}
	sta_channels = {}
	for item in chan:
		if item["tv_genre_id"] not in genres: continue
		name = item["name"].upper()
		# if not name.isascii(): continue
		if any(ele in name for ele in ["***", "###", "---"]): continue
		name = filterout(name)
		if not name: continue
		if name not in sta_channels: sta_channels[name] = []
		if item["cmd"] not in sta_channels[name]:
			sta_channels[name].append(item["cmd"])
	return sta_channels

def getchannels(type=None, group=None):
	if getSetting("stalker") == "true" and not type == "vavoo":
		allchannels = get_stalker_channels() if type == None else get_stalker_channels([group])
	else: allchannels = {}
	if getSetting("vavoo") == "true" and not type == "stalker":
		from vavoo.vavoo_tv import get_vav_channels
		vav_channels = get_vav_channels() if type == None else get_vav_channels([group])
	else: vav_channels = {}
	for k, v in vav_channels.items():
		if k not in allchannels: allchannels[k] = []
		for n in v: allchannels[k].append(n)
	return allchannels

def handle_wait(kanal):
	create = progress.create("Abbrechen zur manuellen Auswahl", "STARTE  : %s" % kanal)
	time_to_wait = int(getSetting("count")) + 1
	for secs in range(1, time_to_wait):
		secs_left = time_to_wait - secs
		progress.update(int(secs / time_to_wait * 100), "STARTE  : %s\nStarte Stream in  : %s" % (kanal, secs_left))
		monitor.waitForAbort(1)
		if (progress.iscanceled()):
			progress.close()
			return False
	progress.close()
	return True

def livePlay(name, type=None, group=None):
	m = getchannels(type, group).get(name)
	if not m:
		showFailedNotification()
		return
	i, title = 0, None
	if len(m) > 1:
		if getSetting("auto") == "0":
			cacheOk, last = get_cache("last")
			if cacheOk and last.get("idn") == name: i = last.get("num") + 1
			if i >= len(m): i = 0
			title = "%s (%s/%s)" % (name, i + 1, len(m))  # wird verwendet für infoLabels
		elif getSetting("auto") == "1":
			if not handle_wait(name):  # Dialog aufrufen
				cap = []
				for i, n in enumerate(m, 1): cap.append("STREAM %s" % i)
				i = selectDialog(cap)
				if i < 0: return
			title = "%s (%s/%s)" % (name, i + 1, len(m))  # wird verwendet für infoLabels
		else:
			cap = []
			for i, n in enumerate(m, 1): cap.append("STREAM %s" % i)
			i = selectDialog(cap)
			if i < 0: return
			title = "%s (%s/%s)" % (name, i + 1, len(m))  # wird verwendet für infoLabels
	k = 0
	while True:
		k += 1
		if k > len(m): return
		url, headers = resolve_link(m[i])
		if url: break
		else:
			i += 1
			if i >= len(m): i = 0
	set_cache("last", {"idn": name, "num": i}, 2)
	title = title if title else name
	infoLabels = {"title": title, "plot": "[B]%s[/B] - Stream %s von %s" % (name, i + 1, len(m))}
	o = ListItem(name)
	log("Spiele %s" % url)
	if "hls" in url or "m3u8" in url: inputstream = "inputstream.ffmpegdirect" if getSetting("hlsinputstream") == "0" else "inputstream.adaptive"
	else: inputstream = "inputstream.ffmpegdirect"
	o.setProperty("inputstream", inputstream)
	if inputstream == "inputstream.ffmpegdirect":
		o.setProperty("inputstream.ffmpegdirect.is_realtime_stream", "true")
		o.setProperty("inputstream.ffmpegdirect.stream_mode", "timeshift")
		if getSetting("openmode") != "0": o.setProperty("inputstream.ffmpegdirect.open_mode", "ffmpeg" if getSetting("openmode") == "1" else "curl")
		if "hls" in url or "m3u8" in url: o.setProperty("inputstream.ffmpegdirect.manifest_type", "hls")
	if headers:
		if inputstream == "inputstream.adaptive":
			o.setProperty(f'{inputstream}.common_headers', headers)
			o.setProperty(f'{inputstream}.stream_headers', headers)
		else: url += f"|{headers}"
	o.setPath(url)
	o.setProperty("IsPlayable", "true")
	info_tag = ListItemInfoTag(o, 'video')
	info_tag.set_info(infoLabels)
	set_resolved(o)
	end()

def makem3u():
	m3u = ["#EXTM3U\n"]
	for name in getchannels(): m3u.append('#EXTINF:-1 group-title="Standart",%s\nplugin://plugin.video.vavooto/?name=%s\n' % (name.strip(), name.replace("&", "%26").replace("+", "%2b").strip()))
	m3uPath = os.path.join(addonprofile, "vavoo.m3u")
	with open(m3uPath, "w") as a:
		a.writelines(m3u)
	ok = dialog.ok('VAVOO.TO', 'm3u erstellt in %s' % m3uPath)

# edit kasi
def channels(items=None, type=None, group=None):
	try: lines = json.loads(getSetting("favs"))
	except: lines = []
	results = json.loads(items) if items else getchannels(type, group)
	for name in results:
		index = len(results[name])
		title = name if getSetting("stream_count") == "false" or index == 1 else "%s  (%s)" % (name, index)
		o = ListItem(name)
		img = "%s.png" % name.replace(" ", "").lower()
		iconimage = "DefaultTVShows.png"
		if img in chanicons: iconimage = "https://michaz1988.github.io/logos/%s" % img
		o.setArt({"icon": iconimage, "thumb": iconimage, "poster": iconimage})
		cm = []
		if not name in lines:
			cm.append(("zu TV Favoriten hinzufügen", "RunPlugin(%s?action=addTvFavorit&name=%s)" % (sys.argv[0], name.replace("&", "%26").replace("+", "%2b"))))
			plot = ""
		else:
			plot = "[COLOR gold]TV Favorit[/COLOR]"
			cm.append(("von TV Favoriten entfernen", "RunPlugin(%s?action=delTvFavorit&name=%s)" % (sys.argv[0], name.replace("&", "%26").replace("+", "%2b"))))
		cm.append(("Einstellungen", "RunPlugin(%s?action=settings)" % sys.argv[0]))
		cm.append(("m3u erstellen", "RunPlugin(%s?action=makem3u)" % sys.argv[0]))
		o.addContextMenuItems(cm)
		infoLabels = {"title": title, "plot": plot}
		info_tag = ListItemInfoTag(o, 'video')
		info_tag.set_info(infoLabels)
		o.setProperty("IsPlayable", "true")
		param = {"name": name, "type": type, "group": group} if type else {"name": name}
		add(param, o)
	sort_method()
	end()

def favchannels():
	try: lines = json.loads(getSetting("favs"))
	except: return
	for name in getchannels():
		if not name in lines: continue
		o = ListItem(name)
		img = "%s.png" % name.replace(" ", "").lower()
		iconimage = "DefaultTVShows.png"
		if img in chanicons: iconimage = "https://michaz1988.github.io/logos/%s" % img
		o.setArt({"icon": iconimage, "thumb": iconimage, "poster": iconimage})
		cm = []
		cm.append(("von TV Favoriten entfernen", "RunPlugin(%s?action=delTvFavorit&name=%s)" % (sys.argv[0], name.replace("&", "%26").replace("+", "%2b"))))
		cm.append(("Einstellungen", "RunPlugin(%s?action=settings)" % sys.argv[0]))
		o.addContextMenuItems(cm)
		infoLabels = {"title": name, "plot": "[COLOR gold]Liste der eigene Live Favoriten[/COLOR]"}
		info_tag = ListItemInfoTag(o, 'video')
		info_tag.set_info(infoLabels)
		o.setProperty("IsPlayable", "true")
		add({"name": name}, o)
	sort_method()
	end()

def change_favorit(name, delete=False):
	try:lines = json.loads(getSetting("favs"))
	except: lines = []
	if delete: lines.remove(name)
	else: lines.append(name)
	setSetting("favs", json.dumps(lines))
	if len(lines) == 0: execute("Action(ParentDir)")
	else: execute("Container.Refresh")