# -*- coding: utf-8 -*-
from vavoo.utils import *

chanicons = ['13thstreet.png', '3sat.png', 'animalplanet.png', 'anixe.png', 'ard.png', 'ardalpha.png', 'arte.png', 'atv.png', 'atv2.png', 'automotorsport.png', 'axnblack.png', 'axnwhite.png', 'br.png', 'cartoonito.png', 'cartoonnetwork.png', 'comedycentral.png', 'curiositychannel.png', 'fix&foxi.png', 'dazn1.png', 'dazn2.png', 'deluxemusic.png', 'nationalgeographic.png', 'dmax.png', 'eurosport1.png', 'eurosport2.png', 'nickjunior.png', 'superrtl.png', 'heimatkanal.png', 'history.png', 'hr.png', 'jukebox.png', 'kabel1doku.png', 'pro7.png', 'pro7maxx.png', 'pro7fun.png', 'rtl2.png', 'kika.png', 'kinowelt.png', 'mdr.png', 'universaltv.png', 'discovery.png', 'mtv.png', 'n24doku.png', 'natgeowild.png', 'sky1.png', 'ndr.png', 'nickelodeon.png', 'nitro.png', 'romancetv.png', 'ntv.png', 'one.png', 'orf1.png', 'orf2.png', 'orf3.png', 'orfsportplus.png', 'phoenix.png', 'geotv.png', 'puls24.png', 'puls4.png', 'rbb.png', 'ric.png', 'motorvision.png', 'rtl.png', 'rtlcrime.png', 'rtlliving.png', 'kabel1.png', 'rtlpassion.png', 'rtlup.png', 'sat1.png', 'sat1emotions.png', 'sat1gold.png', 'servustv.png', 'silverline.png', 'sixx.png', 'skyatlantic.png', 'skycinemaaction.png', 'skycinemaclassics.png', 'skycinemafamily.png', 'skycinemahighlights.png', 'skycinemapremieren.png', 'skycrime.png', 'skydocumentaries.png', 'skykrimi.png', 'skynature.png', 'skyreplay.png', 'skyshowcase.png', 'spiegelgeschichte.png', 'kabel1classics.png', 'sport1.png', 'sportdigital.png', 'swr.png', 'syfy.png', 'tagesschau24.png', 'tele5.png', 'tlc.png', 'toggoplus.png', 'crime+investigation.png', 'vox.png', 'voxup.png', 'warnertvcomedy.png', 'warnertvfilm.png', 'warnertvserie.png', 'wdr.png', 'welt.png', 'weltderwunder.png', 'zdf.png', 'zdfinfo.png', 'zdfneo.png', 'zeeone.png', 'skycinemathriller.png']

def test_m3u8(url, headers=None, verify=True):
	headers = headers or {}
	response = None
	try:
		response = request("GET", url, headers=headers, timeout=10, stream=True, retries=0, verify=verify)
		response.raise_for_status()
		is_hls = "m3u8" in url.lower() or "/hls/" in url.lower() or "mpegurl" in response.headers.get("Content-Type", "").lower()
		if getSetting("live_m3u8_test") != "true" or not is_hls:
			return True

		playlist_url = url
		for level in range(3):
			text = response.text
			response.close()
			response = None
			if "#EXTM3U" not in text[:1024]:
				raise ValueError("Ungültige M3U8-Playlist")
			entries = [line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]
			if not entries:
				raise ValueError("M3U8 enthält keine Medien-URL")
			target = urljoin(playlist_url, entries[0])
			if ("#EXT-X-STREAM-INF" in text or ".m3u8" in target.lower()) and level < 2:
				playlist_url = target
				response = request("GET", target, headers=headers, timeout=10, stream=True, retries=0, verify=verify)
				response.raise_for_status()
				continue

			segment_headers = dict(headers)
			segment_headers["Range"] = "bytes=0-1023"
			response = request("GET", target, headers=segment_headers, timeout=10, stream=True, retries=0, verify=verify)
			response.raise_for_status()
			if not next(response.iter_content(1), b""):
				raise ValueError("M3U8-Mediensegment ist leer")
			return True
	except Exception:
		log("M3U8-Streamtest fehlgeschlagen\n%s" % format_exc())
		return False
	finally:
		if response is not None:
			response.close()

