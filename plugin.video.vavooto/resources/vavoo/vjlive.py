# -*- coding: utf-8 -*-
from vavoo.utils import *

chanicons = ['13thstreet.png', '3sat.png', 'animalplanet.png', 'anixe.png', 'ard.png', 'ardalpha.png', 'arte.png', 'atv.png', 'atv2.png', 'automotorsport.png', 'axnblack.png', 'axnwhite.png', 'br.png', 'cartoonito.png', 'cartoonnetwork.png', 'comedycentral.png', 'curiositychannel.png', 'fix&foxi.png', 'dazn1.png', 'dazn2.png', 'deluxemusic.png', 'nationalgeographic.png', 'dmax.png', 'eurosport1.png', 'eurosport2.png', 'nickjunior.png', 'superrtl.png', 'heimatkanal.png', 'history.png', 'hr.png', 'jukebox.png', 'kabel1doku.png', 'pro7.png', 'pro7maxx.png', 'pro7fun.png', 'rtl2.png', 'kika.png', 'kinowelt.png', 'mdr.png', 'universaltv.png', 'discovery.png', 'mtv.png', 'n24doku.png', 'natgeowild.png', 'sky1.png', 'ndr.png', 'nickelodeon.png', 'nitro.png', 'romancetv.png', 'ntv.png', 'one.png', 'orf1.png', 'orf2.png', 'orf3.png', 'orfsportplus.png', 'phoenix.png', 'geotv.png', 'puls24.png', 'puls4.png', 'rbb.png', 'ric.png', 'motorvision.png', 'rtl.png', 'rtlcrime.png', 'rtlliving.png', 'kabel1.png', 'rtlpassion.png', 'rtlup.png', 'sat1.png', 'sat1emotions.png', 'sat1gold.png', 'servustv.png', 'silverline.png', 'sixx.png', 'skyatlantic.png', 'skycinemaaction.png', 'skycinemaclassics.png', 'skycinemafamily.png', 'skycinemahighlights.png', 'skycinemapremieren.png', 'skycrime.png', 'skydocumentaries.png', 'skykrimi.png', 'skynature.png', 'skyreplay.png', 'skyshowcase.png', 'spiegelgeschichte.png', 'kabel1classics.png', 'sport1.png', 'sportdigital.png', 'swr.png', 'syfy.png', 'tagesschau24.png', 'tele5.png', 'tlc.png', 'toggoplus.png', 'crime+investigation.png', 'vox.png', 'voxup.png', 'warnertvcomedy.png', 'warnertvfilm.png', 'warnertvserie.png', 'wdr.png', 'welt.png', 'weltderwunder.png', 'zdf.png', 'zdfinfo.png', 'zdfneo.png', 'zeeone.png', 'skycinemathriller.png']

def get_stream_source(link):
	if not link:
		return ""
	if isinstance(link, dict):
		if link.get("source") in ("lite", "2ix2") or link.get("stream_type") in ("2ix2", "nydus"):
			return "2ix2"
		return "STALKER"
	elif isinstance(link, str):
		if "vavoo" in link.lower():
			return "VAVOO"
		elif "2ix2" in link.lower() or "nydus" in link.lower():
			return "2ix2"
		return "STALKER"
	return "VAVOO"

TS_AUDIO_STREAM_TYPES = {0x03, 0x04, 0x0F, 0x11, 0x81, 0x87}
TS_AUDIO_DESCRIPTOR_TYPES = {0x6A: 0x81, 0x7A: 0x87, 0x7C: 0x0F}
TS_AUDIO_PROBE_BYTES = 512 * 1024

def _ts_payload(packet):
	if len(packet) != 188 or packet[0] != 0x47 or packet[1] & 0x80:
		return None, False
	if not packet[3] & 0x10:
		return b"", bool(packet[1] & 0x40)
	offset = 4
	if packet[3] & 0x20:
		offset += 1 + packet[4]
	if offset > 188:
		return None, False
	return packet[offset:], bool(packet[1] & 0x40)

def _ts_section(payload, payload_start):
	if not payload_start or not payload:
		return None
	pointer = payload[0]
	start = 1 + pointer
	if start + 3 > len(payload):
		return None
	length = 3 + (((payload[start + 1] & 0x0F) << 8) | payload[start + 2])
	if length < 8 or start + length > len(payload):
		return None
	return payload[start:start + length]

