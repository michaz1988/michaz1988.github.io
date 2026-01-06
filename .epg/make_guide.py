import requests, gzip, json, time, os, boto3, uuid, re, hashlib, shutil, base64
from collections import defaultdict
from maclist import alllist
from dateutil.parser import parse
from urllib.parse import quote
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup

datapath = os.path.abspath(os.path.dirname(__file__))
#datapath = "/sdcard/"
mac_list = os.path.join(os.path.dirname(datapath), 'maclist.json')
xtream_list = os.path.join(os.path.dirname(datapath), 'xtreamlist.json')
guide_dest = os.path.join(os.path.dirname(datapath), 'guide.xml')
guidegz_dest = os.path.join(os.path.dirname(datapath), 'guide.xml.gz')
days_to_grab = 3
magentacontentIDs = ["18", "60", "148", "218", "338", "389", "601", "4724"]
tvdids = [37, 38, 39, 40, 41, 42, 43, 44, 46, 47, 48, 49, 50, 51, 52, 54, 55, 56, 57, 58, 59, 60, 64, 66, 70, 71, 100, 104, 115, 133, 138, 146, 154, 175, 194, 276, 277, 402, 450, 451, 452, 453, 468, 471, 472, 485, 492, 507, 511, 527, 528, 529, 531, 532, 537, 551, 552, 564, 568, 590, 597, 603, 610, 613, 614, 615, 625, 626, 627, 633, 656, 659, 694, 756, 757, 759, 761, 763, 765, 766, 767, 770, 771, 778, 782, 783, 1183, 4002, 4003, 4004, 12033, 12035, 12042, 12043, 12045, 12046, 12125, 12147, 12148, 12178, 12184, 12188, 12189, 12195]
try: os.remove(guide_dest)
except: pass
addon_name = "Takealug EPG Grabber"
addon_version = "2.1"
lang = 'de'
enable_rating_mapper = True
episode_format = "onscreen"
channel_format = 'provider'
genre_format = "provider"

R2_ACCESS_KEY = "4b36152b6b64b8a9f4d7010b84f535fc"
R2_SECRET_KEY = "7ad1ed517b6baa6af2fa00d50a1a18b0ce416bb0b6fb14f4c122a2960f1ab9bc"
R2_ENDPOINT_URL = "https://145ef3f7a9832804bef0e31548db8a83.r2.cloudflarestorage.com"
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

today = datetime.today()
now = datetime.now()
timestamp = datetime.timestamp(now)
weekstamp = datetime.timestamp(now+timedelta(days=7))

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

def get_epgLength(days_to_grab, form="%Y-%m-%dT%H:%M:00.000Z"):
	# Calculate Date and Time
	calc_today = datetime.now()-timedelta(days=1)
	calc_then = calc_today+ timedelta(days=days_to_grab+1)
	starttime = calc_today.strftime(form)
	endtime = calc_then.strftime(form)
	return starttime, endtime
	
blog = requests.get("https://ikracccam.blogspot.com/p/link-stalcker-google-drive.html").content
link = BeautifulSoup(blog, 'html.parser').find("div", {"class": "titre-content"}).find("p").text.strip()
page = requests.get(link).text

pattern = re.compile(
	r"URL:\s*(?P<url>\S+)\s*.*?"
	r"MAC:\s*(?P<mac>(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2})\s*.*?"
	r"Expire:\s*(?P<expire>[A-Za-z]+\s+\d{1,2},\s+\d{4},\s+\d{1,2}:\d{2}\s*(?:am|pm)|unknown|unlimited)",
	re.IGNORECASE | re.DOTALL
)

for m in pattern.finditer(page):
	url = m.group("url").strip().rstrip("/")
	if not url.endswith("/c"): url+="/c"
	url = url.replace(":80/c", "/c")
	mac = m.group("mac")
	expire = m.group("expire")
	try:
		if weekstamp > datetime.timestamp(parse(expire)): continue
	except: pass
	if url not in alllist: alllist[url] = []
	if mac not in alllist[url]: alllist[url].append(mac)

