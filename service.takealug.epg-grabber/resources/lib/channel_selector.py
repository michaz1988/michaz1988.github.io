# -*- coding: utf-8 -*-
import xbmc
import xbmcaddon
import xbmcgui
import json
import os
import xbmcvfs

ADDON = xbmcaddon.Addon(id="service.takealug.epg-grabber")
addon_name = ADDON.getAddonInfo('name')
addon_version = ADDON.getAddonInfo('version')
loc = ADDON.getLocalizedString
datapath = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
temppath = os.path.join(datapath, "temp")

# Make a debug logger
def log(message, loglevel=xbmc.LOGDEBUG):
	xbmc.log('[{} {}] {}'.format(addon_name, addon_version, message), loglevel)

# Make OSD Notify Messages
OSD = xbmcgui.Dialog()

def notify(title, message, icon=xbmcgui.NOTIFICATION_INFO):
	OSD.notification(title, message, icon)

def select_channels(provider,provider_list,selected_list):
	"""
	Shows a multiselect list
	:param provider_list: channellist of provider
	:type provider_list: JSON (dict)
	:param selected_list: channellist of user
	:type selected_list; JSON (dict)
	:return: JSON of new selected_list if success, None if aborted
	"""

	items = list()
	selected = list()
	index = 0
	for channel in provider_list.get('channellist', []):
		descriptor = xbmcgui.ListItem(label=channel['name'])
		descriptor.setArt({'icon': channel['pictures'][0]['href']})
		descriptor.setProperty('item', json.dumps(channel))
		for user_item in selected_list.get('channellist', []):
			if channel['contentId'] == user_item['contentId']:
				# mark as 'selected', write mandantory index
				selected.append(index)
				if channel['name'] != user_item['name']:
					# mark as 'channelname has changed' (label2)
					descriptor.setLabel2(user_item['name'])
					## Notify if Channelname has Changed
					log('{} {} {} {}'.format(loc(32373),user_item['name'],loc(32374),channel['name']), xbmc.LOGINFO)
				break
		items.append(descriptor)
		index += 1

	# check for outdated channels in user list
	for user_item in selected_list.get('channellist', []):
		is_outdated = True
		for online_item in provider_list.get('channellist', []):
			if user_item['contentId'] == online_item['contentId']:
				is_outdated = False
				break
		if is_outdated:
			## Notify if Selected Channel no more exist by Provider
			xbmc.log('contentID {} {}'.format(user_item['contentId'],loc(32375)))

	# build new userlist
	multilist = xbmcgui.Dialog().multiselect('{} ]-{}-['.format(provider,loc(32406)), items, preselect=selected, useDetails=True)
	if multilist is not None:
		selected_list = list()
		for selected in multilist:
			selected_list.append(json.loads(items[selected].getProperty('item')))
		return dict({'channellist': selected_list})
	return None