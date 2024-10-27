# -*- coding: utf-8 -*-
import json
import os
from tools import datapath, temppath, log, notify, addon_name, addon_version, loc

def map_genres(items_genre,genre_format,genres_json,genres_warnings_tmp, lang):
    if genre_format == 'eit':
        with open(genres_json, 'r', encoding='utf-8') as c: eit_genre = json.load(c)
        genrelist = items_genre.split(',')
        genres_mapped = list()
        for genre in genrelist:
            if genre not in eit_genre['categories'][lang.upper()]:
                warnings = '\n ]EIT GENRE WARNING[ "{}" Is not in EIT Genre List \n'.format(genre)
                with open(genres_warnings_tmp, 'a' , encoding='utf-8') as f:
                    f.write(warnings)
                genres_mapped.append(genre)
            else:
                genres_mapped.append(eit_genre['categories'][lang.upper()][genre])
        return ",".join(genres_mapped)

    elif genre_format == 'provider':
        channels_mapped = items_genre
        return str(channels_mapped)

def map_channels(channel_id, channel_format,channels_json,channels_warnings_tmp, lang):
    if channel_format == 'rytec':
        with open(channels_json, 'r', encoding='utf-8') as c:
            rytec_id = json.load(c)

        if (channel_id) not in rytec_id['channels'][lang.upper()]:
            warnings = '\n ]CHANNEL WARNING[ "{}" Is not in Rytec List \n'.format(channel_id)
            with open(channels_warnings_tmp, 'a', encoding='utf-8') as f:
               f.write(warnings)
            channels_mapped = channel_id
        else :
            channel_mapped = rytec_id['channels'][lang.upper()][channel_id]
            channels_mapped = channel_id.replace(channel_id, channel_mapped)

        return str(channels_mapped)

    elif channel_format == 'provider':
        channels_mapped = channel_id
        return str(channels_mapped)

def create_channel_warnings(channels_warnings_tmp, channels_warnings, provider, channel_pull):
    ## Create Channel Warnings Textfile
    if os.path.isfile(channels_warnings_tmp):
        lines_seen = set()  # holds lines already seen
        outfile = open(channels_warnings, "w", encoding='utf-8')
        for line in open(channels_warnings_tmp, "r", encoding='utf-8'):
            if line not in lines_seen:  # not a duplicate
                outfile.write(line)
                lines_seen.add(line)
        outfile.close()
        ## Add Information for Pull Requests
        with open(channels_warnings, 'a', encoding='utf-8') as f:
            f.write(channel_pull)
        ## Print Content of Channel Warnings Textfile in Kodi LOG
        warnings_channels = open(channels_warnings, "r", encoding='utf-8').read()
        log('{} {}'.format(provider,warnings_channels), xbmc.LOGINFO)

def create_genre_warnings(genres_warnings_tmp, genres_warnings, provider, genre_pull):
    ## Create Genre Warnings Textfile
    if os.path.isfile(genres_warnings_tmp):
        lines_seen = set()  # holds lines already seen
        outfile = open(genres_warnings, "w", encoding='utf-8')
        for line in open(genres_warnings_tmp, "r", encoding='utf-8'):
            if line not in lines_seen:  # not a duplicate
                outfile.write(line)
                lines_seen.add(line)
        outfile.close()
        ## Add Information for Pull Requests
        with open(genres_warnings, 'a', encoding='utf-8') as f:
            f.write(genre_pull)
        ## Print Content of Genres Warnings Textfile in Kodi LOG
        warnings_genres = open(genres_warnings, "r", encoding='utf-8').read()
        log('{} {}'.format(provider, warnings_genres), xbmc.LOGINFO)

def map_stars(item_starrating):
    if int(item_starrating) <= int(9):
        stars = "• IMDb:☆☆☆☆☆"
    elif (int(item_starrating) >= int(10) and int(item_starrating)<= int(29)):
        stars = "• IMDb:★☆☆☆☆"
    elif (int(item_starrating) >= int(30) and int(item_starrating) <= int(49)):
        stars = "• IMDb:★★☆☆☆"
    elif (int(item_starrating) >= int(50) and int(item_starrating) <= int(69)):
        stars = "• IMDb:★★★☆☆"
    elif (int(item_starrating) >= int(70) and int(item_starrating) <= int(89)):
        stars = "• IMDb:★★★★☆"
    elif (int(item_starrating) >= int(90) and int(item_starrating) <= int(100)):
        stars = "• IMDb:★★★★★"

    return stars

