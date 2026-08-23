# -*- coding: utf-8 -*-
import os
import shutil
import time
import zipfile
import xml.etree.ElementTree as ET

import requests
import routing
import xbmc
import xbmcaddon
from xbmcgui import Dialog, DialogProgress, ListItem, NOTIFICATION_INFO
from xbmcplugin import addDirectoryItem as add
from xbmcplugin import endOfDirectory as end
from xbmcvfs import translatePath

plugin = routing.Plugin()

guisettings ={
	"lookandfeel.skin": '"skin.mimic.lr"',
	"services.webserverpassword": '"kodi"',
	"locale.language": '"resource.language.de_de"',
	"locale.keyboardlayouts": '"German QWERTZ"',
	"locale.activekeyboardlayout": '"German QWERTZ"',
	"locale.country": '"Deutschland"',
	"filelists.showparentdiritems": "false",
	"filelists.ignorethewhensorting": "false",
	"filelists.showhidden": "true",
	"filelists.allowfiledeletion": "true",
	"myvideos.selectaction": 2,
	"epg.epgupdate": 120,
	"epg.futuredaystodisplay": 2,
	"myvideos.usetags": "true",
	"myvideos.stackvideos": "true",
	"videolibrary.groupmoviesets": "true",
	"videolibrary.showemptytvshows": "false",
	"videolibrary.tvshowsselectfirstunwatcheditem": 2,
	"videoplayer.autoplaynextitem": '"1,2"',
	"videoplayer.seeksteps": '"-180,-60,-30,-10,10,30,60,180"',
	"videoplayer.adjustrefreshrate": 2,
	"videoplayer.usedisplayasclock": "true",
	"videoplayer.teletextenabled": "false",
	"locale.audiolanguage": '"default"',
	"videoplayer.preferdefaultflag": "false",
	"locale.subtitlelanguage": '"forced_only"',
	"subtitles.languages": '"German"',
	"subtitles.downloadfirst": "true",
	"subtitles.tv": '"service.subtitles.opensubtitles-com"',
	"subtitles.movie": '"service.subtitles.opensubtitles-com"',
	"pvrmanager.usebackendchannelnumbers": "true",
	"pvrmanager.preselectplayingchannel": "true",
	"pvrplayback.confirmchannelswitch": "false",
	"pvrplayback.signalquality": "false",
	"pvrplayback.enableradiords": "false",
	"services.webserver": "true",
	"services.esallinterfaces": "true",
	"audiooutput.streamsilence": 1,
	"audiooutput.streamnoise": "true",
	"audiooutput.guisoundmode": 0,
	"audiooutput.guisoundvolume": 100,
	"powermanagement.shutdowntime": 30,
	"addons.unknownsources": "true",
	"system.playlistspath": '"special://profile/playlists/"',
	"addons.updatemode": 1}

pvrsettings ={
	"m3uUrl": "https://michaz1988.github.io/tv.m3u",
	"m3uCache": "false",
	"epgUrl": "https://bit.ly/michazguidegz",
	"epgCache": "false",
	"useInputstreamAdaptiveforHls": "true"}

def _set_pvr_settings():
	settings_dir = translatePath('special://profile/addon_data/pvr.iptvsimple')
	instance_files = sorted(
		os.path.join(settings_dir, name)
		for name in os.listdir(settings_dir)
		if name.startswith('instance-settings-') and name.endswith('.xml')
	) if os.path.isdir(settings_dir) else []

	if not instance_files:
		addon = xbmcaddon.Addon('pvr.iptvsimple')
		for key, value in pvrsettings.items():
			addon.setSetting(key, value)
		return False

	updated = False
	for settings_file in instance_files:
		tree = ET.parse(settings_file)
		root = tree.getroot()
		enabled = root.find("./setting[@id='kodi_addon_instance_enabled']")
		if enabled is not None and enabled.text == 'false':
			continue
		items = {item.get('id'): item for item in root.findall('setting')}
		for key, value in pvrsettings.items():
			item = items.get(key)
			if item is None:
				item = ET.SubElement(root, 'setting', {'id': key})
			item.attrib.pop('default', None)
			item.text = value
		temporary_file = settings_file + '.tmp'
		tree.write(temporary_file, encoding='utf-8', xml_declaration=True)
		os.replace(temporary_file, settings_file)
		updated = True
	return updated

