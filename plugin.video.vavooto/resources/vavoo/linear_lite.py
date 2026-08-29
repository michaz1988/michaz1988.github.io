# -*- coding: utf-8 -*-
from vavoo.utils import *
import html
import re
import http.server
import threading
import urllib.parse
import subprocess

BASE_URL = "https://www.2ix2.com"
POSTS_URL = BASE_URL + "/wp-json/wp/v2/posts"
NYDUS_BASE_URL = "https://nydus.org"
NYDUS_LIVE_URL = NYDUS_BASE_URL + "/stream/live/"
NYDUS_EMBED_URL = NYDUS_BASE_URL + "/stream/embedplayer_hq.php?id=%s"

CATEGORIES = (
    {"slug": "de", "label": "Deutsche TV", "category_id": 1},
    {"slug": "at", "label": "Österreichische TV", "category_id": 61},
    {"slug": "ch", "label": "Schweizer TV", "category_id": 100},
)

NYDUS_AUSTRIA_IDS = {"orf-1", "orf-2", "servus-tv"}
NYDUS_SWISS_IDS = {"srf1", "srf2", "srf-info", "srfinfo", "3plus", "4plus", "5plus", "6plus"}

_proxy_server = None
_proxy_port = 19888
_proxy_lock = threading.Lock()


class NydusProxyHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)

        if parsed.path == "/nydus_live.m3u8":
            target_m3u8 = qs.get("url", [""])[0]
            offset = int(qs.get("offset", ["22"])[0])
            referer = qs.get("ref", [""])[0]

            cmd = [
                "curl", "-s",
                "-A", "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Mobile Safari/537.36",
                "-e", referer,
                target_m3u8
            ]
            raw_m3u8 = subprocess.run(cmd, capture_output=True).stdout.decode("utf-8", errors="ignore")
            base_url = target_m3u8.rsplit("/", 1)[0]
            new_lines = []
            for line in raw_m3u8.splitlines():
                line_str = line.strip()
                if line_str and not line_str.startswith("#"):
                    seg_full = f"{base_url}/{line_str}" if not line_str.startswith("http") else line_str
                    proxy_seg = f"http://127.0.0.1:{_proxy_port}/nydus_segment.ts?url={urllib.parse.quote(seg_full)}&offset={offset}&ref={urllib.parse.quote(referer)}"
                    new_lines.append(proxy_seg)
                else:
                    new_lines.append(line_str)

            payload = "\n".join(new_lines).encode("utf-8")
            try:
                self.send_response(200)
                self.send_header("Content-Type", "application/vnd.apple.mpegurl")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            except Exception:
                pass

        elif parsed.path == "/nydus_segment.ts":
            target_seg = qs.get("url", [""])[0]
            offset = int(qs.get("offset", ["22"])[0])
            referer = qs.get("ref", [""])[0]

            cmd = [
                "curl", "-s",
                "-A", "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Mobile Safari/537.36",
                "-e", referer,
                target_seg
            ]
            data = subprocess.run(cmd, capture_output=True).stdout
            ts_bytes = b""

            if b".tsl.csv" in target_seg.encode():
                text = data.decode("utf-8", errors="ignore")
                sliced = text[8 + offset:]
                lines = sliced.splitlines()
                flat = []
                for l in lines:
                    flat.extend(l.split(","))
                flat.reverse()
                encoded = "".join(flat)
                pad = len(encoded) % 4
                if pad:
                    encoded += "=" * (4 - pad)
                try:
                    ts_bytes = base64.b64decode(encoded)
                except Exception:
                    ts_bytes = data
            elif b".tsl.bmp" in target_seg.encode():
                hex_str = data[32 + offset:].decode("ascii", errors="ignore")
                if len(hex_str) % 2:
                    hex_str += "0"
                try:
                    ts_bytes = bytes.fromhex(hex_str)
                except Exception:
                    ts_bytes = data
            elif b".tsl.woff" in target_seg.encode():
                source = data.decode("latin1", errors="ignore")
                hex_str = "".join(f"{ord(c):08x}" for c in source[13:])
                try:
                    ts_bytes = bytes.fromhex(hex_str)
                except Exception:
                    ts_bytes = data
            else:
                ts_bytes = data

            try:
                self.send_response(200)
                self.send_header("Content-Type", "video/MP2T")
                self.send_header("Content-Length", str(len(ts_bytes)))
                self.end_headers()
                self.wfile.write(ts_bytes)
            except Exception:
                pass


