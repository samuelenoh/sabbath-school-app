"""Production WSGI bridge; reuses the same authorization and transaction code."""
import io
import json
import os
import threading
from email.message import Message
from http import HTTPStatus
from urllib.parse import urlparse
import server

class WSGIHandler(server.Handler):
    def __init__(self,environ):
        self.command=environ.get('REQUEST_METHOD','GET').upper()
        self.path=environ.get('PATH_INFO','/')
        if environ.get('QUERY_STRING'): self.path+='?'+environ['QUERY_STRING']
        self.client_address=(environ.get('REMOTE_ADDR','unknown'),0)
        self.headers=Message()
        for key,value in environ.items():
            if key.startswith('HTTP_'): self.headers[key[5:].replace('_','-')]=str(value)
        self.headers['Content-Length']=environ.get('CONTENT_LENGTH') or '0'
        if environ.get('CONTENT_TYPE'): self.headers['Content-Type']=environ['CONTENT_TYPE']
        self.rfile=environ['wsgi.input']
        self.wfile=io.BytesIO();self.response_headers=[];self.status=500
    def send_response(self,status,message=None): self.status=status
    def send_header(self,name,value): self.response_headers.append((name,str(value)))
    def end_headers(self): pass

def create_application():
    server.validate_configuration(hosted=True)
    server.initialize(False)
    expected_host=urlparse(server.configured_origin()).netloc.lower()
    def app(environ,start_response):
        h=WSGIHandler(environ)
        host=environ.get('HTTP_HOST',environ.get('SERVER_NAME','')).lower()
        if host!=expected_host:
            h.send(421,{'error':'Host is not configured for this application.'})
        elif h.command not in ('GET','POST','PUT','DELETE','HEAD'):
            h.send(405,{'error':'Method not allowed.'},headers={'Allow':'GET, HEAD, POST, PUT, DELETE'})
        else:
            h.handle_request('GET' if h.command=='HEAD' else h.command)
        reason=HTTPStatus(h.status).phrase
        start_response(f'{h.status} {reason}',h.response_headers)
        return [b'' if h.command=='HEAD' else h.wfile.getvalue()]
    return app

_app=None
_lock=threading.Lock()
def application(environ,start_response):
    """Lazy compatibility entrypoint. Prefer create_application for fail-fast startup."""
    global _app
    if _app is None:
        with _lock:
            if _app is None: _app=create_application()
    return _app(environ,start_response)
