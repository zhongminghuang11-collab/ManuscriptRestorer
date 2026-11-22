import json
from pathlib import Path
from core import reconstruct_document
from analyzer import detect_red_strikes
root=Path(__file__).resolve().parent
f=json.loads((root/'fixtures/demo.json').read_text(encoding='utf-8'))
r=reconstruct_document({'pages':[f]})
expect_original='今天天气很好，我决定出去走走。\n晚上还要开会。'
expect_final='今天天气不错，我决定顺便出去散步。\n晚上写稿。'
assert r['original']==expect_original,(r['original'],expect_original)
assert r['final']==expect_final,(r['final'],expect_final)
mark=detect_red_strikes((root/'fixtures/demo.png').read_bytes(),f['tokens'])
assert len(mark)>=2
print('双版本重建：PASS')
print('红色划线候选：PASS',len(mark),'项（均未自动确认）')
print('演示修改记录：PASS',len(r['operations']))