def _ensure_nydus_proxy():
    global _proxy_server
    with _proxy_lock:
        if _proxy_server is not None:
            return _proxy_port
        for port in range(19888, 19900):
            try:
                server = http.server.ThreadingHTTPServer(("127.0.0.1", port), NydusProxyHandler)
                t = threading.Thread(target=server.serve_forever, daemon=True)
                t.start()
                _proxy_server = server
                globals()["_proxy_port"] = port
                log(f"Nydus HD Proxy started on 127.0.0.1:{port}")
                return port
            except Exception:
                continue
    return _proxy_port


def lite_groups():
    return [c["label"] for c in CATEGORIES]


def choose_lite_groups():
    all_slugs = [c["slug"] for c in CATEGORIES]
    all_labels = [c["label"] for c in CATEGORIES]
    cache_ok, current = get_cache("lite_groups")
    if not cache_ok or not isinstance(current, list):
        current = all_slugs[:]

    preselect = [all_slugs.index(slug) for slug in current if slug in all_slugs]
    indices = selectDialog(all_labels, "LiteTV Gruppen auswählen", multiselect=True, preselect=preselect)
    if indices is None:
        return current

    selected_slugs = [all_slugs[i] for i in indices]
    set_cache("lite_groups", selected_slugs)
    del_cache("lite_channels")
    return selected_slugs


def _selected_categories():
    cache_ok, current = get_cache("lite_groups")
    if not cache_ok or not isinstance(current, list):
        current = [c["slug"] for c in CATEGORIES]
    return [c for c in CATEGORIES if c["slug"] in current]


