# -*- coding: utf-8 -*-
# Prueft, ob hinter einem aufgeloesten Link wirklich Videodaten liegen, und begrenzt die Zeit pro Stream.
import threading, time, requests
from urllib.parse import parse_qsl, urljoin

LIMIT = 10
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
_PLAYLIST_MAX = 512 * 1024
_session = requests.session()

class Cancelled(BaseException):
	"""Der Nutzer hat abgebrochen. BaseException, damit es die except-Exception-Bloecke der Suche passiert."""

class StreamTimeout(Exception):
	pass

def runLimited(func, limit=LIMIT, cancelled=None):
	"""Fuehrt func hoechstens limit Sekunden aus. Ein haengender Aufruf laeuft als Daemon-Thread aus,
	sein Ergebnis wird verworfen; ein ThreadPoolExecutor wuerde hier auf ihn warten."""
	box = {}
	def worker():
		try: box["result"] = func()
		except Exception as e: box["error"] = e
	thread = threading.Thread(target=worker, daemon=True)
	thread.start()
	end = time.monotonic() + limit
	while thread.is_alive():
		if cancelled and cancelled(): raise Cancelled()
		remaining = end - time.monotonic()
		if remaining <= 0: raise StreamTimeout("mehr als %s Sekunden" % limit)
		thread.join(min(0.1, remaining))
	if "error" in box: raise box["error"]
	return box.get("result")

def _splitUrl(url):
	target, _, rawHeaders = url.partition("|")
	headers = dict(parse_qsl(rawHeaders))
	if not any(name.lower() == "user-agent" for name in headers):
		headers["User-Agent"] = USER_AGENT
	return target, headers

def _fetch(url, headers, deadline):
	"""Liefert finale URL, Content-Type und den Anfang der Antwort (bei Playlisten die ganze Datei)."""
	remaining = deadline - time.monotonic()
	if remaining <= 0: raise StreamTimeout("Zeitlimit erreicht")
	res = _session.get(url, headers=headers, stream=True, timeout=(remaining, remaining))
	try:
		if not res.ok: raise Exception("HTTP %s" % res.status_code)
		data = b""
		for chunk in res.iter_content(4096):
			data += chunk
			if not _isPlaylist(data) or len(data) >= _PLAYLIST_MAX: break
			if time.monotonic() > deadline: raise StreamTimeout("Zeitlimit erreicht")
		return res.url, res.headers.get("Content-Type", "").lower(), data
	finally:
		res.close()

def _isPlaylist(data):
	return data.lstrip(b"\xef\xbb\xbf \r\n\t").startswith(b"#EXTM3U")

def _firstEntry(playlist):
	for line in playlist.decode("utf-8", "ignore").splitlines():
		line = line.strip()
		if line and not line.startswith("#"): return line

def _looksLikeHtml(data):
	head = data.lstrip(b"\xef\xbb\xbf \r\n\t")[:15].lower()
	return head.startswith((b"<!doctype", b"<html", b"<head", b"<body", b"<?xml"))

def check(url, deadline=None):
	"""Wirft eine Exception, wenn der Stream keine Videodaten liefert. Bei HLS wird bis zum ersten
	Segment durchgegangen, denn tote Streams haben oft noch eine gueltige Playlist."""
	if deadline is None: deadline = time.monotonic() + LIMIT
	target, headers = _splitUrl(url)
	for depth in range(4):
		final, contentType, data = _fetch(target, headers, deadline)
		if _isPlaylist(data):
			entry = _firstEntry(data)
			if not entry: raise Exception("Leere Playlist")
			target = urljoin(final, entry)
			continue
		if not data: raise Exception("Keine Daten")
		if _looksLikeHtml(data): raise Exception("Webseite statt Video")
		# HLS-Segmente werden oft als Text oder Bild getarnt, darum gilt der Content-Type nur fuer Direktlinks.
		if depth == 0 and "text" in contentType: raise Exception("Keine Videodatei")
		return
	raise Exception("Playlist zu tief verschachtelt")
