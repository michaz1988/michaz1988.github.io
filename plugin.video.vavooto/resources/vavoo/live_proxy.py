# -*- coding: utf-8 -*-
from vavoo.utils import *
import sys
import urllib.parse
import base64
import math
import time
import threading
import socketserver
from collections import OrderedDict
from http.server import HTTPServer, BaseHTTPRequestHandler

_proxy_server = None
_proxy_port = 19888
_proxy_lock = threading.Lock()
_httpx_client = None

# --- VAVOO Prefetch-Sessions -------------------------------------------------
PREFETCH_MAX_BYTES = 48 * 1024 * 1024   # RAM-Budget pro Session (VAVOO-Segmente bis ~10 MB)
MAX_SESSIONS = 2
SESSION_IDLE_TIMEOUT = 60                # s ohne Zugriff -> Session verwerfen

_vavoo_sessions = {}
_vavoo_sessions_lock = threading.Lock()

# --- Stalker MPEG-TS -> HLS Sessions ----------------------------------------
STALKER_SEGMENT_SECONDS = 4.0
STALKER_PLAYLIST_SEGMENTS = 10
STALKER_MAX_BYTES = 64 * 1024 * 1024
STALKER_SESSION_IDLE_TIMEOUT = 90
STALKER_MAX_SESSIONS = 2
STALKER_RESUME_TIMEOUT = 20.0

_stalker_sessions = {}
_stalker_sessions_lock = threading.Lock()


def get_httpx():
    global _httpx_client
    if _httpx_client is None:
        try:
            import httpx
            # kurze Timeouts: ein toter Host darf den Prefetch-/Request-Pfad nicht minutenlang blockieren
            tmo = httpx.Timeout(connect=5.0, read=20.0, write=5.0, pool=5.0)
            _httpx_client = httpx.Client(http2=True, follow_redirects=True, timeout=tmo, verify=False)
        except Exception:
            log("httpx import failed: %s" % format_exc())
            _httpx_client = False
    return _httpx_client


# Netzwerkfehler (tote Hosts, DNS-Ausfall, Client-Abbruch) sind im Live-Betrieb
# normal - nur eine Kurzmeldung, kein seitenlanger Traceback.
_NET_ERR = (OSError, ConnectionError, TimeoutError)


def _neterr(prefix, exc):
    log("%s: %s" % (prefix, repr(exc)[:200]))


def _reresolve_vavoo(src_b64):
    """Loest denselben VAVOO-Kanal erneut auf und liefert eine frische m3u8-URL."""
    try:
        vavoo_link = base64.b64decode(src_b64.encode("ascii")).decode("utf-8")
    except Exception:
        return ""
    if not vavoo_link:
        return ""
    try:
        headers = {
            "user-agent": "MediaHubMX/2",
            "content-type": "application/json; charset=utf-8",
            "accept-encoding": "gzip",
            "mediahubmx-signature": getAuthSignature(),
        }
        data = {"language": "de", "region": "AT", "url": vavoo_link, "clientVersion": "3.1.0"}
        res = request_json("POST", "https://vavoo.to/mediahubmx-resolve.json", json=data, headers=headers, timeout=8, retries=0)
        fresh = res[0]["url"]
        if fresh:
            log("VAVOO Proxy: Quelle neu aufgeloest")
        return fresh or ""
    except Exception as exc:
        _neterr("VAVOO Proxy Re-Resolve fehlgeschlagen", exc)
        return ""


def _parse_target_duration(text):
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("#EXT-X-TARGETDURATION:"):
            try:
                return max(1, int(float(s.split(":", 1)[1].strip())))
            except Exception:
                return None
    return None


def _media_sequence(text):
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("#EXT-X-MEDIA-SEQUENCE:"):
            return s.split(":", 1)[1].strip()
    return None


RERESOLVE_MIN_INTERVAL = 12.0   # s zwischen zwei Re-Resolves derselben Session


