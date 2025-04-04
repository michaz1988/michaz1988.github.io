import requests, gzip, io, json, time, os, boto3, uuid
from maclist import alllist
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
try: 
    from BeautifulSoup import BeautifulSoup
except ImportError:
    from bs4 import BeautifulSoup
    
datapath = os.path.abspath(os.path.dirname(__file__))
#datapath = "/sdcard/"
mac_list = os.path.join(os.path.dirname(datapath), 'maclist.json')

ACCOUNT_ID = "145ef3f7a9832804bef0e31548db8a83"
DATABASE_API_TOKEN = "13DEJ8ftBLkxoCHzfBU__Pkv0ZyqPLTjvRXXR_qk"
DATABASE_API_URL = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/d1/database/c56590c1-dd25-4d7f-8812-6c6cd1ec69bd/query"
R2_ACCESS_KEY = "4b36152b6b64b8a9f4d7010b84f535fc"
R2_SECRET_KEY = "7ad1ed517b6baa6af2fa00d50a1a18b0ce416bb0b6fb14f4c122a2960f1ab9bc"
R2_BUCKET_NAME = "stbemu"
R2_OBJECT_KEY = "stbemu-db.csv.gz"
R2_ENDPOINT_URL = "https://145ef3f7a9832804bef0e31548db8a83.r2.cloudflarestorage.com"

today = datetime.today()
now = datetime.now()
timestamp = datetime.timestamp(now)

def get_epgLength(days_to_grab, form="%Y-%m-%dT%H:%M:00.000Z"):
	# Calculate Date and Time
	calc_today = datetime(today.year, today.month, today.day, hour=00, minute=00, second=1)
	calc_then = datetime(today.year, today.month, today.day, hour=23, minute=59, second=59)
	calc_then += timedelta(days=days_to_grab)
	starttime = calc_today.strftime(form)
	endtime = calc_then.strftime(form)
	return starttime, endtime


page = requests.get("https://ikracccam.blogspot.com/p/stalker-iptv-ikra_2.html").text
soup = BeautifulSoup(page, 'html.parser')
for tag in soup.find_all('table'):
	u, p, m, e = tag.find_all("th")
	url, port, mac, expire = u.text.strip().rstrip("/").replace(":80/c", "/c").replace("/c", "/portal.php"), p.text.strip(), m.text.strip(), e.text.strip()
	if 'unlimited' in expire:
		if url not in alllist: alllist[url] = []
		if mac not in alllist[url]:
			alllist[url].append(mac)
	else:
		day, month, year = expire.split("-")
		a = datetime(year=int(year), month=int(month), day=int(day), hour=00, minute=00, second=00)
		if datetime.timestamp(a) > timestamp:
			if url not in alllist: alllist[url] = []
			if mac not in alllist[url]:
				alllist[url].append(mac)

s3_client = boto3.client("s3", aws_access_key_id=R2_ACCESS_KEY, aws_secret_access_key=R2_SECRET_KEY, endpoint_url=R2_ENDPOINT_URL)
response = s3_client.get_object(Bucket=R2_BUCKET_NAME, Key=R2_OBJECT_KEY)
gzip_file = gzip.GzipFile(fileobj=response["Body"])
csv_content = gzip_file.read().decode("utf-8").splitlines()
for a in csv_content:
	if "," in a:
		url, mac = a.split(",")
		url = url.strip().rstrip("/").replace(":80/c", "/c").replace("/c", "/portal.php")
		if url not in alllist: alllist[url] = []
		if mac not in alllist[url]:
			alllist[url].append(mac)
			
sorted_dict = dict(sorted(sorted(alllist.items()), key=lambda item: len(item[1]), reverse=True))
with open(mac_list, "w") as k:
	json.dump(sorted_dict, k, indent=4)


addon_name = "Takealug EPG Grabber"
addon_version = "1.1.7"

epg = ['<?xml version="1.0" encoding="UTF-8" ?>\n<!DOCTYPE tv SYSTEM "xmltv.dtd">\n<!-- EPG XMLTV FILE CREATED BY Take-a-LUG TEAM- (c) 2020 Bastian Kleinschmidt -->\n<!-- created on {} -->\n<tv generator-info-name="Takealug EPG Grabber Ver. {}" generator-info-url="https://github.com/DeBaschdi/service.takealug.epg-grabber">\n'.format(str(now), addon_version)]
epg.append('\n<!--  SIMPLI TV  CHANNEL LIST -->\n')
epg.append('	<channel id="PULS24">\n')
epg.append('		<display-name lang="de">PULS24</display-name>\n')
epg.append('		<icon src="https://upload.wikimedia.org/wikipedia/commons/thumb/2/2f/PULS24logo.png/640px-PULS24logo.png" />\n')
epg.append('	</channel>\n')

