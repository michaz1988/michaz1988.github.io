################################################################################
#	  Copyright (C) 2019 drinfernoo										   #
#																			  #
#  This Program is free software; you can redistribute it and/or modify		#
#  it under the terms of the GNU General Public License as published by		#
#  the Free Software Foundation; either version 2, or (at your option)		 #
#  any later version.														  #
#																			  #
#  This Program is distributed in the hope that it will be useful,			 #
#  but WITHOUT ANY WARRANTY; without even the implied warranty of			  #
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the				#
#  GNU General Public License for more details.								#
#																			  #
#  You should have received a copy of the GNU General Public License		   #
#  along with XBMC; see the file COPYING.  If not, write to					#
#  the Free Software Foundation, 675 Mass Ave, Cambridge, MA 02139, USA.	   #
#  http://www.gnu.org/copyleft/gpl.html										#
################################################################################

# Upload implementation adapted from speedtest-cli 2.1.4b1.
# Copyright 2012 Matt Martz, licensed under Apache-2.0.
# https://github.com/sivel/speedtest-cli

import json
import math
import os
import socket
import sys
import threading
import timeit
import xml.etree.ElementTree as ET

from concurrent.futures import ThreadPoolExecutor, as_completed
from http.client import HTTPConnection, HTTPSConnection
from io import BytesIO
from queue import Queue
from statistics import median
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import xbmc
import xbmcgui

user_agent = 'Mozilla/5.0 (Kodi) Python/3 speedtest-cli/2.1.4'
shutdown_event = None


class SpeedtestCliServerListError(Exception):
	"""
"""


class SpeedtestUploadTimeout(Exception):
	pass


def distance(origin, destination):
	(lat1, lon1) = origin
	(lat2, lon2) = destination
	radius = 6371  # km

	dlat = math.radians(lat2 - lat1)
	dlon = math.radians(lon2 - lon1)
	a = math.sin(dlat / 2) * math.sin(dlat / 2) \
		+ math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) \
		* math.sin(dlon / 2) * math.sin(dlon / 2)
	c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
	d = radius * c

	return d


def build_request(url, data=None, headers=None, bump='0'):
	if url[0] == ':':
		schemed_url = 'http{0}'.format(url)
	else:
		schemed_url = url
	delimiter = '&' if '?' in schemed_url else '?'
	final_url = '%s%sx=%d.%s' % (
		schemed_url,
		delimiter,
		int(timeit.time.time() * 1000),
		bump,
	)
	request_headers = dict(headers or {})
	request_headers['User-Agent'] = user_agent
	request_headers['Cache-Control'] = 'no-cache'
	return Request(final_url, data=data, headers=request_headers)


def catch_request(request):
	try:
		uh = urlopen(request, timeout=10)
		return uh
	except (HTTPError, URLError, socket.error):
		e = sys.exc_info()[1]
		xbmc.log("Speedtest Error: {0}".format(e), level=xbmc.LOGDEBUG)
		return None


class FileGetter(threading.Thread):

	def __init__(self, url, start):
		self.url = url
		self.result = None
		self.starttime = start
		threading.Thread.__init__(self)

	def run(self):
		self.result = [0]
		try:
			if timeit.default_timer() - self.starttime <= 10:
				request = build_request(self.url)
				f = urlopen(request, timeout=10)
				while 1 and not shutdown_event.is_set():
					self.result.append(len(f.read(10240)))
					if self.result[-1] == 0:
						break
				f.close()
		except IOError:
			pass


def download_speed(files, quiet=False):
	start = timeit.default_timer()

	def producer(q, files):
		for file in files:
			thread = FileGetter(file, start)
			thread.start()
			q.put(thread, True)
			if not quiet and not shutdown_event.is_set():
				sys.stdout.write('.')
				sys.stdout.flush()

	finished = []

	def consumer(q, total_files):
		while len(finished) < total_files:
			thread = q.get(True)
			while thread.is_alive():
				thread.join(timeout=0.1)
			finished.append(sum(thread.result))
			del thread

	q = Queue(6)
	prod_thread = threading.Thread(target=producer, args=(q, files))
	cons_thread = threading.Thread(target=consumer, args=(q, len(files)))
	start = timeit.default_timer()
	prod_thread.start()
	cons_thread.start()

	while prod_thread.is_alive():
		prod_thread.join(timeout=0.1)

	while cons_thread.is_alive():
		cons_thread.join(timeout=0.1)

	return sum(finished) / (timeit.default_timer() - start)


