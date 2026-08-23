# -*- coding: utf-8 -*-
"""Mark oversized thumbnail caches and clean them before Kodi exits."""

import os
import shutil

import xbmc
from xbmcvfs import translatePath


THUMBNAIL_LIMIT = 50 * 1024 * 1024
THUMBNAIL_PATH = 'special://profile/Thumbnails/'
PACKAGES_PATH = 'special://home/addons/packages/'
MARKER_PATH = 'special://profile/addon_data/plugin.video.tools/thumbnail_cleanup.marker'


def _translated(path):
	return os.path.normpath(translatePath(path))


def directory_exceeds_limit(path, limit=THUMBNAIL_LIMIT):
	"""Return as soon as regular files in path exceed limit bytes."""
	total = 0
	if not os.path.isdir(path):
		return False
	for root, dirs, files in os.walk(path, followlinks=False):
		dirs[:] = [name for name in dirs if not os.path.islink(os.path.join(root, name))]
		for name in files:
			file_path = os.path.join(root, name)
			if os.path.islink(file_path):
				continue
			try:
				total += os.path.getsize(file_path)
			except OSError as error:
				xbmc.log(
					'Thumbnail-Datei konnte nicht geprüft werden: %s' % error,
					xbmc.LOGDEBUG,
				)
			if total > limit:
				return True
	return False


def marker_is_set(marker_path=None):
	marker_path = marker_path or _translated(MARKER_PATH)
	try:
		with open(marker_path, 'r', encoding='utf-8') as marker_file:
			return marker_file.read().strip().lower() == 'true'
	except OSError:
		return False


def set_marker(marker_path=None):
	marker_path = marker_path or _translated(MARKER_PATH)
	marker_directory = os.path.dirname(marker_path)
	os.makedirs(marker_directory, exist_ok=True)
	temporary_path = marker_path + '.tmp'
	with open(temporary_path, 'w', encoding='utf-8') as marker_file:
		marker_file.write('true\n')
	os.replace(temporary_path, marker_path)


def check_at_startup(thumbnail_path=None, marker_path=None):
	"""Check once at Kodi startup and persist a marker above 50 MiB."""
	thumbnail_path = thumbnail_path or _translated(THUMBNAIL_PATH)
	marker_path = marker_path or _translated(MARKER_PATH)
	if marker_is_set(marker_path):
		return True
	if directory_exceeds_limit(thumbnail_path):
		set_marker(marker_path)
		xbmc.log('Thumbnail-Cache überschreitet 50 MiB; Marker wurde gesetzt.', xbmc.LOGINFO)
		return True
	return False


def _remove_directory(path):
	if os.path.isdir(path) and not os.path.islink(path):
		shutil.rmtree(path)
	elif os.path.lexists(path):
		os.remove(path)


def cleanup_before_exit(thumbnail_path=None, packages_path=None, marker_path=None):
	"""Apply marked thumbnail cleanup and always remove cached packages."""
	thumbnail_path = thumbnail_path or _translated(THUMBNAIL_PATH)
	packages_path = packages_path or _translated(PACKAGES_PATH)
	marker_path = marker_path or _translated(MARKER_PATH)

	if marker_is_set(marker_path):
		try:
			_remove_directory(thumbnail_path)
			if os.path.lexists(marker_path):
				os.remove(marker_path)
			xbmc.log('Markierter Thumbnail-Cache wurde vor dem Beenden gelöscht.', xbmc.LOGINFO)
		except OSError as error:
			xbmc.log('Thumbnail-Cache konnte nicht gelöscht werden: %s' % error, xbmc.LOGERROR)

	try:
		_remove_directory(packages_path)
		xbmc.log('Addon-Paketcache wurde vor dem Beenden gelöscht.', xbmc.LOGINFO)
	except OSError as error:
		xbmc.log('Addon-Paketcache konnte nicht gelöscht werden: %s' % error, xbmc.LOGERROR)
