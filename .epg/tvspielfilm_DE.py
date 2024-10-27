# -*- coding: utf-8 -*-
import json
import os
import sys
import requests.cookies
import requests.adapters
import requests
import re
from datetime import datetime
from datetime import timedelta
import xml_structure
import mapper
import filesplit

provider = 'TV SPIELFILM (DE)'
lang = 'de'

from tools import *
provider_temppath = os.path.join(temppath, "tvsDE")

## Enable Multithread
enable_multithread = False
if enable_multithread:
    try:
        from multiprocessing import Process
    except:
        pass

## MAPPING Variables Thx @ sunsettrack4
tvsDE_genres_url = 'https://raw.githubusercontent.com/sunsettrack4/config_files/master/tvs_genres.json'
tvsDE_genres_json = os.path.join(provider_temppath, 'tvs_genres.json')
tvsDE_channels_url = 'https://raw.githubusercontent.com/sunsettrack4/config_files/master/tvs_channels.json'
tvsDE_channels_json = os.path.join(provider_temppath, 'tvs_channels.json')

## Log Files
tvsDE_genres_warnings_tmp = os.path.join(provider_temppath, 'tvsDE_genres_warnings.txt')
tvsDE_genres_warnings = os.path.join(temppath, 'tvsDE_genres_warnings.txt')
tvsDE_channels_warnings_tmp = os.path.join(provider_temppath, 'tvsDE_channels_warnings.txt')
tvsDE_channels_warnings = os.path.join(temppath, 'tvsDE_channels_warnings.txt')

## Read tvsDE Settings
days_to_grab = 2
episode_format = "onscreen"
channel_format = 'provider'
genre_format = "provider"


# Make a debug logger
#def log(message, loglevel=xbmc.LOGDEBUG):
    #xbmc.log('[{} {}] {}'.format(addon_name, addon_version, message), loglevel)


# Make OSD Notify Messages
#OSD = xbmcgui.Dialog()


#def notify(title, message, icon=xbmcgui.NOTIFICATION_INFO):
    #OSD.notification(title, message, icon)

# Calculate Date and Time
today = datetime.today()


## Channel Files
tvsDE_chlist_provider_tmp = os.path.join(provider_temppath, 'chlist_tvsDE_provider_tmp.json')
tvsDE_chlist_provider = os.path.join(provider_temppath, 'chlist_tvsDE_provider.json')
tvsDE_chlist_selected = os.path.join(datapath, 'chlist_tvsDE_selected.json')


tvsDE_header = {'Host': 'live.tvspielfilm.de',
                  'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:75.0) Gecko/20100101 Firefox/75.0',
                  'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                  'Accept-Language': 'de,en-US;q=0.7,en;q=0.3',
                  'Accept-Encoding': 'gzip, deflate, br',
                  'Connection': 'keep-alive',
                  'Upgrade-Insecure-Requests': '1'}

def get_channellist():
    tvsDE_channellist_url = 'https://live.tvspielfilm.de/static/content/channel-list/livetv'
    tvsDE_chlist_url = requests.get(tvsDE_channellist_url, headers=tvsDE_header)
    tvsDE_chlist_url.raise_for_status()
    response = tvsDE_chlist_url.json()
    with open(tvsDE_chlist_provider_tmp, 'w', encoding='utf-8') as provider_list_tmp:
        json.dump(response, provider_list_tmp)

    #### Transform tvsDE_chlist_provider_tmp to Standard chlist Format as tvsDE_chlist_provider

    # Load Channellist from Provider
    with open(tvsDE_chlist_provider_tmp, 'r', encoding='utf-8') as provider_list_tmp:
        tvsDE_channels = json.load(provider_list_tmp)

    # Create empty new tvsDE_chlist_provider
    with open(tvsDE_chlist_provider, 'w', encoding='utf-8') as provider_list:
        provider_list.write(json.dumps({"channellist": []}))

    ch_title = ''

    # Load New Channellist from Provider
    with open(tvsDE_chlist_provider, encoding='utf-8') as provider_list:
        data = json.load(provider_list)

        temp = data['channellist']

        for channels in tvsDE_channels:
            ch_id = channels['id']
            ch_title = channels['name']
            try:
                hdimage = channels['image_large']['url']
            except:
                hdimage = ""
            # channel to be appended
            y = {"contentId": ch_id,
                 "name": ch_title,
                 "pictures": [{"href": hdimage}]}

            # appending channels to data['channellist']
            temp.append(y)

    #Save New Channellist from Provider
    with open(tvsDE_chlist_provider, 'w', encoding='utf-8') as provider_list:
        json.dump(data, provider_list, indent=4)