def _ts_audio_pids(data, sync):
	pmt_pids = set()
	audio = {}
	packets = [data[pos:pos + 188] for pos in range(sync, len(data) - 187, 188)]
	for packet in packets:
		pid = ((packet[1] & 0x1F) << 8) | packet[2]
		if pid != 0:
			continue
		payload, start = _ts_payload(packet)
		section = _ts_section(payload, start)
		if not section or section[0] != 0x00:
			continue
		end = len(section) - 4
		for pos in range(8, end - 3, 4):
			program = (section[pos] << 8) | section[pos + 1]
			if program:
				pmt_pids.add(((section[pos + 2] & 0x1F) << 8) | section[pos + 3])
	for packet in packets:
		pid = ((packet[1] & 0x1F) << 8) | packet[2]
		if pid not in pmt_pids:
			continue
		payload, start = _ts_payload(packet)
		section = _ts_section(payload, start)
		if not section or section[0] != 0x02 or len(section) < 16:
			continue
		program_info_length = ((section[10] & 0x0F) << 8) | section[11]
		pos = 12 + program_info_length
		end = len(section) - 4
		while pos + 5 <= end:
			stream_type = section[pos]
			stream_pid = ((section[pos + 1] & 0x1F) << 8) | section[pos + 2]
			info_length = ((section[pos + 3] & 0x0F) << 8) | section[pos + 4]
			descriptors = section[pos + 5:pos + 5 + info_length]
			desc_pos = 0
			descriptor_type = None
			while desc_pos + 2 <= len(descriptors):
				tag = descriptors[desc_pos]
				size = descriptors[desc_pos + 1]
				if tag in TS_AUDIO_DESCRIPTOR_TYPES:
					descriptor_type = TS_AUDIO_DESCRIPTOR_TYPES[tag]
				desc_pos += 2 + size
			if stream_type in TS_AUDIO_STREAM_TYPES:
				audio[stream_pid] = stream_type
			elif stream_type == 0x06 and descriptor_type is not None:
				audio[stream_pid] = descriptor_type
			pos += 5 + info_length
	return packets, audio

def _valid_audio_frame(data, stream_type):
	# PES header entfernen; mehrere Sync-Treffer verhindern, dass ein zufaelliges
	# Bytepaar als funktionierende Audiospur gilt.
	if data.startswith(b"\x00\x00\x01") and len(data) >= 9:
		data = data[9 + data[8]:]
	hits = 0
	for pos in range(max(0, len(data) - 7)):
		valid = False
		if stream_type in (0x81, 0x87, 0x06) and data[pos:pos + 2] == b"\x0b\x77":
			valid = data[pos + 5] >> 3 <= 16
		elif stream_type == 0x0F and data[pos] == 0xFF and data[pos + 1] & 0xF6 == 0xF0:
			freq = (data[pos + 2] >> 2) & 0x0F
			channels = ((data[pos + 2] & 1) << 2) | (data[pos + 3] >> 6)
			valid = freq < 13 and channels > 0
		elif stream_type == 0x11 and data[pos] == 0x56 and data[pos + 1] & 0xE0 == 0xE0:
			valid = True
		elif stream_type in (0x03, 0x04) and data[pos] == 0xFF and data[pos + 1] & 0xE0 == 0xE0:
			version = (data[pos + 1] >> 3) & 3
			layer = (data[pos + 1] >> 1) & 3
			bitrate = data[pos + 2] >> 4
			rate = (data[pos + 2] >> 2) & 3
			valid = version != 1 and layer != 0 and 0 < bitrate < 15 and rate != 3
		if valid:
			hits += 1
			if hits >= 2:
				return True
	return False

def _mpeg_ts_has_audio(data):
	"""True/False fuer MPEG-TS, None wenn die Daten kein MPEG-TS sind."""
	sync = next((offset for offset in range(min(188, len(data)))
		if all(pos < len(data) and data[pos] == 0x47
			for pos in (offset, offset + 188, offset + 376, offset + 564))), None)
	if sync is None:
		return None
	packets, audio_pids = _ts_audio_pids(data, sync)
	if not audio_pids:
		return False
	payloads = {pid: bytearray() for pid in audio_pids}
	for packet in packets:
		pid = ((packet[1] & 0x1F) << 8) | packet[2]
		if pid not in payloads:
			continue
		payload, _ = _ts_payload(packet)
		if payload:
			payloads[pid].extend(payload)
	return any(_valid_audio_frame(bytes(payloads[pid]), stream_type)
		for pid, stream_type in audio_pids.items())

def _read_probe(response, limit=TS_AUDIO_PROBE_BYTES):
	data = bytearray()
	for chunk in response.iter_content(16384):
		if chunk:
			data.extend(chunk)
		if len(data) >= limit:
			break
	return bytes(data[:limit])

