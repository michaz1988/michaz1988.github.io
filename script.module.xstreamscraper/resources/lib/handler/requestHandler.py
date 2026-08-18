# -*- coding: utf-8 -*-
# Python 3

import time
import xbmcgui, xbmcaddon
import re
import os
import hashlib
import json
import traceback
import ssl
import certifi
import socket
import zlib
import http.client

from resources.lib.config import cConfig
from resources.lib import common
from resources.lib.tools import logger, cCache
from xbmcvfs import translatePath

from urllib.parse import quote, urlencode, urlparse, quote_plus
from urllib.error import HTTPError, URLError
from urllib.request import HTTPHandler, HTTPSHandler, Request, HTTPCookieProcessor, build_opener, urlopen, HTTPRedirectHandler
from http.cookiejar import LWPCookieJar, Cookie
from http.client import HTTPException
from random import choice

class IPHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host, ip=None, port=None, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, context=None):
        self.context = context
        # If an IP is provided, connect to it rather than the resolved host.
        self.ip = ip
        self.actual_host = host  # original hostname for SNI and Host header
        super().__init__(host if not ip else ip, port, timeout=timeout, context=context)

    def connect(self):
        # Create a socket connection to the provided IP (if any)
        if self.ip:
            self.sock = self._create_connection((self.ip, self.port), self.timeout)
            #if self._tunnel_host:
            #    self._tunnel()
            # Wrap the socket with our SSL context using the actual host for SNI.
            self.sock = self.context.wrap_socket(self.sock, server_hostname=self.actual_host)
        else:
            super().connect()

class CustomSecureHTTPSHandler(HTTPSHandler):
    def __init__(self, ip=None):
        # Create an SSL context with certifi's CA bundle.
        context = ssl.create_default_context(cafile=certifi.where())
        # If an IP is provided, disable hostname checking (since we'll verify using SNI later).
        context.check_hostname = False if ip else True
        context.verify_mode = ssl.CERT_REQUIRED
        self.ip = ip
        self.context = context
        super().__init__(context=context)

    def https_open(self, req):
        # Extract the hostname from the request URL.
        parsed = urlparse(req.full_url)
        host = parsed.hostname
        # Define a connection factory that returns an IPHTTPSConnection
        def connection_factory(*args, **kwargs):
            return IPHTTPSConnection(host, ip=self.ip, timeout=req.timeout, context=self.context)
        return self.do_open(connection_factory, req)


class RedirectFilter(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, hdrs, newurl):
        #if cConfig().getSetting('bypassDNSlock', 'false') != 'true':
            #if 'notice.cuii' in newurl:
                #xbmcgui.Dialog().ok(cConfig().getLocalizedString(30265), cConfig().getLocalizedString(30260) + '\n' + cConfig().getLocalizedString(30261))
                #return None
        return HTTPRedirectHandler.redirect_request(self, req, fp, code, msg, hdrs, newurl)

