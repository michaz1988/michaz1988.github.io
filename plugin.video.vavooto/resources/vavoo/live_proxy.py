# -*- coding: utf-8 -*-
from vavoo.utils import *
import urllib.parse
import base64
from http.server import HTTPServer, BaseHTTPRequestHandler
import socketserver
import threading

_proxy_server = None
_proxy_port = 19888
_proxy_lock = threading.Lock()
_httpx_client = None


def get_httpx():
    global _httpx_client
    if _httpx_client is None:
        try:
            import httpx
            _httpx_client = httpx.Client(http2=True, follow_redirects=True, timeout=12, verify=False)
        except Exception:
            log("httpx import failed: %s" % format_exc())
            _httpx_client = False
    return _httpx_client


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

            client = get_httpx()
            if not client:
                self.send_error(500, "HTTP client unavailable")
                return

            if parsed.path == "/nydus_live.m3u8":
                headers = {
                    "User-Agent": BROWSER_UA,
                    "Referer": ref or "https://nydus.org/",
                }
                r = client.get(target_url, headers=headers)
                lines = []
                for line in r.text.splitlines():
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
                headers = {
                    "User-Agent": BROWSER_UA,
                    "Referer": ref or "https://nydus.org/",
                }
                ext = params.get("ext", "csv")
                r = client.get(target_url, headers=headers)
                ts_data = decode_foobarx(r.text, ext, offset)
                self.send_response(200)
                self.send_header("Content-Type", "video/MP2T")
                self.send_header("Content-Length", str(len(ts_data)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(ts_data)

            elif parsed.path == "/vavoo_live.m3u8":
                headers = {
                    "User-Agent": "MediaHubMX/2",
                    "Accept-Encoding": "gzip",
                }
                r = client.get(target_url, headers=headers)
                lines = []
                for line in r.text.splitlines():
                    l = line.strip()
                    if l and not l.startswith("#"):
                        seg_target = urljoin(target_url, l)
                        seg_proxy = f"http://127.0.0.1:{_proxy_port}/vavoo_segment.ts?url={quote_plus(seg_target)}"
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

            elif parsed.path == "/vavoo_segment.ts":
                headers = {
                    "User-Agent": "MediaHubMX/2",
                    "Accept-Encoding": "identity",
                }
                r = client.get(target_url, headers=headers)
                self.send_response(200)
                self.send_header("Content-Type", "video/MP2T")
                self.send_header("Content-Length", str(len(r.content)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(r.content)

            else:
                self.send_error(404, "Not Found")
        except Exception:
            log("UnifiedLiveProxyHandler exception:\n%s" % format_exc())
            try:
                self.send_error(500, "Internal Error")
            except Exception:
                pass

    def log_message(self, format, *args):
        pass


class ThreadedProxyServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


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


def get_vavoo_proxy_url(m3u8_url):
    if not m3u8_url or not isinstance(m3u8_url, str):
        return m3u8_url
    port = ensure_proxy()
    return f"http://127.0.0.1:{port}/vavoo_live.m3u8?url={quote_plus(m3u8_url)}"


def get_nydus_proxy_url(m3u8_url, offset=22, origin=""):
    if not m3u8_url or not isinstance(m3u8_url, str):
        return m3u8_url
    port = ensure_proxy()
    ref_param = f"&ref={quote_plus(origin)}/" if origin else ""
    return f"http://127.0.0.1:{port}/nydus_live.m3u8?url={quote_plus(m3u8_url)}&offset={offset}{ref_param}"
