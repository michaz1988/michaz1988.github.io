# -*- coding: utf-8 -*-
from Cryptodome.Cipher import AES
from Cryptodome.Util.Padding import unpad
import xbmc, xbmcaddon, xbmcgui, os, sys, hashlib, re, time, json, six, xbmcvfs, requests, base64, zlib, types, random, pyaes
from datetime import datetime,date,timedelta
from resources.lib import common, settings
from six.moves.urllib.parse import quote, unquote, quote_plus, unquote_plus, urlparse, urlencode
from six.moves.html_entities import name2codepoint
from difflib import SequenceMatcher
from functools import lru_cache
from os import path, chdir

addon = xbmcaddon.Addon()
addonInfo = addon.getAddonInfo
addonID = addonInfo("id")
addonName = addonInfo("name")
get_setting = addon.getSetting
set_setting = addon.setSetting
api_key="86dd18b04874d9c94afadde7993d94e3"
tmdburl = "https://api.themoviedb.org/3/"
tmdbimg = "https://image.tmdb.org/t/p/%s%s"
translatePath = xbmcvfs.translatePath

class validater():
	pass

def translate_path(*args):
	return translatePath(os.path.join(*args))

addonPath = common.addonPath
profilePath = common.profilePath
settingsxml = translate_path(addonInfo("path"), "resources", "settings.xml")

if not os.path.exists(profilePath):
	os.makedirs(profilePath)

def getAuthSignature():
	_headers={"user-agent": "okhttp/4.11.0", "accept": "application/json", "content-type": "application/json; charset=utf-8", "content-length": "1106", "accept-encoding": "gzip"}
	_data = {"token":"8Us2TfjeOFrzqFFTEjL3E5KfdAWGa5PV3wQe60uK4BmzlkJRMYFu0ufaM_eeDXKS2U04XUuhbDTgGRJrJARUwzDyCcRToXhW5AcDekfFMfwNUjuieeQ1uzeDB9YWyBL2cn5Al3L3gTnF8Vk1t7rPwkBob0swvxA","reason":"player.enter","locale":"de","theme":"dark","metadata":{"device":{"type":"Handset","brand":"google","model":"Nexus 5","name":"21081111RG","uniqueId":"d10e5d99ab665233"},"os":{"name":"android","version":"7.1.2","abis":["arm64-v8a","armeabi-v7a","armeabi"],"host":"android"},"app":{"platform":"android","version":"3.0.2","buildId":"288045000","engine":"jsc","signatures":["09f4e07040149486e541a1cb34000b6e12527265252fa2178dfe2bd1af6b815a"],"installer":"com.android.secex"},"version":{"package":"tv.vavoo.app","binary":"3.0.2","js":"3.1.4"}},"appFocusTime":27229,"playerActive":True,"playDuration":0,"devMode":False,"hasAddon":True,"castConnected":False,"package":"tv.vavoo.app","version":"3.1.4","process":"app","firstAppStart":1728674705639,"lastAppStart":1728674705639,"ipLocation":"","adblockEnabled":True,"proxy":{"supported":["ss"],"engine":"ss","enabled":False,"autoServer":True,"id":"ca-bhs"},"iap":{"supported":False}}
	req = requests.post('https://www.vavoo.tv/api/app/ping', json=_data, headers=_headers).json()
	return req.get("addonSig")

def ok(heading, line1, line2="", line3=""):
	return xbmcgui.Dialog().ok(heading, line1+"\n"+line2+"\n"+line3)

def md5(fname):
    hash_md5 = hashlib.md5()
    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def repair(force=False):
	new_xml = [
		'<settings>',
		' <category label="Einrichten">',
		'  <setting label="TMDB-HELPER einrichten" type="action" action="RunPlugin(plugin://script.module.xstreamscraper/?action=true)"/>',
		' </category>',
		' <category label="VIDEO">',
		'  <setting default="1" id="stream_select" label="Stream Auswahl" type="enum" values="Hoster|Automatisch"/>',
		'  <setting default="true" id="auto_try_next_stream" type="bool" subsetting="true" visible="eq(-1,0)" label="Automatisch nächsten ähnlichen Stream versuchen"/>',
		' </category>',
		' <category label="VAVOO">',
		'  <setting default="true" id="vavoo" label="Vavoo" type="bool"/>',
		' </category>',
		' <category label="Scraper">']
	firststart = False
	profilepath = translate_path(addonInfo('profile'))
	if not os.path.exists(profilepath): os.makedirs(profilepath)
	xstreampluginDB = translate_path(profilePath, "pluginDB")
	scraperpluginDB = translate_path(profilepath, "pluginDB")
	if not os.path.exists(scraperpluginDB) or not os.path.exists(settingsxml):
		firststart = True
		with open(scraperpluginDB, "w") as k: json.dump({}, k)
	if md5(scraperpluginDB) != md5(xstreampluginDB):
		with open(xstreampluginDB) as k: plugins = json.load(k)
		for key , value in plugins.items():
			if not "vod_" in value.get("identifier"): new_xml.append('  <setting default="%s" id="%s" label="%s" type="bool"/>' % (value.get("globalsearch"), value.get("identifier"), value.get("name")))
		new_xml.append(' </category>')
		new_xml.append('</settings>')
		new_xml = six.ensure_text('\n'.join(new_xml))
		with open(settingsxml, 'w', encoding='utf-8') as f: f.write(new_xml)
	if firststart or force:
		xbmcaddon.Addon("plugin.video.themoviedb.helper").setSetting("players_url", "https://michaz1988.github.io/players.zip")
		xbmc.executebuiltin('RunScript(plugin.video.themoviedb.helper, update_players)')
		xbmcaddon.Addon("plugin.video.themoviedb.helper").setSetting("default_player_movies", "xstream.json play_movie")
		xbmcaddon.Addon("plugin.video.themoviedb.helper").setSetting("default_player_episodes", "xstream.json play_episode")

