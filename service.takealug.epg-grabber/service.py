# -*- coding: utf-8 -*-
import xbmc, xbmcaddon, xbmcvfs, xbmcgui, time, os, json, re, socket, sys, platform, importlib, gzip
from datetime import datetime
from collections import Counter
from resources.lib import xml_structure
from resources.providers import magenta_DE, tvspielfilm_DE, swisscom_CH, klack_DE, simpliTV_AT, tvdigital_DE

ADDON = xbmcaddon.Addon(id="service.takealug.epg-grabber")
addon_name = ADDON.getAddonInfo('name')
addon_version = ADDON.getAddonInfo('version')
loc = ADDON.getLocalizedString
datapath = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
temppath = os.path.join(datapath, "temp")
machine = platform.machine()

def getAddonSetting(setting):
	value = True if xbmcaddon.Addon(id="service.takealug.epg-grabber").getSetting(setting).upper() == 'TRUE' else False
	return value

def getAddonCronSetting(setting):
	value = xbmcaddon.Addon(id="service.takealug.epg-grabber").getSetting(setting)
	return value

## Read Global Settings
storage_path = ADDON.getSetting('storage_path')
auto_download = getAddonSetting('auto_download')
timeswitch_1 = int(ADDON.getSetting('timeswitch_1'))
timeswitch_2 = int(ADDON.getSetting('timeswitch_2'))
timeswitch_3 = int(ADDON.getSetting('timeswitch_3'))
enable_rating_mapper = True if ADDON.getSetting('enable_rating_mapper').upper() == 'TRUE' else False
use_local_sock = True if ADDON.getSetting('use_local_sock').upper() == 'TRUE' else False
tvh_local_sock = ADDON.getSetting('tvh_local_sock')

## Get Enabled Grabbers
# Divers
enable_grabber_magentaDE = True if ADDON.getSetting('enable_grabber_magentaDE').upper() == 'TRUE' else False
enable_grabber_tvsDE = True if ADDON.getSetting('enable_grabber_tvsDE').upper() == 'TRUE' else False
enable_grabber_tvdDE = True if ADDON.getSetting('enable_grabber_tvdDE').upper() == 'TRUE' else False
enable_grabber_klackDE = True if ADDON.getSetting('enable_grabber_klackDE').upper() == 'TRUE' else False
enable_grabber_simpliAT = True if ADDON.getSetting('enable_grabber_simpliAT').upper() == 'TRUE' else False
enable_grabber_swcCH = True if ADDON.getSetting('enable_grabber_swcCH').upper() == 'TRUE' else False
# Zattoo
"""enable_grabber_zttDE = True if ADDON.getSetting('enable_grabber_zttDE').upper() == 'TRUE' else False
enable_grabber_zttCH = True if ADDON.getSetting('enable_grabber_zttCH').upper() == 'TRUE' else False
enable_grabber_1und1DE = True if ADDON.getSetting('enable_grabber_1und1DE').upper() == 'TRUE' else False
enable_grabber_qlCH = True if ADDON.getSetting('enable_grabber_qlCH').upper() == 'TRUE' else False
enable_grabber_mnetDE = True if ADDON.getSetting('enable_grabber_mnetDE').upper() == 'TRUE' else False
enable_grabber_walyCH = True if ADDON.getSetting('enable_grabber_walyCH').upper() == 'TRUE' else False
enable_grabber_mweltAT = True if ADDON.getSetting('enable_grabber_mweltAT').upper() == 'TRUE' else False
enable_grabber_bbvDE = True if ADDON.getSetting('enable_grabber_bbvDE').upper() == 'TRUE' else False
enable_grabber_vtxCH = True if ADDON.getSetting('enable_grabber_vtxCH').upper() == 'TRUE' else False
enable_grabber_myvisCH = True if ADDON.getSetting('enable_grabber_myvisCH').upper() == 'TRUE' else False
enable_grabber_gvisCH = True if ADDON.getSetting('enable_grabber_gvisCH').upper() == 'TRUE' else False
enable_grabber_sakCH = True if ADDON.getSetting('enable_grabber_sakCH').upper() == 'TRUE' else False
enable_grabber_nettvDE = True if ADDON.getSetting('enable_grabber_nettvDE').upper() == 'TRUE' else False
enable_grabber_eweDE = True if ADDON.getSetting('enable_grabber_eweDE').upper() == 'TRUE' else False
enable_grabber_qttvCH = True if ADDON.getSetting('enable_grabber_qttvCH').upper() == 'TRUE' else False
enable_grabber_saltCH = True if ADDON.getSetting('enable_grabber_saltCH').upper() == 'TRUE' else False
enable_grabber_swbDE = True if ADDON.getSetting('enable_grabber_swbDE').upper() == 'TRUE' else False
enable_grabber_eirIE = True if ADDON.getSetting('enable_grabber_eirIE').upper() == 'TRUE' else False"""
# Check if any Grabber is enabled
#if (enable_grabber_magentaDE or enable_grabber_tvsDE or enable_grabber_tvdDE or enable_grabber_klackDE or enable_grabber_simpliAT or enable_grabber_swcCH or enable_grabber_zttDE or enable_grabber_zttCH or enable_grabber_1und1DE or enable_grabber_qlCH or enable_grabber_mnetDE or enable_grabber_walyCH or enable_grabber_mweltAT or enable_grabber_bbvDE or enable_grabber_vtxCH or enable_grabber_myvisCH or enable_grabber_gvisCH or enable_grabber_sakCH or enable_grabber_nettvDE or enable_grabber_eweDE or enable_grabber_qttvCH or enable_grabber_saltCH or enable_grabber_swbDE or enable_grabber_eirIE): enabled_grabber = True
if (enable_grabber_magentaDE or enable_grabber_tvsDE or enable_grabber_tvdDE or enable_grabber_klackDE or enable_grabber_simpliAT or enable_grabber_swcCH): enabled_grabber = True
else: enabled_grabber = False

