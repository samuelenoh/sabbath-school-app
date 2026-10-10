"""Production configuration and WSGI security regression tests; isolated databases."""
import io, json, os, secrets, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server
from wsgi import create_application

class ProductionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.password=' '+secrets.token_urlsafe(24)+' '
        self.db=str(Path(self.temp.name)/'production.sqlite3')
        self.env=patch.dict(os.environ,{'SSMS_ENV':'production','SSMS_DB':self.db,
            'SSMS_ORIGIN':'https://church.example','SSMS_SECURE_COOKIES':'1',
            'SSMS_ADMIN_EMAIL':'admin@church.example','SSMS_ADMIN_PASSWORD':self.password,
            'WHATSAPP_MODE':'dry_run'})
        self.env.start();self.addCleanup(self.env.stop)
        self.dbpatch=patch.object(server,'DB',self.db);self.dbpatch.start();self.addCleanup(self.dbpatch.stop)
        self.app=create_application()
    def call(self,path='/',method='GET',data=None,headers=None,length=None,ip='127.0.0.1'):
        raw=json.dumps(data).encode() if data is not None else b''
        env={'REQUEST_METHOD':method,'PATH_INFO':path,'HTTP_HOST':'church.example',
             'HTTP_ORIGIN':'https://church.example','CONTENT_TYPE':'application/json',
             'CONTENT_LENGTH':str(len(raw) if length is None else length),
             'REMOTE_ADDR':ip,'wsgi.input':io.BytesIO(raw),'wsgi.url_scheme':'https'}
        env.update(headers or {});response={}
        def start(status,h):response.update(status=int(status.split()[0]),headers=dict(h))
        body=b''.join(self.app(env,start));response['body']=body
        if body and response['headers'].get('Content-Type','').startswith('application/json'):response['json']=json.loads(body)
        return response
    def login(self,password=None):
        return self.call('/api/login','POST',{'email':'admin@church.example','password':self.password if password is None else password})
    def test_https_cookie_origin_and_password_whitespace(self):
        r=self.login();self.assertEqual(r['status'],200)
        self.assertIn('Secure',r['headers']['Set-Cookie']);self.assertIn('HttpOnly',r['headers']['Set-Cookie'])
        self.assertIn('Strict-Transport-Security',r['headers'])
        h={'HTTP_COOKIE':r['headers']['Set-Cookie'].split(';')[0],'HTTP_X_CSRF_TOKEN':r['json']['csrf']}
        self.assertEqual(self.call('/api/state',headers=h)['status'],200)
        h['HTTP_ORIGIN']='https://attacker.example'
        self.assertEqual(self.call('/api/logout','POST',{},h)['status'],403)
        self.assertEqual(self.login(self.password.strip())['status'],401)
    def test_host_head_methods_and_request_limits(self):
        self.assertEqual(self.call('/healthz')['json'],{'status':'ok'})
        self.assertEqual(self.call(headers={'HTTP_HOST':'evil.example'})['status'],421)
        self.assertEqual(self.call(method='HEAD')['body'],b'')
        self.assertEqual(self.call(method='PATCH')['status'],405)
        for length in (-1,1000001,999):
            self.assertEqual(self.call('/api/login','POST',{'email':'a','password':'b'},length=length)['status'],400)
        self.assertEqual(self.call('/server.py')['status'],404)
    def test_login_throttle_across_ips(self):
        for i in range(8):
            self.assertEqual(self.call('/api/login','POST',{'email':'admin@church.example','password':'incorrect'},ip=f'192.0.2.{i}')['status'],401)
        self.assertEqual(self.login()['status'],429)
    def test_configuration_fail_closed(self):
        for key,value in [('SSMS_ORIGIN','http://church.example'),('SSMS_SECURE_COOKIES','0'),('SSMS_ENV','typo'),('WHATSAPP_MODE','typo'),('WHATSAPP_MODE','live')]:
            with patch.dict(os.environ,{key:value}):
                with self.assertRaises(RuntimeError):server.validate_configuration(hosted=True)
        with self.assertRaises(RuntimeError):server.initialize(True)
        with server.connect() as c:c.execute("UPDATE settings SET value='1' WHERE name='demo_database'")
        with self.assertRaises(RuntimeError):server.initialize(False)
    def test_boolean_consent_and_early_delivery_event(self):
        with self.assertRaises(ValueError):server.bool_field({'whatsapp_opt_in':'false'},'whatsapp_opt_in')
        self.assertFalse(server.bool_field({'whatsapp_opt_in':False},'whatsapp_opt_in'))
        with server.connect() as c:
            c.execute("INSERT INTO delivery_events VALUES('wamid.early','read',?)",(server.now(),))
            c.execute("INSERT INTO messages(template,language,parameters,dedupe,status,provider_id) VALUES('t','en','[]','test','accepted','wamid.early')")
            server.apply_delivery_events(c,'wamid.early')
            self.assertEqual(c.execute('SELECT status FROM messages').fetchone()['status'],'read')
            server.apply_delivery_events(c,'wamid.early')
            self.assertEqual(c.execute('SELECT status FROM messages').fetchone()['status'],'read')

if __name__=='__main__':unittest.main()