tvsDE_header = {'Host': 'live.tvspielfilm.de',
	'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:75.0) Gecko/20100101 Firefox/75.0',
	'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
	'Accept-Language': 'de,en-US;q=0.7,en;q=0.3',
	'Accept-Encoding': 'gzip, deflate, br',
	'Connection': 'keep-alive',
	'Upgrade-Insecure-Requests': '1'}


mac = str(uuid.uuid4())
ter = str(uuid.uuid4())

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

def magentaSession():
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

magentacontentIDs = ["148"]
contentIDs = ['ARD', 'ZDF', 'RTL', 'SAT1', 'PRO7', 'K1', 'RTL2', 'VOX', '3SAT', 'ARTE', 'SERVUSA', 'TELE5', 'SPTVW', 'JUKE', 'HEIMA', 'DMAX', 'SIXX', 'RTL-N', 'RTLPL', 'SPO-D', 'SAT1G', 'PRO7M', 'CC', 'WDR', 'N3', 'BR', 'SWR', 'HR', 'MDR', 'RBB', 'SPORT', 'S1PLU', 'EURO', 'EURO2', 'AMS', 'KIKA', 'SUPER', 'TOGGO', 'RIC', 'NICK', 'FFTV', 'NICKJ', 'NICKT', 'PHOEN', 'ALPHA', 'FES', '2NEO', 'ZINFO', 'ANIXE', 'TLC', 'WDWTV', 'VOXUP', 'TAG24', 'NTV', 'WELT', 'N24DOKU', 'K1DOKU', 'DMC', 'MTV', '123TV', 'ATV', 'ATV2', 'ORF1', 'ORF2', 'ORF3', 'ORFSP', 'OE24TV', 'PULS4', 'SF1', 'SF2', 'CIN', 'SKY-F', 'SKY-A', 'SKY-N', 'SKYCH', 'SKY-CR', 'SKY-D', 'SKY-NA', 'TNT-F', 'KINOW', 'SKY1', 'SKYAT', 'SKY-K', 'SKYRP', 'UNIVE', 'HISHD', 'SP-GE', 'MOVTV', 'HDDIS', 'N-GHD', 'N-GW', '13TH', 'SCIFI', 'TNT-S', 'TNT-C', 'CRIN', 'ROM', 'C-NET', 'CLASS', 'APLAN', 'AXN', 'GEO', 'K1CLA', 'SAT1E', 'PRO7F', 'RTL-C', 'RTL-L', 'PASS', 'SILVE', 'SONY', 'SPTVW', 'TRACE', 'SKYSH']
lang = 'de'
enable_rating_mapper = True
days_to_grab = 5
episode_format = "onscreen"
channel_format = 'provider'
genre_format = "provider"

