# -*- coding: utf-8 -*-
import time, tools, os, io, json, re, sys, requests
from tools import datapath, temppath, log, notify, addon_name, addon_version, loc
from datetime import date, datetime, timedelta
import socket
from collections import Counter
import xml_structure
import magenta_DE
import tvspielfilm_DE
#import swisscom_CH
#import horizon
#import zattoo
import platform
import importlib
tools.delete(os.path.join(datapath, 'log.txt'))
thread_temppath = os.path.join(temppath, "multithread")
machine = platform.machine()

## Read Global Settings
storage_path = os.path.join(datapath, "storage")
tools.makedir(storage_path)
auto_download = False
timeswitch_1 = 0
timeswitch_2 = 0
timeswitch_3 = 0
enable_rating_mapper = False
use_local_sock = False
tvh_local_sock = ""
download_threads = 5
enable_multithread = False


## Get Enabled Grabbers
# Divers
enable_grabber_magentaDE = True
enable_grabber_tvsDE = True
enabled_grabber = True
guide_temp = os.path.join(datapath, 'guide.xml')
guide_dest = os.path.join(os.path.dirname(datapath), 'guide.xml.gz')
grabber_cron = os.path.join(datapath, 'grabber_cron.json')
grabber_cron_tmp = os.path.join(temppath, 'grabber_cron.json')
xmltv_dtd = os.path.join(datapath, 'xmltv.dtd')


def copy_guide_to_destination():
	tools.copy(guide_temp, os.path.join(os.path.dirname(datapath), 'guide.xml'))
	done = tools.comp(guide_temp, guide_dest)
	if done:
		try:
			tools.delete(guide_temp)
			tools.delete(os.path.join(datapath, '__pycache__'))
			tools.delete(storage_path)
			## Write new setting last_download
			with open(grabber_cron, 'r', encoding='utf-8') as f:
				data = json.load(f)
				data['last_download'] = str(int(time.time()))

			with open(grabber_cron_tmp, 'w', encoding='utf-8') as f:
				json.dump(data, f, indent=4)

			## rename temporary file replacing old file
			tools.copy(grabber_cron_tmp, grabber_cron)
			time.sleep(3)
			tools.delete(grabber_cron_tmp)
			notify(addon_name, loc(32350))
			log(loc(32350))
		except:
			log('Worker can´t read cron File, creating new File...'.format(loc(32356)))
			with open(grabber_cron, 'w', encoding='utf-8') as f:
				f.write(json.dumps({'last_download': str(int(time.time())), 'next_download': str(int(time.time()) + 86400)}))
			notify(addon_name, loc(32350))
			log(loc(32350))
	else:
		notify(addon_name, loc(32351))
		log(loc(32351))

def check_channel_dupes():
	with open(guide_temp, encoding='utf-8') as f:
		c = Counter(c.strip() for c in f if c.strip())  # for case-insensitive search
		dupe = []
		for line in c:
			if c[line] > 1:
				if ('display-name' in line or 'icon src' in line or '</channel' in line):
					pass
				else:
					dupe.append(line + '\n')
		dupes = ''.join(dupe)

		if (not dupes == ''):
			log('{} {}'.format(loc(32400), dupes))
			ok = True
			if ok:
				return False
			return False
		else:
			return True