def handle():
	return int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else -1

def selectDialog(list, heading=None, multiselect = False):
	if heading == "default" or heading is None:
		heading = xbmcaddon.Addon().getAddonInfo("name")
	if multiselect: return xbmcgui.Dialog().multiselect(str(heading), list)
	return xbmcgui.Dialog().select(str(heading), list)

def yesno(heading, line1, line2="", line3="", nolabel="", yeslabel=""):
	return xbmcgui.Dialog().yesno(heading, line1+"\n"+line2+"\n"+line3, nolabel, yeslabel)

def get_data(params):
	from resources.lib.handler.requestHandler import cRequestHandler
	query = params.get("query")
	p=int(params.get("p",1))
	if query:
		_id = params.get("id").replace("series","tv")
		url = "%ssearch/%s?api_key=%s&language=de&query=%s&page=%s"%(tmdburl,_id, api_key,quote(query), p)
		oRequest = cRequestHandler(url)
		oRequest.cacheTime = 60 * 60 * 24 * 14
		return json.loads(oRequest.request())
	today=datetime.now().date()
	t, i=params.get("id").replace("series","tv").split(".")
	s=int(params.get("s", 0))
	e=int(params.get("e", 0))
	urlparams = {"api_key": api_key,"language": "de", "region": "DE"}
	if i not in ["now_playing","top_rated","popular","on_tv","trending_day","trending_week"]:
		urlparams.update({"include_video_language": "en,null,de", "include_image_language": "en,null,de"})
	release="release_date.lte" if t=="movie" else "air_date.lte"
	count = 300 if t == "movie" else 150
	if i =="trending_day":
		urlparams.update({"page":p})
		url = "%strending/%s/day" %(tmdburl, t)
	elif i == "trending_week":
		urlparams.update({"page":p})
		url = "%strending/%s/week" %(tmdburl, t)
	elif i =="now_playing":
		url = "%sdiscover/%s" % (tmdburl, t)
		urlparams.update({"sort_by":"popularity.desc","include_video":"true","release_date.gte":today-timedelta(days=41),"release_date.lte":today+timedelta(days=1),"with_release_type":3,"page":p})
	elif i == "popular":
		url = "%sdiscover/%s" % (tmdburl, t)
		urlparams.update({"sort_by":"popularity.desc",release:today,"page":p})
	elif i == "top_rated":
		url = "%sdiscover/%s" % (tmdburl, t)
		urlparams.update({"sort_by":"vote_average.desc",release:today,"vote_count.gte":count,"page":p})
	elif i == "on_tv":
		url = "%sdiscover/%s" % (tmdburl, t)
		urlparams.update({"sort_by":"popularity.desc","air_date.gte":today,"air_date.lte":today+timedelta(days=64),"page":p})
	elif t == "movie":
		url = "%smovie/%s" % (tmdburl, i)
		urlparams.update({"append_to_response":"credits,external_ids,videos,keywords,release_dates,alternative_titles"})
	elif (e != 0) or (s != 0):
		url = "%stv/%s/season/%s" % (tmdburl, i, s)
		urlparams.update({"append_to_response":"credits,external_ids,videos,alternative_titles"})
	else:
		url = "%stv/%s" % (tmdburl, i)
		urlparams.update({"append_to_response":"credits,external_ids,videos,keywords,content_ratings,alternative_titles"})
	url = "%s?%s" % (url, urlencode(urlparams))
	oRequest = cRequestHandler(url)
	oRequest.cacheTime = 60 * 60 * 24 * 14
	return json.loads(oRequest.request())

def getIcon(name, original=False):
	if not name: return "DefaultFolder.png"
	if "/" in name: return tmdbimg % ("original" if original else "w342", name)
	icon = translate_path(addonPath, "resources", "art", "%s.png"%name)
	if os.path.exists(icon): return icon
	return "DefaultFolder.png"

