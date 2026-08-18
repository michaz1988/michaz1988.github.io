# -*- coding: utf-8 -*-
import xbmc, xbmcaddon, xbmcgui, xbmcvfs, json, os, sys, requests
import requests.cookies
import requests.adapters
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from resources.lib import xml_structure, channel_selector, mapper, filesplit

provider = 'simpliTV (AT)'
lang = 'de'
ADDON = xbmcaddon.Addon(id="service.takealug.epg-grabber")
addon_name = ADDON.getAddonInfo('name')
addon_version = ADDON.getAddonInfo('version')
loc = ADDON.getLocalizedString
datapath = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))

## Read simpliAT Settings
days_to_grab = int(ADDON.getSetting('days_to_grab'))
episode_format = ADDON.getSetting('episode_format')
# Make a debug logger

def log(message, loglevel=xbmc.LOGDEBUG):
	xbmc.log('[{} {}] {}'.format(addon_name, addon_version, message), loglevel)
	
# Make OSD Notify Messages
OSD = xbmcgui.Dialog()

def notify(title, message, icon=xbmcgui.NOTIFICATION_INFO):
	OSD.notification(title, message, icon)

## Channel Files
simpliAT_chlist_selected = os.path.join(datapath, 'chlist_simpliAT_selected.json')
header = {
	'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/110.0',
	'Content-type': 'application/json;charset=utf-8',
	'X-Api-Date-Format': 'iso',
	'X-Api-Camel-Case': 'true',
	'referer': 'https://streaming.simplitv.at/'}

def get_epgLength(days_to_grab):
	# Calculate Date and Time
	today = datetime.today()
	calc_today = datetime(today.year, today.month, today.day, hour=00, minute=00, second=1)
	calc_then = datetime(today.year, today.month, today.day, hour=23, minute=59, second=59)
	calc_then += timedelta(days=days_to_grab)
	starttime = calc_today.strftime("%Y-%m-%dT%H:%M:00.000Z")
	endtime = calc_then.strftime("%Y-%m-%dT%H:%M:00.000Z")
	return starttime, endtime

def get_channellist():
	temp = []
	starttime, endtime = get_epgLength(0)
	epg_url = "https://api.app.simplitv.at/v1/EpgTile/FilterProgramTiles"
	epg_post = {"platformCodename": "www", "from": starttime, "to": endtime}
	epg_resp = requests.post(epg_url, headers=header, json=epg_post).json()["programs"]
	prg_url = "https://api.app.simplitv.at/v2/Tile/GetTiles"
	prg_post = {"platformCodename": "www", "requestedTiles": [{"id": epg_resp[i][0]["id"]} for i in epg_resp.keys()]}
	epg_data = requests.post(prg_url, headers=header, json=prg_post).json()["tiles"]
	for channels in epg_data:
		temp.append({"contentId": channels["tileChannel"]["codename"],"name": channels["tileChannel"]["title"],"pictures": [{"href": channels["tileChannel"]["logoUrl"]}]})
	return {"channellist": sorted(temp, key=lambda x: x["name"])}
		
def select_channels():
	## Create empty (Selected) Channel List if not exist
	if not os.path.isfile(simpliAT_chlist_selected):
		with open((simpliAT_chlist_selected), 'w', encoding='utf-8') as selected_list:
			selected_list.write(json.dumps({"channellist": []}))
	## Download chlist_simpliAT_provider.json
	provider_list = get_channellist()
	dialog = xbmcgui.Dialog()
	with open(simpliAT_chlist_selected, 'r', encoding='utf-8') as s:
		selected_list = json.load(s)
	## Start Channel Selector
	user_select = channel_selector.select_channels(provider, provider_list, selected_list)
	if user_select is not None:
		with open(simpliAT_chlist_selected, 'w', encoding='utf-8') as f:
			json.dump(user_select, f, indent=4)
		if os.path.isfile(simpliAT_chlist_selected):
			valid = check_selected_list()
			if valid is True:
				ok = dialog.ok(provider, loc(32402))
				if ok: log(loc(32402), xbmc.LOGINFO)
			elif valid is False:
				log(loc(32403), xbmc.LOGINFO)
				yn = OSD.yesno(provider, loc(32403))
				if yn: select_channels()
				else:
					xbmcvfs.delete(simpliAT_chlist_selected)
					exit()
	else:
		valid = check_selected_list()
		if valid is True:
			ok = dialog.ok(provider, loc(32404))
			if ok: log(loc(32404), xbmc.LOGINFO)
		elif valid is False:
			log(loc(32403), xbmc.LOGINFO)
			yn = OSD.yesno(provider, loc(32403))
			if yn: select_channels()
			else:
				xbmcvfs.delete(simpliAT_chlist_selected)
				exit()
				
def check_selected_list():
	check = 'invalid'
	with open(simpliAT_chlist_selected, 'r', encoding='utf-8') as c:
		selected_list = json.load(c)
	for user_list in selected_list['channellist']:
		if 'contentId' in user_list: check = 'valid'
	if check == 'valid': return True
	else: return False
	