def select_channels():
    ## Create Provider Temppath if not exist
    if not os.path.exists(provider_temppath):
        os.makedirs(provider_temppath)

    ## Create empty (Selected) Channel List if not exist
    if not os.path.isfile(tvsDE_chlist_selected):
        with open((tvsDE_chlist_selected), 'w', encoding='utf-8') as selected_list:
            selected_list.write(json.dumps({"channellist": []}))

    ## Download chlist_tvsDE_provider.json
    get_channellist()
    #dialog = xbmcgui.Dialog()

    with open(tvsDE_chlist_provider, 'r', encoding='utf-8') as o:
        provider_list = json.load(o)

    with open(tvsDE_chlist_selected, 'r', encoding='utf-8') as s:
        selected_list = json.load(s)

    ## Start Channel Selector
    user_select = channel_selector.select_channels(provider, provider_list, selected_list)

    if user_select is not None:
        with open(tvsDE_chlist_selected, 'w', encoding='utf-8') as f:
            json.dump(user_select, f, indent=4)
        if os.path.isfile(tvsDE_chlist_selected):
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
                    delete(tvsDE_chlist_selected)
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
                delete(tvsDE_chlist_selected)
                exit()

def check_selected_list():
    check = 'invalid'
    with open(tvsDE_chlist_selected, 'r', encoding='utf-8') as c:
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
            delete(os.path.join(provider_temppath, f))

    list = os.path.join(provider_temppath, 'list.txt')
    splitname = os.path.join(thread_temppath, 'chlist_tvsDE_selected')

    with open(tvsDE_chlist_selected, 'r', encoding='utf-8') as s:
        selected_list = json.load(s)

    if filesplit.split_chlist_selected(thread_temppath, tvsDE_chlist_selected, splitname, download_threads, enable_multithread):
        multi = True
        needed_threads = sum([len(files) for r, d, files in os.walk(thread_temppath)])
        items_to_download = str(len(selected_list['channellist']))
        log('{} {} {} '.format(provider, items_to_download, loc(32361)))
        #pDialog = xbmcgui.DialogProgressBG()
        log('{} Multithread({}) Mode'.format(provider, needed_threads))
        notify('{} {} '.format(loc(32500), provider), '{} {}'.format('100', loc(32501)))

        jobs = []
        for thread in range(0, int(needed_threads)):
            p = Process(target=download_thread, args=('{}_{}.json'.format(splitname, int(thread)), multi, list, ))
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
        #pDialog.close()
        for file in os.listdir(thread_temppath): delete(os.path.join(thread_temppath, file))

    else:
        multi = False
        log('{} {} '.format(provider, 'Can`t download in Multithreading mode, loading single...'))
        download_thread(tvsDE_chlist_selected, multi, list)

def download_thread(tvsDE_chlist_selected, multi, list):
    requests.adapters.DEFAULT_RETRIES = 5

    with open(tvsDE_chlist_selected, 'r', encoding='utf-8') as s:
        selected_list = json.load(s)

    if not multi:
        items_to_download = str(len(selected_list['channellist']))
        log('{} {} {} '.format(provider, items_to_download, loc(32361)))
        #pDialog = xbmcgui.DialogProgressBG()
        notify('{} {} '.format(loc(32500), provider), '{} {}'.format('100', loc(32501)))

    for user_item in selected_list['channellist']:
        contentID = user_item['contentId']
        channel_name = user_item['name']
        broadcast_files = os.path.join(provider_temppath, '{}_broadcast.json'.format(contentID))

        ## Merge all selected Days in one Json file
        ## create empty broadcastfile
        with open(broadcast_files, 'w', encoding='utf-8') as playbill:
            playbill.write(json.dumps({"broadcasts": []}))

        ## Create a List with downloaded channels
        last_channel_name = '{}\n'.format(channel_name)
        with open(list, 'a', encoding='utf-8') as f:
            f.write(last_channel_name)

        ## open empty broadcastfile
        with open(broadcast_files, encoding='utf-8') as playbill:
            data = json.load(playbill)
            temp = data['broadcasts']

            day_to_start = datetime(today.year, today.month, today.day, hour=00, minute=00, second=1)

            for i in range(0, days_to_grab):
                day_to_grab = day_to_start.strftime("%Y-%m-%d")
                day_to_start += timedelta(days=1)
                tvs_data_url = 'https://live.tvspielfilm.de/static/broadcast/list/{}/{}'.format(contentID, day_to_grab)
                try: tvs_data = requests.get(tvs_data_url, headers=tvsDE_header).json()
                except: tvs_data = ""
                temp.append(tvs_data)

        with open(broadcast_files, 'w', encoding='utf-8') as playbill:
            json.dump(data, playbill, indent=4)

        if not multi:
            items = sum(1 for f in os.listdir(provider_temppath) if f.endswith('_broadcast.json'))
            percent_remain = int(100) - int(items) * int(100) / int(items_to_download)
            percent_completed = int(100) * int(items) / int(items_to_download)
            notify(int(percent_completed), '{} {} '.format(loc(32500), channel_name), '{} {} {}'.format(int(percent_remain), loc(32501), provider))
            if int(items) == int(items_to_download):
                log('{} {}'.format(provider, loc(32363)))
                break
    #if not multi:
        #pDialog.close()

