"""Sabbath School Management System — Python 3.10+, standard library only."""
import argparse, csv, hashlib, hmac, io, json, os, re, secrets, sqlite3, time
from contextlib import contextmanager
from datetime import date, datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).parent
DB = os.environ.get('SSMS_DB', str(ROOT / 'data' / 'ssms.sqlite3'))
ROLES = ('admin', 'secretary', 'teacher', 'treasurer', 'viewer')
MODULES = ('classes', 'members', 'lessons', 'offerings', 'events', 'outreach')
WRITE = {'classes': ('admin','secretary'), 'members': ('admin','secretary'),
         'lessons': ('admin','secretary','teacher'), 'offerings': ('admin','treasurer'),
         'events': ('admin','secretary'), 'outreach': ('admin','secretary','teacher')}

def production():
    return os.environ.get('SSMS_ENV', 'development') == 'production'

def validate_configuration(demo=False, hosted=False):
    if os.environ.get('SSMS_ENV','development') not in ('development','production'): raise RuntimeError('SSMS_ENV must be development or production.')
    mode=os.environ.get('WHATSAPP_MODE','dry_run')
    if mode not in ('dry_run','live'): raise RuntimeError('WHATSAPP_MODE must be dry_run or live.')
    if mode=='live':
        required=('META_ACCESS_TOKEN','META_PHONE_NUMBER_ID','META_GRAPH_VERSION','META_APP_SECRET','META_VERIFY_TOKEN')
        if not all(os.environ.get(k) for k in required): raise RuntimeError('Live WhatsApp requires all five Meta settings.')
        if not re.fullmatch(r'v\d+\.\d+',os.environ['META_GRAPH_VERSION']) or not os.environ['META_PHONE_NUMBER_ID'].isdigit():
            raise RuntimeError('Invalid Meta Graph version or phone-number ID.')
    if hosted and not production(): raise RuntimeError('The hosted WSGI entrypoint requires SSMS_ENV=production.')
    if production():
        if demo: raise RuntimeError('Demo mode is prohibited in production.')
        if not os.environ.get('SSMS_DB') or not Path(DB).is_absolute(): raise RuntimeError('Production requires an explicit absolute SSMS_DB path on persistent storage.')
        origin=os.environ.get('SSMS_ORIGIN','');parsed=urlparse(origin)
        if parsed.scheme!='https' or not parsed.netloc or parsed.path or parsed.query or parsed.fragment or parsed.username:
            raise RuntimeError('SSMS_ORIGIN must be your exact HTTPS origin without a trailing slash.')
        if os.environ.get('SSMS_SECURE_COOKIES')!='1': raise RuntimeError('Production requires SSMS_SECURE_COOKIES=1.')

@contextmanager
def connect():
    c = sqlite3.connect(DB, timeout=15)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    try:
        with c:
            yield c
    finally:
        c.close()

def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    return salt + ':' + hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 210000).hex()

def password_ok(password, stored):
    return hmac.compare_digest(password_hash(password, stored.split(':')[0]), stored)

DUMMY_PASSWORD_HASH=password_hash(secrets.token_urlsafe(24))

def utc_today():
    return datetime.now(timezone.utc).date()

def now():
    return datetime.now(timezone.utc).isoformat()

