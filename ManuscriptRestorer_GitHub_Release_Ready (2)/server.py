"""Local-only ManuscriptRestorer server, deliberately dependency-light.

Launch: python server.py; the browser and app communicate on loopback only.
"""
from __future__ import annotations

import argparse
import base64
import binascii
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import json
from pathlib import Path
import re
import threading
import uuid
from urllib.parse import urlsplit

from core import ManuscriptError, reconstruct_document
from analyzer import load_image, recognize, detect_red_strikes, red_annotation_candidates, render_pdf
from vision_adapter import analyze_vision

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data' / 'projects'
DATA.mkdir(parents=True, exist_ok=True)
MAX_BODY = 45 * 1024 * 1024
MAX_IMAGE_BYTES = 16 * 1024 * 1024
STATIC = {'/': ROOT/'web/index.html', '/web/app.js':ROOT/'web/app.js',
          '/web/style.css':ROOT/'web/style.css', '/fixtures/demo.png':ROOT/'fixtures/demo.png'}
MIME = {'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8',
        '.css':'text/css; charset=utf-8','.png':'image/png'}
lock = threading.RLock()


def unpack_data_url(data: str) -> bytes:
    if not isinstance(data,str) or not re.match(r'^data:image/(png|jpeg|webp);base64,',data):
        raise ManuscriptError('图像必须为PNG/JPEG/WebP格式的Data URL')
    try:
        raw = base64.b64decode(data.split(',',1)[1],validate=True)
    except (binascii.Error,ValueError) as exc:
        raise ManuscriptError('图像编码无效') from exc
    if len(raw)>MAX_IMAGE_BYTES:
        raise ManuscriptError('图片超过16MB')
    load_image(raw)
    return raw


def _project_path(project_id):
    if not isinstance(project_id,str) or not re.fullmatch(r'[0-9a-f]{32}',project_id):
        raise ManuscriptError('项目ID无效')
    return DATA/(project_id+'.json')


def _persist(document):
    if not isinstance(document,dict):
        raise ManuscriptError('项目文件格式错误')
    pages=document.get('pages')
    if not isinstance(pages,list) or not (0 < len(pages) <= 30):
        raise ManuscriptError('项目须包含1至30页')
    name=document.get('name','未命名项目')
    if not isinstance(name,str) or not (1 <= len(name) <= 120):
        raise ManuscriptError('项目名称长度必须为1到120个字符')
    reconstruct_document(document)
    for i,page in enumerate(pages):
        if not isinstance(page,dict):raise ManuscriptError('页面格式无效')
        raw=page.get('image')
        if raw is not None:unpack_data_url(raw)
    pid=document.get('id') or uuid.uuid4().hex
    path=_project_path(pid)
    now=datetime.now(timezone.utc).isoformat(timespec='seconds')
    saved={**document,'id':pid,'version':'1.0','updated_at':now}
    saved.setdefault('created_at',now)
    text=json.dumps(saved,ensure_ascii=False,allow_nan=False)
    if len(text.encode('utf-8')) > 42 * 1024 * 1024:
        raise ManuscriptError('项目文件超过42MB')
    with lock:
        temp=DATA/(pid+'.tmp')
        temp.write_text(text,encoding='utf-8')
        temp.replace(path)
    return {'id':pid,'name':name,'updated_at':now, 'pages':len(pages)}


def _list_projects():
    result=[]
    with lock:
        for p in sorted(DATA.glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True):
            try:
                data=json.loads(p.read_text(encoding='utf-8'))
                result.append({'id':data['id'],'name':data['name'],
                               'updated_at':data.get('updated_at',''),
                               'pages':len(data.get('pages',[]))})
            except (KeyError,ValueError,OSError):
                continue
    return result


def _demo():
    old=json.loads((ROOT/'fixtures/demo.json').read_text(encoding='utf-8'))
    raw=(ROOT/'fixtures/demo.png').read_bytes()
    return {'version':'1.0','name':'内置演示：红笔修改',
            'pages':[{'id':'demo_page','name':'第1页','image':'data:image/png;base64,'+base64.b64encode(raw).decode('ascii'),
                      'tokens':old['tokens'],'edits':old['edits']} ]}