def get_boto(BUCKET_NAME, OBJECT_KEY):
	rows = []
	s3_client = boto3.client("s3", aws_access_key_id=R2_ACCESS_KEY, aws_secret_access_key=R2_SECRET_KEY, endpoint_url=R2_ENDPOINT_URL)
	response = s3_client.get_object(Bucket=BUCKET_NAME, Key=OBJECT_KEY)
	with gzip.GzipFile(fileobj=response["Body"]) as gz:
		for line in gz: rows.append(line.decode("utf-8").replace('"', "").replace("\\", "").replace('"', '').strip().split(","))
	return rows

xtreamlist = []

blog = requests.get("https://ikracccam.blogspot.com/p/link-google-drive-new.html").content
link = BeautifulSoup(blog, 'html.parser').find("div", {"class": "titre-content"}).find("p").text.strip()
page = requests.get(link).text.strip()
pattern = re.compile(r'^(https?://[^:/]+:\d+)/get\.php\?(username=[^&]+&password=[^&]+)(?:&type=m3u)?$')
for url in page.splitlines():
	m = pattern.match(url)
	if m:
		xtreamlist.append({"url": m.group(1).rstrip("/"), "userpass": m.group(2),"region": None})

regions = []
for row in get_boto("xtreamity", "xtreamity-db.csv.gz"):
	try:
		if weekstamp > datetime.timestamp(parse(row[3] + row[4])): continue
	except: pass
	if row[5] not in regions: regions.append(row[5])
	xtreamlist.append({"url": row[0].rstrip("/"), "userpass": f"username={row[1]}&password={row[2]}", "region": row[5]})

# Schritt 1: bekannte Gruppen pro URL sammeln
url_regions = {}
for entry in xtreamlist:
    if entry.get("region"):
        url_regions.setdefault(entry["url"], entry["region"])

# Schritt 2: region=None durch vorhandene Gruppe ersetzen
for entry in xtreamlist:
    if entry.get("region") is None and entry["url"] in url_regions:
        entry["region"] = url_regions[entry["url"]]

# Schritt 3: Gruppieren und Duplikate entfernen
grouped = defaultdict(lambda: {
    "url": None,
    "region": None,
    "userpasses": set()
})

for entry in xtreamlist:
    key = (entry["url"], entry["region"])
    grouped[key]["url"] = entry["url"]
    grouped[key]["region"] = entry["region"]
    grouped[key]["userpasses"].add(entry["userpass"])

# Schritt 4: Sets → Listen, Sortierung nach Anzahl userpasses
result = []
for v in grouped.values():
    v["userpasses"] = sorted(v["userpasses"])
    result.append(v)

result.sort(key=lambda x: len(x["userpasses"]), reverse=True)

pattern = re.compile(r"username=([^&]+)&password=(.+)")

for entry in result:
    converted = []
    for up in entry.get("userpasses", []):
        m = pattern.search(up)
        if m:
            converted.append({
                "user": m.group(1),
                "pass": m.group(2)
            })
    entry["userpasses"] = converted

with open(xtream_list, "w") as k:
	json.dump({"regions": sorted(regions), "urls": result}, k, indent=4)
print("New xtream list created")

for row in get_boto("stbemu", "stbemu.csv.gz"):
	try:
		if weekstamp > datetime.timestamp(parse(row[2] + row[3] + row[4])): continue
	except: pass
	url = row[0].strip().rstrip("/")
	if not url.endswith("/c"): url+="/c"
	url = url.replace(":80/c", "/c")
	if url not in alllist: alllist[url] = []
	if mac not in alllist[url]: alllist[url].append(mac)