def initialize(demo=False):
    validate_configuration(demo)
    Path(DB).parent.mkdir(parents=True, exist_ok=True)
    with connect() as c:
        c.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
          role TEXT NOT NULL, password TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, user_id INTEGER REFERENCES users(id), csrf TEXT, expires REAL);
        CREATE TABLE IF NOT EXISTS records(id INTEGER PRIMARY KEY, module TEXT NOT NULL, data TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1);
        CREATE INDEX IF NOT EXISTS record_module ON records(module);
        CREATE TABLE IF NOT EXISTS attendance(class_id INTEGER REFERENCES records(id), member_id INTEGER REFERENCES records(id),
          day TEXT, status TEXT, study INTEGER, notes TEXT, marked_by INTEGER REFERENCES users(id), updated TEXT,
          PRIMARY KEY(class_id,member_id,day));
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, actor INTEGER, action TEXT, detail TEXT, created TEXT);
        CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY, member_id INTEGER REFERENCES records(id),
          template TEXT, language TEXT, parameters TEXT, dedupe TEXT UNIQUE, status TEXT, attempts INTEGER DEFAULT 0,
          next_attempt REAL DEFAULT 0, provider_id TEXT, error TEXT, created TEXT, updated TEXT);
        CREATE TABLE IF NOT EXISTS rules(id INTEGER PRIMARY KEY, name TEXT, trigger TEXT, template TEXT, language TEXT,
          parameters TEXT, enabled INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS login_attempts(key TEXT PRIMARY KEY, count INTEGER, until REAL);
        CREATE TABLE IF NOT EXISTS settings(name TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS delivery_events(provider_id TEXT, status TEXT, received TEXT,
          PRIMARY KEY(provider_id,status));
        ''')
        demo_flag=c.execute("SELECT value FROM settings WHERE name='demo_database'").fetchone()
        if not demo_flag and c.execute('SELECT id FROM users LIMIT 1').fetchone():
            legacy_demo=c.execute("SELECT id FROM users WHERE email IN ('teacher@ssms.local','teacher2@ssms.local')").fetchone()
            c.execute("INSERT INTO settings VALUES('demo_database',?)",('1' if legacy_demo else '0',))
            demo_flag=c.execute("SELECT value FROM settings WHERE name='demo_database'").fetchone()
        if production() and demo_flag and demo_flag['value']=='1':
            raise RuntimeError('This is a demonstration database. Use a new production database; synthetic accounts must not be deployed.')
        if not c.execute('SELECT id FROM users LIMIT 1').fetchone():
            pwd = os.environ.get('SSMS_DEMO_PASSWORD') if demo else os.environ.get('SSMS_ADMIN_PASSWORD')
            if not pwd and not demo:
                raise RuntimeError('Set SSMS_ADMIN_PASSWORD (12+ characters) for first startup, or use --demo with synthetic data.')
            if not pwd: raise RuntimeError('Set SSMS_DEMO_PASSWORD to a unique local-only password before using --demo.')
            if len(pwd) < 12:
                raise RuntimeError('Administrator password must be at least 12 characters.')
            email=os.environ.get('SSMS_ADMIN_EMAIL','admin@ssms.local').lower()
            if production() and (not os.environ.get('SSMS_ADMIN_EMAIL') or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email)): raise RuntimeError('Set an explicit valid SSMS_ADMIN_EMAIL.')
            c.execute("INSERT INTO settings VALUES('demo_database',?)",('1' if demo else '0',))
            c.execute('INSERT INTO users(name,email,role,password) VALUES(?,?,?,?)',
                      ('Church Administrator', email, 'admin', password_hash(pwd)))
            if demo:
                for name,email,role in [('Grace Mensah','teacher@ssms.local','teacher'),('Daniel Owusu','teacher2@ssms.local','teacher'),
                                        ('Ruth Addo','treasurer@ssms.local','treasurer'),('Esther Boateng','secretary@ssms.local','secretary'),
                                        ('Report Viewer','viewer@ssms.local','viewer')]:
                    c.execute('INSERT INTO users(name,email,role,password) VALUES(?,?,?,?)',(name,email,role,password_hash(pwd)))
                def add(module, data):
                    return c.execute('INSERT INTO records(module,data) VALUES(?,?)',(module,json.dumps(data))).lastrowid
                cls1=add('classes',{'name':'Berean Fellowship','description':'Adult Bible study and fellowship','teacher_id':2,'age_group':'Adults','room':'Main sanctuary','active':True})
                cls2=add('classes',{'name':'Cornerstone Youth','description':'Growing in faith together','teacher_id':3,'age_group':'Youth','room':'Youth hall','active':True})
                for i,name in enumerate(['Ama Asante','Kofi Mensah','Abigail Osei','Samuel Boateng','Elizabeth Addo','Joseph Appiah','Naomi Owusu','David Agyeman']):
                    add('members',{'name':name,'phone':'','email':'','class_id':cls1 if i<5 else cls2,'status':'Active','birthday':'','joined_on':utc_today().isoformat(),'whatsapp_opt_in':False,'consent_at':'','notes':'Synthetic demonstration member'})
                add('lessons',{'title':'Growing together in faith','quarter':'2026 Q4','week':2,'day':'2026-10-10','scripture':'Acts 2:42–47','summary':'Read the passage, reflect on fellowship, and discuss practical ways to care for one another.','resource_url':'https://www.sabbathschoolpersonalministries.org/','class_id':cls1})
                add('events',{'title':'Community Sabbath lunch','day':'2026-10-17','time':'12:30','location':'Fellowship hall','description':'Bring a dish and invite a friend.','capacity':50,'registrations':[]})
                add('outreach',{'title':'Neighborhood care visits','day':'2026-10-18','owner_id':2,'class_id':cls1,'status':'Planned','people_reached':0,'notes':'Coordinate visits with consenting households.'})

def records(c, module):
    return [dict(id=r['id'], version=r['version'], **json.loads(r['data'])) for r in c.execute('SELECT * FROM records WHERE module=? ORDER BY id',(module,))]

def record(c, ident, module):
    r=c.execute('SELECT * FROM records WHERE id=? AND module=?',(ident,module)).fetchone()
    if not r: raise ValueError('Record does not exist.')
    return dict(id=r['id'],version=r['version'],**json.loads(r['data']))

def audit(c, actor, action, detail):
    c.execute('INSERT INTO audit(actor,action,detail,created) VALUES(?,?,?,?)',(actor,action,json.dumps(detail),now()))

def allowed_class(c, user, class_id):
    cls=record(c,class_id,'classes')
    if user['role'] not in ('admin','secretary') and not (user['role']=='teacher' and cls.get('teacher_id')==user['id']):
        raise PermissionError('You can mark attendance only for your assigned classes.')
    if not cls.get('active',True): raise ValueError('This class is inactive.')
    return cls

def iso_day(value):
    try: return date.fromisoformat(value).isoformat()
    except (ValueError,TypeError): raise ValueError('Use a valid date in YYYY-MM-DD format.')

def text_field(data, key, required=False, limit=2000):
    value=data.get(key,'')
    if not isinstance(value,str) or len(value)>limit or (required and not value.strip()):
        raise ValueError(f'{key}: enter valid text (maximum {limit} characters).')
    return value.strip()

def password_field(data,key):
    value=data.get(key,'')
    if not isinstance(value,str) or not value or len(value)>500: raise ValueError('Enter a valid password of at most 500 characters.')
    return value

def bool_field(data,key,default=False):
    value=data.get(key,default)
    if type(value) is not bool: raise ValueError(f'{key}: must be true or false.')
    return value

def positive_id(data, key, required=True):
    v=data.get(key)
    if not required and v in ('',None): return None
    if type(v) is not int or v<1: raise ValueError(f'{key}: choose a valid record.')
    return v

def validate(c, module, data, user, existing=None):
    d={}
    if module=='classes':
        for k in ('name','description','age_group','room'): d[k]=text_field(data,k,k=='name',200 if k!='description' else 2000)
        d['teacher_id']=positive_id(data,'teacher_id')
        if not c.execute("SELECT id FROM users WHERE id=? AND role='teacher' AND active=1",(d['teacher_id'],)).fetchone(): raise ValueError('Assign an active teacher.')
        d['active']=bool_field(data,'active',True)
    elif module=='members':
        for k in ('name','phone','email','notes'): d[k]=text_field(data,k,k=='name')
        if d['phone'] and not re.fullmatch(r'\+[1-9]\d{7,14}',d['phone']): raise ValueError('Phone must use international format, e.g. +233201234567.')
        if d['email'] and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',d['email']): raise ValueError('Enter a valid email address.')
        d['class_id']=positive_id(data,'class_id'); record(c,d['class_id'],'classes')
        d['status']=data.get('status','Active')
        if d['status'] not in ('Active','Inactive','Visitor'): raise ValueError('Invalid member status.')
        d['birthday']=iso_day(data['birthday']) if data.get('birthday') else ''
        d['joined_on']=iso_day(data.get('joined_on') or utc_today().isoformat())
        d['whatsapp_opt_in']=bool_field(data,'whatsapp_opt_in')
        if d['whatsapp_opt_in'] and not d['phone']: raise ValueError('WhatsApp consent requires a phone number.')
        if existing and existing.get('phone')!=d['phone'] and existing.get('whatsapp_opt_in') and d['whatsapp_opt_in']:
            raise ValueError('For a changed phone number, first save with WhatsApp consent unchecked, then record fresh consent for that number.')
        retained_consent=(existing or {}).get('consent_at') if (existing or {}).get('phone')==d['phone'] else ''
        d['consent_at']=(retained_consent or now()) if d['whatsapp_opt_in'] else ''
    elif module=='lessons':
        for k in ('title','quarter','scripture','summary','resource_url'): d[k]=text_field(data,k,k in ('title','quarter'))
        if d['resource_url'] and not re.match(r'^https://[^\s]+$',d['resource_url']): raise ValueError('Resource URL must start with https://.')
        d['week']=data.get('week')
        if type(d['week']) is not int or not 1<=d['week']<=14: raise ValueError('Week must be between 1 and 14.')
        d['day']=iso_day(data.get('day')); d['class_id']=positive_id(data,'class_id')
        if user['role']=='teacher':
            allowed_class(c,user,d['class_id'])
            if existing: allowed_class(c,user,existing['class_id'])
        else: record(c,d['class_id'],'classes')
    elif module=='offerings':
        d['day']=iso_day(data.get('day')); d['class_id']=positive_id(data,'class_id'); record(c,d['class_id'],'classes')
        d['amount_minor']=data.get('amount_minor')
        if type(d['amount_minor']) is not int or not 0<d['amount_minor']<=100000000: raise ValueError('Amount must be positive and at most 1,000,000.')
        d['currency']=text_field(data,'currency',True,3).upper()
        if not re.fullmatch('[A-Z]{3}',d['currency']): raise ValueError('Use a three-letter currency code.')
        d['category']=data.get('category')
        if d['category'] not in ('Sabbath School','Mission','Thirteenth Sabbath','Other'): raise ValueError('Invalid offering category.')
        d['notes']=text_field(data,'notes'); d['receipt']=text_field(data,'receipt',True,100)
        for r in records(c,'offerings'):
            if r['receipt']==d['receipt'] and r['id']!=(existing or {}).get('id'): raise ValueError('Receipt reference already exists.')
    elif module=='events':
        for k in ('title','time','location','description'): d[k]=text_field(data,k,k=='title')
        d['day']=iso_day(data.get('day'))
        if d['time'] and not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',d['time']): raise ValueError('Use HH:MM time.')
        d['capacity']=data.get('capacity',0)
        if type(d['capacity']) is not int or not 0<=d['capacity']<=10000: raise ValueError('Capacity must be 0–10000 (0 means unlimited).')
        d['registrations']=(existing or {}).get('registrations',[])
        if d['capacity'] and len(d['registrations'])>d['capacity']: raise ValueError('Capacity is below current registrations.')
    elif module=='outreach':
        for k in ('title','notes'): d[k]=text_field(data,k,k=='title')
        d['day']=iso_day(data.get('day')); d['class_id']=positive_id(data,'class_id'); record(c,d['class_id'],'classes')
        d['owner_id']=positive_id(data,'owner_id')
        if not c.execute('SELECT id FROM users WHERE id=? AND active=1',(d['owner_id'],)).fetchone(): raise ValueError('Choose an active coordinator.')
        d['status']=data.get('status')
        if d['status'] not in ('Planned','In progress','Completed'): raise ValueError('Invalid outreach status.')
        d['people_reached']=data.get('people_reached',0)
        if type(d['people_reached']) is not int or not 0<=d['people_reached']<=100000: raise ValueError('People reached must be a nonnegative integer.')
        if user['role']=='teacher':
            allowed_class(c,user,d['class_id'])
            if existing: allowed_class(c,user,existing['class_id'])
    return d

def queue_message(c, member, template, language, parameters, dedupe):
    if not member.get('whatsapp_opt_in') or member.get('status')=='Inactive' or not member.get('phone'): return False
    c.execute('INSERT OR IGNORE INTO messages(member_id,template,language,parameters,dedupe,status,created,updated) VALUES(?,?,?,?,?,?,?,?)',
              (member['id'],template,language,json.dumps(parameters),dedupe,'queued',now(),now()))
    return True

def run_rules(c, day):
    queued=0
    for rule in c.execute('SELECT * FROM rules WHERE enabled=1').fetchall():
        for m in records(c,'members'):
            match = rule['trigger']=='weekly' and date.fromisoformat(day).weekday()==4
            match |= rule['trigger']=='birthday' and m.get('birthday','')[5:]==day[5:]
            if rule['trigger']=='absence':
                last=c.execute('SELECT status FROM attendance WHERE member_id=? AND day=?',(m['id'],day)).fetchone()
                match=bool(last and last['status']=='Absent')
            if match:
                params=[p.replace('{name}',m['name']).replace('{date}',day) for p in json.loads(rule['parameters'])]
                before=c.total_changes
                queue_message(c,m,rule['template'],rule['language'],params,f'rule:{rule["id"]}:{day}:{m["id"]}')
                queued+=c.total_changes-before
    return queued

def apply_delivery_events(c, provider_id):
    ranks={'accepted':0,'sent':1,'delivered':2,'read':3}
    r=c.execute('SELECT id,status FROM messages WHERE provider_id=?',(provider_id,)).fetchone()
    if not r: return
    current=r['status']
    events=c.execute('SELECT status FROM delivery_events WHERE provider_id=? ORDER BY received',(provider_id,)).fetchall()
    for event in events:
        target=event['status']
        if (target=='failed' and current not in ('delivered','read')) or ranks.get(target,-1)>ranks.get(current,-1): current=target
    if current!=r['status']: c.execute('UPDATE messages SET status=?,updated=? WHERE id=?',(current,now(),r['id']))

def process_queue(limit=20):
    """Single claimed job, durable result. Ambiguous sends are held for manual reconciliation."""
    results=[]
    with connect() as c:
        cutoff=(datetime.now(timezone.utc)-timedelta(minutes=5)).isoformat()
        c.execute("UPDATE messages SET status='uncertain', error='Worker interrupted; reconcile provider delivery before retry.' WHERE status='sending' AND updated<?",(cutoff,))
        c.execute('DELETE FROM delivery_events WHERE received<?',((datetime.now(timezone.utc)-timedelta(days=30)).isoformat(),))
    for _ in range(limit):
        with connect() as c:
            c.execute('BEGIN IMMEDIATE')
            msg=c.execute("SELECT * FROM messages WHERE status='queued' AND next_attempt<=? ORDER BY id LIMIT 1",(time.time(),)).fetchone()
            if not msg: break
            m=record(c,msg['member_id'],'members')
            if not m.get('whatsapp_opt_in') or m.get('status')=='Inactive' or not m.get('phone'):
                c.execute("UPDATE messages SET status='cancelled',error='Consent withdrawn or recipient unavailable',updated=? WHERE id=?",(now(),msg['id']))
                continue
            c.execute("UPDATE messages SET status='sending',attempts=attempts+1,updated=? WHERE id=?",(now(),msg['id']))
        status,err,provider='dry_run','',None
        if os.environ.get('WHATSAPP_MODE','dry_run')=='live':
            required=('META_ACCESS_TOKEN','META_PHONE_NUMBER_ID','META_GRAPH_VERSION')
            if not all(os.environ.get(k) for k in required): status,err='failed','Missing Meta configuration'
            else:
                payload={'messaging_product':'whatsapp','to':m['phone'].lstrip('+'),'type':'template',
                         'template':{'name':msg['template'],'language':{'code':msg['language']}}}
                params=json.loads(msg['parameters'])
                if params: payload['template']['components']=[{'type':'body','parameters':[{'type':'text','text':p} for p in params]}]
                req=Request(f'https://graph.facebook.com/{os.environ["META_GRAPH_VERSION"]}/{os.environ["META_PHONE_NUMBER_ID"]}/messages',
                            data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+os.environ['META_ACCESS_TOKEN'],'Content-Type':'application/json'})
                try:
                    with urlopen(req,timeout=20) as response: provider=json.load(response)['messages'][0]['id']
                    status='accepted'
                except HTTPError as e:
                    status='queued' if e.code==429 and msg['attempts']<4 else ('uncertain' if e.code>=500 else 'failed')
                    err=f'Meta HTTP {e.code}; consult provider logs (credentials and recipient details omitted).'
                except (URLError,TimeoutError,KeyError,IndexError,TypeError,ValueError,OSError):
                    status,err='uncertain','Delivery outcome unknown; reconcile with Meta before retry.'
        with connect() as c:
            c.execute('UPDATE messages SET status=?,error=?,provider_id=?,next_attempt=?,updated=? WHERE id=?',
                      (status,err,provider,time.time()+60*(2**msg['attempts']),now(),msg['id']))
            if provider: apply_delivery_events(c,provider)
        results.append({'id':msg['id'],'status':status})
    return results

class Handler(BaseHTTPRequestHandler):
    server_version='SSMS/1.0'
    def log_message(self, fmt, *args):
        # Do not log tokens, request bodies or webhook query secrets.
        print(f'{self.command} {urlparse(self.path).path} {args[1] if len(args)>1 else ""}')
    def send(self,status,data=None,headers=None,raw=None,content_type='application/json'):
        body=raw if raw is not None else json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type',content_type+'; charset=utf-8')
        self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','same-origin')
        if production(): self.send_header('Strict-Transport-Security','max-age=31536000')
        self.send_header('Permissions-Policy','camera=(), microphone=(), geolocation=()')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
        for k,v in (headers or {}).items(): self.send_header(k,v)
        self.end_headers(); self.wfile.write(body)
    def request_bytes(self):
        n=int(self.headers.get('Content-Length','0'))
        if not 0<=n<=1000000: raise ValueError('Request body length must be between 0 and 1000000 bytes.')
        raw=self.rfile.read(n)
        if len(raw)!=n: raise ValueError('Incomplete request body.')
        return raw
    def body(self):
        raw=self.request_bytes()
        try: data=json.loads(raw or b'{}')
        except ValueError: raise ValueError('Malformed JSON.')
        if not isinstance(data,dict): raise ValueError('Expected a JSON object.')
        return data
    def auth(self,c,mutate=False):
        cookies={}
        for item in self.headers.get('Cookie','').split(';'):
            if '=' in item:
                k,v=item.strip().split('=',1);cookies[k]=v
        token=hashlib.sha256(cookies.get('ssms_session','').encode()).hexdigest()
        row=c.execute('SELECT u.*,s.csrf FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=? AND s.expires>? AND u.active=1',(token,time.time())).fetchone()
        if not row: raise PermissionError('Sign in to continue.')
        if mutate and not hmac.compare_digest(self.headers.get('X-CSRF-Token',''),row['csrf']): raise PermissionError('Invalid security token. Refresh and try again.')
        return dict(row)
    def do_GET(self): self.handle_request('GET')
    def do_POST(self): self.handle_request('POST')
    def do_PUT(self): self.handle_request('PUT')
    def do_DELETE(self): self.handle_request('DELETE')
    def handle_request(self,method):
        path=urlparse(self.path).path; query=parse_qs(urlparse(self.path).query)
        try:
            if production() and path.startswith('/api/') and method!='GET':
                if not hmac.compare_digest(self.headers.get('Origin',''),os.environ.get('SSMS_ORIGIN','')):
                    raise PermissionError('This request must come from the configured church app origin.')
            if path=='/webhooks/whatsapp': return self.webhook(method,query)
            if path=='/healthz' and method=='GET':
                with connect() as c: c.execute('SELECT 1 FROM users LIMIT 1').fetchone()
                return self.send(200,{'status':'ok'})
            if not path.startswith('/api/'):
                if method!='GET': return self.send(405,{'error':'Method not allowed.'})
                files={'/':('index.html','text/html'),'/app.js':('app.js','application/javascript'),'/style.css':('style.css','text/css')}
                if path not in files: return self.send(404,{'error':'Not found.'})
                f,ct=files[path]; return self.send(200,raw=(ROOT/'static'/f).read_bytes(),content_type=ct)
            with connect() as c:
                if path=='/api/login' and method=='POST':
                    data=self.body(); email=text_field(data,'email',True,254).lower(); pwd=password_field(data,'password')
                    c.execute('BEGIN IMMEDIATE')
                    key=hashlib.sha256((self.client_address[0]+'|'+email).encode()).hexdigest()
                    account_key=hashlib.sha256(('account|'+email).encode()).hexdigest()
                    c.execute('DELETE FROM login_attempts WHERE until<?',(time.time(),))
                    attempt=c.execute('SELECT * FROM login_attempts WHERE key=?',(key,)).fetchone()
                    account_attempt=c.execute('SELECT * FROM login_attempts WHERE key=?',(account_key,)).fetchone()
                    if any(a and a['count']>=8 and a['until']>time.time() for a in (attempt,account_attempt)): return self.send(429,{'error':'Too many attempts. Try again in 15 minutes.'})
                    u=c.execute('SELECT * FROM users WHERE email=? AND active=1',(email,)).fetchone()
                    valid=password_ok(pwd,u['password'] if u else DUMMY_PASSWORD_HASH)
                    if not u or not valid:
                        for ident,a in ((key,attempt),(account_key,account_attempt)):
                            count=a['count']+1 if a and a['until']>time.time() else 1
                            c.execute('INSERT OR REPLACE INTO login_attempts VALUES(?,?,?)',(ident,count,a['until'] if a else time.time()+900))
                        c.commit()
                        return self.send(401,{'error':'Email or password is incorrect.'})
                    c.execute('DELETE FROM login_attempts WHERE key IN (?,?)',(key,account_key))
                    token=secrets.token_urlsafe(32); csrf=secrets.token_urlsafe(32)
                    c.execute('INSERT INTO sessions VALUES(?,?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),u['id'],csrf,time.time()+28800))
                    c.execute('DELETE FROM sessions WHERE expires<?',(time.time(),));c.commit()
                    secure='; Secure' if os.environ.get('SSMS_SECURE_COOKIES')=='1' else ''
                    return self.send(200,{'user':{k:u[k] for k in ('id','name','email','role')},'csrf':csrf},
                                     {'Set-Cookie':f'ssms_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800{secure}'})
                user=self.auth(c,method!='GET'); role=user['role']; uid=user['id']
                if path=='/api/logout' and method=='POST':
                    c.execute('DELETE FROM sessions WHERE user_id=? AND csrf=?',(uid,user['csrf']));c.commit()
                    return self.send(200,{'ok':True},{'Set-Cookie':'ssms_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'})
                if path=='/api/password' and method=='POST':
                    d=self.body(); old=password_field(d,'current');new=password_field(d,'password')
                    if not password_ok(old,user['password']): raise ValueError('Current password is incorrect.')
                    if len(new)<12: raise ValueError('Use at least 12 characters.')
                    c.execute('UPDATE users SET password=? WHERE id=?',(password_hash(new),uid));c.execute('DELETE FROM sessions WHERE user_id=?',(uid,));audit(c,uid,'password.change',{});c.commit()
                    return self.send(200,{'ok':True})
                if path=='/api/state' and method=='GET':
                    data={m:records(c,m) for m in MODULES}
                    # Teachers receive only assigned rosters, lessons and outreach. Other operational roles see all rosters.
                    if role=='teacher':
                        ids={r['id'] for r in data['classes'] if r['teacher_id']==uid}
                        data['classes']=[r for r in data['classes'] if r['id'] in ids]
                        for m in ('members','lessons','outreach'): data[m]=[r for r in data[m] if r.get('class_id') in ids]
                    if role not in ('admin','secretary','treasurer'): data['offerings']=[]
                    users=[dict(r) for r in c.execute('SELECT id,name,email,role,active FROM users ORDER BY name')]
                    if role!='admin': users=[{k:r[k] for k in ('id','name','role','active')} for r in users]
                    attendance=[dict(r) for r in c.execute('SELECT * FROM attendance ORDER BY day DESC')]
                    if role=='teacher': attendance=[r for r in attendance if r['class_id'] in ids]
                    return self.send(200,dict(data,user={k:user[k] for k in ('id','name','email','role')},csrf=user['csrf'],users=users,attendance=attendance,
                      messages=[dict(r) for r in c.execute('SELECT * FROM messages ORDER BY id DESC LIMIT 200')] if role in ('admin','secretary') else [],
                      rules=[dict(r) for r in c.execute('SELECT * FROM rules')] if role in ('admin','secretary') else [],
                      audit=[dict(r) for r in c.execute('SELECT a.*,u.name AS actor_name FROM audit a LEFT JOIN users u ON u.id=a.actor ORDER BY a.id DESC LIMIT 100')] if role=='admin' else [],
                      whatsapp={'mode':os.environ.get('WHATSAPP_MODE','dry_run'),'configured':all(os.environ.get(k) for k in ('META_ACCESS_TOKEN','META_PHONE_NUMBER_ID','META_GRAPH_VERSION','META_APP_SECRET','META_VERIFY_TOKEN'))}))
                if path=='/api/attendance' and method=='POST':
                    d=self.body(); c.execute('BEGIN IMMEDIATE');cid=positive_id(d,'class_id');allowed_class(c,user,cid)
                    day=iso_day(d.get('day'))
                    if date.fromisoformat(day).weekday()!=5: raise ValueError('Attendance date must be a Saturday.')
                    if day>utc_today().isoformat(): raise ValueError('Attendance cannot be marked in the future.')
                    entries=d.get('entries',[])
                    if not isinstance(entries,list) or not entries: raise ValueError('Choose at least one attendance entry.')
                    seen=set()
                    for e in entries:
                        if not isinstance(e,dict): raise ValueError('Invalid attendance entry.')
                        mid=positive_id(e,'member_id');m=record(c,mid,'members')
                        if mid in seen: raise ValueError('Duplicate member entry.')
                        seen.add(mid)
                        if m['class_id']!=cid or m['status']=='Inactive': raise ValueError('Member is not active in this class.')
                        if e.get('status') not in ('Present','Absent','Excused'): raise ValueError('Invalid attendance status.')
                        if type(e.get('study',False)) is not bool: raise ValueError('Study must be a boolean.')
                        notes=text_field(e,'notes')
                        c.execute('INSERT INTO attendance VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(class_id,member_id,day) DO UPDATE SET status=excluded.status,study=excluded.study,notes=excluded.notes,marked_by=excluded.marked_by,updated=excluded.updated',
                                  (cid,mid,day,e['status'],int(e.get('study',False)),notes,uid,now()))
                    audit(c,uid,'attendance.save',{'class_id':cid,'day':day,'count':len(entries)});c.commit()
                    return self.send(200,{'saved':len(entries)})
                if path=='/api/reports.csv' and method=='GET':
                    kind=query.get('kind',['attendance'])[0]; start=iso_day(query.get('start',['2000-01-01'])[0]);end=iso_day(query.get('end',[utc_today().isoformat()])[0])
                    if start>end: raise ValueError('Start date must precede end date.')
                    out=io.StringIO(); writer=csv.writer(out)
                    def safe(v):
                        s=str(v);return "'"+s if s.startswith(('=','+','-','@','\t','\r')) else s
                    if kind=='offerings':
                        if role not in ('admin','secretary','treasurer'): raise PermissionError('Financial reports are restricted.')
                        writer.writerow(['Date','Class','Category','Amount','Currency','Receipt'])
                        classes={r['id']:r['name'] for r in records(c,'classes')}
                        for r in records(c,'offerings'):
                            if start<=r['day']<=end: writer.writerow([safe(v) for v in (r['day'],classes.get(r['class_id'],'Archived'),r['category'],f'{r["amount_minor"]/100:.2f}',r['currency'],r['receipt'])])
                    elif kind=='attendance':
                        writer.writerow(['Date','Class','Member','Status','Studied lesson','Marked by'])
                        members={r['id']:r for r in records(c,'members')}; classes={r['id']:r for r in records(c,'classes')};users={r['id']:r['name'] for r in c.execute('SELECT id,name FROM users')}
                        for r in c.execute('SELECT * FROM attendance WHERE day BETWEEN ? AND ? ORDER BY day',(start,end)):
                            if role=='teacher' and classes[r['class_id']]['teacher_id']!=uid: continue
                            writer.writerow([safe(v) for v in (r['day'],classes[r['class_id']]['name'],members[r['member_id']]['name'],r['status'],'Yes' if r['study'] else 'No',users.get(r['marked_by'],'Archived'))])
                    else: raise ValueError('Unknown report.')
                    audit(c,uid,'report.export',{'kind':kind,'start':start,'end':end});c.commit()
                    return self.send(200,raw=out.getvalue().encode('utf-8-sig'),content_type='text/csv',headers={'Content-Disposition':f'attachment; filename="ssms-{kind}.csv"'})
                if path=='/api/users' and method=='POST':
                    if role!='admin': raise PermissionError('Administrator access required.')
                    d=self.body(); name=text_field(d,'name',True,200);email=text_field(d,'email',True,254).lower();pwd=password_field(d,'password')
                    if d.get('role') not in ROLES or len(pwd)<12 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email): raise ValueError('Use a valid email, role and password of at least 12 characters.')
                    ident=c.execute('INSERT INTO users(name,email,role,password) VALUES(?,?,?,?)',(name,email,d['role'],password_hash(pwd))).lastrowid
                    audit(c,uid,'user.create',{'id':ident,'role':d['role']});c.commit();return self.send(201,{'id':ident})
                if re.fullmatch(r'/api/users/\d+',path) and method=='PUT':
                    if role!='admin': raise PermissionError('Administrator access required.')
                    target=int(path.split('/')[-1]);d=self.body()
                    u=c.execute('SELECT * FROM users WHERE id=?',(target,)).fetchone()
                    if not u: raise ValueError('User not found.')
                    new_role=d.get('role',u['role']);active=bool_field(d,'active',bool(u['active']))
                    if new_role not in ROLES: raise ValueError('Invalid role.')
                    if target==uid and (not active or new_role!='admin'): raise ValueError('You cannot remove your own administrator access.')
                    if new_role!='teacher' or not active:
                        if any(r['teacher_id']==target for r in records(c,'classes')): raise ValueError('Reassign this teacher’s classes first.')
                    c.execute('UPDATE users SET role=?,active=? WHERE id=?',(new_role,int(active),target));c.execute('DELETE FROM sessions WHERE user_id=?',(target,))
                    audit(c,uid,'user.update',{'id':target,'role':new_role,'active':active});c.commit();return self.send(200,{'ok':True})
                if path.startswith('/api/notifications'):
                    if role not in ('admin','secretary'): raise PermissionError('Notification management is restricted.')
                    d=self.body() if method!='GET' else {}
                    if path=='/api/notifications/queue' and method=='POST':
                        template=text_field(d,'template',True,100);language=text_field(d,'language',True,20); params=d.get('parameters',[])
                        self.validate_template(template,language,params)
                        recipients=d.get('member_ids',[])
                        if not isinstance(recipients,list) or not 1<=len(recipients)<=500: raise ValueError('Select between 1 and 500 recipients.')
                        key=text_field(d,'request_id',True,100);queued=0;skipped=0
                        for mid in set(recipients):
                            m=record(c,mid,'members'); before=c.total_changes
                            if queue_message(c,m,template,language,[p.replace('{name}',m['name']) for p in params],f'manual:{key}:{mid}'): queued+=c.total_changes-before
                            else: skipped+=1
                        audit(c,uid,'notifications.queue',{'queued':queued,'skipped':skipped});c.commit();return self.send(200,{'queued':queued,'skipped':skipped})
                    if path=='/api/notifications/process' and method=='POST':
                        audit(c,uid,'notifications.process',{});c.commit();return self.send(200,{'results':process_queue(3)})
                    if re.fullmatch(r'/api/notifications/messages/\d+',path) and method=='POST':
                        c.execute('BEGIN IMMEDIATE');ident=int(path.split('/')[-1]);msg=c.execute('SELECT * FROM messages WHERE id=?',(ident,)).fetchone()
                        if not msg: raise ValueError('Message not found.')
                        action=d.get('action')
                        if action=='cancel':
                            if msg['status']!='queued': raise ValueError('Only queued messages can be cancelled.')
                            c.execute("UPDATE messages SET status='cancelled',updated=? WHERE id=?",(now(),ident))
                        elif action=='retry':
                            if msg['status'] not in ('failed','uncertain'): raise ValueError('Only failed or reconciled uncertain messages can be retried.')
                            if msg['status']=='uncertain' and d.get('reconciled') is not True: raise ValueError('Confirm with Meta that the message was not sent before retrying.')
                            m=record(c,msg['member_id'],'members')
                            if not m.get('whatsapp_opt_in') or m.get('status')=='Inactive': raise ValueError('Recipient no longer eligible.')
                            c.execute("UPDATE messages SET status='queued',next_attempt=0,error='',updated=? WHERE id=?",(now(),ident))
                        else: raise ValueError('Choose cancel or retry.')
                        audit(c,uid,'message.'+action,{'id':ident,'reconciled':d.get('reconciled',False)});c.commit();return self.send(200,{'ok':True})
                    if path=='/api/notifications/rules' and method=='POST':
                        template=text_field(d,'template',True,100);language=text_field(d,'language',True,20);params=d.get('parameters',[])
                        self.validate_template(template,language,params)
                        if d.get('trigger') not in ('weekly','birthday','absence'): raise ValueError('Invalid automation trigger.')
                        ident=c.execute('INSERT INTO rules(name,trigger,template,language,parameters) VALUES(?,?,?,?,?)',
                                        (text_field(d,'name',True,200),d['trigger'],template,language,json.dumps(params))).lastrowid
                        audit(c,uid,'rule.create',{'id':ident});c.commit();return self.send(201,{'id':ident})
                    if re.fullmatch(r'/api/notifications/rules/\d+',path) and method=='DELETE':
                        c.execute('DELETE FROM rules WHERE id=?',(int(path.split('/')[-1]),));audit(c,uid,'rule.delete',{'id':path.split('/')[-1]});c.commit();return self.send(200,{'ok':True})
                    if path=='/api/notifications/run-rules' and method=='POST':
                        queued=run_rules(c,iso_day(d.get('day')));audit(c,uid,'rules.run',{'queued':queued});c.commit();return self.send(200,{'queued':queued})
                if re.fullmatch(r'/api/events/\d+/register',path) and method=='POST':
                    if role not in ('admin','secretary','teacher'): raise PermissionError('Registration management is restricted.')
                    cid=int(path.split('/')[3]);d=self.body();mid=positive_id(d,'member_id');m=record(c,mid,'members')
                    if role=='teacher': allowed_class(c,user,m['class_id'])
                    c.execute('BEGIN IMMEDIATE');e=record(c,cid,'events');regs=e['registrations']
                    cancel=bool_field(d,'cancel')
                    if cancel: regs=[r for r in regs if r!=mid]
                    elif mid not in regs:
                        if e['capacity'] and len(regs)>=e['capacity']: raise ValueError('Event is full.')
                        regs.append(mid)
                    e['registrations']=regs;e.pop('id');e.pop('version')
                    c.execute('UPDATE records SET data=?,version=version+1 WHERE id=?',(json.dumps(e),cid));audit(c,uid,'event.registration',{'event_id':cid,'member_id':mid,'cancel':cancel});c.commit();return self.send(200,{'ok':True})
                match=re.fullmatch(r'/api/(classes|members|lessons|offerings|events|outreach)(?:/(\d+))?',path)
                if match and method in ('POST','PUT','DELETE'):
                    module,ident=match.groups()
                    if role not in WRITE[module]: raise PermissionError('Your role cannot change this module.')
                    c.execute('BEGIN IMMEDIATE')
                    existing=record(c,int(ident),module) if ident else None
                    if method=='DELETE':
                        if not ident: raise ValueError('Record ID required.')
                        if role=='teacher': allowed_class(c,user,existing['class_id'])
                        if module=='members':
                            if c.execute('SELECT 1 FROM attendance WHERE member_id=? UNION SELECT 1 FROM messages WHERE member_id=?',(ident,ident)).fetchone() or any(int(ident) in e['registrations'] for e in records(c,'events')):
                                raise ValueError('Member has history. Set status to Inactive instead.')
                        if module=='classes':
                            if any(r.get('class_id')==int(ident) for m in ('members','lessons','offerings','outreach') for r in records(c,m)) or c.execute('SELECT 1 FROM attendance WHERE class_id=?',(ident,)).fetchone():
                                raise ValueError('Class has related records. Set active to false instead.')
                        if module=='offerings' and role!='admin': raise PermissionError('Only administrators can delete financial records.')
                        c.execute('DELETE FROM records WHERE id=?',(ident,));audit(c,uid,module+'.delete',{'id':ident});c.commit();return self.send(200,{'ok':True})
                    if (method=='PUT')!=bool(ident): raise ValueError('Use POST to create or PUT with an ID to edit.')
                    d=self.body();clean=validate(c,module,d,user,existing)
                    if existing:
                        if d.get('version')!=existing['version']: return self.send(409,{'error':'This record changed. Refresh before editing.'})
                        c.execute('UPDATE records SET data=?,version=version+1 WHERE id=?',(json.dumps(clean),ident))
                    else: ident=c.execute('INSERT INTO records(module,data) VALUES(?,?)',(module,json.dumps(clean))).lastrowid
                    detail={'id':ident}
                    if module=='offerings': detail.update(before=existing,after=clean)
                    audit(c,uid,module+'.save',detail);c.commit();return self.send(200 if existing else 201,{'id':int(ident)})
                return self.send(404,{'error':'Endpoint not found.'})
        except PermissionError as e: return self.send(401 if str(e)=='Sign in to continue.' else 403,{'error':str(e)})
        except sqlite3.IntegrityError: return self.send(409,{'error':'Duplicate record or linked history prevents this change.'})
        except (ValueError,TypeError,KeyError,AttributeError) as e: return self.send(400,{'error':str(e) if isinstance(e,ValueError) else 'Invalid request fields.'})
        except Exception:
            import traceback;traceback.print_exc()
            return self.send(500,{'error':'Unexpected server error. Check server logs.'})
    def validate_template(self,template,language,params):
        if not re.fullmatch('[a-z0-9_]+',template) or not re.fullmatch('[a-z]{2}(?:_[A-Z]{2})?',language): raise ValueError('Use a valid approved template name and language code.')
        if not isinstance(params,list) or len(params)>20 or any(not isinstance(p,str) or len(p)>1000 for p in params): raise ValueError('Template parameters must be a list of text values.')
    def webhook(self,method,query):
        if method=='GET':
            token=os.environ.get('META_VERIFY_TOKEN','')
            if token and query.get('hub.mode')==['subscribe'] and hmac.compare_digest(query.get('hub.verify_token',[''])[0],token):
                return self.send(200,raw=query.get('hub.challenge',[''])[0].encode(),content_type='text/plain')
            return self.send(403,{'error':'Webhook verification failed.'})
        if method!='POST': return self.send(405,{'error':'Method not allowed.'})
        raw=self.request_bytes();secret=os.environ.get('META_APP_SECRET','')
        expected='sha256='+hmac.new(secret.encode(),raw,hashlib.sha256).hexdigest()
        if not secret or not hmac.compare_digest(expected,self.headers.get('X-Hub-Signature-256','')): return self.send(403,{'error':'Invalid webhook signature.'})
        payload=json.loads(raw)
        with connect() as c:
            for entry in payload.get('entry',[]):
                for change in entry.get('changes',[]):
                    for status in change.get('value',{}).get('statuses',[]):
                        provider=status.get('id');target=status.get('status')
                        if not isinstance(provider,str) or len(provider)>300 or target not in ('sent','delivered','read','failed'): continue
                        c.execute('INSERT OR IGNORE INTO delivery_events VALUES(?,?,?)',(provider,target,now()))
                        apply_delivery_events(c,provider)
        return self.send(200,{'ok':True})

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--demo',action='store_true');parser.add_argument('--port',type=int,default=8000);parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--worker',action='store_true',help='Run due rules and process notification queue, then exit')
    parser.add_argument('--init-only',action='store_true',help='Initialize the configured database without starting an HTTP server')
    args=parser.parse_args()
    if args.demo and args.host not in ('127.0.0.1','localhost','::1'): parser.error('Demo mode must bind to loopback only.')
    if production() and not (args.worker or args.init_only): parser.error('Use the WSGI production entrypoint, not the development HTTP server.')
    initialize(args.demo)
    if args.init_only: print('Database initialized.');return
    if args.worker:
        with connect() as c: queued=run_rules(c,utc_today().isoformat())
        print(json.dumps({'queued':queued,'processed':process_queue(100)}));return
    server=ThreadingHTTPServer((args.host,args.port),Handler)
    print(f'SSMS running at http://{args.host}:{server.server_port}',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()

if __name__=='__main__': main()