def convertPluginParams(params):
	p = []
	for key, value in list(params.items()):
		p.append(urlencode({key: value}))
	return ('&').join(sorted(p))

def getPluginUrl(params):
	return "%s?%s" % (sys.argv[0], convertPluginParams(params))

def genrelist(params):
	url ="%sgenre/%s/list?api_key=%s&language=de"%(tmdburl, "movie" if "movie" in params["id"] else "tv", api_key)
	oRequest = cRequestHandler(url)
	oRequest.cacheTime = 60 * 60 * 24 * 14
	return json.loads(oRequest.request())["genres"]

def platform(): # Aufgeführte Plattformen zum Anzeigen der Systemplattform
	if xbmc.getCondVisibility('system.platform.android'):
		return 'Android'
	elif xbmc.getCondVisibility('system.platform.linux'):
		return 'Linux'
	elif xbmc.getCondVisibility('system.platform.linux.Raspberrypi'):
		return 'Linux/RPi'
	elif xbmc.getCondVisibility('system.platform.windows'):
		return 'Windows'
	elif xbmc.getCondVisibility('system.platform.uwp'):
		return 'Windows UWP'	  
	elif xbmc.getCondVisibility('system.platform.osx'):
		return 'OSX'
	elif xbmc.getCondVisibility('system.platform.atv2'):
		return 'ATV2'
	elif xbmc.getCondVisibility('system.platform.ios'):
		return 'iOS'
	elif xbmc.getCondVisibility('system.platform.darwin'):
		return 'iOS'
	elif xbmc.getCondVisibility('system.platform.xbox'):
		return 'XBOX'
	elif xbmc.getCondVisibility('System.HasAddon(service.coreelec.settings)'):
		return "CoreElec"
	elif xbmc.getCondVisibility('System.HasAddon(service.libreelec.settings)'):
		return "LibreElec"
	elif xbmc.getCondVisibility('System.HasAddon(service.osmc.settings)'):
		return "OSMC"		
		

def pluginInfo(): # Plugin Support Informationen
	pass

 
def textBox(heading, announce):
	class TextBox():

		def __init__(self, *args, **kwargs):
			self.WINDOW = 10147
			self.CONTROL_LABEL = 1
			self.CONTROL_TEXTBOX = 5
			xbmc.executebuiltin("ActivateWindow(%d)" % (self.WINDOW, ))
			self.win = xbmcgui.Window(self.WINDOW)
			xbmc.sleep(500)
			self.setControls()

		def setControls(self):
			self.win.getControl(self.CONTROL_LABEL).setLabel(heading)
			try:
				f = open(announce)
				text = f.read()
			except:
				text = announce
			self.win.getControl(self.CONTROL_TEXTBOX).setText(str(text))
			return

	TextBox()
	while xbmc.getCondVisibility('Window.IsVisible(10147)'):
		xbmc.sleep(500)
 
 