def create_xml_channels():
	log('{} {}'.format(provider,loc(32362)), xbmc.LOGINFO)
	with open(simpliAT_chlist_selected, 'r', encoding='utf-8') as c:
		selected_list = json.load(c)
	items_to_download = str(len(selected_list['channellist']))
	items = 0
	pDialog = xbmcgui.DialogProgressBG()
	pDialog.create('{} {} '.format(loc(32502),provider), '{} {}'.format('100',loc(32501)))
	## Create XML Channels Provider information
	xml_structure.xml_channels_start(provider)
	for user_item in selected_list['channellist']:
		items += 1
		percent_remain = int(100) - int(items) * int(100) / int(items_to_download)
		percent_completed = int(100) * int(items) / int(items_to_download)
		channel_name = user_item['name']
		channel_icon = user_item['pictures'][0]['href']
		channel_id = channel_name
		pDialog.update(int(percent_completed), '{} {} '.format(loc(32502),channel_name),'{} {} {}'.format(int(percent_remain),loc(32501),provider))
		if str(percent_completed) == str(100):
			log('{} {}'.format(provider,loc(32364)), xbmc.LOGINFO)
		## Create XML Channel Information with provided Variables
		xml_structure.xml_channels(channel_name, channel_id, channel_icon, lang)
	pDialog.close()

def get_epg(contentID):
	starttime, endtime = get_epgLength(days_to_grab)
	epg_url = "https://api.app.simplitv.at/v1/EpgTile/FilterProgramTiles"
	epg_post = {"platformCodename": "www", "from": starttime, "to": endtime}
	epg_resp = requests.post(epg_url, headers=header, json=epg_post).json()["programs"]
	prg_url = "https://api.app.simplitv.at/v2/Tile/GetTiles"
	prg_post = {"platformCodename": "www", "requestedTiles": [{"id": a["id"]} for i in epg_resp.keys() for a in epg_resp[i] if i == contentID]}
	return requests.post(prg_url, headers=header, json=prg_post).json()["tiles"]
	
def create_xml_broadcast(enable_rating_mapper):
	contentIDs, channel_names = [], {}
	log('{} {}'.format(provider, loc(32365)), xbmc.LOGINFO)
	with open(simpliAT_chlist_selected, 'r', encoding='utf-8') as c:
		selected_list = json.load(c)
	for user_item in selected_list['channellist']:
		contentID = user_item['contentId']
		channel_names[contentID] = user_item['name']
		contentIDs.append(contentID)
	xml_structure.xml_broadcast_start(provider)
	with ThreadPoolExecutor(len(contentIDs)) as executor:
		future_to_url = {executor.submit(get_epg, contentID):contentID for contentID in contentIDs}
		for future in as_completed(future_to_url):
			contentID = future_to_url[future]
			channel_id = channel_names[contentID]
			for program in future.result():
				item_starttime=program["start"].split('+')[0].replace("-", "").replace("T", "").replace(":", "")
				item_endtime = program["stop"].split('+')[0].replace("-", "").replace("T", "").replace(":", "")
				items_genre = program['categories'][-1]['name'] if len(program.get("categories", [])) > 0 else ""
				item_country = ', '.join([i['name'] for i in program['countries']]) if len(program.get("countries", [])) > 0 else ""
				item_description = program.get("description").replace("\n\n", "")
				item_title = program.get("title", "")
				try: item_picture = program["images"][0]["url"]
				except: item_picture = ""
				item_season = program.get('seasonNumber', "")
				item_episode = program.get("episodeNumber", "")
				item_subtitle = program.get("subTitle", "")
				item_date = program["date"] if program.get("date", 0) != 0 else ""
				item_agerating, item_starrating, items_director, items_producer, items_actor = "", "", "", "", ""
				actor, director, producer = [], [], []
				if len(program.get("people", [])) > 0:
					c = {}
					for i in program["people"]:
						if i["roleName"] == "Regie":
							director.append(i["fullName"])
						elif i["roleName"] == "Produzent":
							producer.append(i["fullName"])
						else:
							actor.append(i["fullName"])
				items_director = ', '.join(director)
				items_producer = ', '.join(producer)
				items_actor = ', '.join(actor)
				## Create XML Broadcast Information with provided Variables
				xml_structure.xml_broadcast(episode_format, channel_id, item_title, item_starttime, item_endtime,item_description, item_country, item_picture, item_subtitle,items_genre,item_date, item_season, item_episode, item_agerating, item_starrating, items_director,items_producer, items_actor, enable_rating_mapper, lang)
	notify(addon_name, '{} {} {}'.format(loc(32370),provider,loc(32371)), icon=xbmcgui.NOTIFICATION_INFO)
	
def check_provider():
	## Create empty (Selected) Channel List if not exist
	if not os.path.isfile(simpliAT_chlist_selected):
		with open((simpliAT_chlist_selected), 'w', encoding='utf-8') as selected_list:
			selected_list.write(json.dumps({"channellist": []}))
		## If no Channellist exist, ask to create one
		yn = OSD.yesno(provider, loc(32405))
		if yn: select_channels()
		else:
			xbmcvfs.delete(simpliAT_chlist_selected)
			return False
	## If a Selected list exist, check valid
	valid = check_selected_list()
	if valid is False:
		yn = OSD.yesno(provider, loc(32405))
		if yn: select_channels()
		else:
			xbmcvfs.delete(simpliAT_chlist_selected)
			return False
	return True
	
def startup():
	if check_provider():
		get_channellist()
		return True
	else: return False
# Channel Selector
try:
	if sys.argv[1] == 'select_channels_simpliAT': select_channels()
except IndexError: pass