#!/usr/bin/env python3
"""Create the XMLTV guide published by the daily GitHub workflow."""

import argparse
import gzip
import os
import re
import shutil
import time
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote
from datetime import datetime, timedelta

import requests

magentacontentIDs = ["18", "60", "148", "218", "338", "389", "601", "4724"]
tvdids = [37, 38, 39, 40, 41, 42, 43, 44, 46, 47, 48, 49, 50, 51, 52, 54, 55, 56, 57, 58, 59, 60, 64, 66, 70, 71, 100, 104, 115, 133, 138, 146, 154, 175, 194, 276, 277, 402, 450, 451, 452, 453, 468, 471, 472, 485, 492, 507, 511, 527, 528, 529, 531, 532, 537, 551, 552, 564, 568, 590, 597, 603, 610, 613, 614, 615, 625, 626, 627, 633, 656, 659, 694, 756, 757, 759, 761, 763, 765, 766, 767, 770, 771, 778, 782, 783, 1183, 4002, 4003, 4004, 12033, 12035, 12042, 12043, 12045, 12046, 12125, 12147, 12148, 12184, 12188, 12189, 12195]
addon_version = "2.1"
lang = 'de'
enable_rating_mapper = True
episode_format = "onscreen"

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

def request_json(client, method, url, attempts=3, timeout=30, **kwargs):
	"""Request JSON with bounded retries and a useful final error."""
	error = None
	for attempt in range(attempts):
		try:
			response = getattr(client, method)(url, timeout=timeout, **kwargs)
			response.raise_for_status()
			return response.json()
		except (requests.RequestException, ValueError) as exc:
			error = exc
			if attempt + 1 < attempts:
				time.sleep(1 + attempt)
	raise RuntimeError("JSON request failed for %s: %s" % (url, error))


def magentaSession():
	x = 0
	while x < 120:
		session = requests.Session()
		t = session.post(magentaDE_authenticate_url, timeout=5, data=magentaDE_authenticate, headers=magentaDE_header)
		t.raise_for_status()
		if t.json().get("retcode", "0") == "-2":
			time.sleep(0.1)
			x = x + 1
			continue
		break
	else:
		raise RuntimeError("Magenta authentication did not return a session")
	if "CSRFSESSION" not in session.cookies:
		raise RuntimeError("Magenta authentication returned no CSRF cookie")
	session.headers.update({'X_CSRFToken': session.cookies["CSRFSESSION"]})
	return session

def get_epgLength(days_to_grab, form="%Y-%m-%dT%H:%M:00.000Z"):
	# Calculate Date and Time
	calc_today = datetime.now()-timedelta(days=1)
	calc_then = calc_today+ timedelta(days=days_to_grab+1)
	starttime = calc_today.strftime(form)
	endtime = calc_then.strftime(form)
	return starttime, endtime



def parse_args():
	parser = argparse.ArgumentParser()
	parser.add_argument(
		"--output-dir",
		type=Path,
		default=Path(__file__).resolve().parent.parent,
	)
	parser.add_argument("--days", type=int, default=3)
	return parser.parse_args()


