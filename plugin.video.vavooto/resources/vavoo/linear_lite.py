# -*- coding: utf-8 -*-
from vavoo.utils import *
import html
import re
from vavoo.live_proxy import get_httpx, get_nydus_proxy_url

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
    client = get_httpx()
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

        proxy_url = get_nydus_proxy_url(m3u8_url, offset=offset, origin=origin)
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

    result = {}
    for ch in all_channels:
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