def xml_broadcast(episode_format, channel_id, item_title, item_starttime, item_endtime, item_description, item_country, item_picture, item_subtitle, items_genre, item_date, item_season, item_episode, item_agerating, item_starrating, items_director, items_producer, items_actor, enable_rating_mapper, lang):
	global epg
	epg.append('\n')
	if item_starttime and item_endtime and item_title:
		## Programme Condition
		epg.append(f'	<programme start="{item_starttime} +0000" stop="{item_endtime} +0000" channel="{channel_id}">\n')
		stars = ''
		## TITLE Condition
		if item_title: epg.append(f'		<title lang="{lang}">{item_title}</title>\n')
		## SUBTITLE Condition
		if item_subtitle: epg.append(f'		<sub-title lang="{lang}">{item_subtitle}</sub-title>\n')
		## DESCRIPTION Condition
		if item_description:
			item_description = item_description.replace('\n', '\n		')
			if enable_rating_mapper == False: epg.append(f'		<desc lang="{lang}">{item_description}</desc>\n')
			## Rating Mapper
			elif enable_rating_mapper == True:
				country = '' if not item_country else f'({item_country})'
				date = '' if not item_date else f'{item_date}'
				season = '' if not item_season else f'• S{item_season}'
				episode = '' if not item_episode else f'E{item_episode}'
				fsk = '' if not item_agerating else f'• FSK {item_agerating}'
				imdbstars = '' if not stars else f'{stars}'
				desc = f'<desc lang="{lang}">{country} {date} {season} {episode} {fsk} {imdbstars}'
				epg.append('		{}\n		{}</desc>\n'.format(' '.join(desc.split()), item_description))
		## CAST Condition
		if items_producer: producerlist = items_producer.split(',')
		if items_director: directorlist = items_director.split(',')
		if items_actor: actorlist = items_actor.split(',')
		# Complete
		if items_director and items_producer and items_actor:
			epg.append('		<credits>\n')
			for director in directorlist: epg.append(f'			<director>{director}</director>\n')
			for actor in actorlist: epg.append(f'			<actor>{actor}</actor>\n')
			for producer in producerlist: epg.append(f'			<producer>{producer}</producer>\n')
			epg.append('		</credits>\n')
		# Producer + Director
		elif items_director and items_producer and not items_actor:
			epg.append('		<credits>' + '\n')
			for director in directorlist: epg.append(f'			<director>{director}</director>\n')
			for producer in producerlist: epg.append(f'			<producer>{producer}</producer>\n')
			epg.append('	   </credits>\n')
		# Director + Actor
		elif items_director and not items_producer and items_actor:
			epg.append('		<credits>\n')
			for director in directorlist: epg.append(f'			<director>{director}</director>\n')
			for actor in actorlist: epg.append(f'			<actor>{actor}</actor>\n')
			epg.append('		</credits>\n')
		# Producer + Actor
		elif not items_director and items_producer and items_actor:
			epg.append('		<credits>\n')
			for actor in actorlist: epg.append(f'			<actor>{actor}</actor>\n')
			for producer in producerlist: epg.append(f'			<producer>{producer}</producer>\n')
			epg.append('		</credits>\n')
		# Only Director
		elif items_director and not items_producer and not items_actor:
			epg.append('		<credits>\n')
			for director in directorlist: epg.append(f'			<director>{director}</director>\n')
			epg.append('		</credits>\n')
		# Only Producer
		if not items_director and items_producer and not items_actor:
			epg.append('		<credits>\n')
			for producer in producerlist: epg.append(f'			<producer>{producer}</producer>\n')
			epg.append('		</credits>\n')
		# Only Actor
		if not items_director and not items_producer and items_actor:
			epg.append('		<credits>\n')
			for actor in actorlist: epg.append(f'			<actor>{actor}</actor>\n')
			epg.append('		</credits>\n')
		## DATE Condition
		if item_date: epg.append(f'		<date>{item_date}</date>\n')
		## GENRE Condition
		if items_genre:
			genrelist = items_genre.split(',')
			for genre in genrelist: epg.append(f'		<category lang="{lang}">{genre}</category>\n')
		## IMAGE Condition
		if item_picture: epg.append(f'		<icon src="{item_picture}"/>\n')
		## COUNTRY Condition
		if item_country: epg.append(f'		<country>{item_country}</country>\n')
		## EPISODE Condition
		# XMLTV_NS
		if episode_format == 'xmltv_ns':
			if item_season and item_episode:
				item_season_ns = int(item_season) - int(1)
				item_episode_ns = int(item_episode) - int(1)
				epg.append(f'		<episode-num system="xmltv_ns">{item_season_ns} . {item_episode_ns} . </episode-num>\n')
			elif item_season and not item_episode:
				item_season_ns = int(item_season) - int(1)
				epg.append(f'		<episode-num system="xmltv_ns">{item_season_ns} . 0 . </episode-num>\n')
			elif not item_season and item_episode:
				item_episode_ns = int(item_episode) - int(1)
				epg.append(f'		<episode-num system="xmltv_ns">0 . {item_episode_ns} . </episode-num>\n')
		# ONSCREEN
		elif episode_format == 'onscreen':
			if item_season and item_episode: epg.append(f'		<episode-num system="onscreen">S{item_season} E{item_episode}</episode-num>\n')
			elif item_season and not item_episode: epg.append(f'		<episode-num system="onscreen">S{item_season}</episode-num>\n')
			elif not item_season and item_episode: epg.append(f'		<episode-num system="onscreen">E{item_episode}</episode-num>\n')
		## AGE-RATING Condition
		if item_agerating:
			epg.append('		<rating>\n')
			epg.append(f'			<value>{item_agerating}</value>\n')
			epg.append('		</rating>\n')
		## STAR-RATING Condition
		if item_starrating:
			item_starrating = int(item_starrating) / int(10)
			epg.append('		<star-rating system="IMDb">\n')
			epg.append(f'			<value>{item_starrating}/10</value>\n')
			epg.append('		</star-rating>\n')
		epg.append('	</programme>\n')