class cParser:
    @staticmethod
    def _get_compiled_pattern(pattern, flags=0):
        return re.compile(pattern, flags)
    
    @staticmethod
    def _replaceSpecialCharacters(s):
        try:
            # Umlaute Unicode konvertieren
            for t in (('\\/', '/'), ('&amp;', '&'), ('\\u00c4', 'Ä'), ('\\u00e4', 'ä'),
                ('\\u00d6', 'Ö'), ('\\u00f6', 'ö'), ('\\u00dc', 'Ü'), ('\\u00fc', 'ü'),
                ('\\u00df', 'ß'), ('\\u2013', '-'), ('\\u00b2', '²'), ('\\u00b3', '³'),
                ('\\u00e9', 'é'), ('\\u2018', '‘'), ('\\u201e', '„'), ('\\u201c', '“'),
                ('\\u00c9', 'É'), ('\\u2026', '...'), ('\\u202f', 'h'), ('\\u2019', '’'),
                ('\\u0308', '̈'), ('\\u00e8', 'è'), ('#038;', ''), ('\\u00f8', 'ø'),
                ('／', '/'), ('\\u00e1', 'á'), ('&#8211;', '-'), ('&#8220;', '“'), ('&#8222;', '„'),
                ('&#8217;', '’'), ('&#8230;', '…'), ('\\u00bc', '¼'), ('\\u00bd', '½'), ('\\u00be', '¾'),
                ('\\u2153', '⅓'), ('\\u002A', '*')):
                s = s.replace(*t)

            # Umlaute HTML konvertieren
            for h in (('\\/', '/'), ('&#x26;', '&'), ('&#039;', "'"), ("&#39;", "'"),
                ('&#xC4;', 'Ä'), ('&#xE4;', 'ä'), ('&#xD6;', 'Ö'), ('&#xF6;', 'ö'),
                ('&#xDC;', 'Ü'), ('&#xFC;', 'ü'), ('&#xDF;', 'ß') , ('&#xB2;', '²'),
                ('&#xDC;', '³'), ('&#xBC;', '¼'), ('&#xBD;', '½'), ('&#xBE;', '¾'),
                ('&#8531;', '⅓'), ('&#8727;', '*')):
                s = s.replace(*h)
        except:
            pass
        return s

    @staticmethod
    def parseSingleResult(sHtmlContent, pattern, ignoreCase=False):
        if sHtmlContent:
            flags = re.S | re.M
            if ignoreCase:
                flags |= re.I

            matches = cParser._get_compiled_pattern(pattern, flags).search(sHtmlContent)
            
            if matches:
                # Check if there's at least one capturing group
                if matches.lastindex is not None and matches.lastindex >= 1:
                    return True, cParser._replaceSpecialCharacters(matches.group(1))
                else:
                    # fallback to the entire match if no group was captured
                    return True, cParser._replaceSpecialCharacters(matches.group(0))
        return False, None
    
    @staticmethod
    def parse(sHtmlContent, pattern, iMinFoundValue=1, ignoreCase=False):
        if sHtmlContent:
            flags = re.DOTALL
            if ignoreCase:
                flags |= re.I

            aMatches = cParser._get_compiled_pattern(pattern, flags).findall(sHtmlContent)
            
            if len(aMatches) >= iMinFoundValue:
                # handle both single strings and tuples of matches
                if isinstance(aMatches[0], tuple):
                    # Process each string in tuple
                    aMatches = [tuple(cParser._replaceSpecialCharacters(x) if isinstance(x, str) and x is not None else '' for x in match) for match in aMatches]
                else:
                    # Process single strings
                    aMatches = [cParser._replaceSpecialCharacters(x) if isinstance(x, str) and x is not None else '' for x in aMatches]
                
                return True, aMatches
        return False, None

    @staticmethod
    def replace(pattern, sReplaceString, sValue):
        return cParser._get_compiled_pattern(pattern).sub(sReplaceString, sValue)

    @staticmethod
    def search(pattern, sValue, ignoreCase=True):
        flags = 0
        if ignoreCase:
            flags = re.IGNORECASE
        return cParser._get_compiled_pattern(pattern, flags).search(sValue)

    @staticmethod
    def escape(sValue):
        return re.escape(sValue)

    @staticmethod
    def normalizeTitle(sTitle):
        """Titel fuer den Suchvergleich angleichen — EINE Wahrheit fuer alle Filter.

        Kleinschreibung; Punkte, Apostrophe und Sternchen fallen weg (S.W.A.T. ->
        swat, Grey's -> greys, M*A*S*H -> mash); alle anderen Nicht-Wortzeichen
        werden zu einem Leerzeichen (Spider-Man -> spider man, WALL·E -> wall e).
        Umlaute und ß werden umgeschrieben (König -> koenig, Straße -> strasse):
        die Seiten schreiben beides, der Nutzer tippt beides, und beide Seiten
        des Vergleichs bekommen dieselbe Form. Bis zum 11.09.2026 blieben sie
        stehen — „koenig" fand bei sechs Seiten 0 Titel, obwohl die Seiten welche
        mit „König" lieferten (nach der Umschrift 2 bis 20 je Seite). Das Ergebnis dient NUR dem
        Vergleich, angezeigt wird der Originaltitel. Bis zum 02.09.2026 stand
        diese Angleichung nur in xstream.searchAlter; die Site-Suchen verglichen
        zeichengenau, und „spider man" lieferte bei sechs Seiten 0 Treffer, obwohl
        jede davon Spider-Man-Titel fand (hdfilme 26, megakino 22 ...).
        """
        sTitle = str(sTitle).lower()
        for sUmlaut, sUmschrift in (('ä', 'ae'), ('ö', 'oe'), ('ü', 'ue'), ('ß', 'ss')):
            sTitle = sTitle.replace(sUmlaut, sUmschrift)
        sTitle = re.sub(r"[.'\u2019*`\u00b4]", '', sTitle)
        sTitle = re.sub(r'[^\w]+', ' ', sTitle)
        return re.sub(r'\s+', ' ', sTitle).strip()

    # --- Suchtitel: Zusaetze der Seiten, die nicht zum Titel gehoeren -------------------------
    # EINE Wahrheit fuer Weitere Quellen (xstream.searchAlter) und die TMDB-Namenssuche (Trailer,
    # TMDB-Info, Metadaten). Angezeigt wird immer der Originaltitel. Gemessen 29.09.2026 ueber alle
    # 17 Seiten (Listen Seite 1 und 2 am echten Dispatch, 52.142 Suchbegriffe): mit Zusatz fanden
    # die anderen Seiten und TMDB nichts oder das Falsche — „Game of Thrones | GoT" 0 statt 25
    # Treffer, „Rush (AUS)" bei TMDB eine andere Serie, „Die Odyssee *Subbed*" keine TMDB-ID.
    # Alternativname der Seite hinter „ | " (burningseries, 2.628 Titel): der erste Name bleibt.
    _RE_ALT_TITLE = re.compile(r'\s+\|\s+.*$')
    # Seiten-Anmerkung in Sternchen am Titelende: *Subbed*, *ENGLISH*, *2025*, *Gute Qualitaet*
    # (hdfilme, filmpalast). Nur mit Leerzeichen davor — „M*A*S*H" und „Thunderbolts*" bleiben.
    _RE_STAR_NOTE = re.compile(r'\s+\*[^*]{1,40}\*\s*$')
    # Sprach-Zusatz am Titelende: zwei Sprachpaare hintereinander („Jap Dub Ger Sub", „Ger Sub Ch
    # Dub", animetoast), eine Klammer mit hoechstens einem Wort vor Dub/Sub („(Subbed)", „(Italian
    # Dub)"), „(OmU)", und Ger/German + Dub/Sub mit oder ohne Klammer („Ger Sub", „[GerSub]").
    # Ein einzelnes nacktes Dub/Sub ohne Ger bleibt („Duckman … Das Sub" ist ein Folgentitel).
    _RE_LANG_NOTE = re.compile(r'(?:\s+[A-Z][a-z]{0,2}[\s-]+(?:Dub|Sub)(?:bed)?){2,}\s*$'
                               r'|\s*[\(\[]\s*(?:[^\W\d_]+[\s-]+)?(?:Dub|Sub)(?:bed)?\s*[\)\]]\s*$'
                               r'|\s*\(\s*OmU\s*\)\s*$'
                               r'|\s*[\(\[\*]?\bGer(?:man)?[\s-]*(?:Dub|Sub)(?:bed)?\b[\)\]\*]?\s*$', re.I)
    # Kuerzel-Klammer am Titelende aus 2-3 Grossbuchstaben, rund oder eckig: Land oder Format —
    # (US), (UK), (AUS), (ROK), (TV), (ONA), [OVA]. Gross/klein zaehlt: „(Un)Well" oder „(noch)" bleiben.
    _RE_CODE_NOTE = re.compile(r'\s*[\(\[][A-Z]{2,3}[\)\]]\s*$')
    # Typ-Angabe in Klammern am Titelende: (Zeichentrick), (Anime), (Live Action), (Serie),
    # (Realserie), (Filmreihe), (J-Drama)/(K-Drama) — 13 Titel bei burningseries, serienstream, einschalten.
    _RE_TYPE_NOTE = re.compile(r'\s*\(\s*(?:Zeichentrick|Anime|Live\s+Action|Serie|Realserie|Filmreihe|[A-Z]-Drama)\s*\)\s*$', re.I)
    # Staffel-/Folgen-Angabe der Seite in einer Klammer am Titelende, rund oder eckig:
    # „(nur aktuelle/verfuegbare Staffel/Folgen)" (serienstream, 14 Titel), „(Seasons 1 - 16)"
    # (streamcloud), „[2016 zw. s03/s04]" — mit dem Zusatz finden TMDB und die anderen Seiten
    # nichts. Eine Klammer ohne diese Woerter bleibt („(Live in 3D)", „(500) Days of Summer").
    _RE_SEASON_NOTE = re.compile(r'\s*[\(\[][^\(\)\[\]]*\b(?:Staffeln?|Folgen?|Seasons?|s\d{2})\b[^\(\)\[\]]*[\)\]]\s*$', re.I)
    # Jahr in Klammern am Titelende („Black Box *Subbed* (2026)", „Baki Ger Dub (2018)"): die
    # Ende-Regeln sehen sonst keinen Zusatz, weil das Jahr dahinter steht. Weitere Quellen
    # schneidet das Jahr vor dem Aufruf, die TMDB-Suche erst danach — deshalb hier abnehmen.
    _RE_YEAR_TAIL = re.compile(r'\s*\((?:19|20)\d{2}\)\s*$')
    # Fassungs-Angabe in runden oder eckigen Klammern, an beliebiger Stelle: eine Klammer fliegt,
    # sobald sie eines dieser zehn Woerter enthaelt, was sonst darin steht ist egal — „(Directors
    # Cut/Remastered)", „(Ulysses Cut)", „[Uncut]". „(Version 2)", „(Live in 3D)" und Titel ohne
    # Klammer („Uncut Gems", „Final Cut") bleiben. Eine strenge Wortliste je Klammer (39 Woerter)
    # fand am 29.09.2026 weniger und verpasste benannte Schnitte — nicht darauf zurueckbauen.
    _EDITION_WORDS = r'\b(?:uncut|unrated|extended|remastered|uncensored|theatrical|colorized|langfassung|cut|edition)\b'
    _RE_EDITION_NOTE = re.compile(r'\s*(?:\((?=[^()]*' + _EDITION_WORDS + r')[^()]{2,60}\)'
                                  r'|\[(?=[^\[\]]*' + _EDITION_WORDS + r')[^\[\]]{2,60}\])', re.I)

    @staticmethod
    def stripTitleNotes(sTitle):
        """Zusaetze der Seite aus einem SUCHtitel entfernen (Regeln oben). Mehrere Zusaetze am Ende
        („Spriggan (ONA) Ger Sub") werden nacheinander abgebaut. Ohne Treffer kommt der Titel
        zeichengleich zurueck, auch doppelte Leerzeichen bleiben — die Bereinigung darf keinen
        anderen Titel veraendern (Klassenmessung 29.09.2026).
        Steht hinter dem Zusatz noch ein Jahr in Klammern („Black Box *Subbed* (2026)", 193
        Begriffe am 01.10.2026), wird es fuer die Ende-Regeln abgenommen und faellt mit dem
        Zusatz: Weitere Quellen schneidet das Jahr ohnehin vorher, die TMDB-Suche bekommt es als
        eigenen Parameter. Ein Jahr ohne Zusatz davor bleibt stehen (zeichengleich).
        """
        sBody = cParser._RE_YEAR_TAIL.sub('', sTitle) if cParser._RE_YEAR_TAIL.search(sTitle) else sTitle
        sNew = cParser._RE_ALT_TITLE.sub('', sBody)
        for _ in range(3):
            sPrev = sNew
            for oRe in (cParser._RE_STAR_NOTE, cParser._RE_LANG_NOTE, cParser._RE_CODE_NOTE, cParser._RE_TYPE_NOTE, cParser._RE_SEASON_NOTE):
                sNew = oRe.sub('', sNew)
            if sNew == sPrev:
                break
        sNew = cParser._RE_EDITION_NOTE.sub('', sNew)
        if sNew == sBody:
            return sTitle
        # Besteht der Titel NUR aus einer Zusatz-Form, ist sie der Titel: „[REC] (2007)" (kellerkino)
        # traf die Kuerzel-Klammer und kam als leerer Suchtitel zurueck (Audit 02.10.2026)
        if not sNew.strip():
            return sTitle
        # ein durch den Schnitt verwaister Doppelpunkt faellt mit („Digimon Adventure: Ger Sub")
        return sNew.strip().rstrip(':').strip()

    # Englische Staffelformen („Season 2", „2nd Season", „Final Season", „Part 2" — gezaehlt
    # 10.09.2026 ueber 2.956 animetoast-Labels: 232 / 54 / 11 / 26) und die S01E02-Form. Nummern-
    # pflicht ausser bei „Final Season", damit „Season of the Witch" stehen bleibt; „Part N" trifft
    # auch Filmreihen („Deathly Hallows Part 2") und liefert dann die ganze Reihe — gewollt. Nicht
    # mitten in einer Klammer schneiden („Global GUTS (Nickelodeon GUTS Season 4)"), einen uebrig
    # bleibenden Doppelpunkt abwerfen („Attack on Titan: Final Season" → „Attack on Titan").
    _RE_SEASON_FORM = re.compile(r'^(.+?)\s*-?\s+(?:Season\s*\d+|\d+(?:st|nd|rd|th)\s+Season|Final\s+Season|Part\s*\d+)\b.*$', re.I)
    # Staffel UND Folge mit Nummer („S01 E01", „S29 E02", „S1 F7", „S01E03") — die Token in
    # stripSeasonForms kennen nur Staffeln mit fuehrender Null, „South Park S29 E02" blieb bis
    # zum 01.10.2026 als „South Park S29" stehen
    _RE_SEASON_EPISODE = re.compile(r'\s+S\d{1,3}\s*[EF]\d{1,4}\b.*$')

    @staticmethod
    def stripSeasonForms(sTitle):
        """Englische Staffelformen und die S01E02-Form aus einem SUCHtitel schneiden. Stand bis
        zum 29.09.2026 nur in searchAlter; die TMDB-Seriensuche fand deshalb z.B. „Kaiju No. 8 2nd
        Season" nicht (animetoast: 352 Seriennamen, burningseries 19 mit „S01 E01").
        """
        sNew = sTitle
        # Folgenkennung der Neue-Episoden-Listen („Dragon Ball Daima (S01E20) [DE]", serienstream) samt Rest
        sNew = re.sub(r'\s*\(S\d+E\d+\).*$', '', sNew)
        sCut = cParser._RE_SEASON_FORM.sub(r'\1', sNew).strip().rstrip(':').strip()
        if sCut and sCut.count('(') == sCut.count(')'):
            sNew = sCut
        sCut = cParser._RE_SEASON_EPISODE.sub('', sNew)
        if sCut == sNew:
            # nackte Staffel oder Folge wie bisher („Doctor Who S03", „Hogan Family S01-S06", „Serie E05")
            for token in (' S0', ' E0'):
                if token in sNew:
                    sCut = sNew.split(token)[0]
                    break
        if sCut != sNew:
            # nur hier den Trenner mitnehmen („Name - S01E01 - Folge" → „Name"), auch den Gedankenstrich
            # („Ip Man – Die Serie – S01 E10"); ein allgemeines rstrip('-') traefe Titel wie „GAMERA -Rebirth-"
            sNew = sCut.strip().rstrip('-–—:').strip()
        return sNew if sNew != sTitle else sTitle

    # Platzhalter-Titel der Seiten mit der Nummer der Folge: „Folge 5", „Episode 5", hdfilmes „Episoden 5"
    _RE_EPISODE_PLACEHOLDER = re.compile(r'^(?:folge|episoden?)\s*0*(\d+)$', re.I)

    @staticmethod
    def episodeLabel(season, episode, title='', fallback=None):
        """Label eines Folgen-Eintrags — EINE Form auf allen Sites (Jack 06.10.2026): „S01E05 - Titel",
        ohne Titel „S01E05". S/E ist Format wie „(3/12)" in cGui.pageInfo und braucht keinen String.

        Ein Platzhalter-Titel mit derselben Nummer („Folge 5" bei Folge 5) faellt weg, sonst stuende
        die Nummer doppelt da; „Episode 27" bei S02E05 bleibt (Gesamtzaehlung der Seite). Staffel 0
        wird S00 (Specials). Ohne ganze Zahlen fuer Staffel und Folge wird nichts geraten: dann kommt
        `fallback` zurueck (die bisherige Form der Site, wo sie eine eigene hatte), sonst „Folge N - Titel".
        """
        sTitle = str(title or '').strip()
        try:
            iEpisode = int(str(episode).strip())
        except ValueError:
            iEpisode = None
        m = cParser._RE_EPISODE_PLACEHOLDER.match(sTitle)
        if m and int(m.group(1)) == iEpisode:
            sTitle = ''
        try:
            iSeason = int(str(season).strip())
        except ValueError:
            iSeason = None
        if iSeason is not None and iEpisode is not None and iSeason >= 0 and iEpisode >= 0:
            sLabel = 'S%02dE%02d' % (iSeason, iEpisode)
        elif fallback is not None:
            return fallback
        else:
            sLabel = 'Folge %s' % ( iEpisode if iEpisode is not None else str(episode).strip())
        return '%s - %s' % (sLabel, sTitle) if sTitle else sLabel

    @staticmethod
    def searchTitle(sSearchText, sTitle):
        """Titelfilter der Suchen: steht der Suchbegriff im Titel, beide normalisiert?

        Ersetzt das fruehere `cParser.search(cParser.escape(sSearchText), sName)`
        an allen Filterstellen. Normalisiert ist eine Obermenge des strikten
        Vergleichs — es faellt nur Interpunktion weg, jeder alte Treffer bleibt.
        Ein leerer Suchbegriff filtert nicht.
        """
        sNeedle = cParser.normalizeTitle(sSearchText)
        if not sNeedle:
            return True
        return sNeedle in cParser.normalizeTitle(sTitle)

    @staticmethod
    def getNumberFromString(sValue):
        aMatches = re.compile(r'\d+').findall(sValue)
        if len(aMatches) > 0:
            return int(aMatches[0])
        return 0

    @staticmethod
    def urlparse(sUrl):
        return urlparse(sUrl.replace('www.', '')).netloc.title()

    @staticmethod
    def urlDecode(sUrl):
        return unquote(sUrl)

    @staticmethod
    def urlEncode(sUrl, safe=''):
        return quote(sUrl, safe)

    @staticmethod
    def quote(sUrl):
        return quote(sUrl)

    @staticmethod
    def unquotePlus(sUrl):
        return unquote_plus(sUrl)

    @staticmethod
    def quotePlus(sUrl):
        return quote_plus(sUrl)

    @staticmethod
    def B64decode(text):
        import base64
        return base64.b64decode(text).decode('utf-8')