guide_temp = os.path.join(datapath, 'guide.xml')
guide_dest = os.path.join(datapath, 'guide.xml.gz')
grabber_cron = os.path.join(datapath, 'grabber_cron.json')
grabber_cron_tmp = os.path.join(temppath, 'grabber_cron.json')
xmltv_dtd = os.path.join(datapath, 'xmltv.dtd')

## Make a debug logger
def log(message, loglevel=xbmc.LOGDEBUG):
	xbmc.log('[{} {}] {}'.format(addon_name, addon_version, message), loglevel)

## Make OSD Notify Messages
OSD = xbmcgui.Dialog()

## MAKE an Monitor
class Monitor(xbmc.Monitor):
	def __init__(self):
		xbmc.Monitor.__init__(self)
		self.settingsChanged = False

	def onSettingsChanged(self):
		self.settingsChanged = True
monitor = Monitor()

def notify(title, message, icon=xbmcgui.NOTIFICATION_INFO):
	OSD.notification(title, message, icon)

def copy_guide_to_destination():
	try:
		with open(guide_temp, 'rb') as f_in, gzip.open(guide_dest, 'wb') as f_out:
			f_out.writelines(f_in)
		done = True
	except: done = False
	if done:
		try:
			## Write new setting last_download
			with open(grabber_cron, 'r', encoding='utf-8') as f:
				data = json.load(f)
				data['last_download'] = str(int(time.time()))
			with open(grabber_cron_tmp, 'w', encoding='utf-8') as f:
				json.dump(data, f, indent=4)
			## rename temporary file replacing old file
			xbmcvfs.copy(grabber_cron_tmp, grabber_cron)
			xbmc.sleep(3000)
			xbmcvfs.delete(grabber_cron_tmp)
			notify(addon_name, loc(32350), icon=xbmcgui.NOTIFICATION_INFO)
			log(loc(32350), xbmc.LOGINFO)
		except:
			log('Worker can´t read cron File, creating new File...'.format(loc(32356)), xbmc.LOGERROR)
			with open(grabber_cron, 'w', encoding='utf-8') as f:
				f.write(json.dumps({'last_download': str(int(time.time())), 'next_download': str(int(time.time()) + 86400)}))
			notify(addon_name, loc(32350), icon=xbmcgui.NOTIFICATION_INFO)
			log(loc(32350), xbmc.LOGINFO)
	else:
		notify(addon_name, loc(32351), icon=xbmcgui.NOTIFICATION_ERROR)
		log(loc(32351), xbmc.LOGERROR)

