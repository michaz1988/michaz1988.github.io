# -*- coding: utf-8 -*-
import xbmc, xbmcaddon, xbmcgui, xbmcvfs, json, os, sys, requests, re, uuid
import requests.cookies
import requests.adapters
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from resources.lib import xml_structure, channel_selector, mapper, filesplit

provider = 'MAGENTA TV (DE)'
lang = 'de'

ADDON = xbmcaddon.Addon(id="service.takealug.epg-grabber")
addon_name = ADDON.getAddonInfo('name')
addon_version = ADDON.getAddonInfo('version')
loc = ADDON.getLocalizedString
datapath = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
temppath = os.path.join(datapath, "temp")
provider_temppath = os.path.join(temppath, "magentaDE")

## MAPPING Variables Thx @ sunsettrack4
tkm_genres_url = 'https://raw.githubusercontent.com/sunsettrack4/config_files/master/tkm_genres.json'
tkm_genres_json = os.path.join(provider_temppath, 'tkm_genres.json')
tkm_channels_url = 'https://raw.githubusercontent.com/sunsettrack4/config_files/master/tkm_channels.json'
tkm_channels_json = os.path.join(provider_temppath, 'tkm_channels.json')

## Log Files
magentaDE_genres_warnings_tmp = os.path.join(provider_temppath, 'magentaDE_genres_warnings.txt')
magentaDE_genres_warnings = os.path.join(temppath, 'magentaDE_genres_warnings.txt')
magentaDE_channels_warnings_tmp = os.path.join(provider_temppath, 'magentaDE_channels_warnings.txt')
magentaDE_channels_warnings = os.path.join(temppath, 'magentaDE_channels_warnings.txt')

## Read Magenta DE Settings
days_to_grab = int(ADDON.getSetting('days_to_grab'))
episode_format = ADDON.getSetting('episode_format')
channel_format = ADDON.getSetting('magentaDE_channel_format')
genre_format = ADDON.getSetting('magentaDE_genre_format')


# Make a debug logger
def log(message, loglevel=xbmc.LOGDEBUG):
	xbmc.log('[{} {}] {}'.format(addon_name, addon_version, message), loglevel)


# Make OSD Notify Messages
OSD = xbmcgui.Dialog()

## Session UUID
mac = str(uuid.uuid4())
ter = str(uuid.uuid4())

def notify(title, message, icon=xbmcgui.NOTIFICATION_INFO):
	OSD.notification(title, message, icon)

def get_epgLength(days_to_grab):
	# Calculate Date and Time
	today = datetime.today()
	calc_today = datetime(today.year, today.month, today.day, hour=00, minute=00, second=1)
	calc_then = datetime(today.year, today.month, today.day, hour=23, minute=59, second=59)
	calc_then += timedelta(days=days_to_grab)
	starttime = calc_today.strftime("%Y%m%d%H%M%S")
	endtime = calc_then.strftime("%Y%m%d%H%M%S")
	return starttime, endtime

## Channel Files
magentaDE_chlist_selected = os.path.join(datapath, 'chlist_magentaDE_selected.json')
magentaDE_authenticate_url = 'https://api.prod.sngtv.magentatv.de/EPG/JSON/Authenticate'
magentaDE_channellist_url = 'https://api.prod.sngtv.magentatv.de/EPG/JSON/AllChannel'
magentaDE_data_url = 'https://api.prod.sngtv.magentatv.de/EPG/JSON/PlayBillList?userContentFilter=241221015&sessionArea=1&SID=ottall&T=PC_firefox_75'
magentaDE_authenticate = '{"areaid":"1","cnonce":"c4b11948545fb3089720dd8b12c81f8e","mac":"'+mac+'","preSharedKeyID":"NGTV000001","subnetId":"4901","templatename":"NGTV","terminalid":"'+ter+'","terminaltype":"WEB-MTV","terminalvendor":"WebTV","timezone":"UTC","usergroup":"-1","userType":3,"utcEnable":1}'
magentaDE_get_chlist = {'properties': [{'name': 'logicalChannel','include': '/channellist/logicalChannel/contentId,/channellist/logicalChannel/name,/channellist/logicalChannel/pictures/picture/imageType,/channellist/logicalChannel/pictures/picture/href'}],'metaDataVer': 'Channel/1.1', 'channelNamespace': '2','filterlist': [{'key': 'IsHide', 'value': '-1'}], 'returnSatChannel': '0'}
magentaDE_header = {'Host': 'api.prod.sngtv.magentatv.de',
					'origin': 'https://web.magentatv.de',
					'referer': 'https://web.magentatv.de/',
					'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36',
					'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
					'Accept-Language': 'de,en-US;q=0.7,en;q=0.3',
					'Accept-Encoding': 'gzip, deflate, br',
					'Connection': 'keep-alive',
					'Upgrade-Insecure-Requests': '1'}

