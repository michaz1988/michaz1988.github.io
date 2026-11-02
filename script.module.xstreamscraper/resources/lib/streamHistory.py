# -*- coding: utf-8 -*-
# Merkt sich pro Film bzw. Folge die gespielten Streams, damit beim naechsten Mal ein anderer drankommt.
import json, os, re, time, xbmcaddon, xbmcvfs
from urllib.parse import urlparse
from resources.lib.logger import logger

MAX_TITLES = 200
MAX_STREAMS = 50
FAILED_SECONDS = 60 * 60

def _path(name="stream_history.json"):
	return os.path.join(xbmcvfs.translatePath(xbmcaddon.Addon().getAddonInfo("profile")), name)

def _read(name="stream_history.json"):
	try:
		with open(_path(name), encoding="utf-8") as f:
			data = json.load(f)
		return data if isinstance(data, dict) else {}
	except (OSError, ValueError):
		return {}

def _write(data, name="stream_history.json"):
	path = _path(name)
	os.makedirs(os.path.dirname(path), exist_ok=True)
	with open(path + ".tmp", "w", encoding="utf-8") as f:
		json.dump(data, f)
	os.replace(path + ".tmp", path)

def streamId(candidate):
	"""Seite und Hoster statt Link: manche Seiten liefern bei jedem Aufruf einen neuen Link."""
	name = candidate.get("name") or urlparse(str(candidate.get("link"))).netloc
	return ("%s|%s" % (candidate.get("site"), name)).lower()

def used(key):
	"""Gespielte Streams des Titels, der zuletzt gespielte steht am Ende."""
	entry = _read().get(key)
	return entry.get("streams", []) if isinstance(entry, dict) else []

def order(candidates, usedStreams, isFailed=None):
	"""Ungespielte zuerst, danach der am laengsten nicht gespielte, zuletzt die kuerzlich gescheiterten.
	Die Reihenfolge bleibt sonst erhalten."""
	def rank(candidate):
		stream = streamId(candidate)
		return (bool(isFailed and isFailed(candidate)), usedStreams.index(stream) + 1 if stream in usedStreams else 0)
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
		_write(data)
	except Exception as e:
		logger.error("Stream-Verlauf nicht gespeichert: %s" % e)

class Failures:
	"""Kuerzlich im Test gescheiterte Streams. Eine Zeitueberschreitung spricht gegen den ganzen Hoster, gilt also
	fuer alle Titel. Ein Fehler wie 404 betrifft oft nur eine Datei und gilt deshalb nur fuer diesen Titel."""
	FILE = "stream_failures.json"

	def __init__(self, key):
		self.key = key
		now = time.time()
		self.entries = {k: t for k, t in _read(self.FILE).items() if isinstance(t, (int, float)) and now - t < FAILED_SECONDS}

	def _host(self, candidate):
		# "vidsonic.net" von VAVOO und "Vidsonic" von einer Seite sind derselbe Hoster.
		name = candidate.get("name") or urlparse(str(candidate.get("link"))).netloc
		name = re.sub(r"[^a-z0-9.]", "", str(name).lower())
		if name.startswith("www."): name = name[4:]
		return "host|" + name.split(".")[0]

	def _title(self, candidate):
		return "%s|%s" % (self.key, streamId(candidate))

	def _save(self):
		try:
			_write(self.entries, self.FILE)
		except Exception as e:
			logger.error("Gescheiterte Streams nicht gespeichert: %s" % e)

	def has(self, candidate):
		return self._host(candidate) in self.entries or self._title(candidate) in self.entries

	def sameHost(self, a, b):
		return self._host(a) == self._host(b)

	def timedOut(self, candidate):
		self.entries[self._host(candidate)] = int(time.time())
		self._save()

	def broken(self, candidate):
		self.entries[self._title(candidate)] = int(time.time())
		self._save()

	def worked(self, candidate):
		known = [k for k in (self._host(candidate), self._title(candidate)) if k in self.entries]
		for k in known: del self.entries[k]
		if known: self._save()
