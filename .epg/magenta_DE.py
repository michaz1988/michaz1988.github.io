# -*- coding: utf-8 -*-
import json, tools,time
import os
import sys
import requests.cookies
import requests.adapters
import requests
from datetime import datetime
from datetime import timedelta
import xml_structure
import mapper
import filesplit
from tools import datapath, temppath, log, notify, addon_name, addon_version, loc

provider = 'MAGENTA TV (DE)'
lang = 'de'
provider_temppath = os.path.join(temppath, "magentaDE")

## Enable Multithread
enable_multithread = False
if enable_multithread:
    try:
        from multiprocessing import Process
    except:
        pass

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
days_to_grab = 2
episode_format = "onscreen"
channel_format = 'provider'
genre_format = "provider"

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
magentaDE_chlist_provider_tmp = os.path.join(provider_temppath, 'chlist_magentaDE_provider_tmp.json')
magentaDE_chlist_provider = os.path.join(provider_temppath, 'chlist_magentaDE_provider.json')
magentaDE_chlist_selected = os.path.join(datapath, 'chlist_magentaDE_selected.json')

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
magentaDE_session_cookie = os.path.join(provider_temppath, 'cookies.json')


## Login and Authenticate to web.magenta.tv
def magentaDE_session():
    session = requests.Session()
    session.post(magentaDE_login_url, data=json.dumps(magentaDE_login), headers=magentaDE_header)
    session.post(magentaDE_authenticate_url, data=json.dumps(magentaDE_authenticate), headers=magentaDE_header)
    ## Save Cookies to Disk
    with open(magentaDE_session_cookie, 'w', encoding='utf-8') as f:
        json.dump(requests.utils.dict_from_cookiejar(session.cookies), f)


## Get channel list(url)
def get_channellist():
    magentaDE_session()
    session = requests.Session()
    ## Load Cookies from Disk
    with open(magentaDE_session_cookie, 'r', encoding='utf-8') as f:
        session.cookies = requests.utils.cookiejar_from_dict(json.load(f))

    magenta_CSRFToken = session.cookies["CSRFSESSION"]
    session.headers.update({'X_CSRFToken': magenta_CSRFToken})
    magenta_chlist_url = session.post(magentaDE_channellist_url, data=json.dumps(magentaDE_get_chlist),headers=magentaDE_header)
    magenta_chlist_url.raise_for_status()
    response = magenta_chlist_url.json()

    with open(magentaDE_chlist_provider_tmp, 'w', encoding='utf-8') as provider_list_tmp:
        json.dump(response, provider_list_tmp)

    #### Transform magentaDE_chlist_provider_tmp to Standard chlist Format as magentaDE_chlist_provider

    # Load Channellist from Provider
    with open(magentaDE_chlist_provider_tmp, 'r', encoding='utf-8') as provider_list_tmp:
        magentaDE_channels = json.load(provider_list_tmp)

    # Create empty new hznDE_chlist_provider
    with open(magentaDE_chlist_provider, 'w', encoding='utf-8') as provider_list:
        provider_list.write(json.dumps({"channellist": []}))

    ch_title = ''

    # Load New Channellist from Provider
    with open(magentaDE_chlist_provider, encoding='utf-8') as provider_list:
        data = json.load(provider_list)

        temp = data['channellist']

        for channels in magentaDE_channels['channellist']:
            ch_id = channels['contentId']
            ch_title = channels['name']
            for image in channels['pictures']:
                if image['imageType'] == '15':
                    hdimage = image['href']
            # channel to be appended
            y = {"contentId": ch_id,
                 "name": ch_title,
                 "pictures": [{"href": hdimage}]}

            # appending channels to data['channellist']
            temp.append(y)

    #Save New Channellist from Provider
    with open(magentaDE_chlist_provider, 'w', encoding='utf-8') as provider_list:
        json.dump(data, provider_list, indent=4)