def _remove_path(path):
	if os.path.isdir(path) and not os.path.islink(path):
		shutil.rmtree(path)
	elif os.path.lexists(path):
		os.remove(path)

def _archive_destination(profile_path, archive_name):
	if xbmc.getCondVisibility('System.Platform.Android'):
		return os.path.join('/storage/emulated/0/Download', archive_name)
	return os.path.join(profile_path, archive_name)

def _shutdown_kodi():
	xbmc.executebuiltin('Dialog.Close(all,true)')
	Dialog().notification('TOOLS', 'Kodi wird beendet', NOTIFICATION_INFO, 2000, False)
	time.sleep(2)
	os._exit(1)

def _extract_backup(archive_path, destination_path):
	allowed_roots = {'addons', 'userdata'}
	destination_root = os.path.abspath(destination_path)
	with zipfile.ZipFile(archive_path, 'r') as archive:
		members = archive.infolist()
		found_roots = set()
		for member in members:
			name = member.filename.replace('\\', '/')
			normalized = os.path.normpath(name)
			if normalized in ('', '.'):
				continue
			root = normalized.split(os.sep, 1)[0]
			target = os.path.abspath(os.path.join(destination_root, normalized))
			mode = (member.external_attr >> 16) & 0o170000
			if (
				name.startswith('/')
				or normalized == '..'
				or normalized.startswith('..' + os.sep)
				or os.path.commonpath((destination_root, target)) != destination_root
				or root not in allowed_roots
				or mode == 0o120000
			):
				raise ValueError('Ungültiger Pfad im Backup: %s' % member.filename)
			found_roots.add(root)
		if found_roots != allowed_roots:
			raise ValueError('Das Backup muss die Ordner addons und userdata enthalten.')
		for member in members:
			archive.extract(member, destination_path)

def _replace_userdata(source_path, destination_path, protected_path=None):
	destination_path = os.path.normpath(destination_path)
	parent = os.path.dirname(destination_path)
	name = os.path.basename(destination_path)
	marker = '%s.%d.%d' % (os.getpid(), int(time.time() * 1000), time.perf_counter_ns())
	new_path = os.path.join(parent, '.%s.plugin.video.tools.new.%s' % (name, marker))
	old_path = os.path.join(parent, '.%s.plugin.video.tools.old.%s' % (name, marker))
	try:
		shutil.copytree(source_path, new_path)
		if protected_path:
			shutil.copy2(protected_path, os.path.join(new_path, os.path.basename(protected_path)))
		os.replace(destination_path, old_path)
		try:
			os.replace(new_path, destination_path)
		except Exception:
			os.replace(old_path, destination_path)
			raise
	except Exception:
		_remove_path(new_path)
		raise
	return old_path

def _clean_previous_userdata(profile_path):
	profile_path = os.path.normpath(profile_path)
	parent = os.path.dirname(profile_path)
	name = os.path.basename(profile_path)
	current_process = '.%d.' % os.getpid()
	prefixes = (
		'.%s.plugin.video.tools.new.' % name,
		'.%s.plugin.video.tools.old.' % name,
	)
	try:
		for entry in os.listdir(parent):
			if entry.startswith(prefixes) and current_process not in entry:
				_remove_path(os.path.join(parent, entry))
	except OSError as error:
		xbmc.log('Alte Backup-Daten konnten nicht entfernt werden: %s' % error, xbmc.LOGDEBUG)

def _clean_python_cache(build_path):
	for root, dirs, files in os.walk(build_path, topdown=False):
		for name in files:
			if name.lower() == '__pyc' or name.lower().endswith('.pyc'):
				os.remove(os.path.join(root, name))
		for name in dirs:
			if name.lower() in ('__pycache__', '__pyc', '__pyc__'):
				shutil.rmtree(os.path.join(root, name))

def _clean_databases(userdata_path):
	database_path = os.path.join(userdata_path, 'Database')
	if not os.path.isdir(database_path):
		return
	for name in os.listdir(database_path):
		version = name[6:-3] if name.startswith('Addons') and name.endswith('.db') else ''
		if version.isdigit() and int(version) >= 33:
			continue
		_remove_path(os.path.join(database_path, name))

