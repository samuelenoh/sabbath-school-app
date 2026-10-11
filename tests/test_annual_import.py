"""Independent fixtures verify annual arithmetic and safe, repeatable roster import."""
import json,os,secrets,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from annual_report import build_annual_report
import server,import_roster

class AnnualFixtureTests(unittest.TestCase):
    def fixture(self):
        data={m:[] for m in server.MODULES}
        data['classes']=[{'id':1,'name':'Example class','teacher_id':2,'active':True}]
        data['members']=[{'id':10,'name':'PRIVATE NAME','phone':'+233201234599','notes':'PRIVATE NOTE','status':'Active','class_id':1,'joined_on':'2026-02-01'}, {'id':11,'name':'Other member','status':'Visitor','class_id':1,'joined_on':''}]
        data['offerings']=[{'day':'2026-01-03','class_id':1,'currency':'GHS','amount_minor':12345,'category':'Class contribution'}, {'day':'2026-04-04','class_id':1,'currency':'GHS','amount_minor':55,'category':'Mission'}, {'day':'2026-04-04','class_id':1,'currency':'USD','amount_minor':900,'category':'Mission'}, {'day':'2025-12-27','class_id':1,'currency':'GHS','amount_minor':999999,'category':'Class contribution'}]
        data['bookorders']=[{'class_id':1,'year':2026,'quarter':1,'quantity':12,'status':'Received','book_title':'Guide'}, {'class_id':1,'year':2026,'quarter':2,'quantity':5,'status':'Cancelled','book_title':'Guide'}, {'class_id':1,'year':2025,'quarter':4,'quantity':77,'status':'Distributed','book_title':'Old guide'}]
        data['events']=[{'day':'2026-04-04','registrations':[10,11]}]
        data['outreach']=[{'day':'2026-04-04','class_id':1,'status':'Completed','people_reached':7},{'day':'2026-04-04','class_id':1,'status':'Planned','people_reached':100}]
        att=[{'day':'2026-01-03','class_id':1,'member_id':10,'status':'Present','study':1},{'day':'2026-01-03','class_id':1,'member_id':11,'status':'Excused','study':0},{'day':'2025-12-27','class_id':1,'member_id':10,'status':'Present','study':1}]
        return data,att
    def test_selected_year_currency_quarters_and_actual_activity(self):
        data,att=self.fixture();r=build_annual_report(data,att,2026,True)
        self.assertEqual(r['giving']['totals'],[{'currency':'GHS','amount_minor':12400},{'currency':'USD','amount_minor':900}])
        self.assertEqual(r['giving']['class_contributions'],[{'currency':'GHS','amount_minor':12345}])
        self.assertEqual(r['attendance']['present_percent'],50.0);self.assertEqual(r['attendance']['studied'],1)
        self.assertEqual(r['quarters'][0]['attendance']['marked_entries'],2);self.assertEqual(r['quarters'][1]['attendance']['marked_entries'],0)
        self.assertEqual(r['books']['active_quantity'],12);self.assertEqual(r['books']['quantity_by_status']['Cancelled'],5)
        self.assertEqual(r['events']['current_registration_entries'],2);self.assertEqual(r['outreach']['reported_people_reached_completed'],7)
        self.assertEqual(r['membership']['recorded_join_dates_in_year'],1);self.assertEqual(r['programme']['completed_weeks'],0)
        raw=json.dumps(r);self.assertNotIn('PRIVATE',raw);self.assertNotIn('+233201234599',raw)
    def test_read_only_report_redaction_and_missing_year(self):
        data,att=self.fixture();r=build_annual_report(data,att,2002,False)
        self.assertIsNone(r['giving']);self.assertIsNone(r['attendance']['present_percent'])
        self.assertEqual(r['membership']['current_total'],2);self.assertEqual(r['books']['active_quantity'],0)
        self.assertFalse(any('giving' in q for q in r['quarters']+r['class_breakdown']))

class RosterImportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.dbpatch=patch.object(server,'DB',str(Path(self.temp.name)/'import.sqlite3'));self.dbpatch.start()
        self.envpatch=patch.dict(os.environ,{'SSMS_ENV':'development','WHATSAPP_MODE':'dry_run','SSMS_ADMIN_PASSWORD':secrets.token_urlsafe(24)});self.envpatch.start();server.initialize(False)
        with server.connect() as c:
            tid=c.execute('INSERT INTO users(name,email,role,password) VALUES(?,?,?,?)',('Synthetic teacher','example@ssms.local','teacher',server.password_hash(secrets.token_urlsafe(24)))).lastrowid
            self.cid=c.execute('INSERT INTO records(module,data) VALUES(?,?)',('classes',json.dumps({'name':'Synthetic class','teacher_id':tid,'active':True}))).lastrowid
        self.rows=[{'name':'Synthetic roster person','phone_local':'0201234567','residence':'Example residence','class_office':'H.T','notes':'Synthetic source'}]
    def tearDown(self):self.envpatch.stop();self.dbpatch.stop();self.temp.cleanup()
    def test_preview_repeat_import_preserves_leading_zero_unknown_dates_and_consent(self):
        plan=import_roster.import_rows(self.rows,self.cid,False);self.assertEqual(plan[0]['action'],'insert')
        with server.connect() as c:self.assertEqual(server.records(c,'members'),[])
        import_roster.import_rows(self.rows,self.cid,True);repeat=import_roster.import_rows(self.rows,self.cid,True)
        self.assertEqual(repeat[0]['action'],'skip_existing')
        with server.connect() as c:
            m=server.records(c,'members')[0];self.assertEqual(m['phone_local'],'0201234567');self.assertEqual(m['phone'],'+233201234567')
            self.assertEqual(m['joined_on'],'');self.assertFalse(m['whatsapp_opt_in']);self.assertEqual(c.execute('SELECT COUNT(*) AS n FROM messages').fetchone()['n'],0)
    def test_conflict_prevents_entire_batch_and_phone_validation(self):
        import_roster.import_rows(self.rows,self.cid,True)
        rows=[{'name':'Another synthetic person','phone_local':'0201234568'}, {**self.rows[0],'residence':'Conflicting residence'}]
        with self.assertRaises(ValueError):import_roster.import_rows(rows,self.cid,True)
        with server.connect() as c:self.assertEqual(len(server.records(c,'members')),1)
        with self.assertRaises(ValueError):import_roster.normalize_phone('123')
