# -*- coding: utf-8 -*-

# edit 2024-12-05 kasi

if __name__ == "__main__":
	from vavoo.utils import *
	from vavoo import vjackson, stalker, vavoo_tv, vjlive
	joyn_token=translatePath("special://profile/addon_data/plugin.video.joyn/data/auth_tokens")
	if exists(joyn_token):
		try:
			with open(joyn_token) as k:
				joyn_token_json = json.load(k)
			if joyn_token_json["expires_in"] == 86400000:
				joyn_token_json["expires_in"] = 86400
				with open(joyn_token, "w") as k:
					json.dump(joyn_token_json, k)
		except:pass
	params = dict(parse_qsl(sys.argv[2][1:]))
	tv = params.get("name")
	action = params.pop("action", None)
	if tv:
		if action == "addTvFavorit": vjlive.change_favorit(tv)
		elif action == "delTvFavorit": vjlive.change_favorit(tv, True)
		else: vjlive.livePlay(tv, params.get('type'), params.get('group'))
	elif action == None: vjackson.menu(params)
	elif action == "choose": vavoo_tv.choose()
	elif action == "get_genres": stalker.get_genres()
	elif action == "choose_portal": stalker.choose_portal()
	elif action == "new_mac": stalker.new_mac()
	elif action == "clear": clear()
	elif action == "delete_search": delete_search(params)
	elif action == "delallTvFavorit":
		setSetting("favs", "[]")
		execute('Container.Refresh')
	# edit kasi
	elif action == "channels": vjlive.channels(params.get('items'), params.get('type'), params.get('group'))
	elif action == "settings": openSettings(sys.argv[1])
	elif action == "favchannels": vjlive.favchannels()
	elif action == "makem3u": vjlive.makem3u()
	else: getattr(vjackson, action)(params)