def _is_official_addon_data(addon_id):
	addon_id = addon_id.lower()
	return (
		addon_id in {
			'plugin.video.tools',
			'plugin.video.youtube',
			'plugin.video.themoviedb.helper',
		}
		or any(name in addon_id for name in (
			'joyn',
			'amazon',
			'extendedinfo',
			'opensubtitles',
			'resolveurl',
			'slyguy',
			'xtream',
			'xship',
			'youtube.dl',
		))
	)

def _clean_official_addon_data(userdata_path):
	addon_data_path = os.path.join(userdata_path, 'addon_data')
	if not os.path.isdir(addon_data_path):
		return
	for addon_id in os.listdir(addon_data_path):
		if _is_official_addon_data(addon_id):
			_remove_path(os.path.join(addon_data_path, addon_id))

def _is_excluded_build_addon(addon_id):
	addon_id = addon_id.lower()
	return (
		addon_id.startswith(('metadata.', 'inputstream.'))
		or addon_id in {
			'plugin.video.tools',
			'pvr.iptvsimple',
			'service.xbmc.versioncheck',
		}
	)

def _clean_build_addons(build_path):
	addons_path = os.path.join(build_path, 'addons')
	if not os.path.isdir(addons_path):
		return
	for addon_id in os.listdir(addons_path):
		if _is_excluded_build_addon(addon_id):
			_remove_path(os.path.join(addons_path, addon_id))

def _copy_build_sources(build_path, profile_path):
	tools_profile = os.path.normcase(os.path.normpath(profile_path))
	addons_source = translatePath('special://home/addons')
	normalized_addons_source = os.path.normcase(os.path.normpath(addons_source))

	def ignore_packages(source, names):
		if os.path.normcase(os.path.normpath(source)) == normalized_addons_source:
			return {'packages'}.intersection(names)
		return set()

	def ignore_build(source, names):
		if os.path.normcase(os.path.normpath(source)) == tools_profile:
			return {
				'build',
				'build.zip',
				'build.zip.tmp',
				'backup.zip',
				'backup.zip.tmp',
			}.intersection(names)
		return set()

	shutil.copytree(
		addons_source,
		os.path.join(build_path, 'addons'),
		ignore=ignore_packages,
	)
	shutil.copytree(
		translatePath('special://profile'),
		os.path.join(build_path, 'userdata'),
		ignore=ignore_build,
	)