def _extract_stream_url(content):
    text = html.unescape(content or "").replace(r"\/", "/")
    patterns = (
        r"\bfile\s*:\s*['\"]([^'\"]+)['\"]",
        r"['\"]file['\"]\s*:\s*['\"]([^'\"]+)['\"]",
        r"<source[^>]+src\s*=\s*['\"]([^'\"]+)['\"]",
        r"(https?://[^\s'\"<>]+?\.m3u8(?:\?[^\s'\"<>]+)?)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            stream_url = html.unescape(match.group(1)).strip()
            if stream_url.lower().startswith(("http://", "https://")) and ".m3u8" in stream_url.lower():
                return stream_url
    return ""


def _load_2ix2_category(category):
    try:
        headers = {
            "User-Agent": BROWSER_UA,
            "Accept": "application/json,text/html,*/*",
            "Referer": BASE_URL + "/",
            "Connection": "close",
        }
        res = request("GET", POSTS_URL, params={
            "categories": category["category_id"],
            "per_page": 100,
            "_fields": "id,slug,link,title,content",
        }, headers=headers, timeout=12, retries=1)
        res.raise_for_status()
        posts = res.json() or []
        channels = []
        for post in posts:
            content = post.get("content", {}).get("rendered") or ""
            stream_url = _extract_stream_url(content)
            if not stream_url:
                continue
            raw_title = post.get("title", {}).get("rendered") or post.get("slug") or ""
            clean = html.unescape(raw_title)
            clean = re.sub(r"<[^>]+>", " ", clean)
            clean = " ".join(clean.split()).strip()

            clean_upper = clean.upper()
            if "NITRO" in clean_upper:
                name = "NITRO"
            elif "SUPER RTL" in clean_upper or "SUPER-RTL" in clean_upper:
                name = "SUPER RTL"
            elif "RTL 2" in clean_upper or "RTL2" in clean_upper:
                name = "RTL 2"
            elif "RTL" in clean_upper:
                name = "RTL"
            else:
                name = filterout(clean).strip()

            if not name or not name.strip("])"):
                continue

            channels.append({
                "name": name,
                "group": category["label"],
                "group_slug": category["slug"],
                "source": "lite",
                "stream_type": "2ix2",
                "page_url": post.get("link") or BASE_URL,
                "stream_url": stream_url,
            })
        return channels
    except Exception:
        log("LiteTV 2ix2 category %s failed:\n%s" % (category["slug"], format_exc()))
        return []


def _b64decode(value):
    try:
        return base64.b64decode((value or "").encode("ascii")).decode("utf-8", "replace")
    except Exception:
        return ""


def _nydus_category(nydus_id):
    normalized = (nydus_id or "").strip().lower()
    if normalized in NYDUS_AUSTRIA_IDS:
        return "at"
    if normalized in NYDUS_SWISS_IDS:
        return "ch"
    return "de"


def _load_nydus_channels():
    try:
        headers = {
            "User-Agent": BROWSER_UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": NYDUS_LIVE_URL,
            "Connection": "close",
        }
        res = request("GET", NYDUS_LIVE_URL, headers=headers, timeout=15, retries=1)
        res.raise_for_status()
        content = res.text
        match = re.search(r"var\s+str\s*=\s*['\"]([A-Za-z0-9+/=]+)['\"]", content or "")
        if match:
            decoded = _b64decode(match.group(1))
            if decoded:
                content = decoded

        pattern = re.compile(
            r"<a\b[^>]*href=['\"]([^'\"]*/stream/live/([^'\"]+)/)['\"][^>]*>\s*"
            r"<div\b[^>]*class=['\"][^'\"]*tvsender[^'\"]*['\"][^>]*data-id=['\"]([^'\"]+)['\"][^>]*>\s*"
            r"<img\b[^>]*src=['\"]([^'\"]+)['\"][^>]*alt=['\"]([^'\"]+)['\"]",
            re.I | re.S,
        )
        channels = []
        slug_to_label = {c["slug"]: c["label"] for c in CATEGORIES}
        for m in pattern.finditer(content or ""):
            nydus_id = html.unescape(m.group(3)).strip()
            raw_name = html.unescape(m.group(5)).replace("-", " ")
            if not nydus_id or not raw_name:
                continue
            cat_slug = _nydus_category(nydus_id)

            clean_upper = raw_name.upper()
            if "NITRO" in clean_upper:
                name = "NITRO"
            elif "SUPER RTL" in clean_upper or "SUPER-RTL" in clean_upper:
                name = "SUPER RTL"
            elif "RTL 2" in clean_upper or "RTL2" in clean_upper:
                name = "RTL 2"
            elif "RTL" in clean_upper:
                name = "RTL"
            else:
                name = filterout(raw_name).strip()

            if not name or not name.strip("])"):
                continue

            channels.append({
                "name": name,
                "group": slug_to_label.get(cat_slug, "Deutsche TV"),
                "group_slug": cat_slug,
                "source": "lite",
                "stream_type": "nydus",
                "nydus_id": nydus_id,
                "page_url": urljoin(NYDUS_LIVE_URL, html.unescape(m.group(1))),
                "stream_url": "",
            })
        return channels
    except Exception:
        log("LiteTV Nydus load failed:\n%s" % format_exc())
        return []


def _resolve_nydus_hd(nydus_id):
    try:
        cmd1 = [
            "curl", "-s",
            "-A", "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Mobile Safari/537.36",
            "-e", f"https://nydus.org/stream/live/{nydus_id}/",
            f"https://nydus.org/stream/embedplayer_hq.php?id={nydus_id}"
        ]
        html1 = subprocess.run(cmd1, capture_output=True).stdout.decode("utf-8", errors="ignore")
        m_zdec = re.search(r"zdec\s*=\s*['\"]([^'\"]+)", html1)
        if not m_zdec:
            return None, None
        script1 = base64.b64decode(m_zdec.group(1)).decode("utf-8", errors="ignore")

        m_atob = re.search(r"atob\(['\"]([^'\"]+)", script1)
        if not m_atob:
            return None, None
        iframe_url = base64.b64decode(m_atob.group(1)).decode("utf-8", errors="ignore")

        cmd2 = [
            "curl", "-s",
            "-A", "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Mobile Safari/537.36",
            "-e", "https://nydus.org/",
            iframe_url
        ]
        html2 = subprocess.run(cmd2, capture_output=True).stdout.decode("utf-8", errors="ignore")
        m_embed = re.search(r"const\s+EMBED\s*=\s*({[^;]+});", html2)
        if not m_embed:
            return None, None

        embed_obj = json.loads(m_embed.group(1))
        parsed = urllib.parse.urlparse(iframe_url)
        base_origin = f"{parsed.scheme}://{parsed.netloc}"
        channel = embed_obj.get("channel")
        offset = embed_obj.get("hostLengthOffset", 22)
        m3u8_url = f"{base_origin}/conv/go/{channel}/chunks.m3u81a.doc"

        # Check if playlist is reachable and valid
        cmd3 = [
            "curl", "-s",
            "-A", "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Mobile Safari/537.36",
            "-e", f"{base_origin}/",
            m3u8_url
        ]
        m3u8_head = subprocess.run(cmd3, capture_output=True).stdout.decode("utf-8", errors="ignore")
        if "#EXTM3U" not in m3u8_head:
            return None, None

        port = _ensure_nydus_proxy()
        proxy_stream_url = f"http://127.0.0.1:{port}/nydus_live.m3u8?url={urllib.parse.quote(m3u8_url)}&offset={offset}&ref={urllib.parse.quote(base_origin + '/')}"
        return proxy_stream_url, None
    except Exception:
        log("LiteTV _resolve_nydus_hd failed for %s:\n%s" % (nydus_id, format_exc()))
        return None, None


def resolve_lite_stream(channel_info):
    if not isinstance(channel_info, dict):
        return None, None

    stream_type = channel_info.get("stream_type")
    page_url = channel_info.get("page_url") or BASE_URL
    stream_url = channel_info.get("stream_url") or ""

    if stream_type == "nydus":
        nydus_id = channel_info.get("nydus_id")
        if nydus_id:
            hd_url, hd_headers = _resolve_nydus_hd(nydus_id)
            if hd_url:
                return hd_url, hd_headers

            try:
                embed_url = NYDUS_EMBED_URL % quote(nydus_id, safe="")
                headers = {
                    "User-Agent": BROWSER_UA,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Referer": page_url or NYDUS_LIVE_URL,
                    "Connection": "close",
                }
                res = request("GET", embed_url, headers=headers, timeout=10, retries=1)
                res.raise_for_status()
                zdec = re.search(r"zdec\s*=\s*['\"]([^'\"]+)", res.text or "")
                if zdec:
                    script = _b64decode(zdec.group(1))
                    nested = re.search(r"atob\(['\"]([^'\"]+)", script or "")
                    if nested:
                        target = _b64decode(nested.group(1))
                        if target and ".m3u8" in target.lower():
                            stream_headers = {
                                "User-Agent": BROWSER_UA,
                                "Referer": page_url or NYDUS_LIVE_URL,
                            }
                            return target, "&".join([f"{k}={quote_plus(v)}" for k, v in stream_headers.items()])
            except Exception:
                log("LiteTV resolve nydus fallback failed for %s:\n%s" % (nydus_id, format_exc()))

    if stream_type == "2ix2" and stream_url:
        headers = {
            "User-Agent": BROWSER_UA,
            "Referer": page_url or BASE_URL + "/",
        }
        return stream_url, "&".join([f"{k}={quote_plus(v)}" for k, v in headers.items()])

    if stream_url:
        headers = {
            "User-Agent": BROWSER_UA,
            "Referer": page_url,
        }
        return stream_url, "&".join([f"{k}={quote_plus(v)}" for k, v in headers.items()])

    return None, None


def get_lite_channels(groups=False):
    cache_ok, cached = get_cache("lite_channels")
    if cache_ok and isinstance(cached, list) and cached:
        all_channels = cached
    else:
        log("Loading LiteTV channels from Nydus and 2ix2")
        channels = []
        nydus_channels = _load_nydus_channels()
        if nydus_channels:
            channels += nydus_channels

        with ThreadPoolExecutor(max_workers=3) as executor:
            for cat in CATEGORIES:
                channels += _load_2ix2_category(cat)

        all_channels = channels
        set_cache("lite_channels", all_channels, 6)

    if groups is False or groups is None:
        selected_cats = _selected_categories()
        allowed_slugs = {c["slug"] for c in selected_cats}
        allowed_labels = {c["label"] for c in selected_cats}
    else:
        allowed_slugs = set()
        allowed_labels = set()
        for g in groups:
            for c in CATEGORIES:
                if g in (c["slug"], c["label"]):
                    allowed_slugs.add(c["slug"])
                    allowed_labels.add(c["label"])

    result = {}
    for ch in all_channels:
        if ch.get("group_slug") not in allowed_slugs and ch.get("group") not in allowed_labels:
            continue
        name = ch.get("name")
        if not name:
            continue
        if name not in result:
            result[name] = []

        exists = False
        for existing in result[name]:
            if isinstance(existing, dict):
                if existing.get("stream_url") and existing.get("stream_url") == ch.get("stream_url"):
                    exists = True
                    break
                if existing.get("nydus_id") and existing.get("nydus_id") == ch.get("nydus_id"):
                    exists = True
                    break
        if not exists:
            result[name].append(ch)

    return result
