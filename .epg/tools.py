import os, shutil, gzip

addon_name = "Takealug EPG Grabber"
addon_version = "1.1.5+matrix"

datapath = os.path.abspath(os.path.dirname(__file__))
temppath = os.path.join(datapath, "temp")

def loc(id):
	po_file = os.path.join(datapath, "strings.po")
	file =  open(po_file, 'r').read().splitlines()
	for number, line in enumerate(file):
		if 'msgctxt "#{}"'.format(str(id)) in line:
			return file[number+2].split('"')[1]

def notify(title, message, *arg):
	with open(os.path.join(datapath, 'log.txt'), 'a') as k:
		k.write("%s : %s\n" % (title, message))
	print(title, message)

## Make a debug logger
def log(message):
	with open(os.path.join(datapath, 'log.txt'), 'a') as k:
		k.write('[{} {}] {}'.format(addon_name, addon_version, message)+"\n")

def copy(source, destination):
	try:
		shutil.copy(source, destination)
		return True
	except:
		return False
		
def comp(source, destination):
	try:
		with open(source, 'rb') as f_in, gzip.open(destination, 'wb') as f_out:
			f_out.writelines(f_in)
			return True
	except:
		return False

def isfile(file):
	return os.path.isfile(file)

def exists(fileorfolder):
	return os.path.exists(fileorfolder)

def makedir(dir):
	if not os.path.exists(dir):
		os.makedirs(dir)

def delete(fileorfolder, onlyfiles=False):
	if exists(fileorfolder):
		if isfile(fileorfolder):
			os.remove(fileorfolder)
		elif onlyfiles:
			for root, dirs, files in os.walk(fileorfolder):
				for name in files:
					os.remove(os.path.join(root, name))
		else:
			shutil.rmtree(fileorfolder, ignore_errors=True)