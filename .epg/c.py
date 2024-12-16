import requests, os, gzip
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

today = datetime.today()
now = datetime.now()

tvsDE_header = {'Host': 'live.tvspielfilm.de',
	'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:75.0) Gecko/20100101 Firefox/75.0',
	'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
	'Accept-Language': 'de,en-US;q=0.7,en;q=0.3',
	'Accept-Encoding': 'gzip, deflate, br',
	'Connection': 'keep-alive',
	'Upgrade-Insecure-Requests': '1'}

magentaDE_login_url = 'https://api.prod.sngtv.magentatv.de/EPG/JSON/Login?&T=PC_firefox_75'
magentaDE_authenticate_url = 'https://api.prod.sngtv.magentatv.de/EPG/JSON/Authenticate?SID=firstup&T=PC_firefox_75'
magentaDE_channellist_url = 'https://api.prod.sngtv.magentatv.de/EPG/JSON/AllChannel?SID=first&T=PC_firefox_75'
magentaDE_data_url = 'https://api.prod.sngtv.magentatv.de/EPG/JSON/PlayBillList?userContentFilter=241221015&sessionArea=1&SID=ottall&T=PC_firefox_75'
magentaDE_login = {'userId': 'Guest', 'mac': '00:00:00:00:00:00'}
magentaDE_authenticate = {'terminalid': '00:00:00:00:00:00', 'mac': '00:00:00:00:00:00', 'terminaltype': 'WEBTV','utcEnable': '1', 'timezone': 'UTC', 'userType': '3', 'terminalvendor': 'Unknown','preSharedKeyID': 'PC01P00002', 'cnonce': '5c6ff0b9e4e5efb1498e7eaa8f54d9fb'}
magentaDE_get_chlist = {'properties': [{'name': 'logicalChannel','include': '/channellist/logicalChannel/contentId,/channellist/logicalChannel/name,/channellist/logicalChannel/pictures/picture/imageType,/channellist/logicalChannel/pictures/picture/href'}],'metaDataVer': 'Channel/1.1', 'channelNamespace': '2','filterlist': [{'key': 'IsHide', 'value': '-1'}], 'returnSatChannel': '0'}
magentaDE_header = {'Host': 'api.prod.sngtv.magentatv.de',
				  'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:75.0) Gecko/20100101 Firefox/75.0',
				  'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
				  'Accept-Language': 'de,en-US;q=0.7,en;q=0.3',
				  'Accept-Encoding': 'gzip, deflate, br',
				  'Connection': 'keep-alive',
				  'Upgrade-Insecure-Requests': '1'}

def magentaSession():
	session = requests.Session()
	session.post(magentaDE_login_url, json=magentaDE_login, headers=magentaDE_header)
	session.post(magentaDE_authenticate_url, json=magentaDE_authenticate, headers=magentaDE_header)
	session.headers.update({'X_CSRFToken': session.cookies["CSRFSESSION"]})
	return session

magentacontentIDs = ["148"]
contentIDs = ['ARD', 'ZDF', 'RTL', 'SAT1', 'PRO7', 'K1', 'RTL2', 'VOX', '3SAT', 'ARTE', 'SERVUSA', 'TELE5', 'SPTVW', 'JUKE', 'HEIMA', 'DMAX', 'SIXX', 'RTL-N', 'RTLPL', 'SPO-D', 'SAT1G', 'PRO7M', 'CC', 'WDR', 'N3', 'BR', 'SWR', 'HR', 'MDR', 'RBB', 'SPORT', 'S1PLU', 'EURO', 'EURO2', 'AMS', 'KIKA', 'SUPER', 'TOGGO', 'RIC', 'NICK', 'FFTV', 'NICKJ', 'NICKT', 'PHOEN', 'ALPHA', 'FES', '2NEO', 'ZINFO', 'ANIXE', 'TLC', 'WDWTV', 'VOXUP', 'TAG24', 'NTV', 'WELT', 'N24DOKU', 'K1DOKU', 'DMC', 'MTV', '123TV', 'ATV', 'ATV2', 'ORF1', 'ORF2', 'ORF3', 'ORFSP', 'OE24TV', 'PULS4', 'SF1', 'SF2', 'CIN', 'SKY-F', 'SKY-A', 'SKY-N', 'SKYCH', 'SKY-CR', 'SKY-D', 'SKY-NA', 'TNT-F', 'KINOW', 'SKY1', 'SKYAT', 'SKY-K', 'SKYRP', 'UNIVE', 'HISHD', 'SP-GE', 'MOVTV', 'HDDIS', 'N-GHD', 'N-GW', '13TH', 'SCIFI', 'TNT-S', 'TNT-C', 'CRIN', 'ROM', 'C-NET', 'CLASS', 'APLAN', 'AXN', 'GEO', 'K1CLA', 'SAT1E', 'PRO7F', 'RTL-C', 'RTL-L', 'PASS', 'SILVE', 'SONY', 'SPTVW', 'TRACE']
provider = 'TV SPIELFILM (DE)'
lang = 'de'
enable_rating_mapper = True
days_to_grab = 2
episode_format = "onscreen"
channel_format = 'provider'
genre_format = "provider"

