"""Run Waitress behind an HTTPS reverse proxy on one persistent host."""
import os
from waitress import serve
from wsgi import create_application

if __name__=='__main__':
    application=create_application()
    proxy=os.environ.get('SSMS_TRUSTED_PROXY','127.0.0.1')
    if proxy=='*': raise RuntimeError('Set an exact trusted reverse-proxy address; wildcard trust is prohibited.')
    serve(application,host=os.environ.get('SSMS_HOST','127.0.0.1'),port=int(os.environ.get('PORT','8000')),
          threads=4,max_request_body_size=1000000,channel_timeout=30,
          trusted_proxy=proxy,trusted_proxy_headers={'x-forwarded-for','x-forwarded-proto'},clear_untrusted_proxy_headers=True)
