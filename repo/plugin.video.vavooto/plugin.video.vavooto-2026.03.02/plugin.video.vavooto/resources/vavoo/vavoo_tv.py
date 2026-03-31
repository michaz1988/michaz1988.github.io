# -*- coding: utf-8 -*-
from vavoo.utils import *

def vavoo_groups():
	log("Getting VAVOO groups and md5")
	groups=[]
	a =  requests.get("https://www2.vavoo.to/live2/index?output=json").text
	hash = md5(a.encode()).hexdigest()
	chans = json.loads(a)
	for c in chans:
		if c["group"] not in groups: groups.append(c["group"])
	return sorted(groups), hash

def choose():
	groups, hash = vavoo_groups()
	cacheOk, b = get_cache("groups")
	preselect = []
	if cacheOk:
		oldgroups = []
		for a in b:
			if a in groups: oldgroups.append(a)
		preselect = [groups.index(oldgroup) for oldgroup in oldgroups]
	indicies = selectDialog(groups, "Choose VAVOO Groups", True, preselect)
	group = [groups[i] for i in indicies if indicies]
	set_cache("groups", group)
	return group

def new_vav_channels(group):
	_headers={"user-agent": "okhttp/4.11.0", "accept": "application/json", "content-type": "application/json; charset=utf-8", "content-length": "1106", "accept-encoding": "gzip", "mediahubmx-signature": getAuthSignature()}
	items = []
	cursor = 0
	while cursor != None: 
		try:
			_data={"language":"de","region":"AT","catalogId":"iptv","id":"iptv","adult":False,"search":"","sort":"name","filter":{"group":group},"cursor":cursor,"clientVersion":"3.0.2"}
			req = requests.post("https://vavoo.to/mediahubmx-catalog.json", json=_data, headers=_headers).json()
			for r in req["items"]:
				items.append({"url": r["url"], "name": r["name"], "group": r["group"]})
			cursor = req.get("nextCursor")
		except: continue
	return items

def get_vav_channels(groups = False):
	if groups == False: cacheOk, groups = get_cache("groups")
	if not groups: groups = choose()
	cacheOk, chan = get_cache("vav_channels")
	g, newhash = vavoo_groups()
	if cacheOk and isinstance(chan, dict) and (chan["hash"] == newhash):
		channels, oldhash = chan["channels"], chan["hash"] 
	else:
		log("Getting new VAVOO Channels")
		channels = []
		for a in ThreadPoolExecutor().map(new_vav_channels, g):
			channels += a
		set_cache("vav_channels", {"channels": channels, "hash":newhash})
	vavchannels = {}
	for item in channels:
		if item["group"] not in groups: continue
		name = filterout(item["name"])
		if name not in vavchannels: vavchannels[name] = []
		if item["url"] not in vavchannels[name]:
			vavchannels[name].append(item["url"])
	return vavchannels