addon_name = "Takealug EPG Grabber"
addon_version = "1.1.7"

def xml_broadcast(episode_format, channel_id, item_title, item_starttime, item_endtime, item_description, item_country, item_picture, item_subtitle, items_genre, item_date, item_season, item_episode, item_agerating, item_starrating, items_director, items_producer, items_actor, enable_rating_mapper, lang):
    guide = []
    guide.append('\n')

    if (not item_starttime == '' and not item_endtime == '' and not item_title == ''):
        ## Programme Condition
        if (not item_starttime == '' and not item_endtime == ''):
            channel_id = channel_id.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            guide.append('    <programme start="{} +0000" stop="{} +0000" channel="{}">\n'.format(item_starttime, item_endtime, channel_id))

        stars = ''

        ## TITLE Condition
        if not item_title == '':
            item_title = item_title.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            guide.append('        <title lang="{}">{}</title>\n'.format(lang, item_title))

        ## SUBTITLE Condition
        if not item_subtitle == '':
            item_subtitle = item_subtitle.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            guide.append('        <sub-title lang="{}">{}</sub-title>\n'.format(lang, item_subtitle))

        ## DESCRIPTION Condition
        if not item_description == '':
            item_description = item_description.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('\n', '\n        ')
            if enable_rating_mapper == False:
                guide.append('        <desc lang="{}">{}</desc>\n'.format(lang, item_description))

            ## Rating Mapper
            elif enable_rating_mapper == True:
                country = '' if item_country == '' else '({})'.format(item_country)
                date = '' if item_date == '' else '{}'.format(item_date)
                season = '' if item_season == '' else '• S{}'.format(item_season)
                episode = '' if item_episode == '' else 'E{}'.format(item_episode)
                fsk = '' if item_agerating == '' else '• FSK {}'.format(item_agerating)
                imdbstars = '' if stars == '' else '{}'.format(stars)
                desc = '<desc lang="{}">{} {} {} {} {} {}'.format(lang, country, date, season, episode, fsk, imdbstars)
                guide.append('        {}\n        {}</desc>\n'.format(' '.join(desc.split()), item_description))

        ## CAST Condition
        if not items_producer == '':
            items_producer = items_producer.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        producerlist = items_producer.split(',')
        if not items_director == '':
            items_director = items_director.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        directorlist = items_director.split(',')
        if not items_actor == '':
            items_actor = items_actor.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        actorlist = items_actor.split(',')
        # Complete
        if (not items_director == '' and not items_producer == '' and not items_actor == ''):
            guide.append('        <credits>\n')
            for director in directorlist:
                guide.append('            <director>{}</director>\n'.format(director))
            for actor in actorlist:
                guide.append('            <actor>{}</actor>\n'.format(actor))
            for producer in producerlist:
                guide.append('            <producer>{}</producer>\n'.format(producer))
            guide.append('        </credits>\n')
        # Producer + Director
        elif (not items_director == '' and not items_producer == '' and items_actor == ''):
            guide.append('        <credits>' + '\n')
            for director in directorlist:
                guide.append('            <director>{}</director>\n'.format(director))
            for producer in producerlist:
                guide.append('            <producer>{}</producer>\n'.format(producer))
            guide.append('       </credits>\n')
        # Director + Actor
        elif (not items_director == '' and items_producer == '' and not items_actor == ''):
            guide.append('        <credits>\n')
            for director in directorlist:
                guide.append('            <director>{}</director>\n'.format(director))
            for actor in actorlist:
                guide.append('            <actor>{}</actor>\n'.format(actor))
            guide.append('        </credits>\n')
        # Producer + Actor
        elif (items_director == '' and not items_producer == '' and not items_actor == ''):
            guide.append('        <credits>\n')
            for actor in actorlist:
                guide.append('            <actor>{}</actor>\n'.format(actor))
            for producer in producerlist:
                guide.append('            <producer>{}</producer>\n'.format(producer))
            guide.append('        </credits>\n')
        # Only Director
        elif (not items_director == '' and items_producer == '' and items_actor == ''):
            guide.append('        <credits>\n')
            for director in directorlist:
                guide.append('            <director>{}</director>\n'.format(director))
            guide.append('        </credits>\n')
        # Only Producer
        if (items_director == '' and not items_producer == '' and items_actor == ''):
            guide.append('        <credits>\n')
            for producer in producerlist:
                guide.append('            <producer>{}</producer>\n'.format(producer))
            guide.append('        </credits>\n')
        # Only Actor
        if (items_director == '' and items_producer == '' and not items_actor == ''):
            guide.append('        <credits>\n')
            for actor in actorlist:
                guide.append('            <actor>{}</actor>\n'.format(actor))
            guide.append('        </credits>\n')

        ## DATE Condition
        if not item_date == '':
            guide.append('        <date>{}</date>\n'.format(item_date))

        ## GENRE Condition
        if not items_genre == '':
            items_genre = items_genre.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            genrelist = items_genre.split(',')
            for genre in genrelist:
                guide.append('        <category lang="{}">{}</category>\n'.format(lang, genre))


        ## IMAGE Condition
        if not item_picture == '':
            guide.append('        <icon src="{}"/>\n'.format(item_picture))

        ## COUNTRY Condition
        if not item_country == '':
            item_country = item_country.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            guide.append('        <country>{}</country>\n'.format(item_country))

        ## EPISODE Condition
        # XMLTV_NS
        if episode_format == 'xmltv_ns':
            if (not item_season == '' and not item_episode == ''):
                item_season_ns = int(item_season) - int(1)
                item_episode_ns = int(item_episode) - int(1)
                guide.append('        <episode-num system="xmltv_ns">{} . {} . </episode-num>\n'.format(str(item_season_ns),str(item_episode_ns)))
            elif (not item_season == '' and item_episode == ''):
                item_season_ns = int(item_season) - int(1)
                guide.append('        <episode-num system="xmltv_ns">{} . 0 . </episode-num>\n'.format(str(item_season_ns)))
            elif (item_season == '' and not item_episode == ''):
                item_episode_ns = int(item_episode) - int(1)
                guide.append('        <episode-num system="xmltv_ns">0 . {} . </episode-num>\n'.format(str(item_episode_ns)))
        # ONSCREEN
        elif episode_format == 'onscreen':
            if (not item_season == '' and not item_episode == ''):
                guide.append('        <episode-num system="onscreen">S{} E{}</episode-num>\n'.format(item_season, item_episode))
            elif (not item_season == '' and item_episode == ''):
                guide.append('        <episode-num system="onscreen">S{}</episode-num>\n'.format(item_season))
            elif (item_season == '' and not item_episode == ''):
                guide.append('        <episode-num system="onscreen">E{}</episode-num>\n'.format(item_episode))

        ## AGE-RATING Condition
        if (not item_agerating == ''):
            guide.append('        <rating>\n')
            guide.append('            <value>{}</value>\n'.format(item_agerating))
            guide.append('        </rating>\n')

        ## STAR-RATING Condition
        if (not item_starrating == ''):
            item_starrating = int(item_starrating) / int(10)
            guide.append('        <star-rating system="IMDb">\n')
            guide.append('            <value>{}/10</value>\n'.format(item_starrating))
            guide.append('        </star-rating>\n')

        guide.append('    </programme>\n')
        s = ''.join(guide)
        return s