def select_channels():
    ## Create Provider Temppath if not exist
    if not os.path.exists(provider_temppath):
        os.makedirs(provider_temppath)

    ## Create empty (Selected) Channel List if not exist
    if not os.path.isfile(magentaDE_chlist_selected):
        with open((magentaDE_chlist_selected), 'w', encoding='utf-8') as selected_list:
            selected_list.write(json.dumps({"channellist": []}))

    ## Download chlist_magenta_provider.json
    get_channellist()

    with open(magentaDE_chlist_provider, 'r', encoding='utf-8') as o:
        provider_list = json.load(o)

    with open(magentaDE_chlist_selected, 'r', encoding='utf-8') as s:
        selected_list = json.load(s)

    ## Start Channel Selector
    user_select = True

    if user_select is not None:
        with open(magentaDE_chlist_selected, 'w', encoding='utf-8') as f:
            json.dump(user_select, f, indent=4)
        if os.path.isfile(magentaDE_chlist_selected):
            valid = check_selected_list()
            if valid is True:
                ok = dialog.ok(provider, loc(32402))
                if ok:
                    log(loc(32402))
            elif valid is False:
                log(loc(32403))
                yn = OSD.yesno(provider, loc(32403))
                if yn:
                    select_channels()
                else:
                    tools.delete(magentaDE_chlist_selected)
                    exit()
    else:
        valid = check_selected_list()
        if valid is True:
            ok = dialog.ok(provider, loc(32404))
            if ok:
                log(loc(32404))
        elif valid is False:
            log(loc(32403))
            yn = OSD.yesno(provider, loc(32403))
            if yn:
                select_channels()
            else:
                tools.delete(magentaDE_chlist_selected)
                exit()

def check_selected_list():
    check = 'invalid'
    with open(magentaDE_chlist_selected, 'r', encoding='utf-8') as c:
        selected_list = json.load(c)
    for user_list in selected_list['channellist']:
        if 'contentId' in user_list:
            check = 'valid'
    if check == 'valid':
        return True
    else:
        return False

def download_multithread(thread_temppath, download_threads):
    # delete old broadcast files if exist
    for f in os.listdir(provider_temppath):
        if f.endswith('_broadcast.json'):
            tools.delete(os.path.join(provider_temppath, f))

    magentaDE_session()
    list = os.path.join(provider_temppath, 'list.txt')
    splitname = os.path.join(thread_temppath, 'chlist_magentaDE_selected')
    starttime, endtime = get_epgLength(days_to_grab)

    with open(magentaDE_chlist_selected, 'r', encoding='utf-8') as s:
        selected_list = json.load(s)
    if filesplit.split_chlist_selected(thread_temppath, magentaDE_chlist_selected, splitname, download_threads, enable_multithread):
        multi = True
        needed_threads = sum([len(files) for r, d, files in os.walk(thread_temppath)])
        items_to_download = str(len(selected_list['channellist']))
        log('{} {} {} '.format(provider, items_to_download, loc(32361)))
        log('{} Multithread({}) Mode'.format(provider, needed_threads))
        notify('{} {} '.format(loc(32500), provider), '{} {}'.format('100', loc(32501)))

        jobs = []
        for thread in range(0, int(needed_threads)):
            p = Process(target=download_thread, args=('{}_{}.json'.format(splitname, int(thread)), multi, list, starttime, endtime, ))
            jobs.append(p)
            p.start()
        for j in jobs:
            while j.is_alive():
                time.sleep(0.1)
                try:
                    last_line = ''
                    with open(list, 'r', encoding='utf-8') as f:
                        last_line = f.readlines()[-1]
                except:
                    pass
                items = sum(1 for f in os.listdir(provider_temppath) if f.endswith('_broadcast.json'))
                percent_remain = int(100) - int(items) * int(100) / int(items_to_download)
                percent_completed = int(100) * int(items) / int(items_to_download)
                notify(int(percent_completed), '{} {} '.format(loc(32500), last_line), '{} {} {}'.format(int(percent_remain), loc(32501), provider))
                if int(items) == int(items_to_download):
                    log('{} {}'.format(provider, loc(32363)))
                    break
            j.join()
        
        for file in os.listdir(thread_temppath): tools.delete(os.path.join(thread_temppath, file))

    else:
        multi = False
        log('{} {} '.format(provider, 'Can`t download in Multithreading mode, loading single...'))
        download_thread(magentaDE_chlist_selected, multi, list, starttime, endtime)

