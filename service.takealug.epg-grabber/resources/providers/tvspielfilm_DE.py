# -*- coding: utf-8 -*-
import xbmc, xbmcaddon, xbmcgui, xbmcvfs, json, os, sys, requests, re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from resources.lib import xml_structure, channel_selector, mapper, filesplit

provider = 'TV SPIELFILM (DE)'
lang = 'de'
ADDON = xbmcaddon.Addon(id="service.takealug.epg-grabber")
addon_name = ADDON.getAddonInfo('name')
addon_version = ADDON.getAddonInfo('version')
loc = ADDON.getLocalizedString
datapath = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
temppath = os.path.join(datapath, "temp")
provider_temppath = os.path.join(temppath, "tvsDE")

## MAPPING Variables Thx @ sunsettrack4
tvsDE_genres_url = 'https://raw.githubusercontent.com/sunsettrack4/config_files/master/tvs_genres.json'
tvsDE_genres_json = os.path.join(provider_temppath, 'tvs_genres.json')
tvsDE_channels_url = 'https://raw.githubusercontent.com/sunsettrack4/config_files/master/tvs_channels.json'
tvsDE_channels_json = os.path.join(provider_temppath, 'tvs_channels.json')
## Log Files
tvsDE_genres_warnings_tmp = os.path.join(provider_temppath, 'tvsDE_genres_warnings.txt')
tvsDE_genres_warnings = os.path.join(temppath, 'tvsDE_genres_warnings.txt')
tvsDE_channels_warnings_tmp = os.path.join(provider_temppath, 'tvsDE_channels_warnings.txt')
tvsDE_channels_warnings = os.path.join(temppath, 'tvsDE_channels_warnings.txt')
## Read tvsDE Settings
days_to_grab = int(ADDON.getSetting('days_to_grab'))
episode_format = ADDON.getSetting('episode_format')
channel_format = ADDON.getSetting('tvsDE_channel_format')
genre_format = ADDON.getSetting('tvsDE_genre_format')
# Make a debug logger

def log(message, loglevel=xbmc.LOGDEBUG):
	xbmc.log('[{} {}] {}'.format(addon_name, addon_version, message), loglevel)
	
# Make OSD Notify Messages
OSD = xbmcgui.Dialog()

def notify(title, message, icon=xbmcgui.NOTIFICATION_INFO):
	OSD.notification(title, message, icon)
	
# Calculate Date and Time
today = datetime.today()
## Channel Files
tvsDE_chlist_selected = os.path.join(datapath, 'chlist_tvsDE_selected.json')
tvsDE_header = {"user-agent": "Dart/3.5 (dart:io)",
	"content-type": "application/json",
	"accept-encoding": "gzip"}
				  
def get_channellist():
	temp = []
	tvsDE_channels = requests.get('https://rhea-export.tvspielfilm.de/channels/epg').json()["data"]["data_list"]
	for channels in tvsDE_channels: temp.append({"contentId": channels['id'],"name": channels['name'],"pictures": [{"href":f"https://raw.githubusercontent.com/michaz1988/epg/refs/heads/main/tvs-logos/{channels['id']}.png"}]})
	return {"channellist": sorted(temp, key=lambda x: x["name"])}
		
def select_channels():
	if not os.path.exists(provider_temppath):
		os.makedirs(provider_temppath)
	## Create empty (Selected) Channel List if not exist
	if not os.path.isfile(tvsDE_chlist_selected):
		with open((tvsDE_chlist_selected), 'w', encoding='utf-8') as selected_list:
			selected_list.write(json.dumps({"channellist": []}))
	## Download chlist_tvsDE_provider.json
	provider_list = get_channellist()
	dialog = xbmcgui.Dialog()
	with open(tvsDE_chlist_selected, 'r', encoding='utf-8') as s:
		selected_list = json.load(s)
	## Start Channel Selector
	user_select = channel_selector.select_channels(provider, provider_list, selected_list)
	if user_select is not None:
		with open(tvsDE_chlist_selected, 'w', encoding='utf-8') as f:
			json.dump(user_select, f, indent=4)
		if os.path.isfile(tvsDE_chlist_selected):
			valid = check_selected_list()
			if valid is True:
				ok = dialog.ok(provider, loc(32402))
				if ok: log(loc(32402), xbmc.LOGINFO)
			elif valid is False:
				log(loc(32403), xbmc.LOGINFO)
				yn = OSD.yesno(provider, loc(32403))
				if yn: select_channels()
				else:
					xbmcvfs.delete(tvsDE_chlist_selected)
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
				xbmcvfs.delete(tvsDE_chlist_selected)
				exit()
				
