# -*- coding: utf-8 -*-
import re
import unicodedata

from vavoo.utils import *

def _portal_flag(value):
	return str(value).strip().lower() in ("1", "true", "yes")

def _stalker_net_error(exc):
	"""True bei Transport-/DNS-/Timeout-Fehlern - dann liegt es NICHT an der MAC."""
	s = ("%r %s" % (exc, exc)).lower()
	return any(k in s for k in (
		"timeout", "timed out", "connectionerror", "connection aborted", "connection reset",
		"connection refused", "nameresolution", "failed to resolve", "no address associated",
		"maxretryerror", "unreachable", "temporary failure", "[errno 7]", "[errno 111]",
		"[errno 104]", "[errno 110]", "[errno 101]", "remotedisconnected", "read timed out",
	))

def _is_german_language_group(title):
	raw_title = str(title)
	if any(flag in raw_title for flag in ("🇦🇹", "🇩🇪", "🇨🇭")):
		return True
	normalized_title = unicodedata.normalize("NFKD", raw_title)
	normalized_title = normalized_title.encode("ascii", "ignore").decode("ascii").casefold()
	tokens = set(re.findall(r"[a-z0-9]+", normalized_title))
	return bool(tokens.intersection({
		"at", "austria", "austrian", "osterreich",
		"de", "deutsch", "deutschland", "german", "germany",
		"ch", "schweiz", "swiss", "switzerland", "dach",
	}))

class Token:
	def __init__(self, value=None, time=0, mac=None, url=None):
		self.value = value
		self.time = time
		self.mac = mac
		self.url = url

