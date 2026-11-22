import base64
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
from threading import Thread
from urllib.request import Request,urlopen
from urllib.error import HTTPError
import tempfile
import unittest
import server

class ServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.orig=server.DATA
        server.DATA=Path(cls.temp.name)
        cls.srv=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        cls.port=cls.srv.server_port
        cls.thread=Thread(target=cls.srv.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown();cls.srv.server_close();cls.thread.join(timeout=4)
        server.DATA=cls.orig;cls.temp.cleanup()
    def url(self,path):return f'http://127.0.0.1:{self.port}{path}'
    def get(self,path):
        with urlopen(self.url(path),timeout=5) as r:return json.load(r)
    def post(self,path,obj,headers=None):
        h={'Content-Type':'application/json','X-MR-Client':'1'}
        if headers:h.update(headers)
        request=Request(self.url(path),data=json.dumps(obj,ensure_ascii=False).encode('utf-8'),headers=h,method='POST')
        with urlopen(request,timeout=10) as r:return json.load(r)
    def test_health(self):
        d=self.get('/api/health');self.assertEqual(d['version'],'1.0')
    def test_demo_reconstruct(self):
        d=self.get('/api/demo');self.assertEqual(len(d['pages']),1)
        o=self.post('/api/reconstruct',{'pages':d['pages']})
        self.assertIn('天气不错',o['final'])
    def test_save_load_delete(self):
        d=self.get('/api/demo')
        pid=self.post('/api/project/save',d)['project']['id']
        self.assertEqual(self.get('/api/project/'+pid)['id'],pid)
        self.assertTrue(any(p['id']==pid for p in self.get('/api/projects')['projects']))
        self.post('/api/project/delete',{'id':pid})
        with self.assertRaises(HTTPError) as e:self.get('/api/project/'+pid)
        self.assertEqual(e.exception.code,404)
    def test_post_rejects_cross_origin(self):
        with self.assertRaises(HTTPError) as e:self.post('/api/reconstruct',{'pages':[]},{'Origin':'https://evil.invalid'})
        self.assertEqual(e.exception.code,403)
    def test_post_rejects_unknown_client(self):
        req=Request(self.url('/api/reconstruct'),data=b'{}',headers={'Content-Type':'application/json'},method='POST')
        with self.assertRaises(HTTPError) as e:urlopen(req,timeout=5)
        self.assertEqual(e.exception.code,400)
    def test_path_escapes(self):
        with self.assertRaises(HTTPError) as e:self.get('/server.py')
        self.assertEqual(e.exception.code,404)
    def test_ocr_and_marks_http(self):
        d=self.get('/api/demo');p=d['pages'][0]
        try:
            d2=self.post('/api/ocr',{'image':p['image'],'engine':'tesseract','roi':[40,135,940,230]})
        except HTTPError as e:
            self.skipTest('OCR system unavailable')
        self.assertGreater(len(d2['tokens']),3)
        m=self.post('/api/marks',{'image':p['image'],'tokens':p['tokens']})
        self.assertGreaterEqual(len(m['proposals']),2)

if __name__=='__main__':unittest.main()
