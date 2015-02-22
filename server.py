import url_parse
import httplib
import BaseHTTPServer


def render(result):
	pass

class PlatterDAV(BaseHTTPServer.BaseHTTPRequestHandler):
	
	do_GET(self):
		try:
			result = url_parse.parse(self.path)
			self.send_response(httplib.OK, render(result)
		except (IOError, url_parse.NotFoundException):
			self.send_error(httplib.NOT_FOUND)
			