def test_m3u8(url, headers=None, verify=True):
	headers = headers or {}
	response = None
	try:
		response = request("GET", url, headers=headers, timeout=10, stream=True, retries=0, verify=verify)
		response.raise_for_status()
		is_hls = "m3u8" in url.lower() or "/hls/" in url.lower() or "mpegurl" in response.headers.get("Content-Type", "").lower()
		if getSetting("live_m3u8_test") != "true":
			return True
		if not is_hls:
			probe = _read_probe(response)
			has_audio = _mpeg_ts_has_audio(probe)
			if has_audio is False:
				raise ValueError("MPEG-TS enthält keine verwertbaren Audiodaten")
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
			segment_headers["Range"] = "bytes=0-%s" % (TS_AUDIO_PROBE_BYTES - 1)
			response = request("GET", target, headers=segment_headers, timeout=10, stream=True, retries=0, verify=verify)
			response.raise_for_status()
			probe = _read_probe(response)
			if not probe:
				raise ValueError("M3U8-Mediensegment ist leer")
			has_audio = _mpeg_ts_has_audio(probe)
			if has_audio is False:
				raise ValueError("M3U8-Mediensegment enthält keine verwertbaren Audiodaten")
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
				channel = link
				link, headers = StalkerPortal(get_cache_or_setting("stalkerurl"), get_cache_or_setting("mac")).get_tv_stream_url(channel)
				if test_m3u8(link, headers):
					log("function resolve_link Status: OK")
					if getSetting("stalker_ts_hls_proxy") != "false" and is_mpeg_ts_url(link):
						from vavoo.live_proxy import get_stalker_proxy_url
						return get_stalker_proxy_url(link, headers, channel), None
					return link, "&".join([f"{k}={v}" for k, v in headers.items()])
			except Exception:
				log(format_exc())
			return None, None
	elif not "vavoo" in str(link):
		from vavoo.stalker import StalkerPortal
		try:
			channel = link
			link, headers = StalkerPortal(get_cache_or_setting("stalkerurl"), get_cache_or_setting("mac")).get_tv_stream_url(channel)
			if test_m3u8(link, headers):
				log("function resolve_link Status: OK")
				if getSetting("stalker_ts_hls_proxy") != "false" and is_mpeg_ts_url(link):
					from vavoo.live_proxy import get_stalker_proxy_url
					return get_stalker_proxy_url(link, headers, channel), None
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
					return get_vavoo_proxy_url(streamurl, link), None
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
			"use_load_balancing": item.get("use_load_balancing", 0),
			"source": "stalker"
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
		"5": ["stalker", "lite", "vavoo"],
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

def is_mpeg_ts_url(url):
	"""Erkennt explizite MPEG-TS-Links, insbesondere Stalker play/live.php URLs."""
	try:
		parsed = urlsplit(str(url).split("|", 1)[0])
		path = parsed.path.lower()
		query = dict(parse_qsl(parsed.query, keep_blank_values=True))
		extension = str(query.get("extension", "")).lower().lstrip(".")
		return path.endswith((".ts", ".mpegts")) or extension in ("ts", "mpegts")
	except Exception:
		return False