def rep(episode_format, channel_id, item_title, item_starttime, item_endtime, item_description, item_country, item_picture, item_subtitle, items_genre, item_date, item_season, item_episode, item_agerating, item_starrating, items_director, items_producer, items_actor, enable_rating_mapper, lang):
	if channel_id: channel_id = channel_id.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
	if item_title: item_title = item_title.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
	if item_description: item_description = item_description.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
	if item_country: item_country = item_country.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
	if item_subtitle: item_subtitle = item_subtitle.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
	if items_genre: items_genre = items_genre.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
	if items_director: items_director = items_director.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
	if items_producer: items_producer = items_producer.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
	if items_actor: items_actor = items_actor.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
	xml_broadcast(episode_format, channel_id, item_title, item_starttime, item_endtime, item_description, item_country, item_picture, item_subtitle, items_genre, item_date, item_season, item_episode, item_agerating, item_starrating, items_director, items_producer, items_actor, enable_rating_mapper, lang)

def get_epg(tvs_data_url):
	channel_id = tvs_data_url.split("/")[0]
	guide = ["\n"]
	for playbilllist in requests.get("https://live.tvspielfilm.de/static/broadcast/list/%s" % tvs_data_url, headers=tvsDE_header).json():
		item_title = playbilllist.get('title')
		item_description = ""
		description = playbilllist.get('text')
		currentTopics = playbilllist.get('currentTopics')
		conclusion = playbilllist.get('conclusion')
		preview = playbilllist.get('preview')
		if conclusion: item_description += conclusion + "\n"
		if preview: item_description += preview + "\n"
		if currentTopics: item_description += currentTopics + "\n"
		if description: item_description += description + "\n"
		if not item_description: item_description =  'No Program Information available'
		item_country = playbilllist.get('country', "")
		try: item_picture = playbilllist['images'][0]['size4']
		except: item_picture = ""
		item_subtitle = playbilllist.get('episodeTitle', "")
		items_genre = playbilllist.get('genre', "")
		item_date = playbilllist.get('year', "")
		item_agerating = playbilllist.get('fsk', playbilllist.get('childrenInfo', ""))
		items_director = playbilllist.get('director', "")
		try:
			actor_list = list()
			for role, actor in playbilllist['actors'].items():
				actor_list.append("%s : %s" % role, actor)
			items_actor = ','.join(actor_list)
		except: items_actor = ''
		item_starrating = ''
		item_starttime = datetime.fromtimestamp(playbilllist['timestart']).strftime('%Y%m%d%H%M%S')
		item_endtime = datetime.fromtimestamp(playbilllist['timeend']).strftime('%Y%m%d%H%M%S')
		try: item_episode = re.sub(r"\D+", '#', playbilllist['episodeNumber']).split('#')[0]
		except: item_episode = ""
		try: item_season = re.sub(r"\D+", '#', playbilllist['seasonNumber']).split('#')[0]
		except: item_season = ""
		items_producer = ''
		if channel_id: channel_id = channel_id.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
		if item_title: item_title = item_title.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
		if item_description: item_description = item_description.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
		if item_country: item_country = item_country.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
		if item_subtitle: item_subtitle = item_subtitle.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
		if items_genre: items_genre = items_genre.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
		if items_director: items_director = items_director.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
		if items_producer: items_producer = items_producer.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
		if items_actor: items_actor = items_actor.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
		## Programme Condition
		if item_starttime and item_endtime:
			guide.append(f'	<programme start="{item_starttime} +0000" stop="{item_endtime} +0000" channel="{channel_id}">\n')
			stars = ''
			## TITLE Condition
			if item_title: guide.append(f'		<title lang="{lang}">{item_title}</title>\n')
			## SUBTITLE Condition
			if item_subtitle: guide.append(f'		<sub-title lang="{lang}">{item_subtitle}</sub-title>\n')
			## DESCRIPTION Condition
			if item_description: item_description = item_description.replace('\n', '\n		')
			if enable_rating_mapper == False: guide.append(f'		<desc lang="{lang}">{item_description}</desc>\n')
			## Rating Mapper
			elif enable_rating_mapper == True:
				country = '' if not item_country else f'({item_country})'
				date = '' if not item_date else f'{item_date}'
				season = '' if not item_season else f'• S{item_season}'
				episode = '' if not item_episode else f'E{item_episode}'
				fsk = '' if not item_agerating else f'• FSK {item_agerating}'
				imdbstars = '' if stars == '' else f'{stars}'
				desc = f'<desc lang="{lang}">{country} {date} {season} {episode} {fsk} {imdbstars}'
				guide.append('		{}\n		{}</desc>\n'.format(' '.join(desc.split()), item_description))
			## CAST Condition
			if items_producer: producerlist = items_producer.split(',')
			if items_director: directorlist = items_director.split(',')
			if items_actor: actorlist = items_actor.split(',')
			# Complete
			if items_director and items_producer and items_actor:
				guide.append('		<credits>\n')
				for director in directorlist: guide.append(f'			<director>{director}</director>\n')
				for actor in actorlist: guide.append(f'			<actor>{actor}</actor>\n')
				for producer in producerlist: guide.append(f'			<producer>{producer}</producer>\n')
				guide.append('		</credits>\n')
			# Producer + Director
			elif items_director and items_producer and not items_actor:
				guide.append('		<credits>\n')
				for director in directorlist: guide.append(f'			<director>{director}</director>\n')
				for producer in producerlist: guide.append(f'			<producer>{producer}</producer>\n')
				guide.append('	   </credits>\n')
			# Director + Actor
			elif items_director and not items_producer and items_actor:
				guide.append('		<credits>\n')
				for director in directorlist: guide.append(f'			<director>{director}</director>\n')
				for actor in actorlist: guide.append(f'			<actor>{actor}</actor>\n')
				guide.append('		</credits>\n')
			# Producer + Actor
			elif not items_director and items_producer and items_actor:
				guide.append('		<credits>\n')
				for actor in actorlist: guide.append(f'			<actor>{actor}</actor>\n')
				for producer in producerlist: guide.append(f'			<producer>{producer}</producer>\n')
				guide.append('		</credits>\n')
			# Only Director
			elif items_director and not items_producer and not items_actor:
				guide.append('		<credits>\n')
				for director in directorlist: guide.append(f'			<director>{director}</director>\n')
				guide.append('		</credits>\n')
			# Only Producer
			if not items_director and items_producer and not items_actor:
				guide.append('		<credits>\n')
				for producer in producerlist: guide.append(f'			<producer>{producer}</producer>\n')
				guide.append('		</credits>\n')
			# Only Actor
			if not items_director and not items_producer and items_actor:
				guide.append('		<credits>\n')
				for actor in actorlist: guide.append(f'			<actor>{actor}</actor>\n')
				guide.append('		</credits>\n')
			## DATE Condition
			if item_date: guide.append(f'		<date>{item_date}</date>\n')
			## GENRE Condition
			if items_genre:
				genrelist = items_genre.split(',')
				for genre in genrelist: guide.append(f'		<category lang="{lang}">{genre}</category>\n')
			## IMAGE Condition
			if item_picture: guide.append(f'		<icon src="{item_picture}"/>\n')
			## COUNTRY Condition
			if item_country: guide.append(f'		<country>{item_country}</country>\n')
			## EPISODE Condition
			# XMLTV_NS
			if episode_format == 'xmltv_ns':
				if item_season and item_episode:
					item_season_ns = int(item_season) - int(1)
					item_episode_ns = int(item_episode) - int(1)
					guide.append(f'		<episode-num system="xmltv_ns">{item_season_ns} . {item_episode_ns} . </episode-num>\n')
				elif item_season and not item_episode:
					item_season_ns = int(item_season) - int(1)
					guide.append(f'		<episode-num system="xmltv_ns">{item_season_ns} . 0 . </episode-num>\n')
				elif not item_season  and item_episode:
					item_episode_ns = int(item_episode) - int(1)
					guide.append(f'		<episode-num system="xmltv_ns">0 . {item_episode_ns} . </episode-num>\n')
			# ONSCREEN
			elif episode_format == 'onscreen':
				if item_season and item_episode: guide.append(f'		<episode-num system="onscreen">S{item_season} E{item_episode}</episode-num>\n')
				elif item_season and not item_episode: guide.append(f'		<episode-num system="onscreen">S{item_season}</episode-num>\n')
				elif not item_season and item_episode: guide.append(f'		<episode-num system="onscreen">E{item_episode}</episode-num>\n')
			## AGE-RATING Condition
			if item_agerating:
				guide.append('		<rating>\n')
				guide.append(f'			<value>{item_agerating}</value>\n')
				guide.append('		</rating>\n')
			## STAR-RATING Condition
			if item_starrating:
				item_starrating = int(item_starrating) / int(10)
				guide.append('		<star-rating system="IMDb">\n')
				guide.append(f'			<value>{item_starrating}/10</value>\n')
				guide.append('		</star-rating>\n')
			guide.append('	</programme>\n')
	return ''.join(guide)