class StalkerPortal:
	def __init__(self, portal_url, mac, persist=True):
		self.url = portal_url
		self.portal_url = portal_url.rstrip("/").replace('/c', '/server/load.php')
		self.mac = mac.strip()
		self.persist = persist          # False = Probe-Instanz, Token nicht global speichern
		self.__token = Token()
		self.__load_cache()
		self.headers = self.generate_headers()
		self.backoff_factor = 1

	def __load_cache(self):
		try:
			self.__token.__dict__ = json.loads(home.getProperty("token"))
			log('Loading token from cache')
		except Exception:
			log('No token in cache')

	def __save_cache(self):
		# In-Memory-Zustand immer aktuell halten (verhindert unnötigen Doppel-Handshake)
		self.__token.time = time.time()
		self.__token.mac = self.mac
		self.__token.url = self.portal_url
		if not self.persist:
			return
		log('Saving token to cache')
		home.setProperty("token", json.dumps(self.__token.__dict__))

	def generate_headers(self, include_auth=True, include_token=True, custom_headers=None):
		headers = {}
		headers["Accept"] = "*/*"
		headers["User-Agent"] = 'Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like Gecko) MAG200 stbapp ver: 4 rev: 1812 Mobile Safari/533.3'
		headers["Referer"] = self.url
		headers["Accept-Language"] = "en-US,en;q=0.5"
		headers["Pragma"] = "no-cache"
		headers["X-User-Agent"] = "Model: MAG250; Link: WiFi"
		headers["Host"] = urlparse(self.portal_url).netloc
		if include_auth and self.__token.value:
			headers["Authorization"] = "Bearer %s" % self.__token.value
		headers["Cookie"] = self.generate_cookies(include_token=include_token)
		headers["Connection"] = "Close"
		headers["Accept-Encoding"] = "gzip, deflate"
		if custom_headers:
			headers.update(custom_headers)
		log("Generated headers: %s" % headers)
		return headers

	def generate_cookies(self, include_token=True):
		cookies = {"mac": quote(self.mac), "stb_lang": "en", "timezone": quote("Europe/Paris")}
		if include_token and self.__token.value:
			cookies["token"] = quote(self.__token.value)
		return "; ".join(["%s=%s" % (key, value) for key, value in cookies.items()])

	def _retry_wait(self, attempt):
		sleep_time = self.backoff_factor * (2 ** (attempt - 1))
		log("Retrying after %s seconds..." % sleep_time)
		monitor.waitForAbort(sleep_time)

	def make_request_with_retries(self, params, retries=0, timeout=5):
		if not params.get("action") in ["handshake", "get_profile"]: self.ensure_token()
		params["JsHttpRequest"] = "1-xml"
		self._net_error = False
		for attempt in range(1, retries + 2):
			try:
				neterr = False
				try:
					log("Attempt %s: GET %s with params=%s" % (attempt, self.portal_url, params))
					response = request("GET", self.portal_url, params=params, headers=self.headers, timeout=timeout, retries=0)
					log("Received response: %s" % response.status_code)
					a = response.text
					blocked = response.status_code == 403 or "IP adresiniz engellenmistir." in a
					failed = response.status_code >= 400 or blocked or "js" not in a
				except Exception as e:
					log("Erster Portalversuch fehlgeschlagen: %s" % repr(e)[:150])
					a = ""
					blocked = False
					failed = True
					neterr = _stalker_net_error(e)
				if failed and self.headers.get("User-Agent") != BROWSER_UA:
					log("Zweiter Versuch mit Chrome User-Agent")
					chrome_headers = dict(self.headers)
					chrome_headers["User-Agent"] = BROWSER_UA
					try:
						response = request("GET", self.portal_url, params=params, headers=chrome_headers, timeout=timeout, retries=0)
						a = response.text
						blocked = response.status_code == 403 or "IP adresiniz engellenmistir." in a
						failed = response.status_code >= 400 or blocked or "js" not in a
						if not failed:
							self.headers = chrome_headers
							neterr = False
					except Exception as e:
						log("Chrome-Versuch fehlgeschlagen: %s" % repr(e)[:150])
						a = ""
						failed = True
						neterr = neterr or _stalker_net_error(e)
				if blocked:
					log("Abbruch: Portal blockiert")
					return "IP BLOCKED"
				if "js" in a:
					return json.loads(a)["js"]
				if neterr:
					# Netz-/Portalproblem -> MAC NICHT als defekt markieren, aber vor
					# dem naechsten Versuch mit Backoff warten (kein Sofort-Hammern).
					self._net_error = True
					if attempt <= retries:
						self._retry_wait(attempt)
						continue
					log("All %s attempts failed for URL %s" % (attempt, self.portal_url))
					return None
				# Portal hat geantwortet, aber ohne gueltige js-Daten -> MAC defekt.
				# Ein Retry aendert daran nichts -> sofort abbrechen.
				cacheOk, faultymac = get_cache("faultymac")
				if not cacheOk: faultymac = {}
				faultymac.setdefault(self.url, [])
				if self.mac not in faultymac[self.url]:
					faultymac[self.url].append(self.mac)
				set_cache("faultymac", faultymac, 12)
				return None
			except Exception:
				log(format_exc())
			if attempt <= retries:
				self._retry_wait(attempt)
			else:
				log("All %s attempts failed for URL %s" % (attempt, self.portal_url))
		return None

	def handshake(self):
		token = None
		try:
			_params = {"type": "stb", "action": "handshake"}
			response = self.make_request_with_retries(_params)
			if response == "IP BLOCKED": return "IP BLOCKED"
			token = response.get("token")
		except Exception:
			log(format_exc())
		if token:
			self.__token.value = token
			self.__save_cache()
			self.headers["Authorization"] = "Bearer %s" % token

	def ensure_token(self):
		if self.__token.mac != self.mac or self.__token.url != self.portal_url or self.__token.value is None:
			log("Token not present. Performing handshake to obtain token.")
			a = self.handshake()
			if a == "IP BLOCKED": return a
			self.get_profile()
		elif (time.time() - self.__token.time) > 120:
			log("Token expired. Performing refresh to obtain new token.")
			self.get_profile()
		else: log("Existing token is still valid.")

	def get_profile(self):
		params = {
			"type": "stb",
			"action": "get_profile",
			"hd": "1",
			"ver": "ImageDescription: 0.2.18-r23-250; ImageDate: Thu Sep 13 11:31:16 EEST 2018; PORTAL version: 5.6.2; API Version: JS API version: 343; STB API version: 146; Player Engine version: 0x58c",
			"num_banks": "2",
			"stb_type": "MAG250",
			"client_type": "STB",
			"image_version": "218",
			"video_out": "hdmi",
			"auth_second_step": "1",
			"hw_version": "1.7-BD-00",
			"not_valid_token": "0",
			"hw_version_2": sha1(self.mac.encode()).hexdigest(),
			"timestamp": int(time.time()),
			"api_signature": "262",
			"prehash": ""
		}
		try:
			response = self.make_request_with_retries(params)
			if response == "IP BLOCKED":
				setSetting("account_info", "IP BLOCKED")
				setSetting("portal_ok", "IP BLOCKED")
				setSetting("stalker", "false")
				return "IP BLOCKED"
			token = response.get("token")
			if token:
				log("Profile token updated: %s" % token)
				self.__token.value = token
		except Exception:
			log(format_exc())
		else:
			self.__save_cache()
			self.headers["Authorization"] = "Bearer %s" % self.__token.value
			log("function get_profile Updatet headers: %s" % self.headers)
			if self.persist:
				self.watchdog()

	def probe(self):
		"""Schnelltest einer MAC: Handshake + Profil + Account-Info, keine Senderliste.
		Rueckgabe: OK | EXPIRED | INVALID | BLOCKED | NETWORK"""
		self._net_error = False
		try:
			r = self.make_request_with_retries({"type": "stb", "action": "handshake"})
		except Exception as exc:
			return "NETWORK" if _stalker_net_error(exc) else "INVALID"
		if r == "IP BLOCKED":
			return "BLOCKED"
		if not isinstance(r, dict) or not r.get("token"):
			return "NETWORK" if self._net_error else "INVALID"
		self.__token.value = r["token"]
		self.__token.mac = self.mac
		self.__token.url = self.portal_url
		self.__token.time = time.time()
		self.headers["Authorization"] = "Bearer %s" % r["token"]
		try:
			self.get_profile()
			info = self.get_account_info()
		except Exception as exc:
			return "NETWORK" if _stalker_net_error(exc) else "OK"
		if info == "IP BLOCKED":
			return "BLOCKED"
		if not isinstance(info, dict):
			return "NETWORK" if self._net_error else "OK"
		phone = info.get("phone")
		if phone:
			try:
				if time.time() + 43200 > datetime.timestamp(parse(phone)):
					return "EXPIRED"
			except Exception:
				pass
		return "OK"

	def watchdog(self):
		return self.make_request_with_retries({
			"type": "watchdog",
			"action": "get_events",
			"init": "0",
			"cur_play_type": "1",
			"event_active_id": "0"
		})

	def get_account_info(self):
		_params = {"type": "account_info", "action": "get_main_info"}
		return self.make_request_with_retries(_params)

	def genres(self):
		categories = {}
		groups = self.make_request_with_retries({"type": "itv", "action": "get_genres"}, retries=2, timeout=10)
		if groups == "IP BLOCKED":
			setSetting("account_info", "IP BLOCKED")
			setSetting("portal_ok", "IP BLOCKED")
			setSetting("stalker", "false")
			return "IP BLOCKED"
		if not groups: return {}
		for i in groups:
			if i.get("title") and i.get("id") and i.get("id") != "*":
				categories[i.get("title")] = i.get("id")
		return dict(sorted(list(categories.items())))

	def _blacklist(self):
		cacheOk, fm = get_cache("faultymac")
		if not cacheOk or not isinstance(fm, dict):
			fm = {}
		fm.setdefault(self.url, [])
		if self.mac not in fm[self.url]:
			fm[self.url].append(self.mac)
		set_cache("faultymac", fm, 12)

	def _blocked(self):
		setSetting("account_info", "IP BLOCKED")
		setSetting("portal_ok", "IP BLOCKED")
		setSetting("stalker", "false")

	def check(self):
		"""Prueft eine MAC am Portal. Rueckgabe:
		True | 'IP BLOCKED' | 'NETWORK' | 'No Channels' | 'ACCOUNT Infos Empty'
		| 'ACCOUNT Expired' | 'No Genres' | 'No Stream'"""
		try:
			account_info = self.get_account_info()
			if account_info == "IP BLOCKED":
				self._blocked(); return "IP BLOCKED"
			if not account_info or not isinstance(account_info, dict):
				if getattr(self, "_net_error", False):
					return "NETWORK"
				setSetting("account_info", ""); return "ACCOUNT Infos Empty"
			log(account_info)
			phone = account_info.get("phone")
			if phone:
				try:
					expired = time.time() + 43200 > datetime.timestamp(parse(phone))
				except Exception:
					expired = False
				if expired:
					self._blacklist(); setSetting("account_info", ""); return "ACCOUNT Expired"
			setSetting("account_info", ",".join("%s:%s" % (k, v) for k, v in account_info.items()))

			chans = self.channels()
			if chans == "IP BLOCKED":
				self._blocked(); return "IP BLOCKED"
			if not chans or not isinstance(chans, list):
				if getattr(self, "_net_error", False):
					return "NETWORK"
				# Handshake + Account gingen durch -> MAC/Token ok, leere Senderliste =
				# Portal gedrosselt/ueberlastet. MAC NICHT verbrennen.
				log("Stalker check: Account ok, aber Senderliste leer (Portal gedrosselt?)")
				return "No Channels"
			set_cache("sta_channels", chans, int(getSetting("stalk_cache")))

			g = self.genres()
			if g == "IP BLOCKED":
				self._blocked(); return "IP BLOCKED"
			if not g:
				return "NETWORK" if getattr(self, "_net_error", False) else "No Genres"

			# Stream-Test: bis zu 5 zufaellige Sender - EINER muss echte Daten liefern.
			# Login + Senderliste + Gruppen sind ok -> die MAC ist gueltig; scheitert nur
			# der Stream (Geo-/CDN-Sperre auf dieser IP), wird die MAC NICHT verbrannt.
			stream_ok = False
			last_err = None
			for cmd in random.sample(chans, min(5, len(chans))):
				try:
					if not _portal_flag(cmd.get("use_http_tmp_link")) and not _portal_flag(cmd.get("use_load_balancing")):
						surl = cmd["cmd"].split()[-1]
					else:
						surl, _h = self.get_tv_stream_url(cmd)
					if not surl or surl == "IP BLOCKED":
						continue
					r = request("GET", surl, headers=self.headers, timeout=10, stream=True, retries=0)
					code = r.status_code
					body = next(r.iter_content(1), b"") if code < 400 else b""
					r.close()
					if code < 400 and body:
						stream_ok = True; break
					last_err = "HTTP %s" % code
				except Exception as e:
					last_err = e
					if _stalker_net_error(e) or getattr(self, "_net_error", False):
						return "NETWORK"
			if not stream_ok:
				log("Stalker check: Portal/Login ok, aber kein Test-Stream abspielbar (%s)" % repr(last_err)[:120])
				return "No Stream"

			setSetting("portal_ok", "Status OK")
			return True
		except Exception as e:
			log(format_exc())
			if _stalker_net_error(e) or getattr(self, "_net_error", False):
				return "NETWORK"
			return "No Channels"

	def channels(self):
		response = self.make_request_with_retries({"type": "itv", "action": "get_all_channels"}, retries=2, timeout=10)
		if response == "IP BLOCKED":
			setSetting("account_info", "IP BLOCKED")
			setSetting("portal_ok", "IP BLOCKED")
			setSetting("stalker", "false")
			return "IP BLOCKED"
		if isinstance(response, dict): data = response["data"]
		else: return {}
		chan = [{
			"name": a["name"],
			"cmd": a["cmd"],
			"use_http_tmp_link": a.get("use_http_tmp_link", 0),
			"use_load_balancing": a.get("use_load_balancing", 0),
			"tv_genre_id": a["tv_genre_id"]
		} for a in data]
		return chan

	def get_tv_stream_url(self, channel):
		if isinstance(channel, dict):
			cmd = channel.get("cmd", "")
			create_link = _portal_flag(channel.get("use_http_tmp_link")) or _portal_flag(channel.get("use_load_balancing"))
		else:
			# Alte Cache-Einträge enthalten nur cmd. Das bisherige Verhalten bleibt
			# dafür erhalten, bis die Senderliste neu geladen wurde.
			cmd = channel
			create_link = True
		if create_link:
			resp = self.make_request_with_retries({"type": "itv", "action": "create_link", "cmd": cmd})
			if resp == "IP BLOCKED":
				setSetting("account_info", "IP BLOCKED")
				setSetting("portal_ok", "IP BLOCKED")
				setSetting("stalker", "false")
				return None, self.headers
			cmd = resp["cmd"]
		return cmd.split()[-1], self.headers
				