def resolve_link(link):
	if isinstance(link, dict):
		if link.get("source") == "lite":
			from vavoo.linear_lite import resolve_lite_stream
			try:
				stream_url, headers = resolve_lite_stream(link)
				if stream_url and test_m3u8(stream_url, headers=dict(parse_qsl(headers)) if headers else None):
					log("function resolve_link (lite) Status: OK")
					return stream_url, headers
			except Exception:
				log(format_exc())
			return None, None
		else:
			from vavoo.stalker import StalkerPortal
			try:
				link, headers = StalkerPortal(get_cache_or_setting("stalkerurl"), get_cache_or_setting("mac")).get_tv_stream_url(link)
				if test_m3u8(link, headers):
					log("function resolve_link Status: OK")
					return link, "&".join([f"{k}={v}" for k, v in headers.items()])
			except Exception:
				log(format_exc())
			return None, None
	elif not "vavoo" in str(link):
		from vavoo.stalker import StalkerPortal
		try:
			link, headers = StalkerPortal(get_cache_or_setting("stalkerurl"), get_cache_or_setting("mac")).get_tv_stream_url(link)
			if test_m3u8(link, headers):
				log("function resolve_link Status: OK")
				return link, "&".join([f"{k}={v}" for k, v in headers.items()])
		except Exception:
			log(format_exc())
		return None, None
	else:
		_headers = {"user-agent": "MediaHubMX/2", "content-type": "application/json; charset=utf-8", "accept-encoding": "gzip", "mediahubmx-signature": getAuthSignature()}
		_data = {"language": "de", "region": "AT", "url": link, "clientVersion": "3.1.0"}
		url = "https://vavoo.to/mediahubmx-resolve.json"
		try:
			streamurl = request_json("POST", url, json=_data, headers=_headers, timeout=10, retries=1)[0]["url"]
			if test_m3u8(streamurl, verify=False):
				log("function resolve_link Status: OK")
				if getSetting("vavoo_hls_proxy") == "true":
					from vavoo.live_proxy import get_vavoo_proxy_url
					return get_vavoo_proxy_url(streamurl), None
				return streamurl, None
		except Exception:
			log(format_exc())
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
		if any(ele in name for ele in ["***", "###", "---"]): continue
		name = filterout(name).strip()
		if not name or not name.strip("])"): continue
		if name not in sta_channels: sta_channels[name] = []
		channel = {
			"cmd": item["cmd"],
			"use_http_tmp_link": item.get("use_http_tmp_link", 0),
			"use_load_balancing": item.get("use_load_balancing", 0)
		}
		if channel not in sta_channels[name]:
			sta_channels[name].append(channel)
	return sta_channels
def getchannels(type=None, group=None):
	use_stalker = getSetting("stalker") == "true" and (type is None or type == "stalker")
	use_vavoo = getSetting("vavoo") == "true" and (type is None or type == "vavoo")
	use_lite = getSetting("lite") == "true" and (type is None or type == "lite")

	sta_channels = {}
	if use_stalker:
		sta_channels = get_stalker_channels() if group is None else get_stalker_channels([group])

	vav_channels = {}
	if use_vavoo:
		from vavoo.vavoo_tv import get_vav_channels
		vav_channels = get_vav_channels() if group is None else get_vav_channels([group])

	lite_channels = {}
	if use_lite:
		from vavoo.linear_lite import get_lite_channels
		lite_channels = get_lite_channels() if group is None else get_lite_channels([group])

	sta_channels = sta_channels if isinstance(sta_channels, dict) else {}
	vav_channels = vav_channels if isinstance(vav_channels, dict) else {}
	lite_channels = lite_channels if isinstance(lite_channels, dict) else {}

	priority_setting = getSetting("live_priority") or "0"
	priority_order = {
		"0": ["vavoo", "stalker", "lite"],
		"1": ["lite", "vavoo", "stalker"],
		"2": ["stalker", "vavoo", "lite"],
		"3": ["lite", "stalker", "vavoo"],
		"4": ["vavoo", "lite", "stalker"],
	}.get(priority_setting, ["vavoo", "stalker", "lite"])

	source_map = {
		"vavoo": vav_channels,
		"stalker": sta_channels,
		"lite": lite_channels,
	}

	all_names = set(sta_channels.keys()) | set(vav_channels.keys()) | set(lite_channels.keys())
	allchannels = {}
	for name in sorted(all_names):
		streams = []
		for src in priority_order:
			ch_dict = source_map.get(src, {})
			if name in ch_dict:
				for item in ch_dict[name]:
					if item not in streams:
						streams.append(item)
		if streams:
			allchannels[name] = streams

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

