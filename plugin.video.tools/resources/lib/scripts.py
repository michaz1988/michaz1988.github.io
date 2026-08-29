# -*- coding: utf-8 -*-
import io, os, re, shutil, sys, tempfile, threading, time, zipfile

import requests
import xbmc, xbmcaddon, xbmcgui, xbmcplugin
from resources.lib.pyftpdlib.authorizers import DummyAuthorizer
from resources.lib.pyftpdlib.handlers import FTPHandler
from resources.lib.pyftpdlib.servers import FTPServer
from xbmcvfs import translatePath

addon = xbmcaddon.Addon()
addonInfo = addon.getAddonInfo
addonPath = addonInfo('path')
ftppath = translatePath('special://home')
dialog = xbmcgui.Dialog()
monitor = xbmc.Monitor()
WINDOW_HOME = xbmcgui.Window(10000)
FTP_SERVER_PORT_PROPERTY = 'plugin.video.tools.ftp.port'

def localize(id):
	return xbmc.getLocalizedString(id)

def get(key):
	return WINDOW_HOME.getProperty(key)

def xbmcNotify(heading, message, icon=xbmcgui.NOTIFICATION_ERROR):
	dialog.notification(heading=heading, message=message, icon=icon)

def convert_size(num, suffix='B'):
	for unit in ['', 'K', 'M', 'G']:
		if abs(num) < 1024.0:
			return "%3.02f %s%s" % (num, unit, suffix)
		num /= 1024.0
	return "%.02f %s%s" % (num, 'G', suffix)

class ForceWindowThread(threading.Thread):

    def __init__(self, fw):
        threading.Thread.__init__(self)
        self.fw = fw
        self.daemon = True
        self.start()

    def run(self):
        while (not monitor.abortRequested() and self.fw.currentWindow and
               get('Locked') == 'true'):
            winId = xbmcgui.getCurrentWindowId()
            if winId < 13000 or winId >= 14000:
                self.fw.onAction(None)
            if monitor.waitForAbort(0.1):
                break

        return


class ForceWindow(object):
    currentWindow = 0
    last = 0

    def onAction(self, action):
        winId = xbmcgui.getCurrentWindowId()
        xbmc.log('Current window %s, currentWindow window %s' % (winId, self.currentWindow))
        if self.currentWindow and self.currentWindow != winId:
            xbmc.log('Forcing window from %s to %s' % (winId, self.currentWindow))
            xbmc.executebuiltin('ReplaceWindow(%s)' % self.currentWindow)

    def onClose(self):
        if xbmcgui.getCurrentWindowId() == self.currentWindow:
            self.currentWindow = 0

    def create(self, cls, *args, **kwargs):
        xbmc.log('Creating window %r' % cls)
        diff = 0.5 - (time.time() - self.last)
        if diff > 0:
            time.sleep(diff)
        self.last = time.time()
        setProperties = kwargs.pop('setProperties', None)
        window = cls.create(*args, **kwargs)
        if setProperties:
            for key, value in list(setProperties.items()):
                window.setProperty(key, value)

        lastWindow = self.showNotModal(window)
        try:
            return window.doModal()
        finally:
            self.closeNotModal(lastWindow)

        del window
        return

    def showNotModal(self, window=None):
        lastWindow = self.currentWindow
        if window is not None:
            self.currentWindow = 0
            window.show()
        self.currentWindow = xbmcgui.getCurrentWindowId()
        if get('Locked') == 'true':
            ForceWindowThread(self)
        return lastWindow

    def closeNotModal(self, lastWindow):
        self.currentWindow = lastWindow