class HTTPUploaderData:

	def __init__(self, length, timeout):
		self.length = length
		self.start = 0
		self.timeout = timeout
		self._data = None
		self.total = [0]

	def pre_allocate(self):
		chars = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
		multiplier = int(round(int(self.length) / 36.0))
		self._data = BytesIO(
			('content1=%s' % (chars * multiplier)[0:self.length - 9]).encode('utf-8')
		)

	@property
	def data(self):
		if self._data is None:
			self.pre_allocate()
		return self._data

	def read(self, size=10240):
		if timeit.default_timer() - self.start > self.timeout or shutdown_event.is_set():
			raise SpeedtestUploadTimeout()
		chunk = self.data.read(size)
		self.total.append(len(chunk))
		return chunk

	def __len__(self):
		return self.length


class FilePutter(threading.Thread):

	def __init__(self, request, start, timeout):
		threading.Thread.__init__(self)
		self.request = request
		self.request.data.start = self.starttime = start
		self.timeout = timeout
		self.result = 0

	def run(self):
		try:
			if timeit.default_timer() - self.starttime <= self.timeout and not shutdown_event.is_set():
				f = urlopen(self.request, timeout=self.timeout)
				f.read(11)
				f.close()
				self.result = sum(self.request.data.total)
		except (IOError, SpeedtestUploadTimeout):
			self.result = sum(self.request.data.total)
		except (HTTPError, URLError, socket.error):
			self.result = 0


def upload_speed(url, sizes, quiet=False, timeout=10, max_threads=6):
	requests = []
	for index, size in enumerate(sizes):
		data = HTTPUploaderData(size, timeout)
		data.pre_allocate()
		request = build_request(
			url,
			data=data,
			headers={'Content-Length': str(size)},
			bump=str(index),
		)
		requests.append(request)

	start = timeit.default_timer()
	finished = []
	for offset in range(0, len(requests), max_threads):
		if timeit.default_timer() - start > timeout or shutdown_event.is_set():
			break
		threads = [FilePutter(request, start, timeout) for request in requests[offset:offset + max_threads]]
		for thread in threads:
			thread.start()
		for thread in threads:
			thread.join()
			finished.append(thread.result)
			if not quiet and not shutdown_event.is_set():
				sys.stdout.write('.')
				sys.stdout.flush()

	return sum(finished) / (timeit.default_timer() - start)


def get_config():
	request = build_request('http://www.speedtest.net/speedtest-config.php')
	uh = catch_request(request)
	if uh is None:
		return None

	configxml = []

	while 1:
		configxml.append(uh.read(10240))
		if len(configxml[-1]) == 0:
			break
	if int(uh.code) != 200:
		uh.close()
		return None
	uh.close()
	try:
		root = ET.fromstring(b''.join(configxml))
		config = {
			'client': root.find('client').attrib,
			'times': root.find('times').attrib,
			'download': root.find('download').attrib,
			'upload': root.find('upload').attrib,
			}
	except (AttributeError, ET.ParseError):
		xbmc.log('Failed to parse speedtest.net configuration', level=xbmc.LOGDEBUG)
		return None

	del root
	del configxml
	return config


def _api_servers(client):
	url = 'https://www.speedtest.net/api/js/servers?engine=js&https_functional=true&limit=20'
	headers = {
		'User-Agent': 'Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0 Mobile Safari/537.36',
		'Accept': 'application/json, text/plain, */*',
		'Referer': 'https://www.speedtest.net/',
		'Origin': 'https://www.speedtest.net',
		'Accept-Language': 'de-AT,de;q=0.9,en;q=0.8',
	}
	try:
		with urlopen(Request(url, headers=headers), timeout=10) as response:
			servers = json.load(response)
	except (HTTPError, URLError, OSError, ValueError):
		return []
	if not isinstance(servers, list):
		return []

	result = []
	for server in servers:
		try:
			server['d'] = distance(
				(float(client['lat']), float(client['lon'])),
				(float(server['lat']), float(server['lon'])),
			)
		except (KeyError, TypeError, ValueError):
			continue
		if not server.get('https_functional') or not server.get('host'):
			continue
		server['url'] = 'https://%s/speedtest/upload.php' % server['host']
		result.append(server)
	return result