def check_selected_list():
	check = 'invalid'
	with open(tvsDE_chlist_selected, 'r', encoding='utf-8') as c:
		selected_list = json.load(c)
	for user_list in selected_list['channellist']:
		if 'contentId' in user_list: check = 'valid'
	if check == 'valid': return True
	else: return False
		
def create_xml_channels():
	log('{} {}'.format(provider,loc(32362)), xbmc.LOGINFO)
	if channel_format == 'rytec':
		## Save tvsDE_channels.json to Disk
		tvsDE_channels_response = requests.get(tvsDE_channels_url).json()
		with open(tvsDE_channels_json, 'w', encoding='utf-8') as tvsDE_channels:
			json.dump(tvsDE_channels_response, tvsDE_channels)
	with open(tvsDE_chlist_selected, 'r', encoding='utf-8') as c:
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
		## Map Channels
		if channel_id: channel_id = mapper.map_channels(channel_id, channel_format, tvsDE_channels_json, tvsDE_channels_warnings_tmp, lang)
		## Create XML Channel Information with provided Variables
		xml_structure.xml_channels(channel_name, channel_id, channel_icon, lang)
	pDialog.close()
	
#def get_epg(tvs_data_url):
#	k = []
#	for b in requests.post("https://rhea-export.tvspielfilm.de/epg_listing/program_day/channel", headers=tvsDE_header, json=tvs_data_url).json()["data"]["data_list"][0]["broadcasts"]:
#		k.append(requests.get("https://rhea-export.tvspielfilm.de/broadcast/detail/"+str(b["id"])).json()["data"])
#	return k
	
def get_epg(tvs_data_url):
	return requests.post("https://rhea-export.tvspielfilm.de/epg_listing/program_day/channel", headers=tvsDE_header, json=tvs_data_url).json()["data"]["data_list"][0]["broadcasts"]