def magentaDE_session():
	x = 0
	while x < 120:
		session = requests.Session()
		t = session.post(magentaDE_authenticate_url, timeout=5, data=magentaDE_authenticate, headers=magentaDE_header)
		if t.json().get("retcode", "0") == "-2":
			time.sleep(0.1)
			x = x + 1
			continue
		else: break
	session.headers.update({'X_CSRFToken': session.cookies["CSRFSESSION"]})
	return session

## Get channel list(url)
def get_channellist():
	temp = []
	session = magentaDE_session()
	magentaDE_channels = session.post(magentaDE_channellist_url, data=json.dumps(magentaDE_get_chlist),headers=magentaDE_header).json()
	for channels in magentaDE_channels['channellist']:
		ch_id = channels['contentId']
		ch_title = channels['name']
		for image in channels['pictures']:
			if image['imageType'] == '15':
				hdimage = image['href']
		# channel to be appended
		temp.append({"contentId": ch_id,"name": ch_title, "pictures": [{"href": hdimage}]})
	return {"channellist": sorted(temp, key=lambda x: x["name"])}

def select_channels():
	if not os.path.exists(provider_temppath):
		os.makedirs(provider_temppath)
	## Create empty (Selected) Channel List if not exist
	if not os.path.isfile(magentaDE_chlist_selected):
		with open((magentaDE_chlist_selected), 'w', encoding='utf-8') as selected_list:
			selected_list.write(json.dumps({"channellist": []}))
	## Download chlist_magentaDE_provider.json
	provider_list = get_channellist()
	dialog = xbmcgui.Dialog()
	with open(magentaDE_chlist_selected, 'r', encoding='utf-8') as s:
		selected_list = json.load(s)
	## Start Channel Selector
	user_select = channel_selector.select_channels(provider, provider_list, selected_list)
	if user_select is not None:
		with open(magentaDE_chlist_selected, 'w', encoding='utf-8') as f:
			json.dump(user_select, f, indent=4)
		if os.path.isfile(magentaDE_chlist_selected):
			valid = check_selected_list()
			if valid is True:
				ok = dialog.ok(provider, loc(32402))
				if ok: log(loc(32402), xbmc.LOGINFO)
			elif valid is False:
				log(loc(32403), xbmc.LOGINFO)
				yn = OSD.yesno(provider, loc(32403))
				if yn: select_channels()
				else:
					xbmcvfs.delete(magentaDE_chlist_selected)
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
				xbmcvfs.delete(magentaDE_chlist_selected)
				exit()

def check_selected_list():
	check = 'invalid'
	with open(magentaDE_chlist_selected, 'r', encoding='utf-8') as c:
		selected_list = json.load(c)
	for user_list in selected_list['channellist']:
		if 'contentId' in user_list: check = 'valid'
	if check == 'valid': return True
	else: return False

def create_xml_channels():
	log('{} {}'.format(provider,loc(32362)), xbmc.LOGINFO)
	if channel_format == 'rytec':
		## Save magentaDE_channels.json to Disk
		tkm_channels_response = requests.get(tkm_channels_url).json()
		with open(tkm_channels_json, 'w', encoding='utf-8') as tkm_channels:
			json.dump(tkm_channels_response, tkm_channels)
	with open(magentaDE_chlist_selected, 'r', encoding='utf-8') as c:
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
		channel_id = mapper.map_channels(channel_id, channel_format, tkm_channels_json, magentaDE_channels_warnings_tmp, lang)
		## Create XML Channel Information with provided Variables
		xml_structure.xml_channels(channel_name, channel_id, channel_icon, lang)
	pDialog.close()

def get_epg(contentID):
	starttime, endtime = get_epgLength(days_to_grab)
	session = magentaDE_session()
	magentaDE_data = {'channelid': contentID, 'type': '2', 'offset': '0', 'count': '-1', 'isFillProgram': '1','properties': '[{"name":"playbill","include":"ratingForeignsn,id,channelid,name,subName,starttime,endtime,cast,casts,country,producedate,ratingid,pictures,type,introduce,foreignsn,seriesID,genres,subNum,seasonNum"}]','endtime': endtime, 'begintime': starttime}
	return session.post(magentaDE_data_url, json=magentaDE_data, headers=magentaDE_header).json()['playbilllist']
	
