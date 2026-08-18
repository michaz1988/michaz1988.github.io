#!/usr/bin/python
# -*- coding: utf-8 -*-
import os, re, sys

import xbmc, xbmcgui
from urllib.parse import unquote_plus
from urllib.request import urlopen
from xbmcvfs import translatePath

monitor = xbmc.Monitor()
home_path = os.path.join(translatePath('special://home'),'addons')

repository_path_array=[]
for dirname in os.listdir(home_path):
    if os.path.isdir(os.path.join(home_path,dirname)) and 'repository' in str(dirname):
        repository_path_array.append(os.path.join(home_path,dirname))

filesCount =float(0)		
filesCount += float(len(repository_path_array))
count = 0

dp = xbmcgui.DialogProgress()
dp.create('TOOLS','REPO STATUS TEST !\nBITTE WARTEN ...')
update = int(0)
dp.update(update)

if monitor.waitForAbort(1.5):
    sys.exit(0)

output = ''
http_code_array = ['100 Weiter','101 Umschalten von Protokollen','102 Verarbeitung','200 [COLOR green]OK[/COLOR]','201 Erstellt','202 akzeptiert','203 Nicht-maßgebliche Informationen','204 Kein Inhalt','205 Inhalt zurücksetzen','206 Teilinhalt','207 Multi-Status','208 Bereits berichtet','226 IM verwendet','300 Mehrfachauswahl','301 dauerhaft verschoben','302 Gefunden','303 Siehe andere','304 nicht modifiziert','305 Proxy verwenden','307 Vorübergehende Weiterleitung','308 Permanent Redirect','400 schlechte Anfrage','401 Unerlaubt','402 Zahlung erforderlich','403 [COLOR red]verboten[/COLOR]','404 [COLOR red]offline[/COLOR]','405 Methode nicht erlaubt','406 nicht akzeptabel','407 Proxy-Authentifizierung erforderlich','408 Zeitplan anfordern','409 Konflikt','410 gegangen','411 Länge erforderlich','412 Voraussetzung fehlgeschlagen','413 Nutzlast zu groß','414 Request-URI zu lang','415 Nicht unterstützter Medientyp','416 Angeforderte Reichweite nicht befriedigend','417 Erwartung fehlgeschlagen','418 Ich bin eine Teekanne','421 Misdirected Anfrage','422 Unprocessable Entity','423 Gesperrt','424 fehlgeschlagene Abhängigkeit','426 Upgrade erforderlich','428 Voraussetzung erforderlich','429 Zu viele Anfragen','431 Anforderungsheaderfelder zu groß','444 Verbindung ohne Reaktion geschlossen','451 Aus rechtlichen Gründen nicht verfügbar','499 Client Geschlossene Anfrage','500 Interner Serverfehler','501 nicht implementiert','502 [COLOR red]Bad Gateway[/COLOR]','503 Service nicht verfügbar','504 Gateway Zeitüberschreitung','505 HTTP-Version wird nicht unterstützt','506 Variante auch verhandelt','507 Unzureichende Lagerung','508 Loop erkannt','510 nicht verlängert','511 Netzwerk-Authentifizierung erforderlich','599 [COLOR red]Network Connect Timeout Fehler[/COLOR]']

for repository_path in repository_path_array:

    xml_path = os.path.join(repository_path,'addon.xml')
    xml_content = open(xml_path, encoding="utf-8").read()

    for name,url in re.findall(r'<addon[^<>]*>[\s\S].*?name="(.*?)">*?[^<>]*>[\s\S]*?<info[^<>].*?>(.*?)<\/info>',xml_content,re.DOTALL):

        try:

            request = urlopen(unquote_plus(url))
            status_code = str(request.getcode())

            if any(status_code in s for s in http_code_array):

                for http_code in http_code_array:
                    if status_code in http_code:
                        dp.update(update,'TESTE REPO :\n'+unquote_plus(name)+'\n'+unquote_plus(http_code))
                        output += unquote_plus(name) +' = ' + unquote_plus(http_code)  + '\n'

            else:
                dp.update(update,'TESTE REPO :\n'+unquote_plus(name)+'\n'+unquote_plus(http_code))
                output += unquote_plus(name) +' = [COLOR red]Unbekannter Statuscode (( ' + str(status_code)  + ' ))[/COLOR]\n'

        except :
            dp.update(update,'TESTE REPO \n:'+unquote_plus(name)+'\n'+unquote_plus(http_code))
            output += unquote_plus(name) +' = '+ unquote_plus(http_code)  + '\n'

    count += 1
    update = int(count / filesCount * 100)
    dp.update(update)
    if dp.iscanceled():
        dp.close()
        sys.exit(0)

dp.close()
if monitor.waitForAbort(1):
    sys.exit(0)
xbmcgui.Dialog().textviewer('REPO TESTER',output)
