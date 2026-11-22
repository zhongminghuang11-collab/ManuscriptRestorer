"""Auditable character-error-rate evaluation on gold transcriptions.

Usage: python evaluate.py <project.json> <gold.json>
Gold JSON example: {"original": "...", "final": "..."}
A fully automatic project may have no confirmed edits; this is explicitly shown.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from core import reconstruct_document


def distance(a:str,b:str) -> int:
    """Levenshtein distance in Unicode code points; O(min(n,m)) memory."""
    if len(b)>len(a):a,b=b,a
    prev=list(range(len(b)+1))
    for i,ca in enumerate(a,1):
        curr=[i]+[0]*len(b)
        for j,cb in enumerate(b,1):
            curr[j]=min(prev[j]+1,curr[j-1]+1,prev[j-1]+(ca!=cb))
        prev=curr
    return prev[-1]


def cer(reference:str,hypothesis:str):
    d=distance(reference,hypothesis)
    return {'errors':d,'reference_length':len(reference),
            'cer':d/max(1,len(reference))}


def evaluate(project:dict,gold:dict):
    output=reconstruct_document(project)
    if not isinstance(gold,dict) or not all(isinstance(gold.get(k),str) for k in ('original','final')):
        raise ValueError('gold.json必须包含original和final两个文本字符串')
    return {'original':cer(gold['original'],output['original']),
            'final':cer(gold['final'],output['final']),
            'confirmed_edits':output['counts']['confirmed'],
            'pending_edits':output['counts']['pending'],
            'note':'这是字符转写CER，不包含修改定位的Precision/Recall/F1；该指标需单独有人工标注。'}


def main():
    p=argparse.ArgumentParser(description='手稿双版本字符错误率评测')
    p.add_argument('project');p.add_argument('gold')
    args=p.parse_args()
    obj=json.loads(Path(args.project).read_text(encoding='utf-8'))
    gold=json.loads(Path(args.gold).read_text(encoding='utf-8'))
    print(json.dumps(evaluate(obj,gold),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
