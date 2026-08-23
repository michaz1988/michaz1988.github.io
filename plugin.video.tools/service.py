# -*- coding: utf-8 -*-
"""One-time startup maintenance checks for plugin.video.tools."""

import xbmc

from resources.lib import thumbnail_cleanup


if __name__ == '__main__':
	try:
		thumbnail_cleanup.check_at_startup()
	except Exception as error:
		xbmc.log(
			'Thumbnail-Prüfung beim Start fehlgeschlagen: %s' % error,
			xbmc.LOGERROR,
		)