def _zip_build(build_path, archive_path):
	temporary_archive = archive_path + '.tmp'
	_remove_path(temporary_archive)
	with zipfile.ZipFile(temporary_archive, 'w', zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
		for top_level in ('addons', 'userdata'):
			archive.writestr(top_level + '/', '')
			folder = os.path.join(build_path, top_level)
			for root, dirs, files in os.walk(folder):
				for name in files:
					path = os.path.join(root, name)
					archive.write(path, os.path.relpath(path, build_path))
	os.replace(temporary_archive, archive_path)

def _make_archive(title, archive_name, clean_build_addons=False, select_variant=True):
	choice = 1
	if select_variant:
		choice = Dialog().select(title, ['Official', 'Private', 'Abbruch'])
		if choice not in (0, 1):
			return

	profile_path = translatePath(xbmcaddon.Addon().getAddonInfo('profile'))
	build_path = os.path.join(profile_path, 'build')
	archive_path = os.path.join(profile_path, archive_name)
	progress = DialogProgress()
	progress.create(title, 'Daten werden vorbereitet ...')
	try:
		_remove_path(build_path)
		os.makedirs(build_path)
		progress.update(10, 'Add-ons und Benutzerdaten werden kopiert ...')
		_copy_build_sources(build_path, profile_path)
		progress.update(65, 'Build wird bereinigt ...')
		_clean_python_cache(build_path)
		userdata_path = os.path.join(build_path, 'userdata')
		_clean_databases(userdata_path)
		_remove_path(os.path.join(userdata_path, 'Thumbnails'))
		if choice == 0:
			_clean_official_addon_data(userdata_path)
			_remove_path(os.path.join(userdata_path, 'favourites.xml'))
		if clean_build_addons:
			_clean_build_addons(build_path)
		progress.update(80, '%s wird erstellt ...' % archive_name)
		_zip_build(build_path, archive_path)
		progress.update(95, 'Archiv wird abgeschlossen ...')
		final_path = _archive_destination(profile_path, archive_name)
		if os.path.normcase(os.path.abspath(final_path)) != os.path.normcase(os.path.abspath(archive_path)):
			os.makedirs(os.path.dirname(final_path), exist_ok=True)
			shutil.move(archive_path, final_path)
	except Exception as error:
		xbmc.log('%s fehlgeschlagen: %s' % (title, error), xbmc.LOGERROR)
		Dialog().ok(title, 'Archiv konnte nicht erstellt werden:\n%s' % error)
		return
	finally:
		try:
			_remove_path(build_path)
			_remove_path(archive_path + '.tmp')
		finally:
			progress.close()

	Dialog().ok('%s fertig' % title.split()[0], 'Gespeichert unter:\n%s' % final_path)

@plugin.route('/make-backup')
def make_backup():
	_make_archive('Backup erstellen', 'backup.zip', select_variant=False)

@plugin.route('/make-build')
def make_build():
	_make_archive('Build erstellen', 'build.zip', clean_build_addons=True)

@plugin.route('/restore-backup')
def restore_backup():
	profile_path = translatePath('special://profile')
	backup_path = _archive_destination(profile_path, 'backup.zip')
	Dialog().ok(
		'Backup wiederherstellen',
		'Ist Backup in:\n%s' % backup_path,
	)
	if not os.path.isfile(backup_path):
		Dialog().ok('Backup wiederherstellen', 'Backup nicht gefunden:\n%s' % backup_path)
		return

	restore_path = translatePath('special://temp/plugin.video.tools.restore')
	progress = DialogProgress()
	progress.create('Backup wiederherstellen', 'Backup wird geprüft ...')
	try:
		_remove_path(restore_path)
		os.makedirs(restore_path)
		_extract_backup(backup_path, restore_path)
		backup_userdata = os.path.join(restore_path, 'userdata')
		backup_addons = os.path.join(restore_path, 'addons')
		progress.update(40, 'Benutzerdaten werden ersetzt ...')
		protected_backup = None
		if os.path.normcase(os.path.abspath(os.path.dirname(backup_path))) == os.path.normcase(os.path.abspath(profile_path)):
			protected_backup = backup_path
		_replace_userdata(backup_userdata, profile_path, protected_backup)
		progress.update(75, 'Add-ons werden wiederhergestellt ...')
		shutil.copytree(
			backup_addons,
			translatePath('special://home/addons'),
			dirs_exist_ok=True,
		)
		xbmc.executebuiltin('UpdateLocalAddons')
		progress.update(100, 'Backup wurde wiederhergestellt.')
	except Exception as error:
		xbmc.log('Backup wiederherstellen fehlgeschlagen: %s' % error, xbmc.LOGERROR)
		Dialog().ok('Backup wiederherstellen', 'Backup konnte nicht wiederhergestellt werden:\n%s' % error)
		return
	finally:
		try:
			_remove_path(restore_path)
		finally:
			progress.close()

	_shutdown_kodi()

@plugin.route('/')
def index():
	_clean_previous_userdata(translatePath('special://profile'))
	add(plugin.handle, plugin.url_for(bundle),ListItem("Build installieren"))
	add(plugin.handle, plugin.url_for(make_build), ListItem("Build erstellen"))
	add(plugin.handle, plugin.url_for(make_backup), ListItem("Backup erstellen"))
	add(plugin.handle, plugin.url_for(restore_backup), ListItem("Backup wiederherstellen"))
	add(plugin.handle, plugin.url_for(set_settings),ListItem("Kodi-Einstellugen setzen"))
	add(plugin.handle, plugin.url_for(ftp),ListItem("FTP SERVER"))
	add(plugin.handle, plugin.url_for(speedtest), ListItem("Speedtest"))
	add(plugin.handle, plugin.url_for(showIp), ListItem("IP anzeigen"))
	add(plugin.handle, plugin.url_for(repotest),ListItem("Repos testen"))
	add(plugin.handle, plugin.url_for(beenden),ListItem("Beenden"))
	add(plugin.handle, plugin.url_for(buffer), ListItem("Buffer fix"))
	add(plugin.handle, plugin.url_for(cleanthumbs), ListItem("Thumbs entfernen"))
	add(plugin.handle, plugin.url_for(ReloadSkin), ListItem("ReloadSkin"))
	add(plugin.handle, plugin.url_for(setmenu), ListItem("ALLE-EINSTELLUNGEN"), True)
	end(plugin.handle)

@plugin.route('/setmenu')
def setmenu():
	addonids = set()
	for base_path in (translatePath('special://home/addons'),
					  translatePath('special://xbmc/addons')):
		for addonid in os.listdir(base_path):
			settings_file = os.path.join(base_path, addonid, 'resources', 'settings.xml')
			if os.path.isfile(settings_file):
				addonids.add(addonid)
	addons = []
	for addonid in addonids:
		try:
			addon_name = xbmcaddon.Addon(addonid).getAddonInfo('name') or addonid
		except Exception as error:
			xbmc.log('Addon-Name für %s konnte nicht gelesen werden: %s' % (addonid, error), xbmc.LOGDEBUG)
			addon_name = addonid
		addons.append((addon_name, addonid))
	for addon_name, addonid in sorted(addons, key=lambda item: item[0].casefold()):
		label = '%s - Einstellungen' % addon_name
		add(plugin.handle, plugin.url_for(settings, id=addonid), ListItem(label))
	end(plugin.handle)
	
@plugin.route('/settings/<id>')
def settings(id):
	xbmcaddon.Addon(id).openSettings()

@plugin.route('/speedtest')
def speedtest():
	from resources.lib import speedtest_kodi as speedtest_module
	speedtest_module.main()
	
@plugin.route('/repotest')
def repotest():
	from resources.lib import repotest

@plugin.route('/ReloadSkin')
def ReloadSkin():
	xbmc.executebuiltin('ReloadSkin')
	
@plugin.route('/buffer')
def buffer():
	from resources.lib import scripts
	scripts.advancedSettings()
		
@plugin.route('/ftp')
def ftp():
	from resources.lib import scripts
	scripts.show()
    
@plugin.route('/beenden')
def beenden():
	from resources.lib import thumbnail_cleanup
	thumbnail_cleanup.cleanup_before_exit()
	_shutdown_kodi()
	
@plugin.route('/showIp')
def showIp():
	addresses = ['Lokale IP: %s' % xbmc.getIPAddress()]
	for label, url in (('IPv6', 'https://v6.ident.me/'),
					   ('IPv4', 'https://v4.ident.me/')):
		try:
			address = requests.get(url, timeout=10).text.strip()
		except requests.RequestException:
			address = 'nicht verfügbar'
		addresses.append('%s: %s' % (label, address))
	Dialog().ok('IP-Adressen', '\n'.join(addresses))

@plugin.route('/cleanthumbs')
def cleanthumbs():
	if not Dialog().yesno('TOOLS', 'Alle Thumbnails entfernen?'):
		return
	for folder in (translatePath('special://profile/Thumbnails/'),
				   translatePath('special://home/addons/packages/')):
		for root, dirs, files in os.walk(folder):
			for name in files:
				os.remove(os.path.join(root, name))
	Dialog().ok('TOOLS', 'Fertig')
			
@plugin.route('/bundle')
def bundle():
	from resources.lib import scripts
	yesnowindow = Dialog().yesno('TOOLS', 'Build installieren?')
	if yesnowindow and scripts.get_packages():
		_shutdown_kodi()
		
@plugin.route('/set_settings')
def set_settings():
	for key, value in guisettings.items():
		xbmc.executeJSONRPC('{"jsonrpc":"2.0", "method":"Settings.SetSettingValue", "params":{"setting":"%s", "value":%s}, "id":1}' % (key, value))
	if _set_pvr_settings():
		Dialog().ok('TOOLS', 'Einstellungen gesetzt. Kodi neu starten, damit die PVR-Einstellungen wirksam werden.')

plugin.run()
