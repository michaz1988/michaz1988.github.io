# -*- coding: utf-8 -*-
from vavoo.utils import *
import html
import re
from http.server import HTTPServer, BaseHTTPRequestHandler
import socketserver
import threading

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
_httpx_client = None


def _get_httpx():
    global _httpx_client
    if _httpx_client is None:
        try:
            import httpx
            _httpx_client = httpx.Client(http2=True, follow_redirects=True, timeout=12)
        except Exception:
            log("httpx import failed: %s" % format_exc())
            _httpx_client = False
    return _httpx_client


def _decode_foobarx(raw_text, ext, offset):
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


class NydusProxyHandler(BaseHTTPRequestHandler):
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

            client = _get_httpx()
            if not client:
                self.send_error(500, "HTTP2 client unavailable")
                return

            headers = {
                "User-Agent": BROWSER_UA,
                "Referer": ref or "https://nydus.org/",
            }

            if parsed.path == "/nydus_live.m3u8":
                r = client.get(target_url, headers=headers)
                body = r.text
                lines = []
                for line in body.splitlines():
                    l = line.strip()
                    if l and not l.startswith("#"):
                        ext = l.split(".")[-1]
                        seg_target = urljoin(target_url, l)
                        seg_proxy = f"http://127.0.0.1:{_proxy_port}/nydus_segment.ts?url={quote_plus(seg_target)}&ext={ext}&offset={offset}&ref={quote_plus(ref)}"
                        lines.append(seg_proxy)
                    else:
                        lines.append(line)
                res_data = "\n".join(lines).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/vnd.apple.mpegurl")
                self.send_header("Content-Length", str(len(res_data)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(res_data)

            elif parsed.path == "/nydus_segment.ts":
                ext = params.get("ext", "csv")
                r = client.get(target_url, headers=headers)
                ts_data = _decode_foobarx(r.text, ext, offset)
                self.send_response(200)
                self.send_header("Content-Type", "video/MP2T")
                self.send_header("Content-Length", str(len(ts_data)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(ts_data)
            else:
                self.send_error(404, "Not Found")
        except Exception:
            log("NydusProxyHandler exception:\n%s" % format_exc())
            try:
                self.send_error(500, "Internal Error")
            except Exception:
                pass

    def log_message(self, format, *args):
        pass


class ThreadedNydusServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def _ensure_nydus_proxy():
    global _proxy_server, _proxy_port
    with _proxy_lock:
        if _proxy_server is not None:
            return _proxy_port
        for port in (19888, 19889, 19890, 19891, 19892):
            try:
                server = ThreadedNydusServer(("127.0.0.1", port), NydusProxyHandler)
                t = threading.Thread(target=server.serve_forever, daemon=True)
                t.start()
                _proxy_server = server
                _proxy_port = port
                log("LiteTV Nydus HTTP/2 Proxy gestartet auf Port %s" % port)
                return _proxy_port
            except Exception:
                pass
        log("LiteTV Nydus Proxy Server konnte auf keinem Port gestartet werden")
        return 19888


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
                name = filterout(clean_upper).strip()

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
                name = filterout(clean_upper).strip()

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
    client = _get_httpx()
    if not client:
        return None, None
    try:
        url1 = f"https://nydus.org/stream/embedplayer_hq.php?id={nydus_id}"
        h1 = {"User-Agent": BROWSER_UA, "Referer": f"https://nydus.org/stream/live/{nydus_id}/"}
        r1 = client.get(url1, headers=h1)
        zdec = re.search(r"zdec\s*=\s*['\"]([^'\"]+)", r1.text)
        if not zdec:
            return None, None
        s1 = base64.b64decode(zdec.group(1)).decode("utf-8", errors="ignore")
        m_atob = re.search(r"atob\(['\"]([^'\"]+)", s1)
        if not m_atob:
            return None, None
        iframe_url = base64.b64decode(m_atob.group(1)).decode("utf-8", errors="ignore")

        if ".m3u8" in iframe_url.lower():
            stream_headers = {"User-Agent": BROWSER_UA, "Referer": f"https://nydus.org/stream/live/{nydus_id}/"}
            return iframe_url, "&".join([f"{k}={quote_plus(v)}" for k, v in stream_headers.items()])

        h2 = dict(h1)
        h2["Referer"] = "https://nydus.org/"
        r2 = client.get(iframe_url, headers=h2)
        m_embed = re.search(r"const\s+EMBED\s*=\s*({[^;]+});", r2.text)
        if not m_embed:
            return None, None

        embed_obj = json.loads(m_embed.group(1))
        parsed = urlparse(iframe_url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        ch = embed_obj.get("channel")
        offset = embed_obj.get("hostLengthOffset", 22)
        m3u8_url = f"{origin}/conv/go/{ch}/chunks.m3u81a.doc"

        h3 = {"User-Agent": BROWSER_UA, "Referer": origin + "/"}
        r3 = client.get(m3u8_url, headers=h3)
        if "#EXTM3U" not in r3.text:
            return None, None

        port = _ensure_nydus_proxy()
        proxy_url = f"http://127.0.0.1:{port}/nydus_live.m3u8?url={quote_plus(m3u8_url)}&offset={offset}&ref={quote_plus(origin)}/"
        return proxy_url, ""
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
            # 1. Try Nydus HD resolution via HTTP/2 Proxy
            hd_url, hd_headers = _resolve_nydus_hd(nydus_id)
            if hd_url:
                return hd_url, hd_headers

            # 2. Try direct mirror HLS streams (e.g. Antik SK)
            for sfx in ("_mirror", "_mirror2"):
                mirror_url, mirror_headers = _resolve_nydus_hd(f"{nydus_id}{sfx}")
                if mirror_url:
                    return mirror_url, mirror_headers

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
