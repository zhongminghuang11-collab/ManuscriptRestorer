"""Optional *local* Ollama vision inference. All suggestions require review.

An OCR result alone cannot decode complex edit glyphs. A vision model can
provide proposals, but its output is never automatically treated as evidence.
"""
from __future__ import annotations

import base64
import json
import re
from urllib.request import Request, urlopen
from urllib.error import URLError
import uuid

from core import ManuscriptError

OLLAMA_CHAT = 'http://127.0.0.1:11434/api/chat'
PROMPT = '''你是中文手写修改稿的谨慎校勘助手。你的任务不是作文润色或纠错，只识别图像中真实可见的人工修改痕迹。
严格输出一个JSON对象，字段：
{
 "transcription_lines": ["每一行未修改前的原始文字，尽可能逐字忠实；看不清的写□"],
 "suggested_edits": [{"op":"replace|delete|insert_before|insert_after", "original":"确实被编辑的原文小片段，插入时为唯一的锚定文字", "replacement":"替换或插入的文字，删除时空字符串", "evidence":"描述哪一个划线、添字、箭头等证据"}],
 "uncertain": ["无法可靠识别的字、符号和原因"]
}
不要根据语法改写手稿，不要从常识猜测词句，不要创作看不到的修改。只要不确定就写入uncertain，不要编造。
每项original尽量是长度短的唯一原文锚点，方便与OCR原文匹配。禁止自动认为手稿上所有红色字都是替换文字。'''


def _jsonish(text):
    text=text.strip()
    if text.startswith('```'):
        text=re.sub(r'^```(?:json)?\s*','',text)
        text=re.sub(r'\s*```$','',text)
    try:return json.loads(text)
    except ValueError:
        a,b=text.find('{'),text.rfind('}')
        if 0<=a<b:return json.loads(text[a:b+1])
        raise


def ground_suggestions(raw:dict,tokens:list[dict]):
    """Ground model edit proposals to *unique* observed text; reject ambiguity."""
    if not isinstance(raw,dict):raise ManuscriptError('视觉模型返回结果不是JSON对象')
    suggestions=raw.get('suggested_edits',[])
    if not isinstance(suggestions,list):raise ManuscriptError('模型的suggested_edits格式无效')
    proposals=[]
    unmatched=[]
    for s in suggestions[:60]:
        if not isinstance(s,dict):continue
        op=s.get('op')
        original=s.get('original')
        replacement=s.get('replacement','')
        if op not in ('replace','delete','insert_before','insert_after') or not isinstance(original,str) or not original.strip() or len(original)>80 or not isinstance(replacement,str) or len(replacement)>200:
            unmatched.append({'suggestion':s,'reason':'字段缺失或操作不受支持'})
            continue
        if op!='delete' and not replacement.strip():
            unmatched.append({'suggestion':s,'reason':'缺少替换或插入文字'})
            continue
        # match must be globally unique, otherwise model may point at wrong passage
        candidates=[]
        for token in tokens:
            hay=token.get('text','')
            if not isinstance(hay,str):continue
            begin=0
            while True:
                j=hay.find(original,begin)
                if j<0:break
                candidates.append((token,j))
                begin=j+1
        if len(candidates)!=1:
            unmatched.append({'suggestion':s,'reason':f'未找到唯一OCR锚点（匹配{len(candidates)}处）'})
            continue
        token,j=candidates[0]
        span = [j,j+len(original)] if op in ('replace','delete') else ([j,j] if op=='insert_before' else [j+len(original),j+len(original)])
        proposals.append({'id':'vision_'+uuid.uuid4().hex[:12], 'op':op,
                          'target_id':token['id'],'span':span,'text':replacement if op!='delete' else '',
                          'source':'ollama-vision','status':'proposed',
                          'reason':str(s.get('evidence',''))[:250]})
    transcription=raw.get('transcription_lines',[])
    if not isinstance(transcription,list):transcription=[]
    uncertainty=raw.get('uncertain',[])
    if not isinstance(uncertainty,list):uncertainty=[]
    return {'proposals':proposals, 'unmatched':unmatched,
            'transcription_lines':[t[:2000] for t in transcription[:250] if isinstance(t,str)],
            'uncertain':[str(t)[:300] for t in uncertainty[:100]]}


def analyze_vision(image_bytes:bytes,tokens:list[dict],model:str):
    if not isinstance(model,str) or not re.fullmatch(r'[a-zA-Z0-9_.:/-]{1,90}',model):
        raise ManuscriptError('本地Ollama模型名称无效')
    if not isinstance(tokens,list) or len(tokens)>5000:
        raise ManuscriptError('文字框数组无效')
    reference='\n'.join(f"L{t.get('line',0)}: {t.get('text','')}" for t in tokens[:600])
    user_prompt='请分析这张真实手稿图片。以下是未校验的OCR结果，仅供定位，不可当作图像真相：\n'+reference[:12000]
    payload={'model':model, 'stream':False, 'format':'json',
             'messages':[{'role':'system','content':PROMPT},
                         {'role':'user','content':user_prompt,'images':[base64.b64encode(image_bytes).decode('ascii')]}],
             'options':{'temperature':0}}
    raw=json.dumps(payload,ensure_ascii=False).encode('utf-8')
    request=Request(OLLAMA_CHAT,raw,{'Content-Type':'application/json'},method='POST')
    try:
        with urlopen(request,timeout=240) as response:
            result=json.loads(response.read(2*1024*1024))
    except (TimeoutError,URLError,ValueError) as exc:
        raise RuntimeError('连接本地Ollama失败或推理超时；请确认已安装Ollama、已下载视觉模型且本地服务运行') from exc
    try:model_text=result['message']['content']
    except (KeyError,TypeError):
        raise RuntimeError('Ollama没有返回模型文本，请检查模型是否支持图像')
    try:parsed=_jsonish(model_text)
    except (ValueError,TypeError):
        raise RuntimeError('视觉模型没有返回有效JSON，建议使用支持结构化输出的模型')
    return ground_suggestions(parsed,tokens)
