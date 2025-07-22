# -*- coding: utf-8 -*-

# vavoo
#2022-08-08
# edit 2024-12-14

try:
	from resources.lib.utils import help, isBlockedHoster
except:
	from xbmc import executebuiltin
	executebuiltin('Quit')
	exit()

import requests, json


SITE_IDENTIFIER = 'vavoo'
SITE_DOMAIN = 'vavoo.to'
SITE_NAME = SITE_IDENTIFIER.upper()


def getAuthSignature():
	_headers={"user-agent": "okhttp/4.11.0", "accept": "application/json", "content-type": "application/json; charset=utf-8", "content-length": "1106", "accept-encoding": "gzip"}
	_data = {"token":"tosFwQCJMS8qrW_AjLoHPQ41646J5dRNha6ZWHnijoYQQQoADQoXYSo7ki7O5-CsgN4CH0uRk6EEoJ0728ar9scCRQW3ZkbfrPfeCXW2VgopSW2FWDqPOoVYIuVPAOnXCZ5g","reason":"app-blur","locale":"de","theme":"dark","metadata":{"device":{"type":"Handset","brand":"google","model":"Nexus","name":"21081111RG","uniqueId":"d10e5d99ab665233"},"os":{"name":"android","version":"7.1.2","abis":["arm64-v8a","armeabi-v7a","armeabi"],"host":"android"},"app":{"platform":"android","version":"3.1.20","buildId":"289515000","engine":"hbc85","signatures":["6e8a975e3cbf07d5de823a760d4c2547f86c1403105020adee5de67ac510999e"],"installer":"app.revanced.manager.flutter"},"version":{"package":"tv.vavoo.app","binary":"3.1.20","js":"3.1.20"}},"appFocusTime":0,"playerActive":False,"playDuration":0,"devMode":False,"hasAddon":True,"castConnected":False,"package":"tv.vavoo.app","version":"3.1.20","process":"app","firstAppStart":1743962904623,"lastAppStart":1743962904623,"ipLocation":"","adblockEnabled":True,"proxy":{"supported":["ss","openvpn"],"engine":"ss","ssVersion":1,"enabled":True,"autoServer":True,"id":"pl-waw"},"iap":{"supported":False}}
	req = requests.post('https://www.vavoo.tv/api/app/ping', json=_data, headers=_headers).json()
	return req.get("addonSig")

class source:
	def __init__(self):
		self.priority = 1
		self.language = ['de']
		self.domains = ['vavoo.to']
		self.sources = []

	def run(self, titles, year, season=0, episode=0, imdb='', hostDict=None):
		#sources = []
		if season == 0:
			mediatype = 'movie'
			result = requests.get(f'https://api.themoviedb.org/3/find/{imdb}?api_key=be7e192d9ff45609c57344a5c561be1d&external_source=imdb_id').json()["movie_results"][0]
			_data={"language":"de","region":"AT","type":"movie","ids":{"tmdb_id":result["id"]},"name":result["title"],"episode":{},"clientVersion":"3.0.2"}
		else:
			mediatype = 'series'
			result = requests.get(f'https://api.themoviedb.org/3/find/{imdb}?api_key=be7e192d9ff45609c57344a5c561be1d&external_source=imdb_id').json()["tv_results"][0]
			_data={"language":"de","region":"AT","type":"series","ids":{"tmdb_id":result["id"]},"name":result["name"],"episode":{"season":season,"episode":episode},"clientVersion":"3.0.2"}
		_headers={"user-agent": "MediaHubMX/2", "content-type": "application/json; charset=utf-8", "content-length": "1898", "accept-encoding": "gzip", "mediahubmx-signature": getAuthSignature()}
		url = "https://vavoo.to/mediahubmx-source.json"
		mirrors = requests.post(url, json=_data, headers=_headers).json()
		if not mirrors: return self.sources
		for i in mirrors:
			if "de" in i.get('languages', []):
				_headers={"user-agent": "MediaHubMX/2", "content-type": "application/json; charset=utf-8", "content-length": "102", "accept-encoding": "gzip", "mediahubmx-signature": getAuthSignature()}
				_data = {"language":"de","region":"AT","url":i["url"],"clientVersion":"3.0.2"}
				url =  requests.post("https://vavoo.to/mediahubmx-resolve.json", json=_data, headers=_headers).json()["data"]["url"]
				isBlocked, hoster, sUrl, prioHoster = isBlockedHoster(url)
				if isBlocked: continue
				if sUrl: self.sources.append({'source': hoster, 'quality': i.get("tag", "SD"), 'language': 'de', 'url': sUrl, 'direct': True, 'prioHoster': prioHoster})
		return self.sources

	def resolve(self, url):
		return url