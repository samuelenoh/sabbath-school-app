"""Integration tests run against a real HTTP server and isolated SQLite database."""
import hashlib, hmac, json, os, sys, tempfile, threading, unittest, secrets
from pathlib import Path
from http.cookiejar import CookieJar
from urllib.request import build_opener, HTTPCookieProcessor, Request
from urllib.error import HTTPError
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server

TEST_PASSWORD=secrets.token_urlsafe(24)

class Client:
    def __init__(self,url):
        self.url=url;self.csrf='';self.opener=build_opener(HTTPCookieProcessor(CookieJar()))
    def call(self,path,method='GET',data=None,csrf=True,headers=None):
        h={'Content-Type':'application/json'}
        if csrf: h['X-CSRF-Token']=self.csrf
        h.update(headers or {})
        req=Request(self.url+path,data=json.dumps(data).encode() if data is not None else None,method=method,headers=h)
        try: r=self.opener.open(req)
        except HTTPError as e:r=e
        with r:
            raw=r.read();ct=r.headers.get('Content-Type','')
            return r.status,json.loads(raw) if 'application/json' in ct else raw
    def login(self,email='admin@ssms.local',password=TEST_PASSWORD):
        status,d=self.call('/api/login','POST',{'email':email,'password':password});assert status==200,(status,d)
        self.csrf=d['csrf'];return d

class SystemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();server.DB=str(Path(cls.temp.name)/'test.sqlite3')
        os.environ['WHATSAPP_MODE']='dry_run';os.environ['SSMS_DEMO_PASSWORD']=TEST_PASSWORD;os.environ['SSMS_ENV']='development';server.initialize(True)
        cls.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True);cls.thread.start()
        cls.url=f'http://127.0.0.1:{cls.http.server_port}'
    @classmethod
    def tearDownClass(cls):cls.http.shutdown();cls.http.server_close();cls.thread.join();cls.temp.cleanup()
    def setUp(self):self.admin=Client(self.url);self.admin.login()
    def state(self,client=None):
        status,s=(client or self.admin).call('/api/state');self.assertEqual(status,200);return s
    def create(self,module,data):
        status,d=self.admin.call('/api/'+module,'POST',data);self.assertEqual(status,201,d);return d['id']
    def member(self,name='Test Member',cid=1,opt=False):
        return self.create('members',{'name':name,'class_id':cid,'phone':'+233201234567' if opt else '', 'email':'', 'status':'Active','whatsapp_opt_in':opt,'joined_on':'2026-10-01','birthday':'2000-10-10','notes':''})
    def test_01_auth_csrf_and_invalid_login(self):
        anon=Client(self.url);self.assertEqual(anon.call('/api/state')[0],401)
        self.assertEqual(anon.call('/api/login','POST',{'email':'admin@ssms.local','password':'wrong'})[0],401)
        self.assertEqual(self.admin.call('/api/members','POST',{},csrf=False)[0],403)
        self.assertNotIn('password',self.state()['users'][0])
    def test_02_teacher_scope_and_cross_class_attack(self):
        t=Client(self.url);t.login('teacher@ssms.local');s=self.state(t)
        self.assertEqual([r['id'] for r in s['classes']],[1]);self.assertEqual(len(s['members']),5);self.assertEqual(s['offerings'],[])
        d={'class_id':2,'day':'2026-10-10','entries':[{'member_id':8,'status':'Present'}]}
        self.assertEqual(t.call('/api/attendance','POST',d)[0],403)
        d['class_id']=1;self.assertEqual(t.call('/api/attendance','POST',d)[0],400)
        d['entries']=[{'member_id':3,'status':'Present','study':True}]
        self.assertEqual(t.call('/api/attendance','POST',d)[0],200)
        d['entries'][0]['status']='Absent';self.assertEqual(t.call('/api/attendance','POST',d)[0],200)
        rows=[a for a in self.state(t)['attendance'] if a['member_id']==3 and a['day']=='2026-10-10'];self.assertEqual(len(rows),1);self.assertEqual(rows[0]['status'],'Absent')
        self.assertEqual(t.call('/api/members','POST',{'name':'Forbidden'})[0],403)
        t2=Client(self.url);t2.login('teacher2@ssms.local');self.assertEqual([c['id'] for c in self.state(t2)['classes']],[2])
    def test_03_atomic_attendance_date_validation(self):
        mid=self.member('Atomic test')
        d={'class_id':1,'day':'2026-10-10','entries':[{'member_id':mid,'status':'Present'},{'member_id':8,'status':'Present'}]}
        self.assertEqual(self.admin.call('/api/attendance','POST',d)[0],400)
        self.assertFalse(any(a['member_id']==mid for a in self.state()['attendance']))
        d['entries']=d['entries'][:1];d['day']='2026-10-09';self.assertEqual(self.admin.call('/api/attendance','POST',d)[0],400)
        d['day']='2099-10-10';self.assertEqual(self.admin.call('/api/attendance','POST',d)[0],400)
    def test_04_member_crud_conflict_and_history(self):
        mid=self.member('CRUD member');m=next(r for r in self.state()['members'] if r['id']==mid)
        m['name']='Renamed member';self.assertEqual(self.admin.call('/api/members/'+str(mid),'PUT',m)[0],200)
        self.assertEqual(self.admin.call('/api/members/'+str(mid),'PUT',m)[0],409)
        self.assertEqual(self.admin.call('/api/members/'+str(mid),'DELETE')[0],200)
        self.assertEqual(self.admin.call('/api/members/3','DELETE')[0],400)
        self.assertEqual(self.admin.call('/api/classes/1','DELETE')[0],400)
    def test_05_finance_roles_precision_and_unique_receipt(self):
        t=Client(self.url);t.login('treasurer@ssms.local')
        data={'day':'2026-10-10','class_id':1,'amount_minor':12345,'currency':'GHS','category':'Mission','receipt':'TEST-001','notes':'Quarterly gift'}
        status,r=t.call('/api/offerings','POST',data);self.assertEqual(status,201,r)
        self.assertEqual(t.call('/api/offerings','POST',data)[0],400)
        data['amount_minor']=1.1;data['receipt']='TEST-002';self.assertEqual(t.call('/api/offerings','POST',data)[0],400)
        self.assertEqual(t.call('/api/offerings/'+str(r['id']),'DELETE')[0],403)
        teacher=Client(self.url);teacher.login('teacher@ssms.local');self.assertEqual(teacher.call('/api/reports.csv?kind=offerings')[0],403)
        status,csv=t.call('/api/reports.csv?kind=offerings');self.assertEqual(status,200);self.assertIn(b'123.45',csv)
    def test_06_lessons_outreach_and_teacher_ownership(self):
        t=Client(self.url);t.login('teacher@ssms.local')
        lesson={'title':'Test lesson','quarter':'2026 Q4','week':3,'day':'2026-10-17','class_id':1,'scripture':'John 15','summary':'Abide','resource_url':'https://example.org/lesson'}
        self.assertEqual(t.call('/api/lessons','POST',lesson)[0],201)
        lesson['class_id']=2;self.assertEqual(t.call('/api/lessons','POST',lesson)[0],403)
        lesson['class_id']=1;lesson['resource_url']='javascript:alert(1)';self.assertEqual(t.call('/api/lessons','POST',lesson)[0],400)
        outreach={'title':'Care visits','day':'2026-10-10','class_id':1,'owner_id':2,'status':'Completed','people_reached':7,'notes':'With consent'}
        self.assertEqual(t.call('/api/outreach','POST',outreach)[0],201)
        outreach['class_id']=2;self.assertEqual(t.call('/api/outreach','POST',outreach)[0],403)
    def test_07_event_capacity_registration_and_cancel(self):
        event=self.create('events',{'title':'One space','day':'2026-10-17','time':'12:30','capacity':1,'location':'Hall','description':'Test'})
        path=f'/api/events/{event}/register'
        self.assertEqual(self.admin.call(path,'POST',{'member_id':3})[0],200)
        self.assertEqual(self.admin.call(path,'POST',{'member_id':3})[0],200)
        self.assertEqual(self.admin.call(path,'POST',{'member_id':4})[0],400)
        self.assertEqual(self.admin.call(path,'POST',{'member_id':3,'cancel':True})[0],200)
        self.assertEqual(self.admin.call(path,'POST',{'member_id':4})[0],200)
        self.assertEqual(self.admin.call('/api/members/4','DELETE')[0],400)
    def test_08_queue_dedupe_dry_run_and_consent_revocation(self):
        mid=self.member('Consenting member',opt=True)
        d={'template':'sabbath_reminder','language':'en','parameters':['{name}'],'member_ids':[mid,3],'request_id':'test-dedupe'}
        status,r=self.admin.call('/api/notifications/queue','POST',d);self.assertEqual(status,200);self.assertEqual((r['queued'],r['skipped']),(1,1))
        self.assertEqual(self.admin.call('/api/notifications/queue','POST',d)[1]['queued'],0)
        processed=self.admin.call('/api/notifications/process','POST',{})[1];self.assertTrue(any(r['status']=='dry_run' for r in processed['results']))
        d['request_id']='revoke-test';self.admin.call('/api/notifications/queue','POST',d)
        m=next(r for r in self.state()['members'] if r['id']==mid);m['whatsapp_opt_in']=False;self.assertEqual(self.admin.call('/api/members/'+str(mid),'PUT',m)[0],200)
        self.admin.call('/api/notifications/process','POST',{})
        self.assertTrue(any(m['status']=='cancelled' for m in self.state()['messages'] if m['member_id']==mid))
    def test_09_rules_idempotent_and_worker(self):
        mid=self.member('Birthday member',opt=True)
        d={'name':'Birthday greetings','trigger':'birthday','template':'birthday_wish','language':'en','parameters':['{name}','{date}']}
        self.assertEqual(self.admin.call('/api/notifications/rules','POST',d)[0],201)
        self.assertGreater(self.admin.call('/api/notifications/run-rules','POST',{'day':'2026-10-10'})[1]['queued'],0)
        self.assertEqual(self.admin.call('/api/notifications/run-rules','POST',{'day':'2026-10-10'})[1]['queued'],0)
        self.assertTrue(server.process_queue())
    def test_10_webhook_signature_and_monotonic_status(self):
        os.environ['META_APP_SECRET']='test-secret';os.environ['META_VERIFY_TOKEN']='test-verify'
        self.assertEqual(self.admin.call('/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=test-verify&hub.challenge=123')[1],b'123')
        self.assertEqual(self.admin.call('/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=bad')[0],403)
        with server.connect() as c:
            mid=c.execute('SELECT id FROM messages LIMIT 1').fetchone()['id'];c.execute("UPDATE messages SET provider_id='wamid.test',status='accepted' WHERE id=?",(mid,))
        def payload(status):return {'entry':[{'changes':[{'value':{'statuses':[{'id':'wamid.test','status':status}]}}]}]}
        self.assertEqual(self.admin.call('/webhooks/whatsapp','POST',payload('read'))[0],403)
        for status in ('read','sent','delivered','read'):
            d=payload(status);sig='sha256='+hmac.new(b'test-secret',json.dumps(d).encode(),hashlib.sha256).hexdigest()
            self.assertEqual(self.admin.call('/webhooks/whatsapp','POST',d,headers={'X-Hub-Signature-256':sig})[0],200)
        with server.connect() as c:self.assertEqual(c.execute('SELECT status FROM messages WHERE id=?',(mid,)).fetchone()['status'],'read')
    def test_11_user_management_disable_and_password(self):
        status,r=self.admin.call('/api/users','POST',{'name':'Temporary viewer','email':'temporary@example.org','role':'viewer','password':'TemporaryPassword!'});self.assertEqual(status,201)
        v=Client(self.url);v.login('temporary@example.org','TemporaryPassword!');self.assertEqual(v.call('/api/users','POST',{})[0],403)
        self.assertEqual(self.admin.call(f'/api/users/{r["id"]}','PUT',{'active':False,'role':'viewer'})[0],200)
        self.assertEqual(v.call('/api/state')[0],401)
        self.assertEqual(self.admin.call('/api/users/1','PUT',{'role':'viewer'})[0],400)
        self.assertEqual(self.admin.call('/api/users/2','PUT',{'active':False})[0],400)
        self.admin.call(f'/api/users/{r["id"]}','PUT',{'active':True,'role':'viewer'})
        v.login('temporary@example.org','TemporaryPassword!');self.assertEqual(v.call('/api/password','POST',{'current':'TemporaryPassword!','password':'NewPassword!2026'})[0],200)
        self.assertEqual(v.call('/api/state')[0],401);v.login('temporary@example.org','NewPassword!2026')
    def test_12_csv_injection_audit_and_static_security(self):
        mid=self.member('=SUM(1,2)')
        self.admin.call('/api/attendance','POST',{'class_id':1,'day':'2026-10-10','entries':[{'member_id':mid,'status':'Present'}]})
        status,raw=self.admin.call('/api/reports.csv');self.assertEqual(status,200);self.assertIn(b"'=SUM",raw)
        self.assertTrue(self.state()['audit'])
        self.assertEqual(self.admin.call('/server.py')[0],404)
        self.assertEqual(self.admin.call('/data/ssms.sqlite3')[0],404)
        self.assertEqual(self.admin.call('/api/reports.csv?start=2026-10-10&end=2026-01-01')[0],400)
    def test_13_persistence_restart(self):
        count=len(self.state()['members']);server.initialize(True);self.assertEqual(len(self.state()['members']),count)
        with server.connect() as c:self.assertFalse(any(TEST_PASSWORD in r['password'] for r in c.execute('SELECT password FROM users')))
    def test_14_notification_review_and_cancel(self):
        mid=self.member('Review recipient',opt=True)
        self.admin.call('/api/notifications/queue','POST',{'template':'review_template','language':'en','parameters':[],'member_ids':[mid],'request_id':'review'})
        msg=next(m for m in self.state()['messages'] if m['member_id']==mid);path=f'/api/notifications/messages/{msg["id"]}'
        with server.connect() as c:c.execute("UPDATE messages SET status='uncertain' WHERE id=?",(msg['id'],))
        self.assertEqual(self.admin.call(path,'POST',{'action':'retry'})[0],400)
        self.assertEqual(self.admin.call(path,'POST',{'action':'retry','reconciled':True})[0],200)
        self.assertEqual(self.admin.call(path,'POST',{'action':'cancel'})[0],200)
        self.assertEqual(self.admin.call(path,'POST',{'action':'retry'})[0],400)
    def test_15_live_adapter_mocked_and_timeout_hold(self):
        mid=self.member('Mock provider recipient',opt=True)
        for reqid in ('mock-success','mock-timeout'):
            self.admin.call('/api/notifications/queue','POST',{'template':'test_template','language':'en','parameters':['Test'],'member_ids':[mid],'request_id':reqid})
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self):return b'{"messages":[{"id":"wamid.mock-success"}]}'
        with patch.dict(os.environ,{'WHATSAPP_MODE':'live','META_ACCESS_TOKEN':'mock-token','META_PHONE_NUMBER_ID':'123456','META_GRAPH_VERSION':'v99.0'}):
            with patch('server.urlopen',return_value=Response()) as send:
                self.assertEqual(server.process_queue(1)[0]['status'],'accepted')
                req=send.call_args.args[0];self.assertEqual(json.loads(req.data)['to'],'233201234567');self.assertIn('template',json.loads(req.data))
            with patch('server.urlopen',side_effect=TimeoutError):self.assertEqual(server.process_queue(1)[0]['status'],'uncertain')
        self.assertTrue(any(m['status']=='uncertain' for m in self.state()['messages'] if m['member_id']==mid))
    def test_16_viewer_cannot_mutate_or_read_finances(self):
        v=Client(self.url);v.login('viewer@ssms.local')
        self.assertEqual(self.state(v)['offerings'],[])
        self.assertEqual(v.call('/api/attendance','POST',{'class_id':1,'day':'2026-10-10','entries':[{'member_id':3,'status':'Present'}]})[0],403)
        self.assertEqual(v.call('/api/reports.csv?kind=offerings')[0],403)
        self.assertEqual(v.call('/api/notifications/process','POST',{})[0],403)

if __name__=='__main__':unittest.main(verbosity=2)
