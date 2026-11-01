# -*- coding: utf-8 -*-
# Macht die Module von xStream unter resources.lib verfuegbar. Der Scraper bringt nur gui.gui und
# handler.parameterHandler selbst mit, alles andere (requestHandler, tools, config, ...) kommt aus
# dem installierten xStream und passt damit immer zu dessen Seiten.
import os, sys, xbmcaddon
import resources, resources.lib, resources.lib.gui, resources.lib.handler
from resources.lib.addonTools import XSTREAM_ID

xstreamFolder = xbmcaddon.Addon(XSTREAM_ID).getAddonInfo("path")
sourcesFolder = os.path.join(xstreamFolder, "sites")
sys.path.append(sourcesFolder)
sys.path.append(xstreamFolder)
for package, folder in (
	(resources, os.path.join(xstreamFolder, "resources")),
	(resources.lib, os.path.join(xstreamFolder, "resources", "lib")),
	(resources.lib.gui, os.path.join(xstreamFolder, "resources", "lib", "gui")),
	(resources.lib.handler, os.path.join(xstreamFolder, "resources", "lib", "handler")),
):
	if folder not in package.__path__:
		package.__path__.append(folder)

# cConfig() soll Einstellungen, Texte und Profil von xStream nutzen, nicht die des Scrapers.
from resources.lib.config import cConfig
cConfig._default_id = XSTREAM_ID

from resources.lib.logger import logger
from resources.lib import tools

# Bei der Suche laufen viele Seiten parallel: Einblendungen nur ins Log. Muss vor dem Import des
# requestHandlers und der Seiten passieren, weil sie infoDialog beim Import uebernehmen.
def _logInfoDialog(message, *args, **kwargs):
	logger.info(message)
tools.infoDialog = _logInfoDialog
