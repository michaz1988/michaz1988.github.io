# -*- coding: utf-8 -*-
from vavoo.utils import *
import html
import re

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
            
            # Map specific channels accurately
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


def resolve_lite_stream(channel_info):
    if not isinstance(channel_info, dict):
        return None, None
    
    stream_type = channel_info.get("stream_type")
    page_url = channel_info.get("page_url") or BASE_URL
    stream_url = channel_info.get("stream_url") or ""
    
    if stream_type == "2ix2" and stream_url:
        headers = {
            "User-Agent": BROWSER_UA,
            "Referer": page_url or BASE_URL + "/",
        }
        return stream_url, "&".join([f"{k}={quote_plus(v)}" for k, v in headers.items()])
    
    if stream_type == "nydus":
        nydus_id = channel_info.get("nydus_id")
        if not nydus_id:
            return None, None
        try:
            embed_url = NYDUS_EMBED_URL % quote(nydus_id, safe="")
            headers = {
                "User-Agent": BROWSER_UA,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Referer": page_url or NYDUS_LIVE_URL,
                "Connection": "close",
            }
            res = request("GET", embed_url, headers=headers, timeout=12, retries=1)
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
            log("LiteTV resolve nydus failed for %s:\n%s" % (nydus_id, format_exc()))
    
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
        log("Loading LiteTV channels from 2ix2 and Nydus")
        channels = []
        with ThreadPoolExecutor(max_workers=3) as executor:
            for cat in CATEGORIES:
                channels += _load_2ix2_category(cat)
        
        if not channels:
            nydus_fallback = _load_nydus_channels()
            if nydus_fallback:
                channels = nydus_fallback
        
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
