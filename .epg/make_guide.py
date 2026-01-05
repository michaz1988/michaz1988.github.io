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
magentacontentIDs = ["148", "389", "601", "4724", "18", "218", "338"]
tvdids = [71, 37, 38,39,40,44,41,42,56,58,770,277,507,694,763,12033,783,532,46,47,51,50,49,48,52,64,564,656,57,43,771,485,568,597,551,194,104,146,659,276,537,4003,4005,12125,100,66,175,12045,12043,511,70,115,761,54,55,757,759,402,59,60,610,12042,613,614,12195,603,12148,12147,633,450,12046,767,615,12178,12184,782,452,625,627,138,453,626,471,472,590,12035,4004,552,154,531,133,1183,468,4002,492,766,765,527,528,529,451,778,756, 12188,12189]
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
		xtreamlist.append({"url": m.group(1).rstrip("/"), "userpass": m.group(2),"group": None})

groups = []
for row in get_boto("xtreamity", "xtreamity-db.csv.gz"):
	try:
		if weekstamp > datetime.timestamp(parse(row[3] + row[4])): continue
	except: pass
	if row[5] not in groups: groups.append(row[5])
	xtreamlist.append({"url": row[0].rstrip("/"), "userpass": f"username={row[1]}&password={row[2]}", "group": row[5]})

# Schritt 1: bekannte Gruppen pro URL sammeln
url_groups = {}
for entry in xtreamlist:
    if entry.get("group"):
        url_groups.setdefault(entry["url"], entry["group"])

# Schritt 2: group=None durch vorhandene Gruppe ersetzen
for entry in xtreamlist:
    if entry.get("group") is None and entry["url"] in url_groups:
        entry["group"] = url_groups[entry["url"]]

# Schritt 3: Gruppieren und Duplikate entfernen
grouped = defaultdict(lambda: {
    "url": None,
    "group": None,
    "userpasses": set()
})

for entry in xtreamlist:
    key = (entry["url"], entry["group"])
    grouped[key]["url"] = entry["url"]
    grouped[key]["group"] = entry["group"]
    grouped[key]["userpasses"].add(entry["userpass"])

# Schritt 4: Sets → Listen, Sortierung nach Anzahl userpasses
result = []
for v in grouped.values():
    v["userpasses"] = sorted(v["userpasses"])
    result.append(v)

result.sort(key=lambda x: len(x["userpasses"]), reverse=True)

with open(xtream_list, "w") as k:
	json.dump({"groups": sorted(groups), "urls": result}, k, indent=4)
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