class VavooSession:
    """Haelt eine VAVOO-Live-Playlist und einen vorausgeladenen Segment-Cache."""

    def __init__(self, sid, m3u8_url, src_b64):
        self.sid = sid
        self.m3u8_url = m3u8_url
        self.src_b64 = src_b64
        self.pl_headers = {"User-Agent": "MediaHubMX/2", "Accept-Encoding": "gzip"}
        self.seg_headers = {"User-Agent": "MediaHubMX/2", "Accept-Encoding": "identity"}
        self.lock = threading.Lock()
        self.cache = OrderedDict()          # seg_url -> bytes
        self.cache_bytes = 0
        self.prefetched = OrderedDict()     # seg_url -> True (Historie, verhindert Re-Download evakuierter Segmente)
        self.inflight = {}                  # seg_url -> threading.Event
        self.playlist_text = ""
        self.playlist_base = m3u8_url
        self.playlist_ts = 0.0
        self._last_seq = None            # #EXT-X-MEDIA-SEQUENCE der letzten Playlist
        self._seq_since = time.time()    # seit wann steht diese Sequence
        self._last_reresolve = 0.0
        self.target_duration = 6
        self.last_access = time.time()
        self.stop = threading.Event()
        self.prefetch = getSetting("vavoo_proxy_prefetch") != "false"
        self.thread = None

    def start(self):
        if self.prefetch:
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()

    def touch(self):
        self.last_access = time.time()

    # ---- Segment-Cache ----
    def _cache_get(self, seg_url):
        with self.lock:
            data = self.cache.get(seg_url)
            if data is not None:
                self.cache.move_to_end(seg_url)
            return data

    def _cache_put(self, seg_url, data):
        with self.lock:
            if seg_url in self.cache:
                self.cache_bytes -= len(self.cache[seg_url])
            self.cache[seg_url] = data
            self.cache.move_to_end(seg_url)
            self.cache_bytes += len(data)
            while self.cache_bytes > PREFETCH_MAX_BYTES and len(self.cache) > 1:
                _, old = self.cache.popitem(last=False)
                self.cache_bytes -= len(old)

    def _cache_clear(self):
        with self.lock:
            self.cache.clear()
            self.cache_bytes = 0
            self.prefetched.clear()

    # ---- Upstream ----
    def _reresolve(self):
        """Loest dieselbe Quelle neu auf (gedrosselt). True bei Erfolg."""
        now = time.time()
        if not self.src_b64 or now - self._last_reresolve < RERESOLVE_MIN_INTERVAL:
            return False
        self._last_reresolve = now
        fresh = _reresolve_vavoo(self.src_b64)
        if not fresh:
            return False
        with self.lock:
            self.m3u8_url = fresh
        self._cache_clear()
        self._last_seq = None
        self._seq_since = now
        return True

    def _fetch_playlist(self):
        client = get_httpx()
        if not client:
            return None
        url = self.m3u8_url
        try:
            r = client.get(url, headers=self.pl_headers)
        except Exception:
            r = None

        bad = r is None or r.status_code != 200 or "#EXTM3U" not in r.text[:512]
        if not bad:
            # still gestorbener Token: Playlist antwortet 200, aber MEDIA-SEQUENCE
            # ruehrt sich ueber mehrere Segmentlaengen nicht mehr
            seq = _media_sequence(r.text)
            if seq is not None and seq == self._last_seq:
                if time.time() - self._seq_since > max(20.0, 3 * self.target_duration):
                    log("VAVOO Proxy: Playlist eingefroren (seq=%s) -> Re-Resolve" % seq)
                    bad = True
            elif seq != self._last_seq:
                self._last_seq = seq
                self._seq_since = time.time()

        if bad:
            if not self._reresolve():
                return None
            url = self.m3u8_url
            try:
                r = client.get(url, headers=self.pl_headers)
            except Exception:
                r = None
            if r is None or r.status_code != 200 or "#EXTM3U" not in r.text[:512]:
                return None

        text = r.text
        td = _parse_target_duration(text)
        seq = _media_sequence(text)
        with self.lock:
            self.playlist_text = text
            self.playlist_base = url
            self.playlist_ts = time.time()
            if td:
                self.target_duration = td
        if seq != self._last_seq:
            self._last_seq = seq
            self._seq_since = time.time()
        return text

    def _segment_urls(self, text, base):
        out = []
        for line in text.splitlines():
            l = line.strip()
            if l and not l.startswith("#"):
                out.append(urljoin(base, l))
        return out

    def _download(self, seg_url):
        cached = self._cache_get(seg_url)
        if cached is not None:
            return cached
        with self.lock:
            ev = self.inflight.get(seg_url)
            owner = ev is None
            if owner:
                ev = threading.Event()
                self.inflight[seg_url] = ev
        if not owner:
            ev.wait(timeout=25)
            return self._cache_get(seg_url)
        data = None
        try:
            client = get_httpx()
            if client:
                r = client.get(seg_url, headers=self.seg_headers)
                if r.status_code == 200 and r.content:
                    data = r.content
        except Exception as exc:
            _neterr("VAVOO Proxy Segment-Download fehlgeschlagen", exc)
        if data is not None:
            self._cache_put(seg_url, data)
        with self.lock:
            self.inflight.pop(seg_url, None)
        ev.set()
        return data

    def get_segment(self, seg_url):
        self.touch()
        return self._download(seg_url)

    def get_playlist(self):
        self.touch()
        with self.lock:
            text, ts, base = self.playlist_text, self.playlist_ts, self.playlist_base
        # Mit Prefetch-Thread haelt der die Playlist frisch -> Request-Pfad NIE
        # blockieren (sonst haengt ffmpeg im Re-Resolve und laeuft in den I/O-Timeout).
        if text and self.prefetch:
            return text, base
        stale = (not text) or (time.time() - ts > max(1.0, self.target_duration / 2.0))
        if stale:
            if self._fetch_playlist():
                with self.lock:
                    return self.playlist_text, self.playlist_base
        return text, base

    def _run(self):
        fails = 0
        while not self.stop.is_set():
            if time.time() - self.last_access > SESSION_IDLE_TIMEOUT:
                break
            text = self._fetch_playlist()
            if text:
                fails = 0
                with self.lock:
                    base = self.playlist_base
                # ganzes sichtbares Fenster vorausladen (das erste Segment das ffmpeg
                # anfordert soll schon da sein). Byte-Budget + LRU begrenzen den RAM.
                # nur vorwaerts: bereits geladene/evakuierte Segmente nicht erneut ziehen.
                for seg_url in self._segment_urls(text, base):
                    if self.stop.is_set():
                        break
                    if seg_url in self.prefetched:
                        continue
                    self.prefetched[seg_url] = True
                    while len(self.prefetched) > 64:
                        self.prefetched.popitem(last=False)
                    if self._cache_get(seg_url) is None:
                        self._download(seg_url)
                delay = max(1.0, min(5.0, self.target_duration / 2.0))
            else:
                # Upstream/Netz weg -> Backoff, damit wir nicht im Sekundentakt hämmern
                fails += 1
                delay = min(30.0, 3.0 * fails)
            self.stop.wait(delay)
        _drop_vavoo_session(self.sid)