def closest_servers(client, all=False):
	api_servers = _api_servers(client)
	if api_servers:
		return api_servers

	urls = ['http://www.speedtest.net/speedtest-servers-static.php',
			'https://www.speedtest.net/speedtest-servers-static.php']
	errors = []
	servers = {}
	for url in urls:
		try:
			request = build_request(url)
			uh = catch_request(request)
			if uh is None:
				errors.append(url)
				raise SpeedtestCliServerListError
			serversxml = []
			while 1:
				serversxml.append(uh.read(10240))
				if len(serversxml[-1]) == 0:
					break
			if int(uh.code) != 200:
				uh.close()
				raise SpeedtestCliServerListError
			uh.close()
			try:
				root = ET.fromstring(b''.join(serversxml))
				elements = root.iter('server')
			except ET.ParseError:
				raise SpeedtestCliServerListError
			for server in elements:
				attrib = server.attrib
				d = distance([float(client['lat']), float(client['lon'])], [float(attrib.get('lat')),
																			float(attrib.get('lon'))])
				attrib['d'] = d
				if d not in servers:
					servers[d] = [attrib]
				else:
					servers[d].append(attrib)

			del root
			del serversxml
			del elements
		except SpeedtestCliServerListError:
			continue
		if servers:
			break
	if not servers:
		xbmc.log('Failed to retrieve list of speedtest.net servers: {0}'.format('\n'.join(errors)), level=xbmc.LOGDEBUG)
		return []
	closest = []
	for d in sorted(servers.keys()):
		for s in servers[d]:
			closest.append(s)
			if len(closest) == 5 and not all:
				break
		else:
			continue
		break
	del servers
	return closest


def _measure_server_latency(server):
	urlparts = urlparse(server['url'])
	connection_class = HTTPSConnection if urlparts.scheme == 'https' else HTTPConnection
	path = '%s/latency.txt' % os.path.dirname(urlparts.path)
	connection = connection_class(urlparts.netloc, timeout=3)
	headers = {'User-Agent': user_agent, 'Connection': 'keep-alive'}
	latencies = []
	try:
		for attempt in range(4):
			request_path = '%s?x=%d.%d' % (path, int(timeit.time.time() * 1000), attempt)
			start = timeit.default_timer()
			connection.request('GET', request_path, headers=headers)
			response = connection.getresponse()
			body = response.read()
			elapsed = (timeit.default_timer() - start) * 1000
			if response.status != 200 or not body.startswith(b'test=test'):
				return None
			if attempt:
				latencies.append(elapsed)
	except (HTTPError, URLError, OSError, socket.error):
		return None
	finally:
		connection.close()
	if not latencies:
		return None
	return round(median(latencies), 3)


def get_best_server(servers):
	if not servers:
		return None
	results = []
	with ThreadPoolExecutor(max_workers=min(8, len(servers))) as executor:
		futures = {executor.submit(_measure_server_latency, server): server for server in servers}
		for future in as_completed(futures):
			try:
				latency = future.result()
			except Exception as error:
				xbmc.log('Speedtest latency check failed: %s' % error, level=xbmc.LOGDEBUG)
				continue
			if latency is not None:
				results.append((latency, futures[future].get('d', float('inf')), futures[future]))
	if not results:
		return None
	latency, _, best = min(results, key=lambda result: (result[0], result[1]))
	best['latency'] = latency
	return best


def speedtest(simple=False, units=('bit', 8)):
	global shutdown_event
	shutdown_event = threading.Event()

	dp = xbmcgui.DialogProgress()
	try:
		return _run_speedtest(dp, simple, units)
	finally:
		dp.close()


