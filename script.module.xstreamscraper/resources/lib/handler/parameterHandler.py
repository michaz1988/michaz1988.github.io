# -*- coding: utf-8 -*-
# Python 3

import sys
from resources.lib import settings
from six.moves.urllib.parse import parse_qsl, urlsplit, unquote_plus, urlencode


class ParameterHandler:
	def __init__(self):
		if settings.collectMode:
			self.__params = {}
		else:
			self.__params = settings.urlparams

	def getAllParameters(self):
		# returns all parameters as dictionary
		return self.__params

	def getValue(self, paramName):
		# returns value of one parameter as string, if parameter does not exists "False" is returned
		if self.exist(paramName):
			return self.__params[paramName]
			# paramValue = self.__params[paramName]
			# return unquote_plus(paramValue)
		return False

	def exist(self, paramName):
		# checks if paramter with the name "paramName" exists
		return paramName in self.__params

	def setParam(self, paramName, paramValue):
		# set the value of the parameter with the name "paramName" to "paramValue"
		# if there is no such parameter, the parameter is created
		# if no value is given "paramValue" is set "None"
		paramValue = str(paramValue)
		self.__params.update({paramName: paramValue})

	def addParams(self, paramDict):
		# adds a whole dictionary {key1:value1,...,keyN:valueN} of parameters to the ParameterHandler
		# existing parameters are updated
		for key, value in paramDict.items():
			self.__params.update({key: str(value)})

	def getParameterAsUri(self):
		outParams = dict()
		if 'params' in self.__params:
			del self.__params['params']
		if 'function' in self.__params:
			del self.__params['function']
		if 'title' in self.__params:
			del self.__params['title']
		if 'site' in self.__params:
			del self.__params['site']

		if len(self.__params) > 0:
			for param in self.__params:
				if len(self.__params[param]) < 1:
					continue
				outParams[param] = unquote_plus(self.__params[param])
			return urlencode(outParams)
		return 'params=0'