def check_channel_dupes():
	f = ''.join(xml_structure.epg)
	c = Counter(c.strip() for c in f.splitlines() if c.strip())	# for case-insensitive search
	dupe = []
	for line in c:
		if c[line] > 1:
			if ('display-name' in line or 'icon src' in line or '</channel' in line): pass
			else: dupe.append(line.strip('<channel id="').strip('">'))
	dupes = ' ,'.join(dupe)
	if dupe:
		log('{} {}'.format(loc(32400), dupes), xbmc.LOGERROR)
		dialog = xbmcgui.Dialog()
		ok = dialog.ok('ERROR {}'.format(loc(32400)), dupes)
		if ok: return False
		return False
	else: return True

def run_grabber():
	if check_startup():
		importlib.reload(xml_structure)
		importlib.reload(magenta_DE)
		importlib.reload(tvspielfilm_DE)
		importlib.reload(swisscom_CH)
		#importlib.reload(zattoo)
		importlib.reload(klack_DE)
		importlib.reload(simpliTV_AT)
		importlib.reload(tvdigital_DE)
		xml_structure.xml_start()
		## Check Provider , Create XML Channels
		if enable_grabber_magentaDE:
			if magenta_DE.startup(): magenta_DE.create_xml_channels()
		if enable_grabber_tvsDE:
			if tvspielfilm_DE.startup(): tvspielfilm_DE.create_xml_channels()
		if enable_grabber_tvdDE:
			if tvdigital_DE.startup(): tvdigital_DE.create_xml_channels()
		if enable_grabber_klackDE:
			if klack_DE.startup(): klack_DE.create_xml_channels()
		if enable_grabber_simpliAT:
			if simpliTV_AT.startup(): simpliTV_AT.create_xml_channels()
		if enable_grabber_swcCH:
			if swisscom_CH.startup(): swisscom_CH.create_xml_channels()
		"""if enable_grabber_zttDE:
			if zattoo.startup('ztt_de'): zattoo.create_xml_channels('ztt_de')
		if enable_grabber_zttCH:
			if zattoo.startup('ztt_ch'): zattoo.create_xml_channels('ztt_ch')
		if enable_grabber_1und1DE:
			if zattoo.startup('1und1_de'): zattoo.create_xml_channels('1und1_de')
		if enable_grabber_qlCH:
			if zattoo.startup('ql_ch'): zattoo.create_xml_channels('ql_ch')
		if enable_grabber_mnetDE:
			if zattoo.startup('mnet_de'): zattoo.create_xml_channels('mnet_de')
		if enable_grabber_walyCH:
			if zattoo.startup('walytv_ch'): zattoo.create_xml_channels('walytv_ch')
		if enable_grabber_mweltAT:
			if zattoo.startup('meinewelt_at'): zattoo.create_xml_channels('meinewelt_at')
		if enable_grabber_bbvDE:
			if zattoo.startup('bbtv_de'): zattoo.create_xml_channels('bbtv_de')
		if enable_grabber_vtxCH:
			if zattoo.startup('vtxtv_ch'): zattoo.create_xml_channels('vtxtv_ch')
		if enable_grabber_myvisCH:
			if zattoo.startup('myvision_ch'): zattoo.create_xml_channels('myvision_ch')
		if enable_grabber_gvisCH:
			if zattoo.startup('glattvision_ch'): zattoo.create_xml_channels('glattvision_ch')
		if enable_grabber_sakCH:
			if zattoo.startup('sak_ch'): zattoo.create_xml_channels('sak_ch')
		if enable_grabber_nettvDE:
			if zattoo.startup('nettv_de'): zattoo.create_xml_channels('nettv_de')
		if enable_grabber_eweDE:
			if zattoo.startup('tvoewe_de'): zattoo.create_xml_channels('tvoewe_de')
		if enable_grabber_qttvCH:
			if zattoo.startup('quantum_ch'): zattoo.create_xml_channels('quantum_ch')
		if enable_grabber_saltCH:
			if zattoo.startup('salt_ch'): zattoo.create_xml_channels('salt_ch')
		if enable_grabber_swbDE:
			if zattoo.startup('tvoswe_de'): zattoo.create_xml_channels('tvoswe_de')
		if enable_grabber_eirIE:
			if zattoo.startup('eir_ie'): zattoo.create_xml_channels('eir_ie')"""
		# Check for Channel Dupes
		if check_channel_dupes():
			## Create XML Broadcast
			if enable_grabber_magentaDE:
				if magenta_DE.startup(): magenta_DE.create_xml_broadcast(enable_rating_mapper)
			if enable_grabber_tvsDE:
				if tvspielfilm_DE.startup(): tvspielfilm_DE.create_xml_broadcast(enable_rating_mapper)
			if enable_grabber_tvdDE:
				if tvdigital_DE.startup(): tvdigital_DE.create_xml_broadcast(enable_rating_mapper)
			if enable_grabber_klackDE:
				if klack_DE.startup(): klack_DE.create_xml_broadcast(enable_rating_mapper)
			if enable_grabber_simpliAT:
				if simpliTV_AT.startup(): simpliTV_AT.create_xml_broadcast(enable_rating_mapper)
			if enable_grabber_swcCH:
				if swisscom_CH.startup(): swisscom_CH.create_xml_broadcast(enable_rating_mapper)
			"""if enable_grabber_zttDE:
				if zattoo.startup('ztt_de'): zattoo.create_xml_broadcast('ztt_de', enable_rating_mapper)
			if enable_grabber_zttCH:
				if zattoo.startup('ztt_ch'): zattoo.create_xml_broadcast('ztt_ch', enable_rating_mapper)
			if enable_grabber_1und1DE:
				if zattoo.startup('1und1_de'): zattoo.create_xml_broadcast('1und1_de', enable_rating_mapper)
			if enable_grabber_qlCH:
				if zattoo.startup('ql_ch'): zattoo.create_xml_broadcast('ql_ch', enable_rating_mapper)
			if enable_grabber_mnetDE:
				if zattoo.startup('mnet_de'): zattoo.create_xml_broadcast('mnet_de', enable_rating_mapper)
			if enable_grabber_walyCH:
				if zattoo.startup('walytv_ch'): zattoo.create_xml_broadcast('walytv_ch', enable_rating_mapper)
			if enable_grabber_mweltAT:
				if zattoo.startup('meinewelt_at'): zattoo.create_xml_broadcast('meinewelt_at', enable_rating_mapper)
			if enable_grabber_bbvDE:
				if zattoo.startup('bbtv_de'): zattoo.create_xml_broadcast('bbtv_de', enable_rating_mapper)
			if enable_grabber_vtxCH:
				if zattoo.startup('vtxtv_ch'): zattoo.create_xml_broadcast('vtxtv_ch', enable_rating_mapper)
			if enable_grabber_myvisCH:
				if zattoo.startup('myvision_ch'): zattoo.create_xml_broadcast('myvision_ch', enable_rating_mapper)
			if enable_grabber_gvisCH:
				if zattoo.startup('glattvision_ch'): zattoo.create_xml_broadcast('glattvision_ch', enable_rating_mapper)
			if enable_grabber_sakCH:
				if zattoo.startup('sak_ch'): zattoo.create_xml_broadcast('sak_ch', enable_rating_mapper)
			if enable_grabber_nettvDE:
				if zattoo.startup('nettv_de'): zattoo.create_xml_broadcast('nettv_de', enable_rating_mapper)
			if enable_grabber_eweDE:
				if zattoo.startup('tvoewe_de'): zattoo.create_xml_broadcast('tvoewe_de', enable_rating_mapper)
			if enable_grabber_qttvCH:
				if zattoo.startup('quantum_ch'): zattoo.create_xml_broadcast('quantum_ch', enable_rating_mapper)
			if enable_grabber_saltCH:
				if zattoo.startup('salt_ch'): zattoo.create_xml_broadcast('salt_ch', enable_rating_mapper)
			if enable_grabber_swbDE:
				if zattoo.startup('tvoswe_de'): zattoo.create_xml_broadcast('tvoswe_de', enable_rating_mapper)
			if enable_grabber_eirIE:
				if zattoo.startup('eir_ie'): zattoo.create_xml_broadcast('eir_ie', enable_rating_mapper)"""
			## Finish XML
			xml_structure.xml_end()
			copy_guide_to_destination()
			## Write Guide in TVH Socked
			if use_local_sock: write_to_sock()