def livePlay(name, type=None, group=None, retry='0', idx=None):
	try:
		retry = max(0, int(retry))
	except (TypeError, ValueError):
		retry = 0
	is_retry = retry > 0
	try:
		m = getchannels(type, group).get(name)
	except Exception:
		log("livePlay: Kanalliste nicht abrufbar\n%s" % format_exc())
		m = None
	if not m:
		# waehrend eines Auto-Retry keinen Dialog aufpoppen lassen
		if not is_retry:
			showFailedNotification()
		return
	n = len(m)
	try:
		retry_setting = max(0, int(getSetting("live_retry_count")))
	except (TypeError, ValueError):
		retry_setting = 3
	# mindestens jede Quelle einmal durchprobieren
	max_retries = max(retry_setting, n)

	# Startindex: bei Auto-Retry explizit uebergeben, sonst 0
	i = 0
	if idx is not None:
		try:
			i = int(idx) % n
		except (TypeError, ValueError):
			i = 0

	# Quellenauswahl-UI nur beim ersten Versuch, nie waehrend eines Auto-Retry
	if n > 1 and not is_retry:
		mode = getSetting("auto")
		if mode == "0":
			cacheOk, last = get_cache("last")
			if cacheOk and isinstance(last, dict) and last.get("idn") == name:
				i = (last.get("num", -1) + 1) % n
		elif mode == "1":
			if not handle_wait(name):  # Dialog aufrufen
				sel = selectDialog(["STREAM %s (%s)" % (x, get_stream_source(m[x - 1])) for x in range(1, n + 1)])
				if sel < 0: return
				i = sel
		else:
			sel = selectDialog(["STREAM %s (%s)" % (x, get_stream_source(m[x - 1])) for x in range(1, n + 1)])
			if sel < 0: return
			i = sel

	# Quelle(n) aufloesen, bei Fehlschlag zur naechsten wandern
	url = headers = None
	for _ in range(n):
		url, headers = resolve_link(m[i])
		if url: break
		i = (i + 1) % n
	if not url:
		showFailedNotification("Keine funktionierende Quelle")
		return

	# nur bei nutzer-initiiertem Start merken, nicht bei jedem Failover-Hop
	if not is_retry:
		set_cache("last", {"idn": name, "num": i}, 2)
	# Titel/Plot NACH der Aufloesung -> zeigt die tatsaechlich verwendete Quelle
	src = get_stream_source(m[i])
	title = "%s (%s/%s %s)" % (name, i + 1, n, src) if n > 1 else ("%s (%s)" % (name, src) if src else name)

	url_is_proxy = "127.0.0.1" in url
	want_retry = getSetting("live_auto_retry") == "true"

	live_player = None
	# Monitor-Schleife haelt zusaetzlich den Plugin-Prozess (und damit den lokalen
	# HLS-Proxy-Thread) am Leben, solange die Wiedergabe laeuft.
	if want_retry or url_is_proxy:
		from vavoo.player import LivePlayer
		live_player = LivePlayer()
	plot_title = "[B]%s[/B] - Stream %s von %s (%s)" % (name, i + 1, n, src) if n > 1 else ("[B]%s[/B] (%s)" % (name, src) if src else "[B]%s[/B]" % name)
	infoLabels = {"title": title, "plot": plot_title}
	o = ListItem(name)
	log("Spiele %s" % url)
	# Live-TV laeuft ueber inputstream.ffmpegdirect. MPEG-TS ist kein Manifest-
	# Stream und darf daher nicht als HLS/Timeshift deklariert werden.
	is_mpeg_ts = is_mpeg_ts_url(url)
	o.setProperty('inputstream', 'inputstream.ffmpegdirect')
	o.setProperty('inputstream.ffmpegdirect.is_realtime_stream', 'true')
	o.setProperty('inputstream.ffmpegdirect.open_mode', 'ffmpeg')
	if is_mpeg_ts:
		o.setMimeType('video/mp2t')
	else:
		o.setMimeType('application/x-mpegURL')
		o.setProperty('inputstream.ffmpegdirect.stream_mode', 'timeshift')
		o.setProperty('inputstream.ffmpegdirect.manifest_type', 'hls')
	o.setProperty('inputstream.ffmpegdirect.protocol_whitelist','http,https,tcp,tls,crypto')
	stream_opts = ':'.join(['http_persistent=1','multiple_requests=1','reconnect=1','reconnect_streamed=1','reconnect_delay_max=2','timeout=30000000'])
	o.setProperty('inputstream.ffmpegdirect.stream_opts',stream_opts)
	o.setProperty('inputstream.ffmpegdirect.user_agent', 'libmpv')
	if headers:
		url += f"|{headers}"
	o.setPath(url)
	o.setProperty("IsPlayable", "true")
	info_tag = ListItemInfoTag(o, 'video')
	info_tag.set_info(infoLabels)
	set_resolved(o)
	end()
	if not live_player:
		return

	# Stillstand 8s / kein Bild nach 12s -> Abriss, naechste Quelle.
	# "stopped"/"ended" ohne je gelaufenes Bild wird ebenfalls als Fehlstart gewertet.
	result = live_player.wait_for_failure()
	if result not in ("ended", "stalled", "startup_failed"):
		# "stopped" / "abort" -> Nutzer hat beendet, kein Retry
		log("Live-TV kein Retry noetig: %s" % result)
		return

	if not (want_retry and retry < max_retries):
		log("Live-TV Retry erschoepft/deaktiviert (%s)" % result)
		if want_retry and n > 1:
			dialog.notification("VAVOO.TO", "Alle Quellen fehlgeschlagen", xbmcgui.NOTIFICATION_WARNING, 3000)
		return

	next_i = (i + 1) % n
	next_src = get_stream_source(m[next_i])
	log("Live-TV-Stream %s -> naechste Quelle %s/%s (%s) (Versuch %s/%s)" % (result, next_i + 1, n, next_src, retry + 1, max_retries))
	if n > 1:
		dialog.notification("VAVOO.TO", "Wechsle zu Stream %s/%s (%s)" % (next_i + 1, n, next_src), xbmcgui.NOTIFICATION_INFO, 2000)
	try:
		if live_player.isPlaying():
			live_player.stop()
			monitor.waitForAbort(1)
	except Exception:
		log(format_exc())
	params = {"name": name, "retry": str(retry + 1), "idx": str(next_i)}
	if type: params["type"] = type
	if group: params["group"] = group
	live_player.play(url_for(params))

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