def download_thread(magentaDE_chlist_selected, multi, list, starttime, endtime):
    requests.adapters.DEFAULT_RETRIES = 5
    session = requests.Session()

    ## Load Cookies from Disk
    with open(magentaDE_session_cookie, 'r', encoding='utf-8') as f:
        session.cookies = requests.utils.cookiejar_from_dict(json.load(f))
    magenta_CSRFToken = session.cookies["CSRFSESSION"]
    session.headers.update({'X_CSRFToken': magenta_CSRFToken})

    with open(magentaDE_chlist_selected, 'r', encoding='utf-8') as s:
        selected_list = json.load(s)

    if not multi:
        items_to_download = str(len(selected_list['channellist']))
        log('{} {} {} '.format(provider, items_to_download, loc(32361)))
        notify('{} {} '.format(loc(32500), provider), '{} {}'.format('100', loc(32501)))

    for user_item in selected_list['channellist']:
        contentID = user_item['contentId']
        channel_name = user_item['name']
        magentaDE_data = {'channelid': contentID, 'type': '2', 'offset': '0', 'count': '-1', 'isFillProgram': '1','properties': '[{"name":"playbill","include":"ratingForeignsn,id,channelid,name,subName,starttime,endtime,cast,casts,country,producedate,ratingid,pictures,type,introduce,foreignsn,seriesID,genres,subNum,seasonNum"}]','endtime': endtime, 'begintime': starttime}
        response = session.post(magentaDE_data_url, data=json.dumps(magentaDE_data), headers=magentaDE_header)
        response.raise_for_status()
        tkm_data = response.json()
        broadcast_files = os.path.join(provider_temppath, '{}_broadcast.json'.format(contentID))
        with open(broadcast_files, 'w', encoding='utf-8') as playbill:
            json.dump(tkm_data, playbill)

        ## Create a List with downloaded channels
        last_channel_name = '{}\n'.format(channel_name)
        with open(list, 'a', encoding='utf-8') as f:
            f.write(last_channel_name)

        if not multi:
            items = sum(1 for f in os.listdir(provider_temppath) if f.endswith('_broadcast.json'))
            percent_remain = int(100) - int(items) * int(100) / int(items_to_download)
            percent_completed = int(100) * int(items) / int(items_to_download)
            notify(int(percent_completed), '{} {} '.format(loc(32500), channel_name), '{} {} {}'.format(int(percent_remain), loc(32501), provider))
            if int(items) == int(items_to_download):
                log('{} {}'.format(provider, loc(32363)))
                break
    if not multi:
    	pass
        


def create_xml_channels():
    log('{} {}'.format(provider,loc(32362)))
    if channel_format == 'rytec':
        ## Save tkm_channels.json to Disk
        tkm_channels_response = requests.get(tkm_channels_url).json()
        with open(tkm_channels_json, 'w', encoding='utf-8') as tkm_channels:
            json.dump(tkm_channels_response, tkm_channels)

    with open(magentaDE_chlist_selected, 'r', encoding='utf-8') as c:
        selected_list = json.load(c)

    items_to_download = str(len(selected_list['channellist']))
    items = 0

    notify('{} {} '.format(loc(32502),provider), '{} {}'.format('100',loc(32501)))

    ## Create XML Channels Provider information
    xml_structure.xml_channels_start(provider)

    for user_item in selected_list['channellist']:
        items += 1
        percent_remain = int(100) - int(items) * int(100) / int(items_to_download)
        percent_completed = int(100) * int(items) / int(items_to_download)
        channel_name = user_item['name']
        channel_icon = user_item['pictures'][0]['href']
        channel_id = channel_name
        notify(int(percent_completed), '{} {} '.format(loc(32502),channel_name),'{} {} {}'.format(int(percent_remain),loc(32501),provider))
        if str(percent_completed) == str(100):
            log('{} {}'.format(provider,loc(32364)))

        ## Map Channels
        if not channel_id == '':
            channel_id = mapper.map_channels(channel_id, channel_format, tkm_channels_json, magentaDE_channels_warnings_tmp, lang)

        ## Create XML Channel Information with provided Variables
        xml_structure.xml_channels(channel_name, channel_id, channel_icon, lang)
    