def _reap_sessions_locked():
    for sid, s in list(_vavoo_sessions.items()):
        if s.stop.is_set() or time.time() - s.last_access > SESSION_IDLE_TIMEOUT:
            s.stop.set()
            _vavoo_sessions.pop(sid, None)


def _register_vavoo_session(m3u8_url, vavoo_link):
    ensure_proxy()
    src_b64 = ""
    if vavoo_link:
        try:
            src_b64 = base64.b64encode(vavoo_link.encode("utf-8")).decode("ascii")
        except Exception:
            src_b64 = ""
    sid = "%011x" % (int(time.time() * 1000) & 0xfffffffffff)
    sess = VavooSession(sid, m3u8_url, src_b64)
    with _vavoo_sessions_lock:
        _reap_sessions_locked()
        while len(_vavoo_sessions) >= MAX_SESSIONS:
            old_sid, old = next(iter(_vavoo_sessions.items()))
            old.stop.set()
            _vavoo_sessions.pop(old_sid, None)
        _vavoo_sessions[sid] = sess
    # Playlist + erste Segmente sofort holen, damit die erste ffmpeg-Anfrage nicht wartet
    try:
        sess._fetch_playlist()
    except Exception:
        log("VAVOO Proxy Priming fehlgeschlagen:\n%s" % format_exc())
    sess.start()
    return sid


def _get_vavoo_session(sid):
    with _vavoo_sessions_lock:
        s = _vavoo_sessions.get(sid)
    if s:
        s.touch()
    return s


def _drop_vavoo_session(sid):
    with _vavoo_sessions_lock:
        s = _vavoo_sessions.pop(sid, None)
    if s:
        s.stop.set()