def create_xml_channels():
    log('{} {}'.format(provider,loc(32362)))
    if channel_format == 'rytec':
        ## Save tvsDE_channels.json to Disk
        tvsDE_channels_response = requests.get(tvsDE_channels_url).json()
        with open(tvsDE_channels_json, 'w', encoding='utf-8') as tvsDE_channels:
            json.dump(tvsDE_channels_response, tvsDE_channels)

    with open(tvsDE_chlist_selected, 'r', encoding='utf-8') as c:
        selected_list = json.load(c)

    items_to_download = str(len(selected_list['channellist']))
    items = 0
    #pDialog = xbmcgui.DialogProgressBG()
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
            channel_id = mapper.map_channels(channel_id, channel_format, tvsDE_channels_json, tvsDE_channels_warnings_tmp, lang)

        ## Create XML Channel Information with provided Variables
        xml_structure.xml_channels(channel_name, channel_id, channel_icon, lang)
    #pDialog.close()

def create_xml_broadcast(enable_rating_mapper, thread_temppath, download_threads):

    download_multithread(thread_temppath, download_threads)
    log('{} {}'.format(provider,loc(32365)))

    if genre_format == 'eit':
        ## Save tvsDE_genres.json to Disk
        tvsDE_genres_response = requests.get(tvsDE_genres_url).json()
        with open(tvsDE_genres_json, 'w', encoding='utf-8') as tvsDE_genres:
            json.dump(tvsDE_genres_response, tvsDE_genres)

    with open(tvsDE_chlist_selected, 'r', encoding='utf-8') as c:
        selected_list = json.load(c)

    items_to_download = str(len(selected_list['channellist']))
    items = 0
    #pDialog = xbmcgui.DialogProgressBG()
    notify('{} {} '.format(loc(32503),provider), '{} Prozent verbleibend'.format('100'))

    ## Create XML Broadcast Provider information
    xml_structure.xml_broadcast_start(provider)

    for user_item in selected_list['channellist']:
        items += 1
        percent_remain = int(100) - int(items) * int(100) / int(items_to_download)
        percent_completed = int(100) * int(items) / int(items_to_download)
        contentID = user_item['contentId']
        channel_name = user_item['name']
        channel_id = channel_name
        notify(int(percent_completed), '{} {} '.format(loc(32503),channel_name),'{} {} {}'.format(int(percent_remain),loc(32501),provider))
        if str(percent_completed) == str(100):
            log('{} {}'.format(provider,loc(32366)))

        broadcast_files = os.path.join(provider_temppath, '{}_broadcast.json'.format(contentID))
        with open(broadcast_files, 'r', encoding='utf-8') as b:
            broadcastfiles = json.load(b)

        ### Map Channels
        if not channel_id == '':
            channel_id = mapper.map_channels(channel_id, channel_format, tvsDE_channels_json, tvsDE_channels_warnings_tmp, lang)

        try:
            for days in broadcastfiles['broadcasts']:
                for playbilllist in days:
                    try:
                        item_title = playbilllist['title']
                    except (KeyError, IndexError):
                        item_title = ''
                    try:
                        item_starttime = playbilllist['timestart']
                    except (KeyError, IndexError):
                        item_starttime = ''
                    try:
                        item_endtime = playbilllist['timeend']
                    except (KeyError, IndexError):
                        item_endtime = ''
                    try:
                        item_description = playbilllist['text']
                    except (KeyError, IndexError):
                        item_description = ''
                    try:
                        item_country = playbilllist['country']
                    except (KeyError, IndexError):
                        item_country = ''
                    try:
                        item_picture = playbilllist['images'][0]['size4']
                    except (KeyError, IndexError):
                        item_picture = ''
                    try:
                        item_subtitle = playbilllist['episodeTitle']
                    except (KeyError, IndexError):
                        item_subtitle = ''
                    try:
                        items_genre = playbilllist['genre']
                    except (KeyError, IndexError):
                        items_genre = ''
                    try:
                        item_date = playbilllist['year']
                    except (KeyError, IndexError):
                        item_date = ''
                    try:
                        item_season = playbilllist['seasonNumber']
                    except (KeyError, IndexError):
                        item_season = ''
                    try:
                        item_episode = playbilllist['episodeNumber']
                    except (KeyError, IndexError):
                        item_episode = ''
                    try:
                        item_agerating = playbilllist['fsk']
                    except (KeyError, IndexError):
                        item_agerating = ''
                    try:
                        items_director = playbilllist['director']
                    except (KeyError, IndexError):
                        items_director = ''
                    try:
                        actor_list = list()
                        keys_actor = playbilllist['actors']
                        for actor in keys_actor:
                            actor_list.append(list(actor.values())[0])
                        items_actor = ','.join(actor_list)
                    except (KeyError, IndexError):
                        items_actor = ''

                    # Transform items to Readable XML Format
                    item_starrating = ''
                    item_starttime = datetime.utcfromtimestamp(item_starttime).strftime('%Y%m%d%H%M%S')
                    item_endtime = datetime.utcfromtimestamp(item_endtime).strftime('%Y%m%d%H%M%S')

                    if not item_episode == '':
                        item_episode = re.sub(r"\D+", '#', item_episode).split('#')[0]
                    if not item_season == '':
                        item_season = re.sub(r"\D+", '#', item_season).split('#')[0]

                    items_producer = ''
                    if item_description == '':
                        item_description = 'No Program Information available'

                    # Map Genres
                    if not items_genre == '':
                        items_genre = mapper.map_genres(items_genre, genre_format, tvsDE_genres_json, tvsDE_genres_warnings_tmp, lang)

                    ## Create XML Broadcast Information with provided Variables
                    xml_structure.xml_broadcast(episode_format, channel_id, item_title, item_starttime, item_endtime,
                                                item_description, item_country, item_picture, item_subtitle,
                                                items_genre,
                                                item_date, item_season, item_episode, item_agerating, item_starrating, items_director,
                                                items_producer, items_actor, enable_rating_mapper, lang)


        except (KeyError, IndexError):
            log('{} {} {} {} {} {}'.format(provider, loc(32367), channel_name, loc(32368), contentID,loc(32369)))
    #pDialog.close()

    ## Create Channel Warnings Textile
    channel_pull = '\nPlease Create an Pull Request for Missing Rytec Id´s to https://github.com/sunsettrack4/config_files/blob/master/tvs_channels.json\n'
    mapper.create_channel_warnings(tvsDE_channels_warnings_tmp, tvsDE_channels_warnings, provider, channel_pull)

    ## Create Genre Warnings Textfile
    genre_pull = '\nPlease Create an Pull Request for Missing EIT Genres to https://github.com/sunsettrack4/config_files/blob/master/tvs_genres.json\n'
    mapper.create_genre_warnings(tvsDE_genres_warnings_tmp, tvsDE_genres_warnings, provider, genre_pull)

    notify(addon_name, '{} {} {}'.format(loc(32370),provider,loc(32371)))
    log('{} {} {}'.format(loc(32370),provider,loc(32371)))

    if (os.path.isfile(tvsDE_channels_warnings) or os.path.isfile(tvsDE_genres_warnings)):
        notify(provider, '{}'.format(loc(32372)))

    ## Delete old Tempfiles, not needed any more
    for file in os.listdir(provider_temppath): delete(os.path.join(provider_temppath, file))


def check_provider():
    ## Create Provider Temppath if not exist
    if not os.path.exists(provider_temppath):
        os.makedirs(provider_temppath)

    ## Create empty (Selected) Channel List if not exist
    if not os.path.isfile(tvsDE_chlist_selected):
        with open((tvsDE_chlist_selected), 'w', encoding='utf-8') as selected_list:
            selected_list.write(json.dumps({"channellist": []}))

        ## If no Channellist exist, ask to create one
        yn = OSD.yesno(provider, loc(32405))
        if yn:
            select_channels()
        else:
            delete(tvsDE_chlist_selected)
            return False

    ## If a Selected list exist, check valid
    valid = check_selected_list()
    if valid is False:
        yn = OSD.yesno(provider, loc(32405))
        if yn:
            select_channels()
        else:
            delete(tvsDE_chlist_selected)
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
    if sys.argv[1] == 'select_channels_tvsDE':
        select_channels()
except IndexError:
    pass