def create_xml_broadcast(enable_rating_mapper):
	tvs_data_urls, channel_names = [], {}
	log('{} {}'.format(provider,loc(32365)), xbmc.LOGINFO)
	if genre_format == 'eit':
		## Save tvsDE_genres.json to Disk
		tvsDE_genres_response = requests.get(tvsDE_genres_url).json()
		with open(tvsDE_genres_json, 'w', encoding='utf-8') as tvsDE_genres:
			json.dump(tvsDE_genres_response, tvsDE_genres)
	with open(tvsDE_chlist_selected, 'r', encoding='utf-8') as c:
		selected_list = json.load(c)
	for user_item in selected_list['channellist']:
		contentID = user_item['contentId']
		channel_names[contentID] = user_item['name']
		day_to_start = int(time.time())-600
		for i in range(0, days_to_grab):
			tvs_data_urls.append({"channel_id":contentID,"timestamp_selected":day_to_start})
			day_to_start += 86400
	## Create XML Broadcast Provider information
	xml_structure.xml_broadcast_start(provider)
	with ThreadPoolExecutor(len(tvs_data_urls)) as executor:
		future_to_url = {executor.submit(get_epg, tvs_data_url):tvs_data_url for tvs_data_url in tvs_data_urls}
		for future in as_completed(future_to_url):
			contentID = future_to_url[future]["channel_id"]
			o = future.result()
			for playbilllist in o:
				channel_id = channel_names[contentID]
				channel_id = mapper.map_channels(channel_id, channel_format, tvsDE_channels_json, tvsDE_channels_warnings_tmp, lang)
				item_title = playbilllist.get('title')
				item_description = ""
				summary = playbilllist.get('summary', {})
				if summary:
					intro = summary.get('intro')
					body = summary.get('body')
					conclusion = summary.get('conclusion')
					if intro: item_description += intro + "\n"
					if body: item_description += body + "\n"
					if conclusion: item_description += conclusion + "\n"
				if not item_description: item_description =  'No Program Information available'
				production_information = playbilllist.get('production_information', {})
				item_country = ", ".join(production_information.get('countries') or "")
				items_genre = production_information.get('print_genre') or ""
				item_date = production_information.get('year') or ""
				item_subtitle = production_information.get('episode_label') or ""
				cast = production_information.get('cast')
				actor_list = []
				try:
					for a in cast: actor_list.append(a.get('name')+ " als "+ a.get('role'))
					items_actor = ','.join(actor_list)
				except: items_actor =""
				try:
					for label in playbilllist.get('labels', ""):
						if "FSK" in label: item_agerating = label.split()[-1]
				except: item_agerating = ""
				try: item_picture = "https://img.tvspielfilm.de" + playbilllist['images'][0]['relative_path']
				except: item_picture = ""
				items_director = playbilllist.get('director', "")
				item_starrating = ''
				item_starttime = datetime.fromtimestamp(playbilllist['start_time']).strftime('%Y%m%d%H%M%S')
				item_endtime = datetime.fromtimestamp(playbilllist['end_time']).strftime('%Y%m%d%H%M%S')
				try: item_episode = re.sub(r"\D+", '#', playbilllist['episodeNumber']).split('#')[0]
				except: item_episode = ""
				try: item_season = re.sub(r"\D+", '#', playbilllist['seasonNumber']).split('#')[0]
				except: item_season = ""
				items_producer = ''
				xml_structure.xml_broadcast(episode_format, channel_id, item_title, item_starttime, item_endtime,item_description, item_country, item_picture, item_subtitle,items_genre,item_date, item_season, item_episode, item_agerating, item_starrating, items_director,items_producer, items_actor, enable_rating_mapper, lang)
	## Create Channel Warnings Textile
	channel_pull = '\nPlease Create an Pull Request for Missing Rytec Id´s to https://github.com/sunsettrack4/config_files/blob/master/tvs_channels.json\n'
	mapper.create_channel_warnings(tvsDE_channels_warnings_tmp, tvsDE_channels_warnings, provider, channel_pull)
	## Create Genre Warnings Textfile
	genre_pull = '\nPlease Create an Pull Request for Missing EIT Genres to https://github.com/sunsettrack4/config_files/blob/master/tvs_genres.json\n'
	mapper.create_genre_warnings(tvsDE_genres_warnings_tmp, tvsDE_genres_warnings, provider, genre_pull)
	notify(addon_name, '{} {} {}'.format(loc(32370),provider,loc(32371)), icon=xbmcgui.NOTIFICATION_INFO)
	log('{} {} {}'.format(loc(32370),provider,loc(32371), xbmc.LOGINFO))
	if (os.path.isfile(tvsDE_channels_warnings) or os.path.isfile(tvsDE_genres_warnings)):
		notify(provider, '{}'.format(loc(32372)), icon=xbmcgui.NOTIFICATION_WARNING)
	## Delete old Tempfiles, not needed any more
	
def check_provider():
	## Create Provider Temppath if not exist
	if not os.path.exists(provider_temppath):
		os.makedirs(provider_temppath)
	## Create empty (Selected) Channel List if not exist
	if not os.path.isfile(tvsDE_chlist_selected):
		with open((tvsDE_chlist_selected), 'w', encoding='utf-8') as selected_list:
			selected_list.write(json.dumps({"channellist": []}))
		## If no Channellist exist, ask to create one
		yn = OSD.yesno(provider, loc(32405))
		if yn: select_channels()
		else:
			xbmcvfs.delete(tvsDE_chlist_selected)
			return False
	## If a Selected list exist, check valid
	valid = check_selected_list()
	if valid is False:
		yn = OSD.yesno(provider, loc(32405))
		if yn: select_channels()
		else:
			xbmcvfs.delete(tvsDE_chlist_selected)
			return False
	return True
	
def startup():
	if check_provider():
		get_channellist()
		return True
	else: return False
# Channel Selector
try:
	if sys.argv[1] == 'select_channels_tvsDE': select_channels()
except IndexError: pass