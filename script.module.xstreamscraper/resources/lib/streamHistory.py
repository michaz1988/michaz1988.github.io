# -*- coding: utf-8 -*-
# Merkt sich pro Film bzw. Folge die gespielten Streams, damit beim naechsten Mal ein anderer drankommt.
import json, os, time, xbmcaddon, xbmcvfs
from urllib.parse import urlparse
from resources.lib.logger import logger

MAX_TITLES = 200
MAX_STREAMS = 50

def _path():
	return os.path.join(xbmcvfs.translatePath(xbmcaddon.Addon().getAddonInfo("profile")), "stream_history.json")

def _read():
	try:
		with open(_path(), encoding="utf-8") as f:
			data = json.load(f)
		return data if isinstance(data, dict) else {}
	except (OSError, ValueError):
		return {}

def streamId(candidate):
	"""Seite und Hoster statt Link: manche Seiten liefern bei jedem Aufruf einen neuen Link."""
	name = candidate.get("name") or urlparse(str(candidate.get("link"))).netloc
	return ("%s|%s" % (candidate.get("site"), name)).lower()

def used(key):
	"""Gespielte Streams des Titels, der zuletzt gespielte steht am Ende."""
	entry = _read().get(key)
	return entry.get("streams", []) if isinstance(entry, dict) else []

def order(candidates, usedStreams):
	"""Ungespielte zuerst, danach der am laengsten nicht gespielte. Die Reihenfolge bleibt sonst erhalten."""
	def rank(candidate):
		stream = streamId(candidate)
		return usedStreams.index(stream) + 1 if stream in usedStreams else 0
	return sorted(candidates, key=rank)

def remember(key, candidate):
	try:
		data = _read()
		stream = streamId(candidate)
		entry = data.get(key)
		streams = entry.get("streams", []) if isinstance(entry, dict) else []
		streams = [s for s in streams if s != stream] + [stream]
		data[key] = {"streams": streams[-MAX_STREAMS:], "time": int(time.time())}
		if len(data) > MAX_TITLES:
			newest = sorted(data, key=lambda k: data[k].get("time", 0) if isinstance(data[k], dict) else 0, reverse=True)
			data = {k: data[k] for k in newest[:MAX_TITLES]}
		path = _path()
		os.makedirs(os.path.dirname(path), exist_ok=True)
		with open(path + ".tmp", "w", encoding="utf-8") as f:
			json.dump(data, f)
		os.replace(path + ".tmp", path)
	except Exception as e:
		logger.error("Stream-Verlauf nicht gespeichert: %s" % e)
