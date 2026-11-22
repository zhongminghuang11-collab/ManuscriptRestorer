"""Batch CLI for OCR -> proposed edits -> human review -> reconstruction.

python cli.py analyze sample.png -o project.json --engine tesseract
python cli.py render project.json -d ./export
"""
from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path

from analyzer import recognize, detect_red_strikes, render_pdf
from core import reconstruct_document, ManuscriptError
from vision_adapter import analyze_vision

IMAGE_TYPES={'.png':'png','.jpg':'jpeg','.jpeg':'jpeg','.webp':'webp'}

def read_document(images, engine, marks, vision_model):
    pages=[]
    for path in images:
        path=Path(path)
        if not path.is_file():raise ManuscriptError(f'文件不存在：{path}')
        data=path.read_bytes()
        inputs=[]
        if path.suffix.lower()=='.pdf':
            inputs=[(p['name'],p['data'],'png') for p in render_pdf(data)]
        elif path.suffix.lower() in IMAGE_TYPES:
            inputs=[(path.name,data,IMAGE_TYPES[path.suffix.lower()])]
        else:raise ManuscriptError(f'不支持输入文件：{path.name}')
        for name,img,fmt in inputs:
            d=recognize(img,engine=engine)
            page={'id':f'page_{len(pages)+1}', 'name':name,
                  'image':f'data:image/{fmt};base64,'+base64.b64encode(img).decode('ascii'),
                  'tokens':d['tokens'],'edits':[]}
            if marks:
                page['edits'].extend(detect_red_strikes(img,page['tokens']))
            if vision_model:
                v=analyze_vision(img,page['tokens'],vision_model)
                page['edits'].extend(v['proposals'])
                page['visionReview']={'unmatched':v['unmatched'],'uncertain':v['uncertain'],
                                       'transcription_lines':v['transcription_lines']}
            pages.append(page)
    return {'version':'1.0','name':'自动导入的手稿项目','pages':pages}

def render_project(path, destination):
    data=json.loads(Path(path).read_text(encoding='utf-8'))
    result=reconstruct_document(data)
    dest=Path(destination);dest.mkdir(parents=True,exist_ok=True)
    (dest/'original.txt').write_text(result['original'],encoding='utf-8')
    (dest/'final.txt').write_text(result['final'],encoding='utf-8')
    (dest/'operations.json').write_text(json.dumps({
        'operations':result['operations'],
        'pending': [{'page':i+1,'edits':p['pending']} for i,p in enumerate(result['pages']) if p['pending']],
        'rejected': [{'page':i+1,'edits':p['rejected']} for i,p in enumerate(result['pages']) if p['rejected']]},ensure_ascii=False,indent=2),encoding='utf-8')
    report=[f'页面数：{len(result["pages"])}',f'确认修改：{result["counts"]["confirmed"]}',
            f'尚待核对：{result["counts"]["pending"]}',
            '注意：OCR字句和所有自动建议需要按原始图像核实；未确认修改不会进入终稿。']
    (dest/'review.txt').write_text('\n'.join(report),encoding='utf-8')
    return result

def main():
    p=argparse.ArgumentParser(description='ManuscriptRestorer command line')
    sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('analyze',help='对图片/PDF运行本地OCR并建立待审项目')
    a.add_argument('files',nargs='+')
    a.add_argument('-o','--output',default='manuscript_project.json')
    a.add_argument('--engine',choices=['auto','tesseract','paddle'],default='auto')
    a.add_argument('--no-marks',action='store_true')
    a.add_argument('--vision-model',help='可选本地Ollama视觉模型，如qwen3-vl:4b')
    r=sub.add_parser('render',help='重建原稿与终稿')
    r.add_argument('project');r.add_argument('-d','--dest',default='export')
    args=p.parse_args()
    if args.command=='analyze':
        d=read_document(args.files,args.engine,not args.no_marks,args.vision_model)
        Path(args.output).write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
        print(f'已建立：{args.output}，共{len(d["pages"])}页；请人工确认OCR和待审修改。')
    else:
        d=render_project(args.project,args.dest)
        print(f'已导出到{args.dest}：原稿、终稿、修改记录、审阅报告。待审{d["counts"]["pending"]}项。')
if __name__=='__main__':
    try:main()
    except (ManuscriptError,RuntimeError) as e:raise SystemExit(f'错误：{e}')