def get_genres():
	titles, original_titles, ids, preselect = [], [], [], []
	portal = StalkerPortal(get_cache_or_setting("stalkerurl"), get_cache_or_setting("mac"))
	gruppen = portal.genres()
	if not gruppen:
		log("Keine Stalker-Gruppen vom Portal erhalten")
		return []
	for title, groupid in  gruppen.items():
		original_titles.append(title)
		titles.append(title.encode("utf-8", "ignore").decode("ascii", "ignore"))
		ids.append(groupid)
	cacheOk, oldgroups = get_cache("stalker_groups")
	if cacheOk:
		preselect = [ids.index(groupid) for groupid in oldgroups if groupid in ids]
	if not preselect:
		preselect = [
			index for index, title in enumerate(original_titles)
			if _is_german_language_group(title)
		]
	indicies = selectDialog(titles, "Choose Groups", True, preselect)
	if indicies:
		group = [ids[i] for i in indicies]
		set_cache("stalker_groups", group)
		return group
	return []

def get_maclists():
	cacheOk, maclists = get_cache("maclists")
	if not cacheOk: 
		maclists = request_json("GET", "https://github.com/michaz1988/michaz1988.github.io/releases/latest/download/maclist.json", timeout=10, retries=1)
		set_cache("maclists", maclists, 1)
	return maclists