def get_epg(tvs_data_url):
	channel_id = tvs_data_url.split("/")[0]
	guide = ["\n"]
	for playbilllist in requests.get("https://live.tvspielfilm.de/static/broadcast/list/%s" % tvs_data_url, headers=tvsDE_header).json():
		item_title = playbilllist.get('title', "")
		item_description = ""
		description = playbilllist.get('text')
		currentTopics = playbilllist.get('currentTopics')
		conclusion = playbilllist.get('conclusion')
		preview = playbilllist.get('preview')
		if conclusion: item_description += conclusion + "\n"
		if preview: item_description += preview + "\n"
		if currentTopics: item_description += currentTopics + "\n"
		if description: item_description += description + "\n"
		if item_description == "": item_description =  'No Program Information available'
		item_country = playbilllist.get('country',"")
		try: item_picture = playbilllist['images'][0]['size4']
		except: item_picture = ""
		item_subtitle = playbilllist.get('episodeTitle', "")
		items_genre = playbilllist.get('genre',"")
		item_date = playbilllist.get('year',"")
		item_agerating = playbilllist.get('fsk', playbilllist.get('childrenInfo', ""))
		items_director = playbilllist.get('director', "")
		try:
			actor_list = list()
			keys_actor = playbilllist['actors']
			for actor in keys_actor:
				actor_list.append(list(actor.values())[0])
			items_actor = ','.join(actor_list)
		except:
			items_actor = ''
		item_starrating = ''
		item_starttime = datetime.fromtimestamp(playbilllist['timestart']).strftime('%Y%m%d%H%M%S')
		item_endtime = datetime.fromtimestamp(playbilllist['timeend']).strftime('%Y%m%d%H%M%S')
		try: item_episode = re.sub(r"\D+", '#', playbilllist['episodeNumber']).split('#')[0]
		except: item_episode = ""
		try: item_season = re.sub(r"\D+", '#', playbilllist['seasonNumber']).split('#')[0]
		except: item_season = ""
		items_producer = ''
		## Programme Condition
		if (not item_starttime == '' and not item_endtime == ''):
			#channel_id = channel_id.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
			guide.append('	<programme start="{} +0000" stop="{} +0000" channel="{}">\n'.format(item_starttime, item_endtime, channel_id))

		stars = ''

		## TITLE Condition
		if not item_title == '':
			item_title = item_title.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
			guide.append('		<title lang="{}">{}</title>\n'.format(lang, item_title))

		## SUBTITLE Condition
		if not item_subtitle == '':
			item_subtitle = item_subtitle.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
			guide.append('		<sub-title lang="{}">{}</sub-title>\n'.format(lang, item_subtitle))

		## DESCRIPTION Condition
		if not item_description == '':
			item_description = item_description.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('\n', '\n		')
			if enable_rating_mapper == False:
				guide.append('		<desc lang="{}">{}</desc>\n'.format(lang, item_description))

			## Rating Mapper
			elif enable_rating_mapper == True:
				country = '' if item_country == '' else '({})'.format(item_country)
				date = '' if item_date == '' else '{}'.format(item_date)
				season = '' if item_season == '' else '• S{}'.format(item_season)
				episode = '' if item_episode == '' else 'E{}'.format(item_episode)
				fsk = '' if item_agerating == '' else '• FSK {}'.format(item_agerating)
				imdbstars = '' if stars == '' else '{}'.format(stars)
				desc = '<desc lang="{}">{} {} {} {} {} {}'.format(lang, country, date, season, episode, fsk, imdbstars)
				guide.append('		{}\n		{}</desc>\n'.format(' '.join(desc.split()), item_description))

		## CAST Condition
		if not items_producer == '':
			items_producer = items_producer.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
		producerlist = items_producer.split(',')
		if not items_director == '':
			items_director = items_director.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
		directorlist = items_director.split(',')
		if not items_actor == '':
			items_actor = items_actor.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
		actorlist = items_actor.split(',')
		# Complete
		if (not items_director == '' and not items_producer == '' and not items_actor == ''):
			guide.append('		<credits>\n')
			for director in directorlist:
				guide.append('			<director>{}</director>\n'.format(director))
			for actor in actorlist:
				guide.append('			<actor>{}</actor>\n'.format(actor))
			for producer in producerlist:
				guide.append('			<producer>{}</producer>\n'.format(producer))
			guide.append('		</credits>\n')
		# Producer + Director
		elif (not items_director == '' and not items_producer == '' and items_actor == ''):
			guide.append('		<credits>' + '\n')
			for director in directorlist:
				guide.append('			<director>{}</director>\n'.format(director))
			for producer in producerlist:
				guide.append('			<producer>{}</producer>\n'.format(producer))
			guide.append('	   </credits>\n')
		# Director + Actor
		elif (not items_director == '' and items_producer == '' and not items_actor == ''):
			guide.append('		<credits>\n')
			for director in directorlist:
				guide.append('			<director>{}</director>\n'.format(director))
			for actor in actorlist:
				guide.append('			<actor>{}</actor>\n'.format(actor))
			guide.append('		</credits>\n')
		# Producer + Actor
		elif (items_director == '' and not items_producer == '' and not items_actor == ''):
			guide.append('		<credits>\n')
			for actor in actorlist:
				guide.append('			<actor>{}</actor>\n'.format(actor))
			for producer in producerlist:
				guide.append('			<producer>{}</producer>\n'.format(producer))
			guide.append('		</credits>\n')
		# Only Director
		elif (not items_director == '' and items_producer == '' and items_actor == ''):
			guide.append('		<credits>\n')
			for director in directorlist:
				guide.append('			<director>{}</director>\n'.format(director))
			guide.append('		</credits>\n')
		# Only Producer
		if (items_director == '' and not items_producer == '' and items_actor == ''):
			guide.append('		<credits>\n')
			for producer in producerlist:
				guide.append('			<producer>{}</producer>\n'.format(producer))
			guide.append('		</credits>\n')
		# Only Actor
		if (items_director == '' and items_producer == '' and not items_actor == ''):
			guide.append('		<credits>\n')
			for actor in actorlist:
				guide.append('			<actor>{}</actor>\n'.format(actor))
			guide.append('		</credits>\n')

		## DATE Condition
		if not item_date == '':
			guide.append('		<date>{}</date>\n'.format(item_date))

		## GENRE Condition
		if not items_genre == '':
			items_genre = items_genre.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
			genrelist = items_genre.split(',')
			for genre in genrelist:
				guide.append('		<category lang="{}">{}</category>\n'.format(lang, genre))


		## IMAGE Condition
		if not item_picture == '':
			guide.append('		<icon src="{}"/>\n'.format(item_picture))

		## COUNTRY Condition
		if not item_country == '':
			item_country = item_country.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
			guide.append('		<country>{}</country>\n'.format(item_country))

		## EPISODE Condition
		# XMLTV_NS
		if episode_format == 'xmltv_ns':
			if (not item_season == '' and not item_episode == ''):
				item_season_ns = int(item_season) - int(1)
				item_episode_ns = int(item_episode) - int(1)
				guide.append('		<episode-num system="xmltv_ns">{} . {} . </episode-num>\n'.format(str(item_season_ns),str(item_episode_ns)))
			elif (not item_season == '' and item_episode == ''):
				item_season_ns = int(item_season) - int(1)
				guide.append('		<episode-num system="xmltv_ns">{} . 0 . </episode-num>\n'.format(str(item_season_ns)))
			elif (item_season == '' and not item_episode == ''):
				item_episode_ns = int(item_episode) - int(1)
				guide.append('		<episode-num system="xmltv_ns">0 . {} . </episode-num>\n'.format(str(item_episode_ns)))
		# ONSCREEN
		elif episode_format == 'onscreen':
			if (not item_season == '' and not item_episode == ''):
				guide.append('		<episode-num system="onscreen">S{} E{}</episode-num>\n'.format(item_season, item_episode))
			elif (not item_season == '' and item_episode == ''):
				guide.append('		<episode-num system="onscreen">S{}</episode-num>\n'.format(item_season))
			elif (item_season == '' and not item_episode == ''):
				guide.append('		<episode-num system="onscreen">E{}</episode-num>\n'.format(item_episode))

		## AGE-RATING Condition
		if (not item_agerating == ''):
			guide.append('		<rating>\n')
			guide.append('			<value>{}</value>\n'.format(item_agerating))
			guide.append('		</rating>\n')

		## STAR-RATING Condition
		if (not item_starrating == ''):
			item_starrating = int(item_starrating) / int(10)
			guide.append('		<star-rating system="IMDb">\n')
			guide.append('			<value>{}/10</value>\n'.format(item_starrating))
			guide.append('		</star-rating>\n')

		guide.append('	</programme>\n')
	return ''.join(guide)