try:
	url = f'https://stbstalker.alaaeldinee.com/{now.strftime("%Y/%m")}/smart-stb-emu-pro-{now.strftime("%d-%m-%Y")}.html?m=1'
	for b in requests.get(url).text.splitlines():
		if "PORTAL :" in b:
			c = re.findall("PORTAL : .*", b.replace("PORTAL", "\nPORTAL"))
			for d in c: 
				if not "datePublished" in d:
					huii = re.findall("(?<= : ).*?(?=</p>)", d)
					if huii and len(huii) == 5:
						portal, mac, expired = huii[0].strip().rstrip("/"), huii[3], huii[4]
						if not portal.endswith("/c"): portal+="/c"
						portal = portal.replace(":80/c", "/c")
						try:
							if weekstamp > datetime.timestamp(parse(expired)): continue
						except: pass
						if portal not in alllist: alllist[portal] = []
						if mac not in alllist[portal]: alllist[portal].append(mac)
except:pass

sorted_dict = dict(sorted(sorted(alllist.items()), key=lambda item: len(item[1]), reverse=True))
with open(mac_list, "w") as k:
	json.dump(sorted_dict, k, indent=4)
print("New maclist created")

epg = ['<?xml version="1.0" encoding="UTF-8" ?>\n<!DOCTYPE tv SYSTEM "xmltv.dtd">\n<!-- EPG XMLTV FILE CREATED BY Take-a-LUG TEAM- (c) 2020 Bastian Kleinschmidt -->\n<!-- created on {} -->\n<tv generator-info-name="Takealug EPG Grabber Ver. {}" generator-info-url="https://github.com/DeBaschdi/service.takealug.epg-grabber">\n'.format(str(now), addon_version)]
epg.append('\n<!--  SIMPLI TV  CHANNEL LIST -->\n')
epg.append('	<channel id="PULS24">\n')
epg.append('		<display-name lang="de">PULS24</display-name>\n')
epg.append('		<icon src="https://upload.wikimedia.org/wikipedia/commons/thumb/2/2f/PULS24logo.png/640px-PULS24logo.png" />\n')
epg.append('	</channel>\n')
epg.append('\n<!--  TV DIGITAL (DE)  CHANNEL LIST -->\n')
tvdDE_header = {'user-agent': 'PIT-TVdigital-Android/14', 'accept-encoding': 'gzip'}
tvdDE_channels = requests.get('https://mobile.tvdigital.de/appdata?appVersion=50&bundleId=de.funke.tvdigital', headers=tvdDE_header).json()["channels"]
for channels in tvdDE_channels: 
	id = str(channels['id'])
	if int(id) not in tvdids: continue
	name= channels['name'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
	channel_icon = "https://sender.epglogos.de/240x200/"+ channels['img']
	epg.append(f'	<channel id="{id}">\n')
	epg.append(f'		<display-name lang="{lang}">{name}</display-name>\n')
	epg.append(f'		<icon src="{channel_icon}" />\n')
	epg.append('	</channel>\n')
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

print("EPG channellist created")

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
				epg.append('		{}\n{}</desc>\n'.format(' '.join(desc.split()), item_description))
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
	if channel_id: 
		if isinstance(channel_id, int): channel_id = str(channel_id)
		channel_id = channel_id.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
	if item_title: item_title = item_title.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
	if item_description: item_description = item_description.strip().replace('  ', ' ').replace('<br/>', '\n').replace('<br />', '\n').replace('\n\n', '\n')
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
	for playbilllist in requests.get("http://tvs3.cellular.de/broadcast/list/%s" % tvs_data_url).json():
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
		if item_description: item_description = item_description.strip().replace('  ', ' ').replace('<br/>', '\n').replace('<br />', '\n').replace('\n\n', '\n')
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
				guide.append('		{}\n{}</desc>\n'.format(' '.join(desc.split()), item_description))
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

def fetch_broadcasts(day_to_grab, ids):
	broadcast_files = {}
	params = '{"date":%s,"channels":%s}' % (day_to_grab, ids)
	url_program = "https://mobile.tvdigital.de/programbystation?data=" + quote(params) + "&tmpl=app&device=androidv14&displayDensity=200&sdkInt=35"
	response = requests.get(url_program).json()

	for a in response:
		broad = [b["id"] for b in a["broadcasts"]]
		if not broad:
			continue
		params_detail = '{"broadcasts":%s}' % broad
		url_detail = "https://mobile.tvdigital.de/broadcastdetails?data=" + quote(params_detail) + "&tmpl=app&device=androidv14&displayDensity=200&sdkInt=35"
		try:details = requests.get(url_detail).json()
		except: 
			print("error %s "% url_detail)
			try:details = requests.get(url_detail).json()
			except: return {}
		for t in details:
			if t["n"] not in broadcast_files:
				broadcast_files[t["n"]] = []
			broadcast_files[t["n"]].append(t)
	return broadcast_files
		
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

print("SIMPLI TV PROGRAMME LIST ready")

epg.append('\n<!--  TV DIGITAL (DE) PROGRAMME LIST -->')
broadcast_files = {}
day_to_start = datetime.now()-timedelta(days=1)
day_timestamps = [int(datetime.timestamp(day_to_start + timedelta(days=i)))for i in range(days_to_grab+1)]
with ThreadPoolExecutor(max_workers=days_to_grab+1) as executor:
	futures = [executor.submit(fetch_broadcasts, day, tvdids) for day in day_timestamps]
	for future in as_completed(futures):
		result = future.result()
		for key, val in result.items():
			if key not in broadcast_files:
				broadcast_files[key] = []
			broadcast_files[key].extend(val)

for contentID in tvdids:
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
			item_starttime = datetime.fromtimestamp(item_starttime).strftime('%Y%m%d%H%M%S')
			item_endtime = datetime.fromtimestamp(item_endtime).strftime('%Y%m%d%H%M%S')
			if item_episode: item_episode = re.sub(r"\D+", '#', item_episode).split('#')[0]
			if item_season: item_season = re.sub(r"\D+", '#', item_season).split('#')[0]
			if not item_description: item_description = 'No Program Information available'
			rep(episode_format, contentID, item_title, item_starttime, item_endtime,item_description, item_country, item_picture, item_subtitle,items_genre, item_date, item_season, item_episode, item_agerating, item_starrating, items_director,items_producer, items_actor, enable_rating_mapper, lang)
		except (KeyError, IndexError): pass

print("TV DIGITAL (DE) PROGRAMME LIST ready")

epg.append('\n<!--  {MAGENTA TV (DE)}  PROGRAMME LIST -->')
sess = magentaSession()

def mag(contentID):
	starttime, endtime = get_epgLength(days_to_grab, form="%Y%m%d%H%M%S")
	magentaDE_data = {'channelid': contentID, 'type': '2', 'offset': '0', 'count': '-1', 'isFillProgram': '1','properties': '[{"name":"playbill","include":"ratingForeignsn,id,channelid,name,subName,starttime,endtime,cast,casts,country,producedate,ratingid,pictures,type,introduce,foreignsn,seriesID,genres,subNum,seasonNum"}]','endtime': endtime, 'begintime': starttime}
	magentaData = sess.post(magentaDE_data_url, json=magentaDE_data, headers=magentaDE_header).json()['playbilllist']
	return magentaData

with ThreadPoolExecutor(len(magentacontentIDs)) as executor:
	future_to_url = {executor.submit(mag, contentID):contentID for contentID in magentacontentIDs}
	for future in as_completed(future_to_url):
		contentID = future_to_url[future]
		o = future.result()
		for playbilllist in o:
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
print(f"EPG ready")

with open(guide_dest, "w") as k:
	k.write("".join(epg))
with open(guide_dest, 'rb') as f_in, gzip.open(guidegz_dest, 'wb') as f_out:
	f_out.writelines(f_in)