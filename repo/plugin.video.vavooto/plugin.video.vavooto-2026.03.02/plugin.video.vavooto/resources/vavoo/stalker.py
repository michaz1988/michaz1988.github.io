# -*- coding: utf-8 -*-
from vavoo.utils import *

class Token:
	def __init__(self, value=None, time=0, mac=None, url=None):
		self.value = value
		self.time = time
		self.mac = mac
		self.url = url

class StalkerPortal:
	def __init__(self, portal_url, mac):
		self.url = portal_url
		self.portal_url = portal_url.rstrip("/").replace('/c', '/server/load.php')
		self.mac = mac.strip()
		# self.serial = self.generate_serial(self.mac)
		# self.device_id = self.generate_device_id()
		# self.device_id1 = self.device_id
		# self.device_id2 = self.device_id
		self.__token = Token()
		self.__load_cache()
		# self.random = None
		self.headers = self.generate_headers()
		self.backoff_factor = 1

	def __load_cache(self):
		try:
			self.__token.__dict__ = json.loads(home.getProperty("token"))
			log('Loading token from cache')
		except: log('No token in cache')

	def __save_cache(self):
		log('Saving token to cache')
		self.__token.time = time.time()
		self.__token.mac = self.mac
		self.__token.url = self.portal_url
		home.setProperty("token", json.dumps(self.__token.__dict__))

	def generate_serial(self, mac):
		md5_hash = md5(mac.encode()).hexdigest()
		return md5_hash[:13].upper()

	def generate_device_id(self):
		mac_exact = self.mac.strip()
		return sha256(mac_exact.encode()).hexdigest().upper()

	def generate_random_value(self):
		return ''.join(random.choices('0123456789abcdef', k=40))

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

	def make_request_with_retries(self, params, retries=0, timeout=5):
		if not params.get("action") in ["handshake", "get_profile"]: self.ensure_token()
		params["JsHttpRequest"] = "1-xml"
		for attempt in range(1, retries + 2):
			try:
				log("Attempt %s: GET %s with params=%s" % (attempt, self.portal_url, params))
				response = requests.get(self.portal_url, params=params, headers=self.headers, timeout=timeout)
				log("Received response: %s" % response.status_code)
				if response.status_code == 403:
					log("Abbruch: HTTP 403 erhalten")
					return "IP BLOCKED"
				a = response.text
				if "IP adresiniz engellenmistir." in a: return "IP BLOCKED"
				elif "js" in a: return json.loads(a)["js"]
				else:
					cacheOk, faultymac = get_cache("faultymac")
					if not cacheOk: faultymac = {}
					if not self.portal_url in faultymac:
						faultymac[self.portal_url] = []
					if self.mac not in faultymac[self.portal_url]:
						faultymac[self.portal_url].append(self.mac)
					set_cache("faultymac", faultymac)
					continue
			except: log(format_exc())
			if attempt < retries:
				sleep_time = self.backoff_factor * (2 ** (attempt - 1))
				log("Retrying after %s seconds..." % sleep_time)
				monitor.waitForAbort(sleep_time)
			else: log("All %s attempts failed for URL %s" % (retries, self.portal_url))

	def handshake(self):
		token = None
		try:
			_params = {"type": "stb", "action": "handshake"}
			response = self.make_request_with_retries(_params)
			if response == "IP BLOCKED": return "IP BLOCKED"
			token = response.get("token")
		except: log(format_exc())
		if token:
			self.__token.value = token
			self.__save_cache()
			self.headers["Authorization"] = "Bearer %s" % token

	def generate_token(self):
		token_length = 32
		return ''.join(random.choices(string.ascii_uppercase + string.digits, k=token_length))

	def generate_prehash(self, token):
		hash_object = sha1(token.encode())
		return hash_object.hexdigest()

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
			# "sn": self.serial,
			"stb_type": "MAG250",
			"client_type": "STB",
			"image_version": "218",
			"video_out": "hdmi",
			# "device_id": self.device_id1,
			# "device_id2": self.device_id2,
			# "signature": self.generate_signature(),
			"auth_second_step": "1",
			"hw_version": "1.7-BD-00",
			"not_valid_token": "0",
			# "metrics": self.generate_metrics(),
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
		except: log(format_exc())
		else:
			self.__save_cache()
			self.headers["Authorization"] = "Bearer %s" % self.__token.value
			log("function get_profile Updatet headers: %s" % self.headers)

	def generate_signature(self):
		data = self.mac + self.serial + self.device_id1 + self.device_id2
		signature = sha256(data.encode()).hexdigest().upper()
		return signature

	def generate_metrics(self):
		# if not self.random: self.random = self.generate_random_value()
		metrics = {"mac": self.mac, "sn": self.serial, "type": "STB", "model": "MAG250", "uid": ""}  # , "random": self.random
		metrics_str = json.dumps(metrics)
		return metrics_str

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

	def check(self):
		try:
			try:
				chans = self.channels()
				if chans == "IP BLOCKED":
					setSetting("account_info", "IP BLOCKED")
					setSetting("portal_ok", "IP BLOCKED")
					setSetting("stalker", "false")
					return "IP BLOCKED"
				set_cache("sta_channels", chans,  int(getSetting("stalk_cache")))
				cmd = random.choice(chans)
				if cmd["use_http_tmp_link"] == "0":
					streamurl = cmd['cmd'].split()[-1]
				else:
					streamurl, headers = self.get_tv_stream_url(cmd['cmd'])
				res = requests.get(streamurl, headers=self.headers, timeout=10, stream=True)
				res.raise_for_status()
			except:
				cacheOk, faultymac = get_cache("faultymac")
				if not cacheOk:
					faultymac = {}
				if not self.portal_url in faultymac:
					faultymac[self.portal_url] = []
				if self.mac not in faultymac[self.portal_url]:
					faultymac[self.portal_url].append(self.mac)
				set_cache("faultymac", faultymac)
				return "No Channels"
			account_info = self.get_account_info()
			if account_info == "IP BLOCKED":
				setSetting("account_info", "IP BLOCKED")
				setSetting("portal_ok", "IP BLOCKED")
				setSetting("stalker", "false")
				return "IP BLOCKED"
			elif not account_info:
				setSetting("account_info", "")
				return "ACCOUNT Infos Empty"
			else:
				log(account_info)
				phone = account_info.get("phone")
				if phone and (time.time() + 432000) > datetime.timestamp(parse(phone)):
					cacheOk, faultymac = get_cache("faultymac")
					if not cacheOk: faultymac = {}
					if not self.portal_url in faultymac:
						faultymac[self.portal_url] = []
					if self.mac not in faultymac[self.portal_url]:
						faultymac[self.portal_url].append(self.mac)
					set_cache("faultymac", faultymac)
					setSetting("account_info", "")
					return "ACCOUNT Expired"
				account_info_str = ",".join(["%s:%s" % (k, v) for k, v in account_info.items()])
				setSetting("account_info", account_info_str)
			g = self.genres()
			if g == "IP BLOCKED":
				setSetting("account_info", "IP BLOCKED")
				setSetting("portal_ok", "IP BLOCKED")
				setSetting("stalker", "false")
				return "IP BLOCKED"
			if not g: return "No Genres"
			setSetting("portal_ok", "Status OK")
			return True
		except Exception as e:
			log(format_exc())
			return e

	def channels(self):
		response = self.make_request_with_retries({"type": "itv", "action": "get_all_channels"}, retries=2, timeout=10)
		if response == "IP BLOCKED":
			setSetting("account_info", "IP BLOCKED")
			setSetting("portal_ok", "IP BLOCKED")
			setSetting("stalker", "false")
			return "IP BLOCKED"
		if isinstance(response, dict): data = response["data"]
		else: return {}
		chan = [{"name": a["name"], "cmd": a["cmd"], "use_http_tmp_link": a["use_http_tmp_link"], "tv_genre_id": a["tv_genre_id"]} for a in data]
		return chan

	def get_tv_stream_url(self, cmd):
		resp = self.make_request_with_retries({"type": "itv", "action": "create_link", "cmd": cmd})
		if resp == "IP BLOCKED":
			setSetting("account_info", "IP BLOCKED")
			setSetting("portal_ok", "IP BLOCKED")
			setSetting("stalker", "false")
			return None, self.headers
		cmd = resp["cmd"]
		return cmd.split()[-1], self.headers
				