class cRequestHandler:
    # useful for e.g. tmdb request where multiple requests are made within a loop
    persistent_openers = {}

    @staticmethod
    def RandomUA():
        #Random User Agents aktualisiert 08.06.2025
        FF_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:139.0) Gecko/20100101 Firefox/139.0'
        OPERA_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36 OPR/119.0.0.0'
        ANDROID_USER_AGENT = 'Mozilla/5.0 (Linux; Android 15; SM-S931U Build/AP3A.240905.015.A2; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/132.0.6834.163 Mobile Safari/537.36'
        EDGE_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/134.0.0.0'
        CHROME_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36'
        SAFARI_USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.4 Safari/605.1.15'

        _User_Agents = [FF_USER_AGENT, OPERA_USER_AGENT, EDGE_USER_AGENT, CHROME_USER_AGENT, SAFARI_USER_AGENT]
        return choice(_User_Agents)

    def __init__(self, sUrl, caching=True, ignoreErrors=False, method='GET', data=None, compression=True, jspost=False, ssl_verify=False, bypass_dns=False):
        self._sUrl = self.__cleanupUrl(sUrl)
        self._sRealUrl = ''
        self._USER_AGENT = self.RandomUA()
        self._aParameters = {}
        self._headerEntries = {}
        self._profilePath = common.profilePath
        self._cachePath = ''
        self._cookiePath = ''
        self._Status = ''
        self._sResponseHeader = ''
        self._ssl_verify = ssl_verify
        self._bypass_dns = bypass_dns
        self.ignoreDiscard(False)
        self.ignoreExpired(False)
        self.caching = caching
        self.method = method
        self.data = data
        self.ignoreErrors = ignoreErrors
        self.compression = compression
        self.jspost = jspost
        self.cacheTime = int(xbmcaddon.Addon().getSetting('cacheTime') or 600)
        self.requestTimeout = int(xbmcaddon.Addon().getSetting('requestTimeout') or 10)
        self.bypassDNSlock = True
        self.removeBreakLines(True)
        self.removeNewLines(True)
        self.__setDefaultHeader()
        self.__setCachePath()
        self.__setCookiePath()
        self.isMemoryCacheActive = False
        if self.isMemoryCacheActive:
            self._memCache = cCache()
        
        socket.setdefaulttimeout(self.requestTimeout)

    def getStatus(self):
        return self._Status

    def removeNewLines(self, bRemoveNewLines):
        self.__bRemoveNewLines = bRemoveNewLines

    def removeBreakLines(self, bRemoveBreakLines):
        self.__bRemoveBreakLines = bRemoveBreakLines

    def addHeaderEntry(self, sHeaderKey, sHeaderValue):
        self._headerEntries[sHeaderKey] = sHeaderValue

    def getHeaderEntry(self, sHeaderKey):
        if sHeaderKey in self._headerEntries:
            return self._headerEntries[sHeaderKey]

    def addParameters(self, key, value, Quote=False):
        self._aParameters[key] = value if not Quote else quote(str(value))

    def getResponseHeader(self):
        return self._sResponseHeader

    def getRealUrl(self):
        return self._sRealUrl

    def getRequestUri(self):
        return self._sUrl + '?' + urlencode(self._aParameters)

    def __setDefaultHeader(self):
        self.addHeaderEntry('User-Agent', self._USER_AGENT)
        self.addHeaderEntry('Accept-Language', 'de,en-US;q=0.7,en;q=0.3')
        self.addHeaderEntry('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8')
        if self.compression:
            self.addHeaderEntry('Accept-Encoding', 'gzip, deflate')
        self.addHeaderEntry('Connection', 'keep-alive')
        self.addHeaderEntry('Keep-Alive', 'timeout=5')

    @staticmethod
    def __getDefaultHandler(ssl_verify, ip=None):
        if ip:
            return [CustomSecureHTTPSHandler(ip=ip)]    
        elif ssl_verify:
            return [CustomSecureHTTPSHandler()]
        else:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            return [HTTPSHandler(context=ssl_context)]

    @staticmethod
    def __cleanupUrl(url):
        #p = urlparse(url)
        #if p.query:
        #    query = quote_plus(p.query).replace('%3D', '=').replace('%26', '&')
        #    p = p._replace(query=p.query.replace(p.query, query))
        #else:
        #    path = quote_plus(p.path).replace('%2F', '/').replace('%26', '&').replace('%3D', '=')
        #    p = p._replace(path=p.path.replace(p.path, path))
        #return p.geturl()
        return url
    
    def request(self):
        if self.caching and self.cacheTime > 0  and self.method == 'GET' and self.data is None:
            if self.isMemoryCacheActive:
                sContent = self.__readVolatileCache(self.getRequestUri(), self.cacheTime)
            else:
                sContent = self.__readPersistentCache(self.getRequestUri())
            if sContent:
                self._Status = '200'
                return sContent
        else:
            logger.info('-> [requestHandler]: read html for %s' % self.getRequestUri())

        # nur ausführen wenn der übergabeparameter und die konfiguration passen
        if self._bypass_dns and self.bypassDNSlock:
            ### DNS lock bypass
            ip_override = self.__doh_request(self._sUrl)
            ### DNS lock bypass
        else:
            ip_override = None

        cookieJar = LWPCookieJar(filename=self._cookiePath)
        try:
            cookieJar.load(ignore_discard=self.__bIgnoreDiscard, ignore_expires=self.__bIgnoreExpired)
        except Exception as e:
            logger.debug(e)
        
        domain = urlparse(self._sUrl).netloc
        if domain in cRequestHandler.persistent_openers:
            opener = cRequestHandler.persistent_openers[domain]
        else:
            handlers = self.__getDefaultHandler(self._ssl_verify, ip_override)        
            handlers += [HTTPHandler(), HTTPCookieProcessor(cookiejar=cookieJar), RedirectFilter()]
            opener = build_opener(*handlers)
            cRequestHandler.persistent_openers[domain] = opener

        # Prepare parameters for GET/POST
        if self.method == 'POST':
            if self.data is not None:
                if isinstance(self.data, dict):
                    # Default: form data
                    sParameters = urlencode(self.data).encode()
                elif isinstance(self.data, str):
                    sParameters = self.data.encode()
                else:
                    sParameters = self.data
            else:
                sParameters = None
        else:
            sParameters = json.dumps(self._aParameters).encode() if self.jspost else urlencode(self._aParameters, True).encode()
            if len(sParameters) == 0:
                sParameters = None
        
        oRequest = Request(self._sUrl, sParameters if sParameters and len(sParameters) > 0 else None)

        for key, value in self._headerEntries.items():
            oRequest.add_header(key, value)
        
        if self.method == 'POST' and 'Content-Type' not in self._headerEntries:
            oRequest.add_header('Content-Type', 'application/x-www-form-urlencoded')
        elif self.jspost:
            oRequest.add_header('Content-Type', 'application/json')
        
        cookieJar.add_cookie_header(oRequest)
        
        try:
            oResponse = opener.open(oRequest)
        except HTTPError as e:
            if e.code >= 400:
                self._Status = str(e.code)
                data = e.fp.read()
                if 'DDOS-GUARD' in str(data):
                    opener = build_opener(HTTPCookieProcessor(cookieJar))
                    opener.addheaders = [('User-agent', self._USER_AGENT), ('Referer', self._sUrl)]
                    response = opener.open('https://check.ddos-guard.net/check.js')
                    content = response.read().decode('utf-8', 'replace')
                    url2 = re.findall("Image.*?'([^']+)'; new", content)
                    url3 = urlparse(self._sUrl)
                    url3 = '%s://%s/%s' % (url3.scheme, url3.netloc, url2[0])
                    opener = build_opener(HTTPCookieProcessor(cookieJar))
                    opener.addheaders = [('User-agent', self._USER_AGENT), ('Referer', self._sUrl)]
                    opener.open(url3).read()
                    opener = build_opener(HTTPCookieProcessor(cookieJar))
                    opener.addheaders = [('User-agent', self._USER_AGENT), ('Referer', self._sUrl)]
                    oResponse = opener.open(self._sUrl, sParameters if len(sParameters) > 0 else None)
                    if not oResponse:
                        logger.error(' -> [requestHandler]: Failed DDOS-GUARD active: ' + self._sUrl)
                        return 'DDOS GUARD SCHUTZ'
                elif 'cloudflare' in str(e.headers):
                    if not self.ignoreErrors:
                        value = ('!!! CLOUDFLARE-SCHUTZ AKTIV !!! Weitere Informationen: ' + str(e.__class__.__name__) + ' : ' + str(e), str(traceback.format_exc().splitlines()[-3].split('addons')[-1]))
                        #xbmcgui.Dialog().ok(cConfig().getLocalizedString(30166), str(value))  # Error
                    logger.error(' -> [requestHandler]: Failed Cloudflare active: ' + self._sUrl)
                    return 'CLOUDFLARE-SCHUTZ AKTIV' # Meldung geht als "e.doc" in die exception nach default.py
                else:
                    #if not self.ignoreErrors:
                        #xbmcgui.Dialog().ok('xStream', cConfig().getLocalizedString(30259) + ' {0} {1}'.format(self._sUrl, str(e)))
                    logger.error(' -> [requestHandler]: HTTPError ' + str(e) + ' Url: ' + self._sUrl)
                    return 'SEITE NICHT ERREICHBAR'
            else:
                #if not self.ignoreErrors:
                    #xbmcgui.Dialog().ok('xStream', cConfig().getLocalizedString(30259) + ' {0} {1}'.format(self._sUrl, str(e)))
                logger.error(' -> [requestHandler]: HTTPError ' + str(e) + ' Url: ' + self._sUrl)
                return 'SEITE NICHT ERREICHBAR'
        except URLError as e:
            #if not self.ignoreErrors:
                #xbmcgui.Dialog().ok('xStream', str(e.reason))
            logger.error(' -> [requestHandler]: URLError ' + str(e.reason) + ' Url: ' + self._sUrl)
            return 'URL FEHLER'
        except HTTPException as e:
            #if not self.ignoreErrors:
                #xbmcgui.Dialog().ok('xStream', str(e))
            logger.error(' -> [requestHandler]: HTTPException ' + str(e) + ' Url: ' + self._sUrl)
            return 'TIMEOUT'

        self._sResponseHeader = oResponse.info()
        
        content_encoding = self._sResponseHeader.get('Content-Encoding', '').lower()
        if content_encoding:
            raw_content = oResponse.read()
            if content_encoding == 'gzip':
                decompressed = zlib.decompress(raw_content, wbits=zlib.MAX_WBITS | 16)
            elif content_encoding == 'deflate':
                decompressed = zlib.decompress(raw_content, wbits=-zlib.MAX_WBITS)
            else:
                decompressed = raw_content
            sContent = decompressed.decode('utf-8', 'replace')
        else:
            sContent = oResponse.read().decode('utf-8', 'replace')

        if 'lazingfast' in sContent:
            bf = cBF().resolve(self._sUrl, sContent, cookieJar, self._USER_AGENT, sParameters)
            if bf:
                sContent = bf
            else:
                logger.error(' -> [requestHandler]: Failed Blazingfast active: ' + self._sUrl)

        try:
            cookieJar.save(ignore_discard=self.__bIgnoreDiscard, ignore_expires=self.__bIgnoreExpired)
        except Exception as e:
            logger.error(' -> [requestHandler]: Failed save cookie: %s' % e)

        self._sRealUrl = oResponse.geturl()
        self._Status = oResponse.getcode() if self._sUrl == self._sRealUrl else '301'

        if self.__bRemoveNewLines:
            sContent = sContent.replace('\n', '').replace('\r\t', '')
        if self.__bRemoveBreakLines:
            sContent = sContent.replace('&nbsp;', '')

        if self.caching and self.cacheTime > 0 and self.method == 'GET' and self.data is None:
            if self.isMemoryCacheActive:
                self.__writeVolatileCache(self.getRequestUri(), sContent)
            else:
                self.__writePersistentCache(self.getRequestUri(), sContent)

        return sContent

    def __setCookiePath(self):
        cookieFile = os.path.join(self._profilePath, 'cookies')
        if not os.path.exists(cookieFile):
            os.makedirs(cookieFile)
        if 'dummy' not in self._sUrl:
            cookieFile = os.path.join(cookieFile, urlparse(self._sUrl).netloc.replace('.', '_') + '.txt')
            if not os.path.exists(cookieFile):
                open(cookieFile, 'w').close()
            self._cookiePath = cookieFile

    def getCookie(self, sCookieName, sDomain=''):
        cookieJar = LWPCookieJar()
        try:
            cookieJar.load(self._cookiePath, self.__bIgnoreDiscard, self.__bIgnoreExpired)
        except Exception as e:
            logger.error(e)
        for entry in cookieJar:
            if entry.name == sCookieName:
                if sDomain == '':
                    return entry
                elif entry.domain == sDomain:
                    return entry
        return False

    def setCookie(self, oCookie):
        cookieJar = LWPCookieJar()
        try:
            cookieJar.load(self._cookiePath, self.__bIgnoreDiscard, self.__bIgnoreExpired)
            cookieJar.set_cookie(oCookie)
            cookieJar.save(self._cookiePath, self.__bIgnoreDiscard, self.__bIgnoreExpired)
        except Exception as e:
            logger.error(e)

    def ignoreDiscard(self, bIgnoreDiscard):
        self.__bIgnoreDiscard = bIgnoreDiscard

    def ignoreExpired(self, bIgnoreExpired):
        self.__bIgnoreExpired = bIgnoreExpired

    def __doh_request(self, url, doh_server="https://cloudflare-dns.com/dns-query"):
        # Parse the URL
        parsed_url = urlparse(url)
        hostname = parsed_url.hostname
        key = 'doh_request' + hostname

        if self.isMemoryCacheActive and self.cacheTime > 0:
            ip_address = self.__readVolatileCache(key, self.cacheTime)
            if ip_address:
                return ip_address
        
        params = urlencode({"name": hostname, "type": "A"})
        doh_url = f"{doh_server}?{params}"
        req = Request(doh_url)
        req.add_header("Accept", "application/dns-json")

        try:
            response = urlopen(req, timeout=5)
            response_text = response.read().decode("utf-8", "replace")
            dns_response = json.loads(response_text)
            if "Answer" not in dns_response:
                raise Exception("Invalid DNS response")
            ip_address = dns_response["Answer"][0]["data"]
            if self.isMemoryCacheActive and self.cacheTime > 0:
                self.__writeVolatileCache(key, ip_address)

            return ip_address
        except Exception as e:
            logger.error(' -> [requestHandler]: DNS query failed: %s' % e)
            return None

    def __setCachePath(self):
        cache = os.path.join(self._profilePath, 'htmlcache')
        if not os.path.exists(cache):
            os.makedirs(cache)
        self._cachePath = cache

    def __readPersistentCache(self, url):
        h = hashlib.md5(url.encode('utf8')).hexdigest()
        cacheFile = os.path.join(self._cachePath, h)
        fileAge = self.getFileAge(cacheFile)
        if 0 < fileAge < self.cacheTime:
            try:
                with open(cacheFile, 'rb') as f:
                        content = f.read().decode('utf8')
            except Exception:
                logger.error(' -> [requestHandler]: Could not read Cache')
            if content:
                logger.info(' -> [requestHandler]: read html for %s from cache' % url)
                return content
        return None

    def __writePersistentCache(self, url, content):
        try:
            h = hashlib.md5(url.encode('utf8')).hexdigest()
            with open(os.path.join(self._cachePath, h), 'wb') as f:
                f.write(content.encode('utf8'))
        except Exception:
            logger.error(' -> [requestHandler]: Could not write Cache')

    def __writeVolatileCache(self, url, content):
        self._memCache.set(hashlib.md5(url.encode('utf8')).hexdigest(), content)

    def __readVolatileCache(self, url, cache_time):
        entry = self._memCache.get(hashlib.md5(url.encode('utf8')).hexdigest(), cache_time)
        if entry:
            logger.info('-> [requestHandler]: read html for %s from cache' % url)
        return entry

    @staticmethod
    def getFileAge(cacheFile):
        try:
            return time.time() - os.stat(cacheFile).st_mtime
        except Exception:
            return 0

    def clearCache(self):
        # clear volatile cache
        if self.isMemoryCacheActive:
            self._memCache.clear()
        cRequestHandler.persistent_openers.clear()
        
        # clear persistent cache
        files = os.listdir(self._cachePath)
        for file in files:
            os.remove(os.path.join(self._cachePath, file))
            #xbmcgui.Dialog().notification('xStream', cConfig().getLocalizedString(30405), xbmcgui.NOTIFICATION_INFO, 100, False)