base_url = "https://live.tvspielfilm.de/api/cms/"
tvsDE_channellist_url = base_url + "channels/list"
tvsDE_chlist_url = requests.get(tvsDE_channellist_url, headers=tvsDE_header).json()

epg.append('\n<!--  TV SPIELFILM (DE)  CHANNEL LIST -->\n')
tvs_data_urls = []
for channel in tvsDE_chlist_url:
	channel_id = channel['channelId'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
	if channel_id not in contentIDs: continue
	channel_icon = base_url+ channel["imageLarge"]
	channel_name = channel['name'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
	epg.append(f'	<channel id="{channel_id}">\n')
	epg.append(f'		<display-name lang="{lang}">{channel_name}</display-name>\n')
	epg.append(f'		<icon src="{channel_icon}" />\n')
	epg.append('	</channel>\n')
	day_to_start = datetime(today.year, today.month, today.day, hour=00, minute=00, second=1)
	for i in range(0, days_to_grab):
		day_to_grab = day_to_start.strftime("%Y-%m-%d")
		day_to_start += timedelta(days=1)
		tvs_data_urls.append(f'{channel_id}/{day_to_grab}')

epg.append('\n<!--  MAGENTA TV (DE)  CHANNEL LIST -->\n')
magentaDE_channels = magentaSession().post(magentaDE_channellist_url, json=magentaDE_get_chlist,headers=magentaDE_header).json()
for channels in magentaDE_channels["channellist"]:
	channel_id = channels['contentId'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
	if channel_id not in magentacontentIDs: continue
	channel_name = channels['name'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
	for image in channels['pictures']:
		if image['imageType'] == '15':
			channel_icon = image['href']
	epg.append(f'	<channel id="{channel_id}">\n')
	epg.append(f'		<display-name lang="{lang}">{channel_name}</display-name>\n')
	epg.append(f'		<icon src="{channel_icon}" />\n')
	epg.append('	</channel>\n')
		
epg.append('\n<!--  SIMPLI TV PROGRAMME LIST -->')
api_headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/110.0', 'Content-type': 'application/json;charset=utf-8', 'X-Api-Date-Format': 'iso', 'X-Api-Camel-Case': 'true', 'referer': 'https://streaming.simplitv.at/'}
time_start, time_end = get_epgLength(days_to_grab, form="%Y-%m-%dT%H:%M:00.000Z")
epg_url = "https://api.app.simplitv.at/v1/EpgTile/FilterProgramTiles"
epg_post = {"platformCodename": "www", "from": time_start, "to": time_end}
epg_resp = requests.post(epg_url, headers=api_headers, json=epg_post).json()["programs"]
prg_url = "https://api.app.simplitv.at/v2/Tile/GetTiles"
prg_post = {"platformCodename": "www", "requestedTiles": [{"id": a["id"]} for i in epg_resp.keys() for a in epg_resp[i] if i == "puls24"]}
epg_data = requests.post(prg_url, headers=api_headers, json=prg_post).json()["tiles"]
for program in epg_data:
	item_starttime=program["start"].split('+')[0].replace("-", "").replace("T", "").replace(":", "")
	item_endtime = program["stop"].split('+')[0].replace("-", "").replace("T", "").replace(":", "")
	items_genre = program.get('categories', "")[-1]['name'] if len(program.get("categories", [])) > 0 else ""
	item_country = ', '.join([i['name'] for i in program['countries']]) if len(program.get("countries", [])) > 0 else ""
	item_description = program.get("description").replace("\n\n", "")
	item_title = program.get("title")
	try: item_picture = program["images"][0]["url"]
	except: item_picture = ""
	item_season = program.get('seasonNumber', "")
	item_episode = program.get("episodeNumber", "")
	item_subtitle = program.get("subTitle", "")
	item_date = program.get("date", "")
	item_agerating = program.get("ageRating", "")
	item_starrating = ""
	actor, director, producer, desc = [], [], [], []
	if len(program.get("people", [])) > 0:
		c = {}
		for i in program["people"]:
			if i["roleCodename"] == "director": director.append(i["fullName"])
			elif i["roleName"] == "Produzent": producer.append(i["fullName"])
			elif i["roleCodename"] == "actor": actor.append(i["fullName"])
			else: desc.append("%s : %s" % (i["roleName"], i["fullName"]))
	items_director = ', '.join(director)
	items_producer = ', '.join(producer)
	items_actor = ', '.join(actor)
	item_description+= "\n"+', '.join(desc)
	rep('onscreen', "PULS24", item_title, item_starttime, item_endtime, item_description, item_country, item_picture, item_subtitle, items_genre, item_date, item_season, item_episode, item_agerating, item_starrating, items_director, items_producer, items_actor, False, lang)
epg.append('\n<!--  TV SPIELFILM (DE)  PROGRAMME LIST -->')

with ThreadPoolExecutor(len(tvs_data_urls)) as executor:
	futures = [executor.submit(get_epg, tvs_data_url) for tvs_data_url in tvs_data_urls]
	for future in as_completed(futures):
		o = future.result()
		epg.append(o)

epg.append('\n<!--  {MAGENTA TV (DE)}  PROGRAMME LIST -->')
starttime, endtime = get_epgLength(days_to_grab, form="%Y%m%d%H%M%S")
for contentID in magentacontentIDs:
	magentaDE_data = {'channelid': contentID, 'type': '2', 'offset': '0', 'count': '-1', 'isFillProgram': '1','properties': '[{"name":"playbill","include":"ratingForeignsn,id,channelid,name,subName,starttime,endtime,cast,casts,country,producedate,ratingid,pictures,type,introduce,foreignsn,seriesID,genres,subNum,seasonNum"}]','endtime': endtime, 'begintime': starttime}
	magentaData = magentaSession().post(magentaDE_data_url, json=magentaDE_data, headers=magentaDE_header).json()['playbilllist']
	for playbilllist in magentaData:
		item_title = playbilllist.get('name')
		item_starttime = playbilllist.get('starttime')
		item_endtime = playbilllist.get('endtime')
		item_description = playbilllist.get('introduce')
		item_country = playbilllist.get('country')
		try: item_picture = playbilllist['pictures'][1]['href']
		except (KeyError, IndexError): item_picture = ''
		item_subtitle = playbilllist.get('subName')
		items_genre = playbilllist.get('genres')
		item_date = playbilllist.get('producedate')
		item_season = playbilllist.get('seasonNum')
		item_episode = playbilllist.get('subNum')
		item_agerating = playbilllist.get('ratingid')
		try: items_director = playbilllist['cast']['director']
		except (KeyError, IndexError): items_director = ''
		try: items_producer = playbilllist['cast']['producer']
		except (KeyError, IndexError): items_producer = ''
		actor = []
		try: 
			casts =  playbilllist.get('casts')
			if casts: actor  = [i["castName"] for i in casts]
		except: actor = []
		items_actor = ", ".join(actor)
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
		rep(episode_format, contentID, item_title, item_starttime, item_endtime, item_description, item_country, item_picture, item_subtitle, items_genre, item_date, item_season, item_episode, item_agerating, item_starrating, items_director, items_producer, items_actor, enable_rating_mapper, lang)
		
epg.append('\n</tv>\n')

guide_dest = os.path.join(os.path.dirname(datapath), 'guide.xml')
guidegz_dest = os.path.join(os.path.dirname(datapath), 'guide.xml.gz')
with open(guide_dest, "w") as k:
	k.write("".join(epg))
with open(guide_dest, 'rb') as f_in, gzip.open(guidegz_dest, 'wb') as f_out:
	f_out.writelines(f_in)