def main():
	args = parse_args()
	if args.days < 1:
		raise ValueError("--days must be at least 1")
	output_dir = args.output_dir.resolve()
	output_dir.mkdir(parents=True, exist_ok=True)
	days_to_grab = args.days
	now = datetime.now()

	epg = ['<?xml version="1.0" encoding="UTF-8" ?>\n<!DOCTYPE tv SYSTEM "xmltv.dtd">\n<!-- EPG XMLTV FILE CREATED BY Take-a-LUG TEAM- (c) 2020 Bastian Kleinschmidt -->\n<!-- created on {} -->\n<tv generator-info-name="Takealug EPG Grabber Ver. {}" generator-info-url="https://github.com/DeBaschdi/service.takealug.epg-grabber">\n'.format(str(now), addon_version)]
	epg.append('\n<!--  SIMPLI TV  CHANNEL LIST -->\n')
	epg.append('	<channel id="PULS24">\n')
	epg.append('		<display-name lang="de">PULS24</display-name>\n')
	epg.append('		<icon src="https://upload.wikimedia.org/wikipedia/commons/thumb/2/2f/PULS24logo.png/640px-PULS24logo.png" />\n')
	epg.append('	</channel>\n')
	epg.append('\n<!--  TV DIGITAL (DE)  CHANNEL LIST -->\n')
	tvdDE_header = {'user-agent': 'PIT-TVdigital-Android/14', 'accept-encoding': 'gzip'}
	tvdDE_channels = request_json(
		requests,
		"get",
		'https://mobile.tvdigital.de/appdata?appVersion=50&bundleId=de.funke.tvdigital',
		headers=tvdDE_header,
	)["channels"]
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
	magentaDE_channels = request_json(
		magentaSession(),
		"post",
		magentaDE_channellist_url,
		json=magentaDE_get_chlist,
		headers=magentaDE_header,
	)
	for channels in magentaDE_channels["channellist"]:
		channel_id = channels['contentId'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
		if channel_id not in magentacontentIDs: continue
		channel_name = channels['name'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
		channel_icon = ""
		for image in channels['pictures']:
			if image['imageType'] == '15':
				channel_icon = image['href']
		epg.append(f'	<channel id="{channel_id}">\n')
		epg.append(f'		<display-name lang="{lang}">{channel_name}</display-name>\n')
		epg.append(f'		<icon src="{channel_icon}" />\n')
		epg.append('	</channel>\n')

	print("EPG channellist created")

	def xml_broadcast(episode_format, channel_id, item_title, item_starttime, item_endtime, item_description, item_country, item_picture, item_subtitle, items_genre, item_date, item_season, item_episode, item_agerating, item_starrating, items_director, items_producer, items_actor, enable_rating_mapper, lang):
		nonlocal epg
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

	def fetch_broadcasts(day_to_grab, ids):
		broadcast_files = {}
		params = '{"date":%s,"channels":%s}' % (day_to_grab, ids)
		url_program = "https://mobile.tvdigital.de/programbystation?data=" + quote(params) + "&tmpl=app&device=androidv14&displayDensity=200&sdkInt=35"
		response = request_json(requests, "get", url_program)

		for a in response:
			broad = [b["id"] for b in a["broadcasts"]]
			if not broad:
				continue
			params_detail = '{"broadcasts":%s}' % broad
			url_detail = "https://mobile.tvdigital.de/broadcastdetails?data=" + quote(params_detail) + "&tmpl=app&device=androidv14&displayDensity=200&sdkInt=35"
			details = request_json(requests, "get", url_detail)
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
	epg_resp = request_json(
		requests, "post", epg_url, headers=api_headers, json=epg_post
	)["programs"]
	prg_url = "https://api.app.simplitv.at/v2/Tile/GetTiles"
	prg_post = {"platformCodename": "www", "requestedTiles": [{"id": a["id"]} for i in epg_resp.keys() for a in epg_resp[i] if i == "puls24"]}
	epg_data = request_json(
		requests, "post", prg_url, headers=api_headers, json=prg_post
	)["tiles"]
	for program in epg_data:
		item_starttime=program["start"].split('+')[0].replace("-", "").replace("T", "").replace(":", "")
		item_endtime = program["stop"].split('+')[0].replace("-", "").replace("T", "").replace(":", "")
		items_genre = program.get('categories', "")[-1]['name'] if len(program.get("categories", [])) > 0 else ""
		item_country = ', '.join(
			i['name'] for i in program.get('countries', [])
		)
		item_description = (program.get("description") or "").replace("\n\n", "")
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
	for day in day_timestamps:
		result = fetch_broadcasts(day, tvdids)
		for key, val in result.items():
			if key not in broadcast_files:
				broadcast_files[key] = []
			broadcast_files[key].extend(val)

	for contentID in tvdids:
		for playbilllist in broadcast_files.get(contentID, []):
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
		magentaData = request_json(
			sess,
			"post",
			magentaDE_data_url,
			json=magentaDE_data,
			headers=magentaDE_header,
		)['playbilllist']
		return magentaData

	for contentID in magentacontentIDs:
		o = mag(contentID)
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

	xml_content = "".join(epg)
	ET.fromstring(xml_content)
	guide_path = output_dir / "guide.xml"
	gzip_path = output_dir / "guide.xml.gz"
	guide_tmp = guide_path.with_suffix(".xml.tmp")
	gzip_tmp = gzip_path.with_suffix(".gz.tmp")
	try:
		guide_tmp.write_text(xml_content, encoding="utf-8")
		with guide_tmp.open("rb") as source:
			with gzip.open(gzip_tmp, "wb") as destination:
				shutil.copyfileobj(source, destination)
		os.replace(guide_tmp, guide_path)
		os.replace(gzip_tmp, gzip_path)
	finally:
		for temporary in (guide_tmp, gzip_tmp):
			if temporary.exists():
				temporary.unlink()


if __name__ == "__main__":
	main()
