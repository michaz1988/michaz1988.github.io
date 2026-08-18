# -*- coding: utf-8 -*-

# edit 2024-12-05 kasi

if __name__ == "__main__":
	from vavoo.utils import *
	from vavoo import vjackson, stalker, vavoo_tv, vjlive
	params = dict(parse_qsl(sys.argv[2][1:]))
	tv = params.get("name")
	action = params.pop("action", None)
	actions = {
		"choose": lambda: vavoo_tv.choose(),
		"get_genres": lambda: stalker.get_genres(),
		"choose_portal": lambda: stalker.choose_portal(),
		"new_mac": lambda: stalker.new_mac(),
		"clear": lambda: clear(),
		"delete_search": lambda: delete_search(params),
		"channels": lambda: vjlive.channels(params.get('items'), params.get('type'), params.get('group')),
		"settings": lambda: openSettings(sys.argv[1]),
		"favchannels": lambda: vjlive.favchannels(),
		"makem3u": lambda: vjlive.makem3u()
	}
	if tv:
		if action == "addTvFavorit": vjlive.change_favorit(tv)
		elif action == "delTvFavorit": vjlive.change_favorit(tv, True)
		else: vjlive.livePlay(tv, params.get('type'), params.get('group'))
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
