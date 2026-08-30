# -*- coding: utf-8 -*-

# edit 2024-12-05 kasi

if __name__ == "__main__":
	from vavoo.utils import *
	from vavoo import vjackson, stalker, vavoo_tv, vjlive, linear_lite
	params = dict(parse_qsl(sys.argv[2][1:]))
	tv = params.get("name")
	action = params.pop("action", None)
	actions = {
		"choose": lambda: vavoo_tv.choose(),
		"get_genres": lambda: stalker.get_genres(),
		"choose_portal": lambda: stalker.choose_portal(),
		"new_mac": lambda: stalker.new_mac(),
		"clear_lite_cache": lambda: (del_cache("lite_channels"), dialog.notification("VAVOO.TO", "LiteTV Cache gelöscht", xbmcgui.NOTIFICATION_INFO, 2000)),
		"clear": lambda: clear(),
		"delete_search": lambda: delete_search(params),
		"channels": lambda: vjlive.channels(params.get('items'), params.get('type'), params.get('group')),
		"settings": lambda: openSettings(sys.argv[1]),
		"favchannels": lambda: vjlive.favchannels()
	}
	if tv:
		if action == "addTvFavorit": vjlive.change_favorit(tv)
		elif action == "delTvFavorit": vjlive.change_favorit(tv, True)
		else: vjlive.livePlay(tv, params.get('type'), params.get('group'), params.get('retry', '0'), params.get('idx'))
	elif action is None:
		vjackson.menu(params)
	elif action == "delallTvFavorit":
		setSetting("favs", "[]")
		execute('Container.Refresh')
	elif action in actions:
		actions[action]()
	else:
		handler = getattr(vjackson, action, None)
		if callable(handler) and not action.startswith("_"):
			handler(params)
		else:
			log("Unbekannte action: %s" % action)
			vjackson.menu(params)