def _run_speedtest(dp, simple, units):
	line1 = '[COLOR {0}]Starting test..[/COLOR]'.format('orange')
	dp.create('{0}: [COLOR {1}]Speed Test[/COLOR]'.format('TOOLS', 'yellow'), line1)
	dp.update(0)
	xbmc.log('Retrieving speedtest.net configuration...', level=xbmc.LOGDEBUG)
	line2 = '[COLOR {0}]Retrieving speedtest.net configuration...[/COLOR]'.format('orange')
	dp.update(2, line1+'\n'+line2)
	config = get_config()
	if not config:
		xbmcgui.Dialog().ok('Speed Test', 'Die Speedtest-Konfiguration konnte nicht geladen werden.')
		return None

	xbmc.log('Retrieving speedtest.net server list...', level=xbmc.LOGDEBUG)
	line3 = '[COLOR {0}]Retrieving speedtest.net server list...[/COLOR]'.format('orange')
	dp.update(4, line1+'\n'+line2+'\n'+line3)

	servers = closest_servers(config['client'])
	if not servers:
		xbmcgui.Dialog().ok('Speed Test', 'Es konnte kein Speedtest-Server gefunden werden.')
		return None

	xbmc.log('Testing from %(isp)s (%(ip)s)...' % config['client'], level=xbmc.LOGDEBUG)
	line1 = '[COLOR ' + 'orange' + ']Testing From:[/COLOR] [COLOR ' \
		+ 'yellow' + ']%(isp)s (%(ip)s)[/COLOR]' % config['client']
	dp.update(6, line1)

	xbmc.log('Selecting best server based on latency...', level=xbmc.LOGDEBUG)
	line2 = '[COLOR {0}]Selecting best server based on latency...[/COLOR]'.format('orange')
	dp.update(8, '\n'+line2)
	best = get_best_server(servers)
	if not best:
		xbmcgui.Dialog().ok(
			'Speed Test',
			'Keiner der gefundenen Server hat auf den Ping-Test geantwortet.',
		)
		return None

	xbmc.log('Hosted by %(sponsor)s (%(name)s) [%(d)0.2f km]: %(latency)s ms' % best)

	line2 = ('[COLOR ' + 'orange'
			 + ']Server location: %(name)s [%(d)0.2f km]: %(latency)s ms[/COLOR]' % best)
	dp.update(10, '\n'+line2)

	sizes = [350, 500, 750, 1000, 1500, 2000, 2500, 3000, 3500, 4000]
	urls = []
	for size in sizes:
		for i in range(0, 4):
			urls.append('{0}/random{1}x{2}.jpg'.format(os.path.dirname(best['url']), size, size))

	xbmc.log('Testing download speed', level=xbmc.LOGDEBUG)
	line3 = '[COLOR {0}]Testing download speed...[/COLOR]'.format('orange')
	dp.update(15, '\n\n'+line3)
	dlspeed = download_speed(urls, simple)

	xbmc.log('Download: %0.2f M%s/s' % (dlspeed / 1000 / 1000 * units[1], units[0]))

	upload_config = config['upload']
	upload_sizes = [32768, 65536, 131072, 262144, 524288, 1048576, 7340032]
	ratio = max(1, int(upload_config.get('ratio', 1)))
	upload_sizes = upload_sizes[ratio - 1:] or upload_sizes[-1:]
	max_chunks = max(1, int(upload_config.get('maxchunkcount', len(upload_sizes))))
	chunk_repetitions = int(math.ceil(max_chunks / len(upload_sizes)))
	sizes = (upload_sizes * chunk_repetitions)[:max_chunks]
	upload_timeout = max(1, int(upload_config.get('testlength', 10)))
	upload_threads = max(1, int(upload_config.get('threads', 6)))

	xbmc.log('[COLOR red]Testing upload speed[/COLOR]', level=xbmc.LOGDEBUG)
	line2 = '[COLOR %s]Testing download speed:[/COLOR] [COLOR %s]%0.2f M%s/s[/COLOR]' % ('orange', 'yellow', dlspeed / 1000 / 1000 * units[1], units[0])
	line3 = '[COLOR {0}]Testing upload speed...[/COLOR]'.format('orange')
	dp.update(65, '\n'+line2+'\n'+line3)
	ulspeed = upload_speed(
		best['url'],
		sizes,
		simple,
		timeout=upload_timeout,
		max_threads=upload_threads,
	)

	xbmc.log('Upload: %0.2f M%s/s' % (ulspeed / 1000 / 1000 * units[1], units[0]))

	if ulspeed < 1:
		xbmcgui.Dialog().ok('Speed Test', 'Der gewählte Server hat keine Upload-Daten angenommen.')
		return None

	line1 = line2
	line2 = '[COLOR %s]Testing upload speed:[/COLOR] [COLOR %s]%0.2f M%s/s[/COLOR]' % ('orange', 'yellow', ulspeed / 1000 / 1000 * units[1], units[0])
	line3 = '[COLOR %s]Getting results...[/COLOR]' % 'orange'
	dp.update(95, line1+'\n'+line2+'\n'+line3)

	ping = int(round(best['latency'], 0))
	curserver = '%(name)s [%(d)0.2f km]: %(latency)s ms' % best
	download = dlspeed / 1000 / 1000 * units[1]
	upload = ulspeed / 1000 / 1000 * units[1]
	dp.update(100, line1+'\n'+line2)
	return download, units[0], upload, units[0], ping, curserver


def main():
	try:
		result = speedtest()
		if result:
			download, download_unit, upload, upload_unit, ping, server = result
			xbmcgui.Dialog().ok(
				'Speed Test',
				'Download: %.2f M%s/s\nUpload: %.2f M%s/s\nPing: %d ms\nServer: %s' % (
					download, download_unit, upload, upload_unit, ping, server
				),
			)
	except KeyboardInterrupt:
		xbmc.log('\nCancelling...', level=xbmc.LOGDEBUG)
	except Exception as error:
		xbmc.log('Speedtest fehlgeschlagen: %s' % error, level=xbmc.LOGERROR)
		xbmcgui.Dialog().ok('Speed Test', 'Der Speedtest ist fehlgeschlagen:\n%s' % error)


if __name__ == '__main__':
	main()