def write_to_sock():
	if check_startup():
		if (use_local_sock and os.path.isfile(guide_temp)):
			sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
			epg = open(guide_temp, 'rb')
			epg_data = epg.read()
			try:
				log('{} {}'.format(loc(32380), tvh_local_sock), xbmc.LOGINFO)
				notify(addon_name, loc(32380), icon=xbmcgui.NOTIFICATION_INFO)
				sock.connect(tvh_local_sock)
				sock.sendall(epg_data)
				log('{} {}'.format(sock.recv, tvh_local_sock), xbmc.LOGINFO)
			except socket.error as e:
				notify(addon_name, '{} {}'.format(loc(32379), e), icon=xbmcgui.NOTIFICATION_ERROR)
				log('{} {}'.format(loc(32379), e), xbmc.LOGERROR)
			finally:
				sock.close()
				epg.close()
		else:
			ok = dialog.ok(loc(32119), loc(32409))
			if ok: log(loc(32409), xbmc.LOGERROR)

def worker(timeswitch_1, timeswitch_2, timeswitch_3):
	initiate_download = False
	## Read Settings for last / next_download
	try:
		with open(grabber_cron, 'r', encoding='utf-8') as f:
			cron = json.load(f)
			next_download = cron['next_download']
			last_download = cron['last_download']
	except:
		log('Worker can´t read cron File, creating new File...'.format(loc(32356)), xbmc.LOGERROR)
		with open(grabber_cron, 'w', encoding='utf-8') as f:
			f.write(json.dumps({'last_download': str(int(time.time())), 'next_download': str(int(time.time()) + 86400)}))
		with open(grabber_cron, 'r', encoding='utf-8') as f:
			cron = json.load(f)
			next_download = cron['next_download']
			last_download = cron['last_download']
	log('{} {}'.format(loc(32352), datetime.fromtimestamp(int(last_download)).strftime('%d.%m.%Y %H:%M')), xbmc.LOGDEBUG)
	if (int(next_download) > int(last_download)):
		log('{} {}'.format(loc(32353), datetime.fromtimestamp(int(next_download)).strftime('%d.%m.%Y %H:%M')), xbmc.LOGDEBUG)
	if int(next_download) < int(time.time()):
		# suggested download time has passed (e.g. system was offline) or time is now, download epg
		# and set a new timestamp for the next download
		log('{} {}'.format(loc(32352), datetime.fromtimestamp(int(last_download)).strftime('%d.%m.%Y %H:%M')), xbmc.LOGINFO)
		log('{} {}'.format(loc(32353), datetime.fromtimestamp(int(next_download)).strftime('%d.%m.%Y %H:%M')), xbmc.LOGINFO)
		log('{}'.format(loc(32356)), xbmc.LOGINFO)
		initiate_download = True
	## If next_download < last_download, initiate an Autodownload
	if initiate_download:
		notify(addon_name, loc(32357), icon=xbmcgui.NOTIFICATION_INFO)
		run_grabber()
		## Update Cron Settings
		with open(grabber_cron, 'r', encoding='utf-8') as f:
			cron = json.load(f)
			next_download = cron['next_download']
			last_download = cron['last_download']
	## Calculate the next_download Setting
	# get Settings for daily_1, daily_2, daily_3
	today = datetime.today()
	now = int(time.time())
	calc_daily_1 = datetime(today.year, today.month, day=today.day, hour=timeswitch_1, minute=0, second=0)
	calc_daily_2 = datetime(today.year, today.month, day=today.day, hour=timeswitch_2, minute=0, second=0)
	calc_daily_3 = datetime(today.year, today.month, day=today.day, hour=timeswitch_3, minute=0, second=0)
	try:
		daily_1 = int(calc_daily_1.strftime("%s"))
		daily_2 = int(calc_daily_2.strftime("%s"))
		daily_3 = int(calc_daily_3.strftime("%s"))
	except ValueError:
		daily_1 = int(time.mktime(calc_daily_1.timetuple()))
		daily_2 = int(time.mktime(calc_daily_2.timetuple()))
		daily_3 = int(time.mktime(calc_daily_3.timetuple()))
	## If sheduleplan for daily 1,2,3 is in the past, plan it for next day
	if daily_1 <= now: daily_1 += 86400
	if daily_2 <= now: daily_2 += 86400
	if daily_3 <= now: daily_3 += 86400
	## Find the lowest Integer for next download
	next_download = min([int(daily_1), int(daily_2), int(daily_3)])
	## Write new setting next_download
	with open(grabber_cron, 'w', encoding='utf-8') as f:
		f.write(json.dumps({'last_download': str(int(last_download)), 'next_download': str(int(next_download))}))

