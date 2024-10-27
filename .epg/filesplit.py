# -*- coding: utf-8 -*-
import os
import json
from copy import deepcopy
import tools


def split_chlist_selected(thread_temppath, chlist_selected, splitname, download_threads, enable_multithread):
    #Create Tempfolder if not exist
    if not os.path.exists(thread_temppath):
        os.makedirs(thread_temppath)

    if download_threads == 1:
        return False

    if not enable_multithread:
        return False

    try:
        ## Make Shure Folder is Clean
        for file in os.listdir(thread_temppath): tools.delete(os.path.join(thread_temppath, file))

        json_data = open(chlist_selected)
        data = json.load(json_data)

        default = deepcopy(data)
        default['channellist'] = []

        items = len(data['channellist'])
        files = (int(items) + int(download_threads)) / int(download_threads)
        ran = range(items)
        steps = ran[int(files)::int(files)]

        data_split = deepcopy(default)
        count = 0


        for i in ran:
            data_split['channellist'].append(data['channellist'][i])
            if i in steps or i == items - 1:
                part = os.path.join(thread_temppath, '{}_{}.json'.format(splitname, str(count)))
                with open(part, 'w') as parts:
                    json.dump(data_split, parts)
                data_split = deepcopy(default)
                count = count + 1
        return True
    except:
        return False

