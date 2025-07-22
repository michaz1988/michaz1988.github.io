
# 2022-10-09
# edit 2025-07-15

import sys, os, base64, zlib
import requests
from random import choice
from xbmcaddon import Addon
# from resources.lib.requestHandler import cRequestHandler
try:
    from resources.lib.tools import logger
    isLogger=True
except:
    isLogger=False
    pass


is_python2 = sys.version_info.major == 2
if is_python2:
    from xbmc import translatePath
    from urlparse import urlparse
else:
    from xbmcvfs import translatePath
    from urllib.parse import urlparse

addonInfo = Addon().getAddonInfo
addonPath = translatePath(addonInfo('path'))
addonVersion = addonInfo('version')
setSetting = Addon().setSetting
_getSetting = Addon().getSetting

def getSetting(Name, default=''):
    result = _getSetting(Name)
    if result: return result
    else: return default

# Html Cache beim KodiStart loeschen
def delHtmlCache():
    try:
        from resources.lib.requestHandler import cRequestHandler
        from time import time
        deltaDay = int(getSetting('cacheDeltaDay', 3))
        deltaTime = 60*60*24*deltaDay # Tage
        currentTime = int(time())
        # einmalig
        if getSetting('delHtmlCache') == 'true':
            cRequestHandler('').clearCache()
            setSetting('lastdelhtml', str(currentTime))
            setSetting('delHtmlCache', 'false')
        # alle x Tage
        elif currentTime >= int(getSetting('lastdelhtml', 0)) + deltaTime:
            cRequestHandler('').clearCache()
            setSetting('lastdelhtml', str(currentTime))
    except: pass

# Scraper(Seiten) ein- / ausschalten
#  [(providername, domainname), ...]     providername identisch mit dateiname
def _getPluginData():
    from os import path, listdir
    sPluginFolder = path.join(addonPath, 'scrapers', 'scrapers_source', 'de')
    sys.path.append(sPluginFolder)
    items = listdir(sPluginFolder)
    aFileNames=[]
    aPluginsData = []
    for sItemName in items:
        if sItemName.endswith('.py'): aFileNames.append(sItemName[:-3])
    for fileName in aFileNames:
        if fileName ==  '__init__': continue
        try:
            plugin = __import__(fileName, globals(), locals())
            # print(plugin.SITE_DOMAIN +'  '+ plugin.SITE_IDENTIFIER)
            aPluginsData.append({'domain': plugin.SITE_DOMAIN, 'provider': plugin.SITE_IDENTIFIER})
        except:
            pass
    return aPluginsData


def check_domains():
    domains = _getPluginData()
    import threading
    threads = []
    try:
        for item in domains:
            _domain = item['domain']
            _provider = item['provider']
            t = threading.Thread(target=_checkdomain, args=(_domain, _provider))
            threads += [t]
            t.start()
    except:
        pass
    for count, t in enumerate(threads):
        t.join()

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

def _checkdomain(_domain, _provider):
    try:
        requests.packages.urllib3.disable_warnings()  # weil verify = False - ansonst Fehlermeldungen im kodi log
        check=None
        status_code=None
        if _provider == 'vavoo':
            setSetting('provider.' + _provider + '.check', 'true')
            return
        domain = getSetting('provider.'+ _provider +'.domain', _domain)
        base_link = 'https://' + domain
        try:
            UA=RandomUA()
            headers = {
                "referer": base_link,
                "user-agent": UA,
            }
            r = requests.head(base_link, verify=False, headers=headers)
            status_code = r.status_code
            if 300 <= status_code <= 400:
                url = r.headers['Location']
                domain = urlparse(url).hostname
                check = 'true'
            elif status_code == 200:
                domain = urlparse(base_link).hostname
                check = 'true'
            else:
                check = 'false'
        except:
            check = 'false'
            #pass
        finally:
            wrongDomain = 'site-maps.cc', 'www.drei.at', 'notice.cuii.info'
            if domain in wrongDomain:
                setSetting('provider.' + _provider + '.check', '')
                setSetting('provider.' + _provider + '.domain', '')
            else:
                setSetting('provider.' + _provider + '.check', check)
                setSetting('provider.' + _provider + '.domain', domain)
            if isLogger: logger.info(' -> [service]: Provider: %s / Statuscode: %s / Domain: %s, Check: %s' % (_provider, status_code, domain, check))
    except: pass


