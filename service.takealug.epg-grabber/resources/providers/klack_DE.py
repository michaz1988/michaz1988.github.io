# -*- coding: utf-8 -*-
import xbmc, xbmcaddon, xbmcgui, xbmcvfs, json, os, sys, requests, re, urllib, hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
import concurrent.futures
from resources.lib import xml_structure, channel_selector, mapper, filesplit

provider = 'KLACK (DE)'
lang = 'de'
ADDON = xbmcaddon.Addon(id="service.takealug.epg-grabber")
addon_name = ADDON.getAddonInfo('name')
addon_version = ADDON.getAddonInfo('version')
loc = ADDON.getLocalizedString
datapath = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))

## Read klackDE Settings
days_to_grab = int(ADDON.getSetting('days_to_grab'))
episode_format = ADDON.getSetting('episode_format')
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
klackDE_chlist_selected = os.path.join(datapath, 'chlist_klackDE_selected.json')
klackDE_header = {'User-Agent': 'PIT-Klack-Android/18', 'Accept-Encoding': 'gzip'}

def get_channellist():
	temp = []
	klackDE_channels = requests.get('https://mobile.klack.de/appdata?appVersion=104&bundleId=proofit.klack.phone', headers=klackDE_header).json()["channels"]
	for channels in klackDE_channels: temp.append({"contentId": channels['id'],"name": channels['name'],"pictures": [{"href": "https://imagesmobile.klack.de/images/stories/stations/app/svg/"+ channels['imgActive']}]})
	return {"channellist": sorted(temp, key=lambda x: x["name"])}
		
def select_channels():
	## Create empty (Selected) Channel List if not exist
	if not os.path.isfile(klackDE_chlist_selected):
		with open((klackDE_chlist_selected), 'w', encoding='utf-8') as selected_list:
			selected_list.write(json.dumps({"channellist": []}))
	## Download chlist_klackDE_provider.json
	provider_list = get_channellist()
	dialog = xbmcgui.Dialog()
	with open(klackDE_chlist_selected, 'r', encoding='utf-8') as s:
		selected_list = json.load(s)
	## Start Channel Selector
	user_select = channel_selector.select_channels(provider, provider_list, selected_list)
	if user_select is not None:
		with open(klackDE_chlist_selected, 'w', encoding='utf-8') as f:
			json.dump(user_select, f, indent=4)
		if os.path.isfile(klackDE_chlist_selected):
			valid = check_selected_list()
			if valid is True:
				ok = dialog.ok(provider, loc(32402))
				if ok: log(loc(32402), xbmc.LOGINFO)
			elif valid is False:
				log(loc(32403), xbmc.LOGINFO)
				yn = OSD.yesno(provider, loc(32403))
				if yn: select_channels()
				else:
					xbmcvfs.delete(klackDE_chlist_selected)
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
				xbmcvfs.delete(klackDE_chlist_selected)
				exit()
				
def check_selected_list():
	check = 'invalid'
	with open(klackDE_chlist_selected, 'r', encoding='utf-8') as c:
		selected_list = json.load(c)
	for user_list in selected_list['channellist']:
		if 'contentId' in user_list: check = 'valid'
	if check == 'valid': return True
	else: return False

def get_url(params):
	todo = "getProgramByChannel" if "date" in params else "getBroadcastDetails"
	hash_input = 'Kdfdfk599smd83x0LLacde27khF84Dn87sj3JJhdlooe%s%s' % (todo, params)
	key = hashlib.sha256(hash_input.encode('utf-8')).hexdigest()
	param = urllib.parse.quote(params)
	return "https://mobile.klack.de/api/Android/2/%s.json?checksum=%s&params=%s" % (todo, key, param)

def download_day(day_to_grab, ids):
    broadcast_files = {}
    params = '{"date":%s,"channels":%s}' % (day_to_grab, ids)
    try:
        response = requests.get(get_url(params)).json()
        for a in response:
            broad = [b["id"] for b in a["broadcasts"]]
            if not broad:
                continue
            params = '{"broadcasts":%s}' % broad
            details = requests.get(get_url(params)).json()
            for t in details:
                if t["n"] not in broadcast_files:
                    broadcast_files[t["n"]] = []
                broadcast_files[t["n"]].append(t)
    except Exception as e:
        log(f'Error processing day {day_to_grab}: {e}', xbmc.LOGERROR)
    return broadcast_files