def get_genres():
	titles, ids, preselect = [], [], []
	portal = StalkerPortal(get_cache_or_setting("stalkerurl"), get_cache_or_setting("mac"))
	gruppen = portal.genres()
	for title, groupid in  gruppen.items():
		titles.append(title.encode("utf-8", "ignore").decode("ascii", "ignore"))
		ids.append(groupid)
	cacheOk, oldgroups = get_cache("stalker_groups")
	if cacheOk: preselect = [ids.index(i) for i in oldgroups]
	indicies = selectDialog(titles, "Choose Groups", True, preselect)
	if indicies:
		group = [ids[i] for i in indicies]
		set_cache("stalker_groups", group)
		return group
	return []

def get_maclists():
	cacheOk, maclists = get_cache("maclists")
	if not cacheOk: 
		maclists = requests.get("https://github.com/michaz1988/michaz1988.github.io/releases/latest/download/maclist.json").json()
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
	maclist = maclists[url]
	return check_portal(url, maclist, silent)
	
def check_portal(url, maclist, silent=False):
	cacheOk, faultymac = get_cache("faultymac")
	if not cacheOk: faultymac = {}
	faultymaclist = faultymac.get(url, [])
	cacheOk, vav = get_cache("stalkerurl")
	if cacheOk and vav != url: del_cache("stalker_groups")
	set_cache("stalkerurl", url)
	setSetting("stalkerurl", url)
	del_cache("sta_channels")
	if silent == False: progress.create("TESTE STALKER MAC ADRESSEN", "Verfügbare Mac Adressen %s" % len(maclist))
	retry = int(getSetting("stalker_retry"))
	i = 0
	while not monitor.abortRequested() and i <= retry:
		i += 1
		if silent == False and i >= 1: monitor.waitForAbort(1)
		if silent == False:
			if progress.iscanceled():
				progress.close()
				break
		log("Versuch :%s" % i)
		setSetting("portal_ok", "Teste Mac Adressen, Versuch :%s/%s" % (i, retry))
		if silent == False: progress.update(int(i / retry * 100), "Teste Mac Adressen, Versuch :%s/%s" % (i, retry))
		while True:
			mac = random.choice(maclist)
			if mac not in faultymaclist: break
		setSetting("mac", mac)
		set_cache("mac", mac)
		portal = StalkerPortal(url, mac)
		check = portal.check()
		if check == True:
			if silent == False: progress.close()
			execute("Container.Refresh")
			return
		elif check == "IP BLOCKED":
			if silent == False:
				progress.update(int(i / retry * 100), "Teste Mac Adressen, Versuch :%s/%s\nFehler %s" % (i, retry, check))
				progress.close()
			dialog.notification('VAVOO.TO', f'{check} – anderes Portal auswählen, deaktiviere Stalker', xbmcgui.NOTIFICATION_ERROR, 2000)
			setSetting("stalker", "false")
			return False
		else:
			if silent == False: progress.update(int(i / retry * 100), "Teste Mac Adressen, Versuch :%s/%s\nFehler %s" % (i, retry, check))
	if silent == False: progress.close()
	execute("Container.Refresh")
	log("Keine funktionierende Mac")
	setSetting("portal_ok", "Keine gültige Mac")
	return False