def create_xml_broadcast(enable_rating_mapper, thread_temppath, download_threads):

    download_multithread(thread_temppath, download_threads)
    log('{} {}'.format(provider, loc(32365)))

    if genre_format == 'eit':
        ## Save tkm_genres.json to Disk
        tkm_genres_response = requests.get(tkm_genres_url).json()
        with open(tkm_genres_json, 'w', encoding='utf-8') as tkm_genres:
            json.dump(tkm_genres_response, tkm_genres)

    with open(magentaDE_chlist_selected, 'r', encoding='utf-8') as c:
        selected_list = json.load(c)

    items_to_download = str(len(selected_list['channellist']))
    items = 0
    notify('{} {} '.format(loc(32503), provider), '{} Prozent verbleibend'.format('100'))

    ## Create XML Broadcast Provider information
    xml_structure.xml_broadcast_start(provider)

    for user_item in selected_list['channellist']:
        items += 1
        percent_remain = int(100) - int(items) * int(100) / int(items_to_download)
        percent_completed = int(100) * int(items) / int(items_to_download)
        contentID = user_item['contentId']
        channel_name = user_item['name']
        channel_id = channel_name
        notify(int(percent_completed), '{} {} '.format(loc(32503), channel_name), '{} {} {}'.format(int(percent_remain), loc(32501), provider))
        if str(percent_completed) == str(100):
            log('{} {}'.format(provider, loc(32366)))

        broadcast_files = os.path.join(provider_temppath, '{}_broadcast.json'.format(contentID))
        with open(broadcast_files, 'r', encoding='utf-8') as b:
            broadcastfiles = json.load(b)

        ### Map Channels
        if not channel_id == '':
            channel_id = mapper.map_channels(channel_id, channel_format, tkm_channels_json, magentaDE_channels_warnings_tmp, lang)

        try:
            for playbilllist in broadcastfiles['playbilllist']:
                try:
                    item_title = playbilllist['name']
                except (KeyError, IndexError):
                    item_title = ''
                try:
                    item_starttime = playbilllist['starttime']
                except (KeyError, IndexError):
                    item_starttime = ''
                try:
                    item_endtime = playbilllist['endtime']
                except (KeyError, IndexError):
                    item_endtime = ''
                try:
                    item_description = playbilllist['introduce']
                except (KeyError, IndexError):
                    item_description = ''
                try:
                    item_country = playbilllist['country']
                except (KeyError, IndexError):
                    item_country = ''
                try:
                    item_picture = playbilllist['pictures'][1]['href']
                except (KeyError, IndexError):
                    item_picture = ''
                try:
                    item_subtitle = playbilllist['subName']
                except (KeyError, IndexError):
                    item_subtitle = ''
                try:
                    items_genre = playbilllist['genres']
                except (KeyError, IndexError):
                    items_genre = ''
                try:
                    item_date = playbilllist['producedate']
                except (KeyError, IndexError):
                    item_date = ''
                try:
                    item_season = playbilllist['seasonNum']
                except (KeyError, IndexError):
                    item_season = ''
                try:
                    item_episode = playbilllist['subNum']
                except (KeyError, IndexError):
                    item_episode = ''
                try:
                    item_agerating = playbilllist['ratingid']
                except (KeyError, IndexError):
                    item_agerating = ''
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

                # Transform items to Readable XML Format
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

                # Map Genres
                if not items_genre == '':
                    items_genre = mapper.map_genres(items_genre, genre_format, tkm_genres_json, magentaDE_genres_warnings_tmp, lang)

                ## Create XML Broadcast Information with provided Variables
                xml_structure.xml_broadcast(episode_format, channel_id, item_title, item_starttime, item_endtime,
                                            item_description, item_country, item_picture, item_subtitle, items_genre,
                                            item_date, item_season, item_episode, item_agerating, item_starrating, items_director,
                                            items_producer, items_actor, enable_rating_mapper, lang)

        except (KeyError, IndexError):
            log('{} {} {} {} {} {}'.format(provider,loc(32367),channel_name,loc(32368),contentID,loc(32369)))
    

    ## Create Channel Warnings Textile
    channel_pull = '\nPlease Create an Pull Request for Missing Rytec Id´s to https://github.com/sunsettrack4/config_files/blob/master/tkm_channels.json\n'
    mapper.create_channel_warnings(magentaDE_channels_warnings_tmp, magentaDE_channels_warnings, provider, channel_pull)

    ## Create Genre Warnings Textfile
    genre_pull = '\nPlease Create an Pull Request for Missing EIT Genres to https://github.com/sunsettrack4/config_files/blob/master/tkm_genres.json\n'
    mapper.create_genre_warnings(magentaDE_genres_warnings_tmp, magentaDE_genres_warnings, provider, genre_pull)

    notify(addon_name, '{} {} {}'.format(loc(32370),provider,loc(32371)))
    log('{} {} {}'.format(loc(32370),provider,loc(32371)))
    time.sleep(4)

    if (os.path.isfile(magentaDE_channels_warnings) or os.path.isfile(magentaDE_genres_warnings)):
        notify(provider, '{}'.format(loc(32372)))
        time.sleep(3)

    ## Delete old Tempfiles, not needed any more
    for file in os.listdir(provider_temppath): tools.delete(os.path.join(provider_temppath, file))


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
        if yn:
            select_channels()
        else:
            tools.delete(magentaDE_chlist_selected)
            return False

    ## If a Selected list exist, check valid
    valid = check_selected_list()
    if valid is False:
        yn = OSD.yesno(provider, loc(32405))
        if yn:
            select_channels()
        else:
            tools.delete(magentaDE_chlist_selected)
            return False
    return True

def startup():
    if check_provider():
        get_channellist()
        return True
    else:
        return False

# Channel Selector
try:
    if sys.argv[1] == 'select_channels_magentaDE':
        select_channels()
except IndexError:
    pass