base_url = "https://live.tvspielfilm.de/api/cms/"
tvsDE_channellist_url = base_url + "channels/list"
tvsDE_chlist_url = requests.get(tvsDE_channellist_url, headers=tvsDE_header).json()


epg = ['<?xml version="1.0" encoding="UTF-8" ?>\n<!DOCTYPE tv SYSTEM "xmltv.dtd">\n<!-- EPG XMLTV FILE CREATED BY Take-a-LUG TEAM- (c) 2020 Bastian Kleinschmidt -->\n<!-- created on {} -->\n<tv generator-info-name="Takealug EPG Grabber Ver. {}" generator-info-url="https://github.com/DeBaschdi/service.takealug.epg-grabber">\n'.format(str(now), addon_version)]
epg.append('\n<!--  {}  CHANNEL LIST -->\n'.format('ZAPPN'))
epg.append('    <channel id="{}">\n'.format('PULS24'))
epg.append('        <display-name lang="{}">{}</display-name>\n'.format(lang, 'PULS24'))
epg.append('        <icon src="{}" />\n'.format('https://upload.wikimedia.org/wikipedia/commons/thumb/2/2f/PULS24logo.png/640px-PULS24logo.png'))
epg.append('    </channel>\n')
epg.append('\n<!--  {}  CHANNEL LIST -->\n'.format(provider))