def create_xml_broadcast(enable_rating_mapper):
	contentIDs, channel_names = [], {}
	log('{} {}'.format(provider, loc(32365)), xbmc.LOGINFO)
	if genre_format == 'eit':
		## Save tkm_genres.json to Disk
		tkm_genres_response = requests.get(tkm_genres_url).json()
		with open(tkm_genres_json, 'w', encoding='utf-8') as tkm_genres:
			json.dump(tkm_genres_response, tkm_genres)
	with open(magentaDE_chlist_selected, 'r', encoding='utf-8') as c:
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
			channel_id = mapper.map_channels(channel_id, channel_format, tkm_channels_json, magentaDE_channels_warnings_tmp, lang)
			o = future.result()
			for playbilllist in o:
				item_title = playbilllist.get('name', "")
				item_starttime = playbilllist.get('starttime', "")
				item_endtime = playbilllist.get('endtime', "")
				item_description = playbilllist.get('introduce', "")
				item_country = playbilllist.get('country', "")
				try: item_picture = playbilllist['pictures'][1]['href']
				except (KeyError, IndexError): item_picture = ''
				item_subtitle = playbilllist.get('subName', "")
				items_genre = playbilllist.get('genres', "")
				item_date = playbilllist.get('producedate', "")
				item_season = playbilllist.get('seasonNum', "")
				item_episode = playbilllist.get('subNum', "")
				item_agerating = playbilllist.get('ratingid', "")
				try: items_director = playbilllist['cast']['director']
				except (KeyError, IndexError): items_director = ''
				try: items_producer = playbilllist['cast']['producer']
				except (KeyError, IndexError): items_producer = ''
				try: items_actor = playbilllist['cast']['actor']
				except (KeyError, IndexError): items_actor = ''
				item_starrating = ''
				if item_date:
					item_date = item_date.split('-')
					item_date = item_date[0]
				if item_starttime and item_endtime:
					start = item_starttime.split(' UTC')
					item_starttime = start[0].replace(' ', '').replace('-', '').replace(':', '')
					stop = item_endtime.split(' UTC')
					item_endtime = stop[0].replace(' ', '').replace('-', '').replace(':', '')
				if item_country: item_country = item_country.upper()
				if item_agerating == '-1': item_agerating = ''
				# Map Genres
				if not items_genre == '': items_genre = mapper.map_genres(items_genre, genre_format, tkm_genres_json, magentaDE_genres_warnings_tmp, lang)
				## Create XML Broadcast Information with provided Variables
				xml_structure.xml_broadcast(episode_format, channel_id, item_title, item_starttime, item_endtime,item_description, item_country, item_picture, item_subtitle,items_genre,item_date, item_season, item_episode, item_agerating, item_starrating, items_director,items_producer, items_actor, enable_rating_mapper, lang)

	## Create Channel Warnings Textile
	channel_pull = '\nPlease Create an Pull Request for Missing Rytec Id´s to https://github.com/sunsettrack4/config_files/blob/master/tkm_channels.json\n'
	mapper.create_channel_warnings(magentaDE_channels_warnings_tmp, magentaDE_channels_warnings, provider, channel_pull)
	## Create Genre Warnings Textfile
	genre_pull = '\nPlease Create an Pull Request for Missing EIT Genres to https://github.com/sunsettrack4/config_files/blob/master/tkm_genres.json\n'
	mapper.create_genre_warnings(magentaDE_genres_warnings_tmp, magentaDE_genres_warnings, provider, genre_pull)
	notify(addon_name, '{} {} {}'.format(loc(32370),provider,loc(32371)), icon=xbmcgui.NOTIFICATION_INFO)
	log('{} {} {}'.format(loc(32370),provider,loc(32371), xbmc.LOGINFO))
	xbmc.sleep(4000)
	if (os.path.isfile(magentaDE_channels_warnings) or os.path.isfile(magentaDE_genres_warnings)):
		notify(provider, '{}'.format(loc(32372)), icon=xbmcgui.NOTIFICATION_WARNING)
		xbmc.sleep(3000)

def check_provider():
	## Create Provider Temppath if not exist
	if not os.path.exists(provider_temppath):
		os.makedirs(provider_temppath)
	## Create empty (Selected) Channel List if not exist
	if not os.path.isfile(magentaDE_chlist_selected):
		with open((magentaDE_chlist_selected), 'w', encoding='utf-8') as selected_list:
			selected_list.write(json.dumps({"channellist": []}))
		## If no Channellist exist, ask to create one
		yn = OSD.yesno(provider, loc(32405))
		if yn: select_channels()
		else:
			xbmcvfs.delete(magentaDE_chlist_selected)
			return False
	## If a Selected list exist, check valid
	valid = check_selected_list()
	if valid is False:
		yn = OSD.yesno(provider, loc(32405))
		if yn: select_channels()
		else:
			xbmcvfs.delete(magentaDE_chlist_selected)
			return False
	return True
	
def startup():
	if check_provider():
		get_channellist()
		return True
	else: return False
# Channel Selector
try:
	if sys.argv[1] == 'select_channels_magentaDE': select_channels()
except IndexError: pass