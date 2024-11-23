import xbmc
from resources.lib import tools

if __name__ == '__main__':
	monitor = xbmc.Monitor()
	
	while not monitor.abortRequested():
		if monitor.waitForAbort(10):
			break
		tools.repair()