def livePlay(name, type=None, group=None, retry='0'):
	try:
		retry = max(0, int(retry))
	except (TypeError, ValueError):
		retry = 0
	try:
		max_retries = max(0, int(getSetting("live_retry_count")))
	except (TypeError, ValueError):
		max_retries = 1
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
	live_player = None
	if getSetting("live_auto_retry") == "true" and retry < max_retries:
		from vavoo.player import LivePlayer
		live_player = LivePlayer()
	infoLabels = {"title": title, "plot": "[B]%s[/B] - Stream %s von %s" % (name, i + 1, len(m))}
	o = ListItem(name)
	log("Spiele %s" % url)
	if "hls" in url or "m3u8" in url: inputstream = "inputstream.ffmpegdirect" if getSetting("hlsinputstream") == "0" else "inputstream.adaptive"
	else: inputstream = "inputstream.ffmpegdirect"
	o.setProperty("inputstream", inputstream)
	if inputstream == "inputstream.ffmpegdirect":
		o.setProperty('inputstream', 'inputstream.ffmpegdirect')
		o.setProperty('inputstream.ffmpegdirect.is_realtime_stream', 'true')
		o.setProperty('inputstream.ffmpegdirect.stream_mode', 'timeshift')
		o.setProperty('inputstream.ffmpegdirect.open_mode', 'ffmpeg')
		o.setProperty('inputstream.ffmpegdirect.manifest_type', 'hls')
		o.setProperty('inputstream.ffmpegdirect.protocol_whitelist','http,https,tcp,tls,crypto')
		stream_opts = ':'.join(['http_persistent=1','multiple_requests=1','reconnect=1','reconnect_streamed=1','reconnect_delay_max=2','timeout=10000000'])
		o.setProperty('inputstream.ffmpegdirect.stream_opts',stream_opts)
		o.setProperty('inputstream.ffmpegdirect.user_agent', 'libmpv')
		#if getSetting("openmode") != "0": o.setProperty("inputstream.ffmpegdirect.open_mode", "ffmpeg" if getSetting("openmode") == "1" else "curl")
	else:
		o.setProperty('inputstream.adaptive.manifest_type', 'hls')
		o.setProperty('inputstream.adaptive.stream_selection_type', 'adaptive')
		o.setProperty('inputstream.adaptive.config', '{"ssl_verify_peer":false}')
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
	if live_player:
		try:
			retry_delay = max(1, int(getSetting("live_retry_delay")))
		except (TypeError, ValueError):
			retry_delay = 10
		result = live_player.wait_for_failure(retry_delay)
		if result in ("ended", "stalled"):
			log("Live-TV-Stream %s; resolve Sender erneut" % result)
			dialog.notification("VAVOO.TO", "Stream unterbrochen - verbinde erneut", xbmcgui.NOTIFICATION_INFO, 3000)
			if result == "stalled" and live_player.isPlaying():
				live_player.stop()
			params = {"name": name, "retry": str(retry + 1)}
			if type: params["type"] = type
			if group: params["group"] = group
			live_player.play(url_for(params))
		else:
			log("Live-TV Auto-Retry nicht gestartet: %s" % result)

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
	except (TypeError, ValueError):
		lines = []
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
	except (TypeError, ValueError):
		return
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
	except (TypeError, ValueError):
		lines = []
	if delete:
		if name in lines:
			lines.remove(name)
	else:
		if name not in lines:
			lines.append(name)
	setSetting("favs", json.dumps(lines))
	if len(lines) == 0: execute("Action(ParentDir)")
	else: execute("Container.Refresh")