def infoDialog(message, heading="", icon="", time=5000, sound=False):
	# Waehrend der Quellensuche laufen viele Seiten parallel: Meldungen nur ins Log.
	logger.info(message)

class logger:
	@staticmethod
	def info(sInfo):
		logger.__writeLog(sInfo, cLogLevel=xbmc.LOGINFO)

	@staticmethod
	def debug(sInfo):
		logger.__writeLog(sInfo, cLogLevel=xbmc.LOGDEBUG)

	@staticmethod
	def warning(sInfo):
		logger.__writeLog(sInfo, cLogLevel=xbmc.LOGWARNING)

	@staticmethod
	def error(sInfo):
		logger.__writeLog(sInfo, cLogLevel=xbmc.LOGERROR)

	@staticmethod
	def fatal(sInfo):
		logger.__writeLog(sInfo, cLogLevel=xbmc.LOGFATAL)

	@staticmethod
	def __writeLog(sLog, cLogLevel=xbmc.LOGDEBUG):
		from resources.lib.handler.parameterHandler import ParameterHandler
		params = ParameterHandler()
		#if utils.get_setting("debug") == 'true':
		if True:
			cLogLevel=xbmc.LOGINFO
		try:
			if params.exist('site'):
				site = params.getValue('site')
				sLog = "[xStream Scraper] -> [%s]: %s" % (site, sLog)
			else:
				sLog = "[xStream Scraper] %s" % (sLog)
			if xbmc.getInfoLabel('System.BuildVersionCode') == '':
				
				if cLogLevel == 1:
					settings.logging.info(sLog)
				elif cLogLevel == 3:
					settings.logging.error(sLog)
				elif cLogLevel == 4:
					settings.logging.critical(sLog)
				else:
					settings.logging.debug(sLog)
			xbmc.log(sLog, cLogLevel)
		except Exception as e:
			if xbmc.getInfoLabel('System.BuildVersionCode') == '':
				print('Logging Failure: %s' % e)
			xbmc.log('Logging Failure: %s' % e, cLogLevel)
			pass