def choose_portal():
	maclists = get_maclists()
	a, b, c = [], [], []
	for key, value in maclists.items():
		a.append(key)
		b.append(value)
		c.append("%s, %s mac" % (urlsplit(key).hostname, len(value)))
	indicies = selectDialog(c, "Stalkerurl auswählen")
	if indicies >=0: check_portal(a[indicies], b[indicies])

def new_mac(silent=False):
	log("Getting New Mac")
	url = get_cache_or_setting("stalkerurl")
	maclists = get_maclists()
	maclist = maclists.get(url)
	if not maclist:
		log("Keine MAC-Liste für URL: %s" % url)
		return False
	return check_portal(url, maclist, silent)
	
def _probe_one(url, mac):
	try:
		return mac, StalkerPortal(url, mac, persist=False).probe()
	except Exception as exc:
		return mac, ("NETWORK" if _stalker_net_error(exc) else "INVALID")

def prefilter_macs(url, maclist, faultymaclist, limit=12):
	"""Paralleler Handshake-Schnelltest. Rueckgabe: (status, good, expired, probed)."""
	pool = [m for m in maclist if m not in faultymaclist]
	random.shuffle(pool)
	pool = pool[:limit]
	if not pool:
		return "EMPTY", [], [], []
	try:
		# schonend: nur 2 gleichzeitig, sonst blockt das Portal die IP
		with ThreadPoolExecutor(max_workers=min(2, len(pool))) as ex:
			results = list(ex.map(lambda m: _probe_one(url, m), pool))
	except Exception:
		log(format_exc())
		results = [_probe_one(url, m) for m in pool]
	good, expired, net, bad = [], [], 0, 0
	for mac, status in results:
		if status == "OK":
			good.append(mac)
		elif status == "EXPIRED":
			expired.append(mac)
		elif status == "BLOCKED":
			return "BLOCKED", [], [], pool
		elif status == "NETWORK":
			net += 1
		else:
			bad += 1
			if mac not in faultymaclist:
				faultymaclist.append(mac)
	log("prefilter_macs: %s gut, %s abgelaufen, %s Netzfehler, %s defekt (von %s)" % (len(good), len(expired), net, bad, len(pool)))
	if not good and not expired and net and bad == 0:
		return "NETWORK", [], [], pool
	return "OK", good, expired, pool

