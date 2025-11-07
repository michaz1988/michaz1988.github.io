import hashlib, os, json, requests, shutil, base64
datapath = os.path.abspath(os.path.dirname(__file__))
logo_md5 = os.path.join(os.path.dirname(datapath), 'tvsp.md5')
with open(logo_md5) as k:
	logomd5 = k.read()

tvsDE_channels = requests.get('https://rhea-export.tvspielfilm.de/channels/epg').json()["data"]["data_list"]
newmd5 = hashlib.md5(json.dumps(tvsDE_channels).encode()).hexdigest()
if logomd5 != newmd5:
	tvs_logos = os.path.join(os.path.dirname(datapath), 'tvs-logos')
	shutil.rmtree(tvs_logos)
	os.mkdir(tvs_logos)
	with open(logo_md5, "w") as k:
		k.write(newmd5)
	for b in tvsDE_channels:
		logo = b["logo"].replace("data:image/png;base64,","")
		with open(os.path.join(tvs_logos, f"{b['id']}.png"), "wb") as k:
			k.write(base64.b64decode(logo))
	print("New tvs-logos")