class cUtil:
    @staticmethod
    def removeHtmlTags(sValue, sReplace=''):
        return re.compile(r'<.*?>').sub(sReplace, sValue)

    @staticmethod
    def unescape(text):
        # edit kasi 2024-11-26 so für py2/py3 oder für nur py3 unichr ersetzen durch chr
        try: unichr
        except NameError: unichr = chr

        def fixup(m):
            text = m.group(0)
            if not text.endswith(';'): text += ';'
            if text[:2] == '&#':
                try:
                    if text[:3] == '&#x':
                        return unichr(int(text[3:-1], 16))
                    else:
                        return unichr(int(text[2:-1]))
                except ValueError:
                    pass
            else:
                try:
                    text = unichr(name2codepoint[text[1:-1]])
                except KeyError:
                    pass
            return text

        if isinstance(text, str):
            try:
                text = text.decode('utf-8')
            except Exception:
                try:
                    text = text.decode('utf-8', 'ignore')
                except Exception:
                    pass
        return re.compile('&(\\w+;|#x?\\d+;?)').sub(fixup, text.strip())

    @staticmethod
    def cleanse_text(text):
        if text is None: text = ''
        text = cUtil.removeHtmlTags(text)
        return text

    @staticmethod
    def evp_decode(cipher_text, passphrase, salt=None):
        if not salt:
            salt = cipher_text[8:16]
            cipher_text = cipher_text[16:]
        key, iv = cUtil.evpKDF(passphrase, salt)
        decrypter = pyaes.Decrypter(pyaes.AESModeOfOperationCBC(key, iv))
        plain_text = decrypter.feed(cipher_text)
        plain_text += decrypter.feed()
        return plain_text.decode("utf-8")

    @staticmethod
    def evpKDF(pwd, salt, key_size=32, iv_size=16):
        temp = b''
        fd = temp
        while len(fd) < key_size + iv_size:
            h = hashlib.md5()
            h.update(temp + pwd + salt)
            temp = h.digest()
            fd += temp
        key = fd[0:key_size]
        iv = fd[key_size:key_size + iv_size]
        return key, iv
        
    @staticmethod
    def isSimilar(sSearch, sText, threshold=0.9):
        return (SequenceMatcher(None, sSearch, sText).ratio() >= threshold)

    @staticmethod
    @lru_cache(maxsize=200000)
    def get_seq_match_ratio(token1, token2):
        return SequenceMatcher(None, token1, token2).ratio()
    
    @staticmethod
    def isSimilarByToken(sSearch, sText, threshold=0.9):
        tokens_sSearch = sSearch.split()
        tokens_sText = sText.split()

        if not tokens_sSearch:
            return False

            # get_ratio = lambda a, b: SequenceMatcher(None, a, b).ratio()
        best_ratios = [
            max(cUtil.get_seq_match_ratio(token, token2) for token2 in tokens_sText)
            for token in tokens_sSearch
        ]
        return (sum(best_ratios) / len(best_ratios)) >= threshold

class cCache(object):
    _win = None

    def __init__(self):
        # see https://kodi.wiki/view/Window_IDs
        self._win = xbmcgui.Window(10000)

    def __del__(self):
        del self._win

    def get(self, key, cache_time):
        cachedata = self._win.getProperty(key)

        if cachedata:
            cachedata = eval(cachedata)
            if time.time() - cachedata[0] < cache_time or cache_time < 0:
                return cachedata[1]
            else:
                self._win.clearProperty(key)

        return None
    
    def set(self, key, data):
        self._win.setProperty(key, repr((time.time(), data)))

    def clear(self):
        self._win.clearProperties()
        
def valid_email(email): #ToDo: Funktion in Settings / Konten aktivieren
	# Email Muster
	pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'

	# Überprüfen der EMail-Adresse mit dem Muster
	if re.match(pattern, email):
		return True
	else:
		return False