def check_portal(url, maclist, silent=False):
	cacheOk, faultymac = get_cache("faultymac")
	if not cacheOk or not isinstance(faultymac, dict): faultymac = {}
	faultymaclist = list(faultymac.get(url, []))
	cacheOk, vav = get_cache("stalkerurl")
	if cacheOk and vav != url: del_cache("stalker_groups")
	set_cache("stalkerurl", url)
	setSetting("stalkerurl", url)
	del_cache("sta_channels")
	if silent == False:
		progress.create("TESTE STALKER MAC ADRESSEN", "Pruefe Mac Adressen ...")
	setSetting("portal_ok", "Teste Mac Adressen ...")
	try:
		budget = max(10, int(getSetting("stalker_retry")))
	except (TypeError, ValueError):
		budget = 10
	batch_size = min(24, max(8, budget))
	# "Login ok, kein Stream" weiter durchprobieren: manuell grosszuegig, im Hintergrund knapp
	stream_budget = min(len(maclist), budget if silent else max(30, budget * 2))

	tried = set(faultymaclist)
	checks = 0
	hard_checks = 0
	no_stream_macs = []
	nochan = 0
	saw_expired = False

	for _round in range(6):
		if hard_checks >= budget or checks >= stream_budget or monitor.abortRequested():
			break
		if silent == False and progress.iscanceled():
			progress.close(); return False
		pool = [m for m in maclist if m not in tried]
		if not pool:
			break
		status, good, expired, probed = prefilter_macs(url, pool, faultymaclist, batch_size)
		tried.update(probed)
		tried.update(faultymaclist)
		faultymac[url] = faultymaclist
		set_cache("faultymac", faultymac, 12)
		saw_expired = saw_expired or bool(expired)

		if status == "BLOCKED":
			if silent == False: progress.close()
			dialog.notification("VAVOO.TO", "IP BLOCKED - anderes Portal waehlen, Stalker deaktiviert", xbmcgui.NOTIFICATION_ERROR, 3000)
			setSetting("stalker", "false"); setSetting("account_info", "IP BLOCKED"); setSetting("portal_ok", "IP BLOCKED")
			return False
		if status == "NETWORK":
			if silent == False:
				progress.close()
				dialog.notification("VAVOO.TO", "Stalker-Portal nicht erreichbar - Netzwerk pruefen", xbmcgui.NOTIFICATION_WARNING, 3000)
			setSetting("portal_ok", "Portal nicht erreichbar")
			return False
		if not good:
			continue

		for mac in good:
			if hard_checks >= budget or checks >= stream_budget or monitor.abortRequested():
				break
			if silent == False and progress.iscanceled():
				progress.close(); return False
			checks += 1
			if silent == False:
				_lim = stream_budget if no_stream_macs else budget
				progress.update(min(99, int(checks * 100 / max(_lim, 1))), "Vollstaendiger Test %s/%s\n%s" % (checks, _lim, mac))
			setSetting("portal_ok", "Vollstaendiger Test %s/%s" % (checks, (stream_budget if no_stream_macs else budget)))
			setSetting("mac", mac)
			set_cache("mac", mac)
			chk = StalkerPortal(url, mac).check()
			if chk == True:
				if silent == False: progress.close()
				execute("Container.Refresh")
				return True
			if chk == "IP BLOCKED":
				if silent == False: progress.close()
				dialog.notification("VAVOO.TO", "IP BLOCKED - anderes Portal waehlen, Stalker deaktiviert", xbmcgui.NOTIFICATION_ERROR, 3000)
				setSetting("stalker", "false")
				return False
			if chk == "NETWORK":
				if silent == False:
					progress.close()
					dialog.notification("VAVOO.TO", "Stalker-Portal nicht erreichbar", xbmcgui.NOTIFICATION_WARNING, 3000)
				setSetting("portal_ok", "Portal nicht erreichbar")
				return False
			if chk in ("No Stream", "No Channels"):
				# MAC/Login ok, aber Portal liefert nicht (Stream gesperrt / Senderliste leer)
				# -> weiter mit der naechsten MAC, MAC NICHT verbrennen
				no_stream_macs.append(mac)
				if chk == "No Channels": nochan += 1
				if silent == False:
					progress.update(min(99, int(checks * 100 / max(stream_budget, 1))), "Login ok, Stream gesperrt - weiter  %s/%s" % (checks, stream_budget))
				continue
			# No Channels / No Genres / ACCOUNT Expired  (check() hat ggf. schon geblacklistet)
			hard_checks += 1
			if mac not in faultymaclist:
				faultymaclist.append(mac)
			faultymac[url] = faultymaclist
			set_cache("faultymac", faultymac, 12)

	if silent == False: progress.close()
	execute("Container.Refresh")
	if no_stream_macs:
		setSetting("mac", no_stream_macs[0])
		set_cache("mac", no_stream_macs[0])
		if nochan >= len(no_stream_macs):
			msg = "Login ok - Portal liefert keine Senderliste (ueberlastet?)"
		else:
			msg = "Login ok - kein Stream abspielbar (Geo/IP/Portal)"
		setSetting("portal_ok", msg)
		if silent == False:
			dialog.notification("VAVOO.TO", msg, xbmcgui.NOTIFICATION_WARNING, 4000)
	elif saw_expired:
		setSetting("portal_ok", "Nur abgelaufene Mac Adressen")
	else:
		setSetting("portal_ok", "Keine gueltige Mac")
	log("check_portal: keine funktionierende Mac (checks=%s no_stream=%s)" % (checks, len(no_stream_macs)))
	return False