class Handler(BaseHTTPRequestHandler):
    server_version='ManuscriptRestorer/1.0'

    def _secure_host(self):
        host=self.headers.get('Host','')
        return host in {f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}',
                        f'[::1]:{self.server.server_port}'}

    def _secure_request(self):
        if not self._secure_host():
            self._json({'error':'Host不受信任'},403)
            return False
        origin=self.headers.get('Origin')
        if origin and origin not in {f'http://127.0.0.1:{self.server.server_port}',
                                     f'http://localhost:{self.server.server_port}'}:
            self._json({'error':'跨来源请求被拒绝'},403)
            return False
        return True

    def _respond(self,code, content, mime):
        self.send_response(code)
        self.send_header('Content-Type',mime)
        self.send_header('Content-Length',str(len(content)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('X-Frame-Options','DENY')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'self'; img-src 'self' data: blob:; style-src 'self'; script-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        try:self.wfile.write(content)
        except (BrokenPipeError,ConnectionResetError):pass

    def _json(self,result,code=200):
        try:raw=json.dumps(result,ensure_ascii=False,allow_nan=False).encode('utf-8')
        except (TypeError,ValueError):
            raw=json.dumps({"error":"内部响应格式错误"},ensure_ascii=False).encode("utf-8")
            code=500
        self._respond(code,raw,'application/json; charset=utf-8')

    def do_GET(self):
        if not self._secure_request():return
        route=urlsplit(self.path)
        if route.path=='/api/health':
            from shutil import which
            try:import pytesseract; tesseract=bool(which('tesseract'))
            except ImportError:tesseract=False
            from importlib.util import find_spec
            self._json({'ok':True,'version':'1.0','tesseract':tesseract,
                        'paddle':find_spec('paddleocr') is not None,
                        'pdf':find_spec('pypdfium2') is not None,
                        'vision':True,
                        'storage':str(DATA)})
            return
        if route.path=='/api/projects':
            self._json({'projects':_list_projects()});return
        if route.path=='/api/demo':
            self._json(_demo());return
        if route.path.startswith('/api/project/'):
            try:
                p=_project_path(route.path.rsplit('/',1)[1])
                if not p.exists():return self._json({'error':'项目不存在'},404)
                self._respond(200,p.read_bytes(),'application/json; charset=utf-8')
            except ManuscriptError as exc:self._json({'error':str(exc)},400)
            return
        path=STATIC.get(route.path)
        if path and path.is_file():
            return self._respond(200,path.read_bytes(),MIME[path.suffix])
        return self._json({'error':'未找到该路径'},404)

    def _read_json(self):
        if self.headers.get('X-MR-Client')!='1' or not self.headers.get('Content-Type','').lower().startswith('application/json'):
            raise ManuscriptError('缺少本地客户端请求标记或JSON Content-Type')
        try:length=int(self.headers.get('Content-Length',''))
        except ValueError:raise ManuscriptError('请求长度无效')
        if length<=0 or length>MAX_BODY:
            raise ManuscriptError('请求超过45MB或为空')
        try:obj=json.loads(self.rfile.read(length))
        except (ValueError,UnicodeError):raise ManuscriptError('JSON数据无效')
        if not isinstance(obj,dict):raise ManuscriptError('请求须是JSON对象')
        return obj

    def do_POST(self):
        if not self._secure_request():return
        route=urlsplit(self.path).path
        try:
            data=self._read_json()
            if route=='/api/reconstruct':
                return self._json(reconstruct_document(data))
            if route=='/api/ocr':
                img=unpack_data_url(data.get('image',''))
                return self._json(recognize(img,engine=data.get('engine','auto'),
                                            roi=data.get('roi'),remove_red=data.get('remove_red',True)))
            if route=='/api/marks':
                img=unpack_data_url(data.get('image',''))
                tokens=data.get('tokens',[])
                if not isinstance(tokens,list) or len(tokens)>5000:
                    raise ManuscriptError('文字框数组无效')
                return self._json({'proposals':detect_red_strikes(img,tokens),
                                   'ink_regions':red_annotation_candidates(img),
                                   'note':'颜色及位置检测是几何候选，不直接改变终稿'})
            if route=='/api/vision':
                img=unpack_data_url(data.get('image',''))
                return self._json(analyze_vision(img,data.get('tokens',[]),data.get('model','qwen3-vl:4b')))
            if route=='/api/pdf':
                b64=data.get('data','')
                if not isinstance(b64,str) or len(b64)>29_000_000:
                    raise ManuscriptError('PDF数据超限')
                try:pdf=base64.b64decode(b64,validate=True)
                except (binascii.Error,ValueError):raise ManuscriptError('PDF编码错误')
                images=render_pdf(pdf)
                return self._json({'pages':[{'name':p['name'],'image':'data:image/png;base64,'+base64.b64encode(p['data']).decode('ascii')} for p in images]})
            if route=='/api/project/save':
                return self._json({'project':_persist(data)})
            if route=='/api/project/delete':
                p=_project_path(data.get('id'))
                with lock:
                    if p.exists():p.unlink()
                return self._json({'ok':True})
            return self._json({'error':'API不存在'},404)
        except (ManuscriptError,RuntimeError) as exc:
            return self._json({'error':str(exc)},400)
        except Exception as exc:
            # Don't leak stack traces, paths, or manuscript text to clients.
            print('内部请求失败:',type(exc).__name__,str(exc)[:300])
            return self._json({'error':'内部处理失败，查看服务器终端日志'},500)

    def log_message(self, format, *args):
        # Paths are logged, never upload bodies or full document contents.
        super().log_message(format,*args)


def main():
    p=argparse.ArgumentParser(description='ManuscriptRestorer local server')
    p.add_argument('--port',type=int,default=8765)
    args=p.parse_args()
    if not (1024<=args.port<=65535):
        raise SystemExit('端口应在1024到65535之间')
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    print(f'ManuscriptRestorer v1.0 已启动： http://127.0.0.1:{args.port}')
    print('本地项目存储目录：',DATA)
    try:server.serve_forever()
    except KeyboardInterrupt:print('\n服务已停止')
    finally:server.server_close()

if __name__=='__main__':main()
