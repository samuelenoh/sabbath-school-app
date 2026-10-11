"""Run the same real HTTP/authorization suite on a disposable PostgreSQL database."""
import os,tempfile,threading,unittest
from pathlib import Path
from urllib.parse import urlparse
import test_system as shared
import server

@unittest.skipUnless(os.environ.get('SSMS_TEST_POSTGRES_URL'),'Dedicated PostgreSQL test URL not configured')
class PostgreSQLSystemTests(shared.SystemTests):
    @classmethod
    def setUpClass(cls):
        target=os.environ['SSMS_TEST_POSTGRES_URL']
        if urlparse(target).hostname not in ('localhost','127.0.0.1','postgres') or not urlparse(target).path.rstrip('/').endswith('_test'):
            raise RuntimeError('Refusing destructive test setup: use a local disposable database named with _test.')
        import psycopg
        with psycopg.connect(target,autocommit=True) as c:
            c.execute('DROP SCHEMA public CASCADE');c.execute('CREATE SCHEMA public')
        cls.temp=tempfile.TemporaryDirectory();server.DB=target
        os.environ['WHATSAPP_MODE']='dry_run';os.environ['SSMS_DEMO_PASSWORD']=shared.TEST_PASSWORD;os.environ['SSMS_ENV']='development'
        server.initialize(True)
        cls.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True);cls.thread.start()
        cls.url=f'http://127.0.0.1:{cls.http.server_port}'

    def test_17_concurrent_workers_claim_one_job(self):
        mid=self.member('Concurrent dry-run recipient',opt=True)
        with server.connect() as c:c.execute("UPDATE messages SET status='cancelled' WHERE status='queued'")
        status,_=self.admin.call('/api/notifications/queue','POST',{'template':'concurrent_test','language':'en','parameters':[],'member_ids':[mid],'request_id':'concurrent-test'})
        self.assertEqual(status,200)
        results=[];errors=[]
        def work():
            try:results.append(server.process_queue(1))
            except Exception as error:errors.append(error)
        workers=[threading.Thread(target=work) for _ in range(2)]
        for t in workers:t.start()
        for t in workers:t.join(timeout=30)
        self.assertFalse(any(t.is_alive() for t in workers));self.assertEqual(errors,[])
        self.assertEqual(sum(len(result) for result in results),1)
        with server.connect() as c:
            row=c.execute('SELECT attempts,status FROM messages WHERE member_id=?',(mid,)).fetchone()
            self.assertEqual(row['attempts'],1)
