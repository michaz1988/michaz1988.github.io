# -*- coding: utf-8 -*-
"""Kodi user interface for the bundled speedtest-cli engine."""

import threading

import xbmc
import xbmcgui

from resources.lib import speedtest as speedtest_cli


TITLE = 'Speedtest'


class TestCancelled(Exception):
	pass


def _update(progress, percent, message, shutdown_event):
	if progress.iscanceled():
		shutdown_event.set()
		raise TestCancelled()
	progress.update(percent, message)


def _transfer_callback(progress, start_percent, span, label, shutdown_event):
	finished = [0]

	def callback(index, total, start=False, end=False, transferred=None,
				 elapsed=None):
		if not end:
			return
		finished[0] += 1
		message = label
		if transferred is not None and elapsed:
			speed = float(transferred) * 8.0 / float(elapsed) / 1000000.0
			message = '%s\nAktuell: %.2f Mbit/s' % (label, speed)
		percent = start_percent + int(span * finished[0] / max(total, 1))
		_update(progress, percent, message, shutdown_event)

	return callback


def run_test():
	progress = xbmcgui.DialogProgress()
	shutdown_event = threading.Event()
	progress.create(TITLE, 'Speedtest wird vorbereitet …')

	try:
		_update(progress, 2, 'Konfiguration wird geladen …', shutdown_event)
		test = speedtest_cli.Speedtest(
			timeout=10,
			secure=True,
			shutdown_event=shutdown_event,
		)

		client = test.config.get('client', {})
		isp = client.get('isp', 'Unbekannter Anbieter')
		_update(progress, 8, 'Serverliste wird geladen …\n%s' % isp, shutdown_event)
		test.get_servers()

		_update(progress, 15, 'Bester Server wird ermittelt …', shutdown_event)
		server = test.get_best_server()
		server_name = server.get('name', 'Unbekannt')
		sponsor = server.get('sponsor', 'Unbekannt')
		ping = float(server.get('latency', 0))

		download_label = 'Download wird getestet …\n%s (%s)' % (sponsor, server_name)
		_update(progress, 20, download_label, shutdown_event)
		download_callback = _transfer_callback(
			progress, 20, 43, download_label, shutdown_event
		)
		test.download(callback=download_callback)

		upload_label = 'Upload wird getestet …\n%s (%s)' % (sponsor, server_name)
		_update(progress, 65, upload_label, shutdown_event)
		upload_callback = _transfer_callback(
			progress, 65, 33, upload_label, shutdown_event
		)
		test.upload(callback=upload_callback, pre_allocate=False)

		_update(progress, 100, 'Speedtest abgeschlossen.', shutdown_event)
		results = test.results
		return {
			'download': results.download / 1000.0 / 1000.0,
			'upload': results.upload / 1000.0 / 1000.0,
			'ping': ping,
			'server': server_name,
			'sponsor': sponsor,
		}
	finally:
		shutdown_event.set()
		progress.close()


def main():
	try:
		result = run_test()
	except TestCancelled:
		xbmc.log('Speedtest vom Benutzer abgebrochen.', xbmc.LOGINFO)
		return
	except Exception as error:
		xbmc.log('Speedtest fehlgeschlagen: %s' % error, xbmc.LOGERROR)
		xbmcgui.Dialog().ok(
			TITLE,
			'Der Speedtest ist fehlgeschlagen:\n%s' % error,
		)
		return

	xbmcgui.Dialog().ok(
		TITLE,
		'Download: %.2f Mbit/s\n'
		'Upload: %.2f Mbit/s\n'
		'Ping: %.2f ms\n'
		'Server: %s (%s)' % (
			result['download'],
			result['upload'],
			result['ping'],
			result['sponsor'],
			result['server'],
		),
	)


if __name__ == '__main__':
	main()