def _ts_sync_offset(data):
    """Findet einen belastbaren 188-Byte-MPEG-TS-Paketanfang."""
    if not data:
        return None
    for offset in range(min(188, len(data))):
        if data[offset] != 0x47:
            continue
        checks = min(3, (len(data) - offset - 1) // 188 + 1)
        if checks >= 2 and all(data[offset + (n * 188)] == 0x47 for n in range(checks)):
            return offset
    if len(data) < 376 and data[0] == 0x47:
        return 0
    return None


_PTS_WRAP = 1 << 33


def _packet_video_pts(packet):
    if len(packet) != 188 or packet[0] != 0x47 or not (packet[1] & 0x40):
        return None
    afc = (packet[3] >> 4) & 3
    if afc in (0, 2):
        return None
    offset = 4
    if afc == 3:
        offset += 1 + packet[4]
    if offset + 14 > 188:
        return None
    payload = packet[offset:]
    if payload[:3] != b"\x00\x00\x01" or not (0xE0 <= payload[3] <= 0xEF):
        return None
    if not (payload[7] & 0x80):
        return None
    pts = payload[9:14]
    return ((pts[0] & 0x0E) << 29) | (pts[1] << 22) | ((pts[2] & 0xFE) << 14) | (pts[3] << 7) | ((pts[4] & 0xFE) >> 1)


def _pts_after(value, reference):
    delta = (value - reference) % _PTS_WRAP
    return 0 < delta < (_PTS_WRAP // 2)


def _latest_video_pts(data, reference=None):
    latest = reference
    for pos in range(0, len(data) - 187, 188):
        pts = _packet_video_pts(data[pos:pos + 188])
        if pts is not None and (latest is None or _pts_after(pts, latest)):
            latest = pts
    return latest


def _pat_pmt_pid(packet):
    if len(packet) != 188 or packet[0] != 0x47 or not (packet[1] & 0x40):
        return None
    afc = (packet[3] >> 4) & 3
    if afc in (0, 2):
        return None
    offset = 4
    if afc == 3:
        offset += 1 + packet[4]
    if offset >= 188:
        return None
    offset += 1 + packet[offset]
    if offset + 12 > 188 or packet[offset] != 0x00:
        return None
    section_length = ((packet[offset + 1] & 0x0F) << 8) | packet[offset + 2]
    end = min(188, offset + 3 + section_length - 4)
    pos = offset + 8
    while pos + 4 <= end:
        program = (packet[pos] << 8) | packet[pos + 1]
        if program:
            return ((packet[pos + 2] & 0x1F) << 8) | packet[pos + 3]
        pos += 4
    return None


def _trim_reconnect_overlap(buffer, reference_pts, psi):
    complete = (len(buffer) // 188) * 188
    for pos in range(0, complete, 188):
        packet = bytes(buffer[pos:pos + 188])
        pid = ((packet[1] & 0x1F) << 8) | packet[2]
        if pid == 0:
            psi["pat"] = packet
            pmt_pid = _pat_pmt_pid(packet)
            if pmt_pid is not None:
                psi["pmt_pid"] = pmt_pid
        elif pid == psi.get("pmt_pid"):
            psi["pmt"] = packet
        elif pid == 17:
            psi["sdt"] = packet
        pts = _packet_video_pts(packet)
        if pts is not None and _pts_after(pts, reference_pts):
            prefix = b"".join(psi[key] for key in ("pat", "pmt", "sdt") if psi.get(key))
            return bytearray(prefix) + buffer[pos:], True
    if complete:
        del buffer[:complete]
    return buffer, False


class StalkerTsSession:
    """Macht aus wiederholt endenden MPEG-TS-Antworten einen lokalen Live-HLS-Stream."""

    def __init__(self, sid, stream_url, headers=None, channel=None):
        self.sid = sid
        self.stream_url = stream_url
        self.headers = self._clean_headers(headers)
        self.channel = channel
        self.condition = threading.Condition()
        self.segments = OrderedDict()
        self.cache_bytes = 0
        self.next_sequence = 0
        self.discontinuity_count = 0
        self.pending_discontinuity = False
        self.last_video_pts = None
        self.target_duration = max(1, int(math.ceil(STALKER_SEGMENT_SECONDS)))
        self.last_access = time.time()
        self.stop = threading.Event()
        self.thread = None

    @staticmethod
    def _clean_headers(headers):
        cleaned = {}
        for key, value in dict(headers or {}).items():
            if str(key).lower() not in ("connection", "accept-encoding"):
                cleaned[str(key)] = str(value)
        cleaned["Accept-Encoding"] = "identity"
        return cleaned

    def start(self):
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def touch(self):
        self.last_access = time.time()

    def _add_segment(self, data, duration, discontinuity):
        if not data:
            return
        self.last_video_pts = _latest_video_pts(data, self.last_video_pts)
        with self.condition:
            seq = self.next_sequence
            self.next_sequence += 1
            disc_before = self.discontinuity_count
            if discontinuity:
                self.discontinuity_count += 1
            self.target_duration = max(self.target_duration, int(math.ceil(float(duration))))
            self.segments[seq] = {
                "seq": seq,
                "data": data,
                "duration": max(0.1, float(duration)),
                "discontinuity": bool(discontinuity),
                "disc_before": disc_before,
            }
            self.cache_bytes += len(data)
            while (len(self.segments) > STALKER_PLAYLIST_SEGMENTS or
                   self.cache_bytes > STALKER_MAX_BYTES) and len(self.segments) > 1:
                _, old = self.segments.popitem(last=False)
                self.cache_bytes -= len(old["data"])
            self.condition.notify_all()

    def _reresolve(self):
        if self.channel is None:
            return False
        try:
            from vavoo.stalker import StalkerPortal
            fresh_url, fresh_headers = StalkerPortal(
                get_cache_or_setting("stalkerurl"), get_cache_or_setting("mac")
            ).get_tv_stream_url(self.channel)
            if not fresh_url:
                return False
            self.stream_url = fresh_url
            self.headers = self._clean_headers(fresh_headers)
            log("Stalker TS Proxy: temporaeren Link neu aufgeloest")
            return True
        except Exception as exc:
            _neterr("Stalker TS Proxy Re-Resolve fehlgeschlagen", exc)
            return False

    def _run(self):
        failures = 0
        reconnects = 0
        while not self.stop.is_set():
            if time.time() - self.last_access > STALKER_SESSION_IDLE_TIMEOUT:
                break

            response = None
            buffer = bytearray()
            aligned = False
            received = False
            segment_started = time.monotonic()
            resume_pts = self.last_video_pts if self.pending_discontinuity else None
            resume_started = time.monotonic()
            resume_psi = {}
            try:
                response = request(
                    "GET", self.stream_url, headers=self.headers, stream=True,
                    timeout=(8, 15), retries=0
                )
                response.raise_for_status()
                for chunk in response.iter_content(chunk_size=64 * 1024):
                    if self.stop.is_set():
                        break
                    if not chunk:
                        continue
                    received = True
                    buffer.extend(chunk)
                    if not aligned:
                        offset = _ts_sync_offset(buffer)
                        if offset is None:
                            if len(buffer) > 188 * 5:
                                del buffer[:-188 * 3]
                            continue
                        if offset:
                            del buffer[:offset]
                        aligned = True
                        segment_started = time.monotonic()

                    now = time.monotonic()
                    if resume_pts is not None:
                        buffer, resumed = _trim_reconnect_overlap(buffer, resume_pts, resume_psi)
                        if not resumed and now - resume_started < STALKER_RESUME_TIMEOUT:
                            continue
                        if resumed:
                            log("Stalker TS Proxy: Wiederholung bis zum letzten Video-PTS uebersprungen")
                        else:
                            log("Stalker TS Proxy: PTS-Suche nach Timeout fortgesetzt")
                        resume_pts = None
                        segment_started = now
                    complete = (len(buffer) // 188) * 188
                    if complete and now - segment_started >= STALKER_SEGMENT_SECONDS:
                        payload = bytes(buffer[:complete])
                        del buffer[:complete]
                        self._add_segment(payload, now - segment_started, self.pending_discontinuity)
                        self.pending_discontinuity = False
                        segment_started = now
            except Exception as exc:
                _neterr("Stalker TS Proxy Upstream", exc)
            finally:
                if response is not None:
                    try:
                        response.close()
                    except Exception:
                        pass

            complete = (len(buffer) // 188) * 188 if aligned else 0
            if complete and resume_pts is None:
                now = time.monotonic()
                self._add_segment(
                    bytes(buffer[:complete]), now - segment_started,
                    self.pending_discontinuity
                )
                self.pending_discontinuity = False

            if received:
                failures = 0
                reconnects += 1
                self.pending_discontinuity = True
                # Derselbe temporaere Link kann beim erneuten GET denselben
                # Ausschnitt wiederholen. Deshalb fuer denselben Sender nach
                # jedem EOF zuerst einen frischen create_link anfordern.
                refreshed = self._reresolve()
                log("Stalker TS Proxy: Upstream-Ende, Reconnect %s (%s)" % (
                    reconnects, "frischer Link" if refreshed else "bestehender Link"
                ))
                delay = 0.2 if refreshed else 1.0
            else:
                failures += 1
                if failures >= 3 and self._reresolve():
                    failures = 0
                delay = min(5.0, float(failures or 1))
            self.stop.wait(delay)

        _drop_stalker_session(self.sid)

    def get_playlist(self, port):
        self.touch()
        deadline = time.time() + 8.0
        with self.condition:
            while not self.segments and not self.stop.is_set():
                remaining = deadline - time.time()
                if remaining <= 0:
                    break
                self.condition.wait(min(remaining, 0.5))
            items = list(self.segments.values())
        if not items:
            return ""

        lines = [
            "#EXTM3U",
            "#EXT-X-VERSION:3",
            "#EXT-X-TARGETDURATION:%s" % self.target_duration,
            "#EXT-X-MEDIA-SEQUENCE:%s" % items[0]["seq"],
            "#EXT-X-DISCONTINUITY-SEQUENCE:%s" % items[0]["disc_before"],
        ]
        for item in items:
            if item["discontinuity"]:
                lines.append("#EXT-X-DISCONTINUITY")
            lines.append("#EXTINF:%.3f," % item["duration"])
            lines.append(
                "http://127.0.0.1:%s/stalker_segment.ts?sid=%s&seq=%s"
                % (port, self.sid, item["seq"])
            )
        return "\n".join(lines) + "\n"

    def get_segment(self, seq):
        self.touch()
        with self.condition:
            item = self.segments.get(seq)
            return item["data"] if item else None


def _reap_stalker_sessions_locked():
    for sid, sess in list(_stalker_sessions.items()):
        if sess.stop.is_set() or time.time() - sess.last_access > STALKER_SESSION_IDLE_TIMEOUT:
            sess.stop.set()
            _stalker_sessions.pop(sid, None)


def _register_stalker_session(stream_url, headers=None, channel=None):
    sid = "s%014x" % (int(time.time() * 1000000) & 0xfffffffffffffff)
    sess = StalkerTsSession(sid, stream_url, headers, channel)
    with _stalker_sessions_lock:
        _reap_stalker_sessions_locked()
        while len(_stalker_sessions) >= STALKER_MAX_SESSIONS:
            old_sid, old = next(iter(_stalker_sessions.items()))
            old.stop.set()
            _stalker_sessions.pop(old_sid, None)
        _stalker_sessions[sid] = sess
    sess.start()
    return sid


def _get_stalker_session(sid):
    with _stalker_sessions_lock:
        sess = _stalker_sessions.get(sid)
    if sess:
        sess.touch()
    return sess


def _drop_stalker_session(sid):
    with _stalker_sessions_lock:
        sess = _stalker_sessions.pop(sid, None)
    if sess:
        sess.stop.set()


def decode_foobarx(raw_text, ext, offset):
    try:
        if ext == "woff":
            return raw_text[13:].encode("utf-8")
        elif ext == "bmp":
            return bytes.fromhex(raw_text[32 + offset:].strip())
        elif ext == "csv":
            sliced = raw_text[8 + offset:]
            lines = sliced.replace("\r\n", "\n").split("\n")
            tokens = []
            for line in lines:
                tokens.extend(line.split(","))
            tokens.reverse()
            return base64.b64decode("".join(tokens))
    except Exception:
        log("FooBarX decode failed: %s" % format_exc())
    return b""


class UnifiedLiveProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    timeout = 30

    # ---- Antwort-Helfer (Keep-Alive-sicher: immer korrekte Content-Length) ----
    def _write(self, body):
        try:
            self.wfile.write(body)
        except Exception:
            self.close_connection = True

    def _fail(self, code, msg=""):
        # send_error kann selbst BrokenPipe werfen, wenn der Client (ffmpeg) schon weg ist
        try:
            self.send_error(code, msg)
        except Exception:
            self.close_connection = True

    def _parse_range(self, total):
        rng = self.headers.get("Range")
        if not rng or not rng.startswith("bytes="):
            return None
        try:
            s, _, e = rng[6:].partition("-")
            start = int(s) if s.strip() else 0
            end = int(e) if e.strip() else total - 1
            end = min(end, total - 1)
            if start < 0 or start > end:
                return None
            if start == 0 and end == total - 1:
                return None
            return start, end
        except Exception:
            return None

    def _respond_text(self, text, ctype):
        body = text.encode("utf-8") if isinstance(text, str) else text
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        if self.command != "HEAD":
            self._write(body)

    def _respond_bytes(self, data, ctype):
        total = len(data)
        rng = self._parse_range(total)
        if rng:
            start, end = rng
            body = data[start:end + 1]
            self.send_response(206)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, total))
        else:
            body = data
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(total))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        if self.command != "HEAD":
            self._write(body)

    def _passthrough(self, client, url, req_headers, ctype):
        want_range = bool(self.headers.get("Range"))
        try:
            with client.stream("GET", url, headers=req_headers) as r:
                if r.status_code != 200:
                    self._fail(502, "Upstream %s" % r.status_code)
                    return
                clen = r.headers.get("content-length")
                if clen and not want_range and self.command != "HEAD":
                    self.send_response(200)
                    self.send_header("Content-Type", ctype)
                    self.send_header("Content-Length", clen)
                    self.send_header("Accept-Ranges", "bytes")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    for chunk in r.iter_bytes():
                        if not chunk:
                            continue
                        try:
                            self.wfile.write(chunk)
                        except Exception:
                            self.close_connection = True
                            return
                else:
                    self._respond_bytes(r.read(), ctype)
        except Exception as exc:
            _neterr("Proxy Passthrough Fehler", exc)
            self._fail(502, "Upstream Fehler")

    def _serve_session_segment(self, sess, seg_url):
        """Cache-Hit: sofort. Miss: waehrend des Downloads durchstreamen (kein
        9-Sekunden-Blackout fuer ffmpeg) und parallel in den Cache legen."""
        cached = sess._cache_get(seg_url)
        if cached is not None:
            self._respond_bytes(cached, "video/MP2T")
            return
        rng = self.headers.get("Range", "")
        real_range = rng.startswith("bytes=") and rng not in ("bytes=0-", "bytes=0-0")
        client = get_httpx()
        if not client:
            self._fail(502, "HTTP client unavailable")
            return
        try:
            with client.stream("GET", seg_url, headers=sess.seg_headers) as r:
                if r.status_code != 200:
                    self._fail(504, "Segment %s" % r.status_code)
                    return
                clen = r.headers.get("content-length")
                if real_range or not clen:
                    data = r.read()
                    if clen and len(data) == int(clen):
                        sess._cache_put(seg_url, data)
                    elif not clen and data:
                        sess._cache_put(seg_url, data)
                    self._respond_bytes(data, "video/MP2T")
                    return
                total = int(clen)
                self.send_response(200)
                self.send_header("Content-Type", "video/MP2T")
                self.send_header("Content-Length", clen)
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                buf = bytearray()
                broken = False
                for chunk in r.iter_bytes():
                    if not chunk:
                        continue
                    buf += chunk
                    if not broken and self.command != "HEAD":
                        try:
                            self.wfile.write(chunk)
                        except Exception:
                            self.close_connection = True
                            broken = True
                if len(buf) == total:
                    sess._cache_put(seg_url, bytes(buf))
        except Exception as exc:
            _neterr("Segment-Stream Fehler", exc)
            self._fail(504, "Segment nicht verfuegbar")

    # ---- Router ----
    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            params = dict(parse_qsl(parsed.query))
            target_url = params.get("url", "")
            ref = params.get("ref", "")
            try:
                offset = int(params.get("offset", 22))
            except Exception:
                offset = 22

            if parsed.path == "/stalker_live.m3u8":
                sess = _get_stalker_session(params.get("sid", ""))
                if sess is None:
                    self._fail(404, "Stalker Session nicht gefunden")
                    return
                text = sess.get_playlist(self.server.server_address[1])
                if not text:
                    self._fail(503, "Noch keine TS-Daten")
                    return
                self._respond_text(text, "application/vnd.apple.mpegurl")
                return

            if parsed.path == "/stalker_segment.ts":
                sess = _get_stalker_session(params.get("sid", ""))
                try:
                    seq = int(params.get("seq", "-1"))
                except (TypeError, ValueError):
                    seq = -1
                data = sess.get_segment(seq) if sess is not None else None
                if data is None:
                    self._fail(404, "Segment nicht gefunden")
                    return
                self._respond_bytes(data, "video/MP2T")
                return

            client = get_httpx()
            if not client:
                self._fail(500, "HTTP client unavailable")
                return

            if parsed.path == "/nydus_live.m3u8":
                headers = {"User-Agent": BROWSER_UA, "Referer": ref or "https://nydus.org/"}
                try:
                    r = client.get(target_url, headers=headers)
                except Exception as exc:
                    _neterr("Nydus Playlist Fehler", exc)
                    self._fail(502, "Upstream nicht verfuegbar")
                    return
                port = self.server.server_address[1]
                lines = []
                for line in r.text.splitlines():
                    l = line.strip()
                    if l and not l.startswith("#"):
                        ext = l.split(".")[-1]
                        seg_target = urljoin(target_url, l)
                        lines.append("http://127.0.0.1:%d/nydus_segment.ts?url=%s&ext=%s&offset=%d&ref=%s"
                                     % (port, quote_plus(seg_target), ext, offset, quote_plus(ref)))
                    else:
                        lines.append(line)
                self._respond_text("\n".join(lines), "application/vnd.apple.mpegurl")

            elif parsed.path == "/nydus_segment.ts":
                headers = {"User-Agent": BROWSER_UA, "Referer": ref or "https://nydus.org/"}
                ext = params.get("ext", "csv")
                try:
                    r = client.get(target_url, headers=headers)
                except Exception as exc:
                    _neterr("Nydus Segment Fehler", exc)
                    self._fail(502, "Upstream nicht verfuegbar")
                    return
                ts_data = decode_foobarx(r.text, ext, offset)
                self._respond_bytes(ts_data, "video/MP2T")

            elif parsed.path == "/vavoo_live.m3u8":
                sid = params.get("sid", "")
                sess = _get_vavoo_session(sid) if sid else None
                port = self.server.server_address[1]
                if sess is not None:
                    text, base = sess.get_playlist()
                    if not text:
                        self._fail(502, "Upstream nicht verfuegbar")
                        return
                    out = []
                    for line in text.splitlines():
                        l = line.strip()
                        if l and not l.startswith("#"):
                            seg_abs = urljoin(base, l)
                            tok = base64.urlsafe_b64encode(seg_abs.encode("utf-8")).decode("ascii").rstrip("=")
                            out.append("http://127.0.0.1:%d/vavoo_segment.ts?sid=%s&seg=%s" % (port, sid, tok))
                        else:
                            out.append(line)
                    self._respond_text("\n".join(out), "application/vnd.apple.mpegurl")
                    return
                # Fallback ohne Session (url= / src=)
                src_b64 = params.get("src", "")
                pl_headers = {"User-Agent": "MediaHubMX/2", "Accept-Encoding": "gzip"}
                try:
                    r = client.get(target_url, headers=pl_headers)
                except Exception:
                    r = None
                if src_b64 and (r is None or r.status_code != 200 or "#EXTM3U" not in r.text[:512]):
                    fresh = _reresolve_vavoo(src_b64)
                    if fresh:
                        target_url = fresh
                        try:
                            r = client.get(target_url, headers=pl_headers)
                        except Exception:
                            r = None
                if r is None:
                    self._fail(502, "Upstream nicht verfuegbar")
                    return
                out = []
                for line in r.text.splitlines():
                    l = line.strip()
                    if l and not l.startswith("#"):
                        seg_abs = urljoin(target_url, l)
                        out.append("http://127.0.0.1:%d/vavoo_segment.ts?url=%s" % (port, quote_plus(seg_abs)))
                    else:
                        out.append(line)
                self._respond_text("\n".join(out), "application/vnd.apple.mpegurl")

            elif parsed.path == "/vavoo_segment.ts":
                seg_headers = {"User-Agent": "MediaHubMX/2", "Accept-Encoding": "identity"}
                seg_tok = params.get("seg", "")
                sid = params.get("sid", "")
                if seg_tok:
                    try:
                        seg_url = base64.urlsafe_b64decode(seg_tok + "=" * (-len(seg_tok) % 4)).decode("utf-8")
                    except Exception:
                        seg_url = ""
                    if not seg_url:
                        self._fail(400, "bad segment token")
                        return
                    sess = _get_vavoo_session(sid) if sid else None
                    if sess is not None:
                        sess.touch()
                        self._serve_session_segment(sess, seg_url)
                        return
                    self._passthrough(client, seg_url, seg_headers, "video/MP2T")
                    return
                self._passthrough(client, target_url, seg_headers, "video/MP2T")

            else:
                self._fail(404, "Not Found")
        except _NET_ERR as exc:
            _neterr("Proxy Verbindungsabbruch", exc)
            self.close_connection = True
        except Exception as exc:
            # httpx-Fehler sind keine OSError -> hier per Name abfangen, kein Traceback
            if exc.__class__.__module__.split(".")[0] in ("httpx", "httpcore", "h2", "requests", "urllib3", "ssl"):
                _neterr("Proxy Netzfehler", exc)
            else:
                log("UnifiedLiveProxyHandler exception:\n%s" % format_exc())
            self._fail(500, "Internal Error")
            self.close_connection = True

    do_HEAD = do_GET

    def log_message(self, fmt, *args):
        try:
            log("PROXY %s %s Range=%s" % (self.command, self.path[:160], self.headers.get("Range")))
        except Exception:
            pass


class ThreadedProxyServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def handle_error(self, request, client_address):
        # ffmpeg trennt Keep-Alive-Verbindungen hart -> das ist normal, kein Traceback
        exc = sys.exc_info()[1]
        if isinstance(exc, (ConnectionError, BrokenPipeError, TimeoutError, OSError, ValueError)):
            return
        log("Proxy Server-Fehler:\n%s" % format_exc())


def ensure_proxy():
    global _proxy_server, _proxy_port
    with _proxy_lock:
        if _proxy_server is not None:
            return _proxy_port
        for port in (19888, 19889, 19890, 19891, 19892, 19893, 19894, 19895):
            try:
                server = ThreadedProxyServer(("127.0.0.1", port), UnifiedLiveProxyHandler)
                t = threading.Thread(target=server.serve_forever, daemon=True)
                t.start()
                _proxy_server = server
                _proxy_port = port
                log("Live HLS Proxy Server gestartet auf Port %s" % port)
                return _proxy_port
            except Exception:
                pass
        log("Live HLS Proxy Server konnte auf keinem Port gestartet werden")
        return 19888


def get_vavoo_proxy_url(m3u8_url, vavoo_link=""):
    if not m3u8_url or not isinstance(m3u8_url, str):
        return m3u8_url
    port = ensure_proxy()
    if not isinstance(vavoo_link, str):
        vavoo_link = ""
    extra = ""
    if vavoo_link:
        try:
            extra = "&src=" + quote_plus(base64.b64encode(vavoo_link.encode("utf-8")).decode("ascii"))
        except Exception:
            extra = ""
    try:
        sid = _register_vavoo_session(m3u8_url, vavoo_link)
        # src bleibt an der URL: nach dem Verwerfen der Session (Idle-Timeout)
        # kann der Fallback-Zweig die Quelle neu aufloesen.
        return f"http://127.0.0.1:{port}/vavoo_live.m3u8?sid={sid}{extra}"
    except Exception:
        log("VAVOO Proxy Session-Setup fehlgeschlagen:\n%s" % format_exc())
    return f"http://127.0.0.1:{port}/vavoo_live.m3u8?url={quote_plus(m3u8_url)}{extra}"


def get_stalker_proxy_url(stream_url, headers=None, channel=None):
    """Registriert einen endlichen Stalker-TS-Link als fortlaufende lokale HLS-Quelle."""
    if not stream_url or not isinstance(stream_url, str):
        return stream_url
    port = ensure_proxy()
    try:
        sid = _register_stalker_session(stream_url, headers, channel)
        return f"http://127.0.0.1:{port}/stalker_live.m3u8?sid={sid}"
    except Exception:
        log("Stalker TS Proxy Session-Setup fehlgeschlagen:\n%s" % format_exc())
        return stream_url


def get_nydus_proxy_url(m3u8_url, offset=22, origin=""):
    if not m3u8_url or not isinstance(m3u8_url, str):
        return m3u8_url
    port = ensure_proxy()
    ref_param = f"&ref={quote_plus(origin)}/" if origin else ""
    return f"http://127.0.0.1:{port}/nydus_live.m3u8?url={quote_plus(m3u8_url)}&offset={offset}{ref_param}"