class cBF:
    def resolve(self, url, html, cookie_jar, user_agent, sParameters):
        page = urlparse(url).scheme + '://' + urlparse(url).netloc
        j = re.compile('<script[^>]src="([^"]+)').findall(html)
        if j:
            opener = build_opener(HTTPCookieProcessor(cookie_jar))
            opener.addheaders = [('User-agent', user_agent), ('Referer', url)]
            opener.open(page + j[0])
        a = re.compile(r'xhr\.open\("GET","([^,]+)",').findall(html)
        if a:
            import random
            aespage = page + a[0].replace('" + ww +"', str(random.randint(700, 1500)))
            opener = build_opener(HTTPCookieProcessor(cookie_jar))
            opener.addheaders = [('User-agent', user_agent), ('Referer', url)]
            html = opener.open(aespage).read().decode('utf-8', 'replace')
            cval = self.aes_decode(html)
            cdata = re.compile('cookie="([^="]+).*?domain[^>]=([^;]+)').findall(html)
            if cval and cdata:
                c = Cookie(version=0, name=cdata[0][0], value=cval, port=None, port_specified=False, domain=cdata[0][1], domain_specified=True, domain_initial_dot=False, path="/", path_specified=True, secure=False, expires=time.time() + 21600, discard=False, comment=None, comment_url=None, rest={})
                cookie_jar.set_cookie(c)
                opener = build_opener(HTTPCookieProcessor(cookie_jar))
                opener.addheaders = [('User-agent', user_agent), ('Referer', url)]
                return opener.open(url, sParameters if len(sParameters) > 0 else None).read().decode('utf-8', 'replace')

    @staticmethod
    def aes_decode(html):
        try:
            import pyaes
            keys = re.compile(r'toNumbers\("([^"]+)"').findall(html)
            if keys:
                from binascii import hexlify, unhexlify
                msg = unhexlify(keys[2])
                key = unhexlify(keys[0])
                iv = unhexlify(keys[1])
                decrypter = pyaes.Decrypter(pyaes.AESModeOfOperationCBC(key, iv))
                plain_text = decrypter.feed(msg)
                plain_text += decrypter.feed()
                return hexlify(plain_text).decode()
        except Exception as e:
            logger.error(e)