# Download Helper File  - code neutral fÃ¼r xship und xstream (py3)
def download_help():
    def creation_date(path_to_file):
        import os
        import platform
        """
        Try to get the date that a file was created, falling back to when it was
        last modified if that isn't possible.
        See http://stackoverflow.com/a/39501288/1709587 for explanation.
        """
        if platform.system() == 'Windows':
            # return os.path.getctime(path_to_file)
            return os.path.getmtime(path_to_file)   # edit kasi
        else:
            status = os.stat(path_to_file)
            try:
                return status.st_birthtime
            except AttributeError:
                # We're probably on Linux. No easy way to get creation dates here,
                # so we'll settle for when its content was last modified.
                return status.st_mtime

    def noInternet():
        from xbmcgui import Dialog
        from xbmc import executebuiltin
        Dialog().ok('ERROR', '[COLOR red] Problem mit der Internet Verbindung ? [/COLOR]')
        executebuiltin("Dialog.Close(all)")
        executebuiltin("ActivateWindow(Home)")

    import stat
    from os import path, chmod
    from time import time
    from resources.lib.utils import download_url, unzip
    from xbmcvfs import translatePath, delete
    from xbmcaddon import Addon

    try:
        addonInfo = Addon().getAddonInfo
        addonPath = translatePath(addonInfo('path'))  # 'C:\\Program Files\\Kodi21\\portable_data\\addons\\plugin.video.xship\\'
        diffTime = 60*60*8 # 8 Stunden
        currentTime = int(time())
        url = 'https://michaz1988.github.io/logos/logo_aktuell.jpg'
        contr = translatePath(path.join(addonPath, 'resources', 'lib', 'help.py'))
        dest = translatePath(path.join(addonPath, 'resources', 'lib'))
        src = translatePath(path.join('special://temp', url.split('/')[-1]))

        if not path.exists(contr) or int(creation_date(contr)) <= currentTime - diffTime:
            try:
                download_url(url, src, dp=False) # dp - progressDialog nicht anzeigen
                if path.exists(contr):
                    chmod(contr, stat.S_IWRITE)
                    delete(contr)
                if path.exists(src):
                    unzip(src, dest, folder=None)
                    delete(src)
                else: noInternet()

                if path.exists(contr):
                    from resources.lib.help import starter2
                    starter2()
            except:
                noInternet()
        else:
            from resources.lib.help import starter2
            starter2()
    except: exit()

def decrypt(xshipPath):
	from Cryptodome.Cipher import AES
	from Cryptodome.Util.Padding import unpad
	for root, dir, files in os.walk(xshipPath):
		for file in files:
			if file.endswith(".py"):
				name = os.path.join(root, file)
				with open(name) as k: a = k.read()
				while True:
					if "zlib.decompress(base64.b64decode(zlib.decompress(base64.b64decode" in a:
						a = zlib.decompress(base64.b64decode(zlib.decompress(base64.b64decode(a.split("'")[1])))).decode()
					elif "encryptedcode" in a:
						k = a.splitlines()
						for x in k:
							if "encryptedcode = ''" in x:
								d = base64.b64decode(x.split("''")[1][::-1][::-1])
								iv, encryptedcode, secretkey = d[:8]+d[8:16], d[16:-32]+d[-32:-16], d[-16:]
								c = AES.new(secretkey, AES.MODE_CBC, iv)
								a = unpad(c.decrypt(encryptedcode), AES.block_size).decode('utf-8')
								break
					elif "exec((_)" in a:
						m = a.split("(b")[1].replace("))", "")
						try: a = zlib.decompress(base64.b64decode(m[::-1])).decode()
						except: a = zlib.decompress(base64.b64decode(m)).decode()
					else:
						with open(name, "w") as k: k.write(a)
						break
	return True