class FtpThread(threading.Thread):

    def __init__(self, server, port):
        super(FtpThread, self).__init__()
        self.daemon = False
        self.server = server
        self.port = str(port)

    def run(self):
        try:
            while (not monitor.abortRequested() and
                   get(FTP_SERVER_PORT_PROPERTY) == self.port):
                self.server.serve_forever(
                    timeout=0.5, blocking=False, handle_exit=False)
        except Exception as e:
            xbmc.log('Failed running FTP server: %r' % e, xbmc.LOGERROR)
        finally:
            self.server.close_all()
            if get(FTP_SERVER_PORT_PROPERTY) == self.port:
                WINDOW_HOME.clearProperty(FTP_SERVER_PORT_PROPERTY)


class MyAuthorizer(DummyAuthorizer):

    def validate_authentication(self, username, password, handler):
        handler.username = 'anonymous'
        DummyAuthorizer.validate_authentication(self, handler.username, password, handler)


class FtpWindow(xbmcgui.WindowXML):
    CANCEL_BUTTON_ID = 301
    BACKGROUND_BUTTON_ID = 302
    server = None
    run_in_background = False

    @classmethod
    def create(cls):
        return cls('ftp.xml', addonPath, 'Main', '1080i')

    def onInit(self):
        try:
            self.setProperty('LocalIP0' , xbmc.getIPAddress())
            self.run_in_background = False

            running_port = get(FTP_SERVER_PORT_PROPERTY)
            if running_port:
                self.setProperty('Port', running_port)
                self.setProperty('Started', 'true')
                return

            authorizer = MyAuthorizer()
            authorizer.add_anonymous(ftppath, perm='elradfmw')
            handler = FTPHandler
            handler.authorizer = authorizer
            ports = [3721, 3722, 3723]
            for port in ports:
                try:
                    self.server = FTPServer(('0.0.0.0', port), handler)
                except Exception as e:
                    xbmc.log('Failed starting FTP on port %s: %r' % (port, e), xbmc.LOGERROR)
                    self.server = None
                else:
                    break

            if self.server is None:
                xbmcNotify(localize(257), localize(39525))
                self.close()
                return
            self.setProperty('Port', str(port))
            self.setProperty('Started', 'true')
            WINDOW_HOME.setProperty(FTP_SERVER_PORT_PROPERTY, str(port))
            FtpThread(self.server, port).start()
        except Exception as e:
            xbmc.log('Failed starting FTP server: %r' % e, xbmc.LOGERROR)
            import traceback
            traceback.print_exc()
            xbmcNotify(localize(257), localize(39526))
            self.close()

        return

    def onClick(self, controlID):
        if controlID == self.CANCEL_BUTTON_ID:
            WINDOW_HOME.clearProperty(FTP_SERVER_PORT_PROPERTY)
            self.close()
        elif controlID == self.BACKGROUND_BUTTON_ID:
            self.run_in_background = True
            xbmcNotify('FTP SERVER', 'FTP-Server läuft im Hintergrund',
                       xbmcgui.NOTIFICATION_INFO)
            self.close()

    def onAction(self, action):
        if action.getId() in (xbmcgui.ACTION_PREVIOUS_MENU, xbmcgui.ACTION_NAV_BACK):
            self.onClick(self.CANCEL_BUTTON_ID)
            return
        ForceWindow().onAction(action)

    def close(self):
        ForceWindow().onClose()
        super(FtpWindow, self).close()

    def doModal(self):
        try:
            return xbmcgui.WindowXML.doModal(self)
        finally:
            if self.server and not self.run_in_background:
                self.server.close_all()

def show():
    xbmc.executebuiltin('Dialog.Close(all,true)')
    ForceWindow().create(FtpWindow)