def check_internet(host="8.8.8.8", port=53, timeout=3):
	try:
		socket.setdefaulttimeout(timeout)
		socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
		return True
	except socket.error as ex: return False

def check_startup():
	#Create Tempfolder if not exist
	if not os.path.exists(temppath): os.makedirs(temppath)
	#if storage_path == 'choose':
		#notify(addon_name, loc(32359), icon=xbmcgui.NOTIFICATION_ERROR)
		#log(loc(32359), xbmc.LOGERROR)
		#return False
	if not enabled_grabber:
		notify(addon_name, loc(32360), icon=xbmcgui.NOTIFICATION_ERROR)
		log(loc(32360), xbmc.LOGERROR)
		return False
	if use_local_sock:
		socked_string = '.sock'
		if not re.search(socked_string, tvh_local_sock):
			notify(addon_name, loc(32378), icon=xbmcgui.NOTIFICATION_ERROR)
			log(loc(32378), xbmc.LOGERROR)
			return False
	## create Crontab File which not exists at first time
	if (not os.path.isfile(grabber_cron) or os.stat(grabber_cron).st_size <= 1):
		with open(grabber_cron, 'w', encoding='utf-8') as f:
			f.write(json.dumps({'last_download': str(int(time.time())), 'next_download': str(int(time.time()) + 86400)}))
	## Clean Tempfiles
	for file in os.listdir(temppath):
		xbmcvfs.delete(os.path.join(temppath, file))
	## Check internet Connection
	if not check_internet():
		retries = 12
		while retries > 0:
			log(loc(32385), xbmc.LOGINFO)
			notify(addon_name, loc(32385), icon=xbmcgui.NOTIFICATION_INFO)
			xbmc.sleep(5000)
			if check_internet():
				log(loc(32386), xbmc.LOGINFO)
				notify(addon_name, loc(32386), icon=xbmcgui.NOTIFICATION_INFO)
				return True
			else: retries -= 1
		if retries == 0:
			log(loc(32387), xbmc.LOGERROR)
			notify(addon_name, loc(32387), icon=xbmcgui.NOTIFICATION_ERROR)
			return False
	else: return True

if __name__ == '__main__':
	if check_startup():
		try:
			dialog = xbmcgui.Dialog()
			if sys.argv[1] == 'manual_download':
				if not auto_download:
					ret = dialog.yesno('Takealug EPG Grabber', loc(32401))
					if ret:
						notify(addon_name, loc(32376), icon=xbmcgui.NOTIFICATION_INFO)
						run_grabber()
				elif auto_download:
					ok = dialog.ok(addon_name, loc(32414))
					if ok: pass
					pass
			if sys.argv[1] == 'write_to_sock':
				ret = dialog.yesno(loc(32119), loc(32408))
				if ret: write_to_sock()
		except IndexError:
			while not monitor.waitForAbort(30):
				if monitor.settingsChanged:
					log('Settings changed Reloading', xbmc.LOGINFO)
					auto_download = getAddonSetting('auto_download')
					if auto_download:
						timeswitch_1 = int(getAddonCronSetting('timeswitch_1'))
						timeswitch_2 = int(getAddonCronSetting('timeswitch_2'))
						timeswitch_3 = int(getAddonCronSetting('timeswitch_3'))
					monitor.settingsChanged = False
				if auto_download: worker(timeswitch_1, timeswitch_2, timeswitch_3)