def run_grabber():
	tools.delete(os.path.join(datapath, 'log.txt'))
	if check_startup():
		importlib.reload(xml_structure)
		importlib.reload(magenta_DE)
		importlib.reload(tvspielfilm_DE)
		xml_structure.xml_start()
		xml_structure.xml_channels_start('ZAPPN')
		xml_structure.xml_channels('PULS24', 'PULS24', 'https://upload.wikimedia.org/wikipedia/commons/thumb/2/2f/PULS24logo.png/640px-PULS24logo.png', 'de')
		xml_structure.xml_channels('ServusTV', 'ServusTV', 'https://upload.wikimedia.org/wikipedia/commons/thumb/3/37/ServusTV_Logo.png/640px-ServusTV_Logo.png', 'de')
		if enable_grabber_magentaDE:
			if magenta_DE.startup():
				magenta_DE.create_xml_channels()
		if enable_grabber_tvsDE:
			if tvspielfilm_DE.startup():
				tvspielfilm_DE.create_xml_channels()

		# Check for Channel Dupes
		if check_channel_dupes():

			## Create XML Broadcast
			api_headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/110.0', 'Content-type': 'application/json;charset=utf-8', 'X-Api-Date-Format': 'iso', 'X-Api-Camel-Case': 'true', 'referer': 'https://streaming.simplitv.at/'}
			data_headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/110.0', 'Accept': 'application/json'}
			time_start = str(datetime.now().strftime("%Y-%m-%dT%H:%M:00.000Z"))
			time_end = str((datetime.now() + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:00.000Z"))
			epg_url = "https://api.app.simplitv.at/v1/EpgTile/FilterProgramTiles?$headers=%7B%22Content-Type%22:%22application%2Fjson%3Bcharset%3Dutf-8%22,%22X-Api-Date-Format%22:%22iso%22,%22X-Api-Camel-Case%22:true%7D"
			epg_post = json.dumps({"platformCodename": "www", "from": time_start, "to": time_end})
			epg_resp = requests.post(epg_url, timeout=5, headers=api_headers, data=epg_post, allow_redirects=False).json()["programs"]
			prg_url = "https://api.app.simplitv.at/v2/Tile/GetTiles?$headers=%7B%22Content-Type%22:%22application%2Fjson%3Bcharset%3Dutf-8%22,%22X-Api-Date-Format%22:%22iso%22,%22X-Api-Camel-Case%22:true%7D"
			prg_post = json.dumps({"platformCodename": "www", "requestedTiles": [{"id": a["id"]} for i in epg_resp.keys() for a in epg_resp[i] if i == "puls24"]})
			epg_data = requests.post(prg_url, timeout=5, headers=api_headers, data=prg_post, allow_redirects=False).json()["tiles"]
			for program in epg_data:
				item_starttime = datetime.strptime(program["start"].split('+')[0], '%Y-%m-%dT%H:%M:%S').strftime('%Y%m%d%H%M%S')
				item_endtime = datetime.strptime(program["stop"].split('+')[0], '%Y-%m-%dT%H:%M:%S').strftime('%Y%m%d%H%M%S')
				items_genre = program['categories'][-1]['name'] if len(program.get("categories", [])) > 0 else ""
				item_country = ', '.join([i['name'] for i in program['countries']]) if len(program.get("countries", [])) > 0 else ""
				item_description = program.get("description", "").replace("\n\n", "")
				item_title = program.get("title", "")
				try: item_picture = program["images"][0]["url"]
				except: item_picture = ""
				item_season = program.get('seasonNumber', "")
				item_episode = program.get("episodeNumber", "")
				item_subtitle = program.get("subTitle", "")
				item_date = program["date"] if program.get("date", 0) != 0 else ""
				item_agerating, item_starrating, items_director, items_producer = "", "", "", ""
				if len(program.get("people", [])) > 0:
					c = {}
					for i in program["people"]:
						if not c.get('[B]'+i["roleName"]+'[/B]', False):
							c['[B]'+i["roleName"]+'[/B]'] = []
						c['[B]'+i["roleName"]+'[/B]'].append(i["fullName"])
					items_actor = '; '.join([i+': '+', '.join([a for a in c[i]]) for i in c.keys()])
				else: items_actor = ""
				xml_structure.xml_broadcast('onscreen', "PULS24", item_title, item_starttime, item_endtime, item_description, item_country, item_picture, item_subtitle, items_genre, item_date, item_season, item_episode, item_agerating, item_starrating, items_director, items_producer, items_actor, False, "de")
			
			prg_post = json.dumps({"platformCodename": "www", "requestedTiles": [{"id": a["id"]} for i in epg_resp.keys() for a in epg_resp[i] if i == "servustv-austria"]})
			epg_data = requests.post(prg_url, timeout=5, headers=api_headers, data=prg_post, allow_redirects=False).json()["tiles"]
			for program in epg_data:
				item_starttime = datetime.strptime(program["start"].split('+')[0], '%Y-%m-%dT%H:%M:%S').strftime('%Y%m%d%H%M%S')
				item_endtime = datetime.strptime(program["stop"].split('+')[0], '%Y-%m-%dT%H:%M:%S').strftime('%Y%m%d%H%M%S')
				items_genre = program['categories'][-1]['name'] if len(program.get("categories", [])) > 0 else ""
				item_country = ', '.join([i['name'] for i in program['countries']]) if len(program.get("countries", [])) > 0 else ""
				item_description = program.get("description", "").replace("\n\n", "")
				item_title = program.get("title", "")
				try: item_picture = program["images"][0]["url"]
				except: item_picture = ""
				item_season = program.get('seasonNumber', "")
				item_episode = program.get("episodeNumber", "")
				item_subtitle = program.get("subTitle", "")
				item_date = program["date"] if program.get("date", 0) != 0 else ""
				item_agerating, item_starrating, items_director, items_producer = "", "", "", ""
				if len(program.get("people", [])) > 0:
					c = {}
					for i in program["people"]:
						if not c.get('[B]'+i["roleName"]+'[/B]', False):
							c['[B]'+i["roleName"]+'[/B]'] = []
						c['[B]'+i["roleName"]+'[/B]'].append(i["fullName"])
					items_actor = '; '.join([i+': '+', '.join([a for a in c[i]]) for i in c.keys()])
				else: items_actor = ""
				xml_structure.xml_broadcast('onscreen', "ServusTV", item_title, item_starttime, item_endtime, item_description, item_country, item_picture, item_subtitle, items_genre, item_date, item_season, item_episode, item_agerating, item_starrating, items_director, items_producer, items_actor, False, "de")
			if enable_grabber_magentaDE:
				if magenta_DE.startup():
					magenta_DE.create_xml_broadcast(enable_rating_mapper, thread_temppath, download_threads)
			if enable_grabber_tvsDE:
				if tvspielfilm_DE.startup():
					tvspielfilm_DE.create_xml_broadcast(enable_rating_mapper, thread_temppath, download_threads)

			## Finish XML
			xml_structure.xml_end()
			copy_guide_to_destination()

def check_internet(host="8.8.8.8", port=53, timeout=3):
	try:
		socket.setdefaulttimeout(timeout)
		socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
		return True
	except socket.error as ex:
		return False

def check_startup():
	#Create Tempfolder if not exist
	tools.makedir(temppath)
	tools.makedir(thread_temppath)

	if storage_path == 'choose':
		notify(addon_name, loc(32359))
		log(loc(32359))
		return False

	if not enabled_grabber:
		notify(addon_name, loc(32360))
		log(loc(32360))
		return False

	if use_local_sock:
		socked_string = '.sock'
		if not re.search(socked_string, tvh_local_sock):
			notify(addon_name, loc(32378))
			log(loc(32378))
			return False

	if enable_multithread:
		#log(machine)
		#log('Multithreading is currently under Kodi 19 broken, please disable it')
		ok = True
		if ok:
			return True
		return False

	## create Crontab File which not exists at first time
	if (not os.path.isfile(grabber_cron) or os.stat(grabber_cron).st_size <= 1):
		with open(grabber_cron, 'w', encoding='utf-8') as f:
			f.write(json.dumps({'last_download': str(int(time.time())), 'next_download': str(int(time.time()) + 86400)}))

	## Clean Tempfiles
	for file in os.listdir(temppath):
		tools.delete(os.path.join(temppath, file))

	## Check internet Connection
	if not check_internet():
		retries = 12
		while retries > 0:
			log(loc(32385))
			notify(addon_name, loc(32385))
			time.sleep(5)
			if check_internet():
				log(loc(32386))
				notify(addon_name, loc(32386))
				return True
			else:
				retries -= 1
		if retries == 0:
			log(loc(32387))
			notify(addon_name, loc(32387))
			return False
	else:
		return True

run_grabber()