tvs_data_urls = []
for channel in tvsDE_chlist_url:
	channel_id = channel['channelId']
	if channel_id not in contentIDs: continue
	channel_icon = base_url+ channel["imageLarge"]
	channel_name = channel['name']
	channel_name_short = channel['nameShort']
	epg.append('    <channel id="{}">\n'.format(channel_id))
	epg.append('        <display-name lang="{}">{}</display-name>\n'.format(lang, channel_name))
	epg.append('        <icon src="{}" />\n'.format(channel_icon))
	epg.append('    </channel>\n')
	day_to_start = datetime(today.year, today.month, today.day, hour=00, minute=00, second=1)
	for i in range(0, days_to_grab):
		day_to_grab = day_to_start.strftime("%Y-%m-%d")
		day_to_start += timedelta(days=1)
		tvs_data_urls.append('{}/{}'.format(channel_id, day_to_grab))


epg.append('\n<!--  {}  CHANNEL LIST -->\n'.format('MAGENTA TV (DE)'))
magentaDE_channels = magentaSession().post(magentaDE_channellist_url, json=magentaDE_get_chlist,headers=magentaDE_header).json()
for channels in magentaDE_channels["channellist"]:
	channel_id = channels['contentId']
	if channel_id not in magentacontentIDs: continue
	channel_name = channels['name']
	for image in channels['pictures']:
		if image['imageType'] == '15':
			channel_icon = image['href']
	epg.append('    <channel id="{}">\n'.format(channel_id))
	epg.append('        <display-name lang="{}">{}</display-name>\n'.format(lang, channel_name))
	epg.append('        <icon src="{}" />\n'.format(channel_icon))
	epg.append('    </channel>\n')