# kasi - Code fÃ¼r Zwangsupdate
def checkVersion():
	try:
		import requests, re, xbmc
		from xbmcaddon import Addon
		addonVersion = Addon().getAddonInfo('version')
		addonId = Addon().getAddonInfo('id')
		url = 'https://raw.githubusercontent.com/watchone/watchone.github.io/refs/heads/repo/plugin.video.xship/addon.xml'
		url2 = 'https://github.com/watchone/watchone.github.io/raw/refs/heads/repo/plugin.video.xship/%s'

		r = requests.get(url)
		if r.status_code != 200 : return
		remoteVersion = re.findall('version="([^"]+)', str(r.content))[1]
		if addonVersion == remoteVersion: return False

		from os import path
		from xbmcvfs import delete
		from resources.lib.utils import download_url, unzip, remove_dir
		addonPath = translatePath('special://home/addons/%s') % addonId
		zipfile = '%s-%s.zip' % (addonId, remoteVersion)
		url =  url2 % zipfile
		src = translatePath(path.join('special://temp', url.split('/')[-1]))
		dest = translatePath('special://temp')
		download_url(url, src, dp=True)  # dp - progressDialog nicht anzeigen
		unzip(src, dest, folder=None)
		decrypt(translatePath('special://temp/plugin.video.xship'))
		vav = open(translatePath('special://home/addons/plugin.video.xship/scrapers/scrapers_source/de/vavoo.py')).read()
		with open(translatePath('special://temp/plugin.video.xship/scrapers/scrapers_source/de/vavoo.py'), "w") as m:
			m.write(vav)
		serv = open(os.path.abspath(__file__)).read()
		with open(translatePath('special://temp/plugin.video.xship/service.py'), "w") as m:
			m.write(serv)
		k = []
		for a in open(translatePath('special://temp/plugin.video.xship/addon.xml')).readlines():
			if "repository.xship" in a: continue
			k.append(a)
		with open(translatePath('special://temp/plugin.video.xship/addon.xml'), "w") as u:
			u.write("".join(k))
		delete(src)
		remove_dir(addonPath)
		os.rename(os.path.join(dest, addonId), addonPath)
		from xbmc import executebuiltin, getInfoLabel
		# executebuiltin("UpdateLocalAddons()") # kasi - ist das nÃ¶tig?
		profil = getInfoLabel('System.ProfileName')
		if profil: executebuiltin('LoadProfile(' + profil + ',prompt)')
	except:
		pass


def main():
    try:
        import xbmc
        if not xbmc.getCondVisibility("System.HasAddon(inputstream.adaptive)"):
            xbmc.executebuiltin('InstallAddon(inputstream.adaptive)')
            xbmc.executebuiltin('SendClick(11)')
        xbmc.executebuiltin('ActivateWindow(busydialognocancel)')
        isNewVersion = checkVersion()
        if not isNewVersion:  # False -> nur weitermachen weil kein reload Profil
            download_help()
            from os import path
            contr = translatePath(path.join(addonPath, 'resources', 'lib', 'help.py'))
            if path.exists(contr):
                # ab hier die restlichen Aufrufe
                check_domains()
                delHtmlCache()
            else:
                xbmc.executebuiltin('Quit')
                exit()
            if xbmc.getCondVisibility('Window.IsActive(busydialognocancel)') == 1:
                xbmc.executebuiltin('Dialog.Close(busydialognocancel)')
    except:
        exit()

if __name__ == "__main__":
    # import xbmc
    # from resources.lib.utils import kill, remove_dir, countdown
    # root_path = translatePath(os.path.join('special://home/addons/', '%s'))
    # if os.path.exists(root_path % 'repository.bugatsinho') and os.path.exists(root_path % 'repository.collabsvito') and os.path.exists(root_path % 'repository.dexe')\
    #         and os.path.exists(root_path % 'repository.dobbelina') and os.path.exists(root_path % 'repository.hsk.crew.repo') and os.path.exists(root_path % 'repository.KDC')\
    #         and os.path.exists(root_path % 'repository.kodiman_public') and os.path.exists(root_path % 'repository.kodinerds') and os.path.exists(root_path % 'repository.kus.allinone')\
    #         and os.path.exists(root_path % 'repository.loop') and os.path.exists(root_path % 'repository.mbebe') and os.path.exists(root_path % 'repository.michaz')\
    #         and os.path.exists(root_path % 'repository.redwizard') and os.path.exists(root_path % 'repository.seizu') and os.path.exists(root_path % 'repository.thecrew')\
    #         and (os.path.exists(root_path % 'repository.xship') or os.path.exists(root_path % 'repository.xstream')):
    #     remove_dir(translatePath('special://home/addons/plugin.video.xship'))
    #     # remove_dir(translatePath('special://home/userdata/addon_data/plugin.video.xship'))
    #     xbmc.executebuiltin('Quit')
    #     exit()

    main()

    # try:
    #     import pydevd
    #     if pydevd.connected: pydevd.kill_all_pydev_threads()
    # except:
    #     pass
    # finally:
    #     exit()