class Downloader:
	def __init__(self):
		self.progress_dialog = xbmcgui.DialogProgress()
		
	def download(self, url, place=None):
		self.progress_dialog.create("TOOLS", "Starte Download...")
		self.progress_dialog.update(0)
		f = io.BytesIO() if place == None else open(place, 'wb')
		response = requests.get(url, headers={'user-agent': 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36'' (KHTML, like Gecko) Chrome/35.0.1916.153 Safari''/537.36 SE 2.X MetaSr 1.0'}, stream=True)
		total = response.headers.get('content-length')
		if total is None:
			f.write(response.content)
		else:
			downloaded = 0
			total = int(total)
			start_time = time.time()
			mb = 1024*1024
			for chunk in response.iter_content(chunk_size=max(int(total/512), mb)):
				downloaded += len(chunk)
				f.write(chunk)
				done = int(100 * downloaded / total)
				kbps_speed = downloaded / (time.time() - start_time)
				if kbps_speed > 0 and not done >= 100:
					eta = (total - downloaded) / kbps_speed
				else:
					eta = 0
				kbps_speed = kbps_speed / 1024
				type_speed = 'KB'
				if kbps_speed >= 1024:
					kbps_speed = kbps_speed / 1024
					type_speed = 'MB'
				line1 = '[COLOR %s][B]Size:[/B] [COLOR %s]%.02f[/COLOR] MB of [COLOR %s]%.02f[/COLOR] MB[/COLOR]' % ('white', 'limegreen', downloaded / mb, 'limegreen', total / mb)
				line2 = '[COLOR %s][B]Speed:[/B] [COLOR %s]%.02f [/COLOR]%s/s ' % ('white', 'limegreen', kbps_speed, type_speed)
				div = divmod(eta, 60)
				line3 = '[B]ETA:[/B] [COLOR %s]%02d:%02d[/COLOR][/COLOR]' % ('limegreen', div[0], div[1])
				self.progress_dialog.update(done, line1+"\n"+line2+"\n"+line3)
		return f

class Unpacker:
	def __init__(self):
		self.progress_dialog = xbmcgui.DialogProgress()

	@staticmethod
	def _destination(output_path, member):
		name = member.filename.replace('\\', '/')
		normalized = os.path.normpath(name)
		output_root = os.path.abspath(output_path)
		destination = os.path.abspath(os.path.join(output_root, normalized))
		mode = (member.external_attr >> 16) & 0o170000
		if (
			name.startswith('/')
			or normalized == '..'
			or normalized.startswith('..' + os.sep)
			or os.path.commonpath((output_root, destination)) != output_root
			or mode == 0o120000
		):
			raise ValueError('Ungültiger Pfad im Build: %s' % member.filename)
		return destination

	@staticmethod
	def _extract_atomic(archive, member, destination):
		if member.is_dir():
			os.makedirs(destination, exist_ok=True)
			return
		parent = os.path.dirname(destination)
		os.makedirs(parent, exist_ok=True)
		descriptor, temporary_path = tempfile.mkstemp(
			prefix='.plugin.video.tools-',
			dir=parent,
		)
		try:
			with os.fdopen(descriptor, 'wb') as target, archive.open(member, 'r') as source:
				shutil.copyfileobj(source, target, 1024 * 1024)
			os.replace(temporary_path, destination)
		finally:
			if os.path.exists(temporary_path):
				os.remove(temporary_path)

	def unpack(self, _in, _out):
		self.progress_dialog.create("TOOLS", "Entpacken läuft...")
		self.progress_dialog.update(0)
		count = 0
		size = 0
		try:
			with zipfile.ZipFile(_in, 'r') as zin:
				items = zin.infolist()
				if not items:
					raise ValueError('Das Build-Archiv ist leer.')
				destinations = [self._destination(_out, item) for item in items]
				nFiles = float(len(items))
				zipsize = convert_size(sum(item.file_size for item in items))
				for item, destination in zip(items, destinations):
					count += 1
					prog = int(count / nFiles * 100)
					size += item.file_size
					line1 = '[COLOR {0}][B]File:[/B][/COLOR] [COLOR {1}]{2}/{3}[/COLOR] '.format('white','limegreen',count,int(nFiles))
					line2 = '[COLOR {0}][B]Size:[/B][/COLOR] [COLOR {1}]{2}/{3}[/COLOR]'.format('white','limegreen',convert_size(size),zipsize)
					line3 = '[COLOR {0}]{1}[/COLOR]'.format('limegreen', str(item.filename).split('/')[-1])
					self._extract_atomic(zin, item, destination)
					self.progress_dialog.update(prog, line1+"\n"+line2+"\n"+line3)
			return True
		finally:
			self.progress_dialog.close()

def xml_data_advSettings_New(size):
	xml_data="""<advancedsettings>
	  <cache>
		<memorysize>%s</memorysize> 
		<buffermode>1</buffermode>
		<readfactor>4.0</readfactor>
	  </cache>
	  <epg>
		<displayupdatepopup>false</displayupdatepopup>
	</epg>
</advancedsettings>""" % size
	return xml_data

def advancedSettings():
	XML_FILE   =  translatePath(os.path.join('special://home/userdata' , 'advancedsettings.xml'))
	FREEMEM	=  xbmc.getInfoLabel("System.FreeMemory")
	BUFFER_F   =  re.sub('[^0-9]','',FREEMEM)
	BUFFER_F   = int(BUFFER_F) / 3 *0.9
	BUFFERSIZE = BUFFER_F * 1024 * 1024
	choice = dialog.yesno('Tool','Buffer Fix:\nOptimaler Buffer bei deinem System:	   ' + str(BUFFERSIZE) + ' Byte   /   ' + str(BUFFER_F) + ' MB\nWie wilst du optimieren?', yeslabel='Automatisch',nolabel='Selbst eingeben')
	if choice == 1: 
		with open(XML_FILE, "w") as f:
			xml_data = xml_data_advSettings_New(str(BUFFERSIZE))
			f.write(xml_data)
			dialog.ok('Kodi','Buffer wurde auf ' + str(int(BUFFER_F)) + ' MB eingestellt.\nKodi wird beendet, damit Die Einstellung wirksam wird. Bitte neu starten.')
	elif choice == 0:
		BUFFERSIZE = _get_keyboard( default=str(BUFFERSIZE), heading="Buffer In Bytes eingeben")
		with open(XML_FILE, "w") as f:
			xml_data = xml_data_advSettings_New(str(BUFFERSIZE))
			f.write(xml_data)
			dialog.ok('Tools','Buffer wurde manuell eingestellt.\nKodi wird beendet, damit Die Einstellung wirksam wird. Bitte neu starten.')
	os._exit(1)

def _get_keyboard( default="", heading="", hidden=False ):
	""" shows a keyboard and returns a value """
	keyboard = xbmc.Keyboard( default, heading, hidden )
	keyboard.doModal()
	if ( keyboard.isConfirmed() ):
		return str( keyboard.getText())
	return default
	
def get_packages():
	xbmc.executebuiltin('InstallAddon(pvr.iptvsimple)')
	xbmc.executebuiltin('SendClick(11)')
	build = xbmcaddon.Addon().getSetting('build')
	xbmcplugin.setSetting(int(sys.argv[1]), "newinstalled", "true")
	data = Downloader().download(build)
	home = translatePath('special://home')
	if Unpacker().unpack(data, home) == True:
		xbmc.executebuiltin('UpdateLocalAddons')
		time.sleep(1)
		addonlist=["pvr.iptvsimple", "inputstream.adaptive", "inputstream.ffmpegdirect", "inputstream.rtmp"]
		home_path = os.path.join(home,'addons')
		for dirname in os.listdir(home_path):
			if os.path.isdir(os.path.join(home_path,dirname)):
				if not 'packages' in str(dirname):
					if not 'temp' in str(dirname):
						addonlist.append(dirname)
		for addon in addonlist:
			xbmc.executeJSONRPC('{{"jsonrpc":"2.0","id":1,"method":"Addons.SetAddonEnabled","params":{{"addonid":"{}","enabled":true}}}}'.format(addon))
		#open(translatePath('special://home/update'), 'w')
		return True
	return False
		