def download_thread():
    broadcast_files = {}
    with open(klackDE_chlist_selected, 'r', encoding='utf-8') as s:
        selected_list = json.load(s)['channellist']
    ids = [item['contentId'] for item in selected_list]

    day_to_start = datetime(today.year, today.month, today.day, hour=0, minute=0, second=1)
    days = [int(datetime.timestamp(day_to_start + timedelta(days=i))) for i in range(days_to_grab)]

    with ThreadPoolExecutor(max_workers=len(selected_list)) as executor:  # Du kannst die Zahl anpassen
        futures = {executor.submit(download_day, day, ids): day for day in days}
        for future in as_completed(futures):
            result = future.result()
            for key, value in result.items():
                if key not in broadcast_files:
                    broadcast_files[key] = []
                broadcast_files[key].extend(value)

    return broadcast_files
	
def create_xml_channels():
	log('{} {}'.format(provider,loc(32362)), xbmc.LOGINFO)
	with open(klackDE_chlist_selected, 'r', encoding='utf-8') as c:
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

def create_xml_broadcast(enable_rating_mapper):
	log('{} {}'.format(provider,loc(32365)), xbmc.LOGINFO)
	with open(klackDE_chlist_selected, 'r', encoding='utf-8') as c:
		selected_list = json.load(c)
	## Create XML Broadcast Provider information
	broadcast_files = download_thread()
	xml_structure.xml_broadcast_start(provider)
	for user_item in selected_list['channellist']:
		contentID = user_item['contentId']
		channel_name = user_item['name']
		for playbilllist in broadcast_files[contentID]:
			try:
				item_title = playbilllist.get('title', "")
				item_starttime = playbilllist.get('startTime', "")
				item_endtime = playbilllist.get('z', "")
				item_description = ""
				if playbilllist.get('o'):
					 item_description = playbilllist.get('o')+"\n"
				if playbilllist.get('H',""):
					item_description += '\n'.join(playbilllist.get('H',""))
				item_country = playbilllist.get('u', "")
				item_picture = playbilllist.get('w', "")
				item_subtitle = playbilllist.get('E', "")
				items_genre = playbilllist.get('t', "")
				item_date = playbilllist.get('v', "")
				item_season = playbilllist.get('B', "")
				item_episode = playbilllist.get('C', "")
				item_agerating = playbilllist.get('K', "")
				ad = playbilllist.get('G')
				items_director, items_actor = "", ""
				director_list, actor_list = [], []
				if ad:
					for key , value in dict(zip(ad[::2], ad[1::2])).items():
						if value == "Regie": director_list.append(key)
						else: actor_list.append(f"{key} als {value}")
					items_actor = ','.join(actor_list)
					items_director = ','.join(director_list)
				items_producer, item_starrating = "", ""
				item_starttime = datetime.utcfromtimestamp(item_starttime).strftime('%Y%m%d%H%M%S')
				item_endtime = datetime.utcfromtimestamp(item_endtime).strftime('%Y%m%d%H%M%S')
				if item_episode: item_episode = re.sub(r"\D+", '#', item_episode).split('#')[0]
				if item_season: item_season = re.sub(r"\D+", '#', item_season).split('#')[0]
				if not item_description: item_description = 'No Program Information available'
				xml_structure.xml_broadcast(episode_format, channel_name, item_title, item_starttime, item_endtime,item_description, item_country, item_picture, item_subtitle,items_genre, item_date, item_season, item_episode, item_agerating, item_starrating, items_director,items_producer, items_actor, enable_rating_mapper, lang)
			except (KeyError, IndexError):
				log('{} {} {} {} {} {}'.format(provider, loc(32367), channel_name, loc(32368), contentID,loc(32369)))
	notify(addon_name, '{} {} {}'.format(loc(32370),provider,loc(32371)), icon=xbmcgui.NOTIFICATION_INFO)
	
def check_provider():
	## Create empty (Selected) Channel List if not exist
	if not os.path.isfile(klackDE_chlist_selected):
		with open((klackDE_chlist_selected), 'w', encoding='utf-8') as selected_list:
			selected_list.write(json.dumps({"channellist": []}))
		## If no Channellist exist, ask to create one
		yn = OSD.yesno(provider, loc(32405))
		if yn: select_channels()
		else:
			xbmcvfs.delete(klackDE_chlist_selected)
			return False
	## If a Selected list exist, check valid
	valid = check_selected_list()
	if valid is False:
		yn = OSD.yesno(provider, loc(32405))
		if yn: select_channels()
		else:
			xbmcvfs.delete(klackDE_chlist_selected)
			return False
	return True
	
def startup():
	if check_provider():
		get_channellist()
		return True
	else: return False
# Channel Selector
try:
	if sys.argv[1] == 'select_channels_klackDE': select_channels()
except IndexError: pass