from wsgidav import util
import url_parse
from url_parse import Directory, ReadOnly, NotFoundException
from writable import Writeable, WriteableDirectory
from wsgidav.dav_error import DAVError, HTTP_FORBIDDEN
from wsgidav.dav_provider import DAVProvider, DAVCollection, DAVNonCollection
import os, os.path
from os.path import join as j
import datetime
import time

slims_repo_base = "/tmp"

buffer_size = 16384

class PlatterProvider(DAVProvider):
	
	def getResourceInst(self, path, environ):
		try:
			result = url_parse.parse(path)
			if isinstance(result, Directory):
				return PlatterFolderResource(path, environ, result)
			if isinstance(result, ReadOnly):
				return PlatterFileResource(path, environ, result)
		except NotFoundException:
			return None
	
class PlatterAbstract():
	"Abstract mix-in for DAVResources with no metadata"
	
	def noValue(self):
		return None
	
	getCreationDate = datetime.datetime.today()
	getDirectoryInfo = noValue
	getEtag = noValue
	getLastModified = noValue
	supportRecursiveMove = lambda s, d: False
	
class PlatterFileResource(DAVNonCollection):
	
	def __init__(self, path, environ, file_endpoint):
		super(PlatterFileResource, self).__init__(path, environ)
		self.file = file_endpoint
		self.path = j(slims_repo_base, self.file.path)
		
	def getContentType(self):
		return util.guessMimeType(self.path)
		
	def getDisplayName(self):
		return self.file.name
		
	def getCreationDate(self):
		return time.mktime(self.file.creation_date.timetuple())
		
	def getLastModified(self):
		return time.mktime(self.file.modify_date.timetuple())
		
	def supportEtag(self):
		return True
		
	def getEtag(self):
		return util.getETag(self.path)
		
	def supportRanges(self):
		return True
		
	def getContentLength(self):
		return os.stat(self.path).st_size
		
	def getContent(self):
		return open(self.path, 'rb', buffer_size)
		
	def beginWrite(self, contentType=None):
		if isinstance(self.file, Writable):
			return self.file.writestream()
		raise DAVError(HTTP_FORBIDDEN)	
			
	def delete(self):
		if isinstance(self.file, Writable):
			return self.file.deleteMe()
		raise DAVError(HTTP_FORBIDDEN)
		
	def supportRecursiveMove(self, destPath):
		return False
	
class PlatterFolderResource(DAVCollection, PlatterAbstract):
	
	def __init__(self, path, environ, dir):
		super(PlatterFolderResource, self).__init__(path, environ)
		self.dir = dir
		
	def getMemberNames(self):
		return list(self.dir)
		
	def getMember(self, name):
		return self.provider.getResourceInst(j(self.path, name), self.environ)
		
	def createEmptyResource(self, name):
		if isinstance(self.dir, WriteableDirectory):
			return self.provider.getResourceInst(j(self.path, self.dir.new_file(name).name))
		raise DAVError(HTTP_FORBIDDEN)
		
	def createCollection(self, name):
		raise DAVError(HTTP_FORBIDDEN)
		
	def copyMoveSingle(self, destPath, isMove):
		raise DAVError(HTTP_FORBIDDEN)
		