epg.append('\n<!--  {}  PROGRAMME LIST -->'.format('ZAPPN'))
api_headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/110.0', 'Content-type': 'application/json;charset=utf-8', 'X-Api-Date-Format': 'iso', 'X-Api-Camel-Case': 'true', 'referer': 'https://streaming.simplitv.at/'}
time_start = str(now.strftime("%Y-%m-%dT%H:%M:00.000Z"))
time_end = str((now + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:00.000Z"))
epg_url = "https://api.app.simplitv.at/v1/EpgTile/FilterProgramTiles"
epg_post = {"platformCodename": "www", "from": time_start, "to": time_end}
epg_resp = requests.post(epg_url, timeout=5, headers=api_headers, json=epg_post, allow_redirects=False).json()["programs"]
prg_url = "https://api.app.simplitv.at/v2/Tile/GetTiles"
prg_post = {"platformCodename": "www", "requestedTiles": [{"id": a["id"]} for i in epg_resp.keys() for a in epg_resp[i] if i == "puls24"]}
epg_data = requests.post(prg_url, timeout=5, headers=api_headers, json=prg_post, allow_redirects=False).json()["tiles"]
for program in epg_data:
	item_starttime = datetime.strptime(program["start"].split('+')[0], '%Y-%m-%dT%H:%M:%S').strftime('%Y%m%d%H%M%S')
	item_endtime = datetime.strptime(program["stop"].split('+')[0], '%Y-%m-%dT%H:%M:%S').strftime('%Y%m%d%H%M%S')
	items_genre = ', '.join([i.get('name', "") for i in program.get('categories', []) if i["typeCodename"] != "genre"])
	item_country = ', '.join([i['name'] for i in program['countries']]) if len(program.get("countries", [])) > 0 else ""
	item_description = program.get("description", "").strip("\n\n").strip("<br /><br />")
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
			if i["roleCodename"] == "director":
				items_director = i["fullName"]
			else:
				if not c.get('[B]'+i["roleName"]+'[/B]', False):
					c['[B]'+i["roleName"]+'[/B]'] = []
				c['[B]'+i["roleName"]+'[/B]'].append(i["fullName"])
		items_actor = '; '.join([i+': '+', '.join([a for a in c[i]]) for i in c.keys()])
	else: items_actor = ""
	epg.append(xml_broadcast('onscreen', "PULS24", item_title, item_starttime, item_endtime, item_description, item_country, item_picture, item_subtitle, items_genre, item_date, item_season, item_episode, item_agerating, item_starrating, items_director, items_producer, items_actor, False, "de"))


epg.append('\n<!--  {}  PROGRAMME LIST -->'.format(provider))


with ThreadPoolExecutor(len(tvs_data_urls)) as executor:
	futures = [executor.submit(get_epg, tvs_data_url) for tvs_data_url in tvs_data_urls]
	for future in as_completed(futures):
		o = future.result()
		epg.append(o)

epg.append('\n<!--  {}  PROGRAMME LIST -->'.format('MAGENTA TV (DE)'))
starttime = datetime(today.year, today.month, today.day, hour=00, minute=00, second=1).strftime("%Y%m%d%H%M%S")
calc_then = datetime(today.year, today.month, today.day, hour=23, minute=59, second=59)
calc_then += timedelta(days=days_to_grab)
endtime = calc_then.strftime("%Y%m%d%H%M%S")
for contentID in magentacontentIDs:
	magentaDE_data = {'channelid': contentID, 'type': '2', 'offset': '0', 'count': '-1', 'isFillProgram': '1','properties': '[{"name":"playbill","include":"ratingForeignsn,id,channelid,name,subName,starttime,endtime,cast,casts,country,producedate,ratingid,pictures,type,introduce,foreignsn,seriesID,genres,subNum,seasonNum"}]','endtime': endtime, 'begintime': starttime}
	magentaData = magentaSession().post(magentaDE_data_url, json=magentaDE_data, headers=magentaDE_header).json()['playbilllist']
	for playbilllist in magentaData:
		item_title = playbilllist.get('name',"")
		item_starttime = playbilllist.get('starttime', "")
		item_endtime = playbilllist.get('endtime',"")
		item_description = playbilllist.get('introduce',"")
		item_country = playbilllist.get('country',"")
		try:
			item_picture = playbilllist['pictures'][1]['href']
		except (KeyError, IndexError):
			item_picture = ''
		item_subtitle = playbilllist.get('subName',"")
		items_genre = playbilllist.get('genres',"")
		item_date = playbilllist.get('producedate',"")
		item_season = playbilllist.get('seasonNum',"")
		item_episode = playbilllist.get('subNum', "")
		item_agerating = playbilllist.get('ratingid', "")
		try:
			items_director = playbilllist['cast']['director']
		except (KeyError, IndexError):
			items_director = ''
		try:
			items_producer = playbilllist['cast']['producer']
		except (KeyError, IndexError):
			items_producer = ''
		try:
			items_actor = playbilllist['cast']['actor']
		except (KeyError, IndexError):
			items_actor = ''
		item_starrating = ''
		if not item_date == '':
			item_date = item_date.split('-')
			item_date = item_date[0]
		if (not item_starttime == '' and not item_endtime == ''):
			start = item_starttime.split(' UTC')
			item_starttime = start[0].replace(' ', '').replace('-', '').replace(':', '')
			stop = item_endtime.split(' UTC')
			item_endtime = stop[0].replace(' ', '').replace('-', '').replace(':', '')
		if not item_country == '':
			item_country = item_country.upper()
		if item_agerating == '-1':
			item_agerating = ''
		epg.append(xml_broadcast(episode_format, contentID, item_title, item_starttime, item_endtime, item_description, item_country, item_picture, item_subtitle, items_genre, item_date, item_season, item_episode, item_agerating, item_starrating, items_director, items_producer, items_actor, enable_rating_mapper, lang))

epg.append('\n</tv>\n')


datapath = os.path.abspath(os.path.dirname(__file__))
guide_dest = os.path.join(os.path.dirname(datapath), 'guide.xml')
guidegz_dest = os.path.join(os.path.dirname(datapath), 'guide.xml.gz')
with open(guide_dest, "w") as k:
	k.write("".join(epg))
with open(guide_dest, 'rb') as f_in, gzip.open(guidegz_dest, 'wb') as f_out:
	f_out.writelines(f_in)