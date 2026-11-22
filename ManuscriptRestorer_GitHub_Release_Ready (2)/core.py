"""ManuscriptRestorer: deterministic, auditable reconstruction engine.

No OCR guesses are applied automatically.  Edits are explicit byte-independent
Unicode codepoint intervals on immutable source text.
"""
from __future__ import annotations

import math
from typing import Any

VERSION = "1.0"
OPS = {"replace", "delete", "insert_before", "insert_after"}
STATUSES = {"confirmed", "proposed", "rejected"}

class ManuscriptError(ValueError):
    pass

def _nonempty(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ManuscriptError(f"{label}必须是非空字符串")
    return value

def _rect(rect, label):
    if rect is None:
        return
    if not isinstance(rect, list) or len(rect) != 4 or any(
        not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) for v in rect
    ) or rect[0] >= rect[2] or rect[1] >= rect[3]:
        raise ManuscriptError(f"{label}: bbox无效，应为[x1,y1,x2,y2]")

def _span(edit, token):
    length = len(token["text"])
    op = edit["op"]
    default = [0, length] if op in ("replace", "delete") else ([0, 0] if op == "insert_before" else [length, length])
    span = edit.get("span", default)
    if not isinstance(span, list) or len(span) != 2 or any(type(n) is not int for n in span):
        raise ManuscriptError(f"修改{edit['id']}的字符范围必须是[start,end]")
    start, end = span
    if start < 0 or end > length or start > end:
        raise ManuscriptError(f"修改{edit['id']}字符范围越界")
    if op in ("replace", "delete") and start == end:
        raise ManuscriptError(f"修改{edit['id']}删除/替换范围不能为空")
    if op in ("insert_before", "insert_after") and start != end:
        raise ManuscriptError(f"修改{edit['id']}插入位置应为[pos,pos]")
    return [start, end]

def reconstruct(page: dict) -> dict:
    """Reconstruct one page from tokens and confirmed edit events."""
    if not isinstance(page, dict):
        raise ManuscriptError("页面必须是对象")
    tokens, edits = page.get("tokens", []), page.get("edits", [])
    if not isinstance(tokens, list) or len(tokens) > 5000:
        raise ManuscriptError("tokens最多5000项")
    if not isinstance(edits, list) or len(edits) > 10000:
        raise ManuscriptError("edits最多10000项")
    ids, mapped = set(), {}
    ordered = []
    for index, token in enumerate(tokens):
        if not isinstance(token, dict):
            raise ManuscriptError(f"第{index+1}个文字框无效")
        tid = _nonempty(token.get("id"), "文字框ID")
        if tid in ids:
            raise ManuscriptError(f"文字框ID重复：{tid}")
        ids.add(tid)
        if not isinstance(token.get("text"), str) or not token["text"]:
            raise ManuscriptError(f"文字框{tid}原文不能为空")
        line = token.get("line", 0)
        order = token.get("order", index)
        if type(line) is not int or not (0 <= line < 100000):
            raise ManuscriptError(f"文字框{tid}行号无效")
        if type(order) not in (int, float) or not math.isfinite(order):
            raise ManuscriptError(f"文字框{tid}顺序无效")
        _rect(token.get("bbox"), f"文字框{tid}")
        ordered.append((line, order, index, token))
        mapped[tid] = token
    ordered.sort(key=lambda x: x[:3])
    seen, confirmed, pending, rejected = set(), [], [], []
    bytarget = {}
    for index, edit in enumerate(edits):
        if not isinstance(edit, dict):
            raise ManuscriptError(f"第{index+1}条修改无效")
        eid = _nonempty(edit.get("id"), "修改ID")
        if eid in seen:
            raise ManuscriptError(f"修改ID重复：{eid}")
        seen.add(eid)
        op = edit.get("op")
        status = edit.get("status", "proposed")
        if op not in OPS or status not in STATUSES:
            raise ManuscriptError(f"修改{eid}操作或状态无效")
        tid = edit.get("target_id")
        if tid not in mapped:
            raise ManuscriptError(f"修改{eid}指向不存在的文字框：{tid}")
        value = edit.get("text", "")
        if not isinstance(value, str) or (op != "delete" and not value):
            raise ManuscriptError(f"修改{eid}新文字无效")
        _rect(edit.get("bbox"), f"修改{eid}")
        span = _span(edit, mapped[tid])
        normalized = {**edit, "span": span, "status": status, "text": value}
        if status == "confirmed":
            confirmed.append(normalized)
            bytarget.setdefault(tid, []).append(normalized)
        elif status == "proposed":
            pending.append(normalized)
        else:
            rejected.append(normalized)

    original_lines, final_lines = [], []
    last_line = None
    source_run, final_run = [], []
    for line, _, _, token in ordered:
        if last_line is not None and line != last_line:
            original_lines.append("".join(source_run))
            final_lines.append("".join(final_run))
            source_run, final_run = [], []
        last_line = line
        content, tid = token["text"], token["id"]
        source_run.append(content)
        changes = bytarget.get(tid, [])
        structural = sorted([e for e in changes if e["op"] in ("delete", "replace")], key=lambda e: e["span"][0])
        inserts = {}
        for e in changes:
            if e["op"] in ("insert_before", "insert_after"):
                pos = e["span"][0]
                inserts.setdefault(pos, []).append(e["text"])
        for i in range(1, len(structural)):
            if structural[i]["span"][0] < structural[i-1]["span"][1]:
                raise ManuscriptError(f"文字框{tid}存在重叠的已确认替换/删除")
        for pos in inserts:
            if any(a["span"][0] < pos < a["span"][1] for a in structural):
                raise ManuscriptError(f"文字框{tid}的插入位置落入删除/替换范围内部")
        i = 0
        j = 0
        pieces = []
        while i <= len(content):
            pieces.extend(inserts.get(i, []))
            if i == len(content):
                break
            if j < len(structural) and structural[j]["span"][0] == i:
                e = structural[j]
                if e["op"] == "replace":
                    pieces.append(e["text"])
                i = e["span"][1]
                j += 1
            else:
                pieces.append(content[i])
                i += 1
        final_run.append("".join(pieces))
    if ordered:
        original_lines.append("".join(source_run))
        final_lines.append("".join(final_run))
    operations = []
    for e in confirmed:
        token = mapped[e["target_id"]]
        a, b = e["span"]
        operations.append({
            "id": e["id"], "op": e["op"], "status": "confirmed",
            "target_id": e["target_id"], "span": e["span"],
            "before": token["text"][a:b], "after": e["text"] if e["op"] != "delete" else "",
            "target_bbox": token.get("bbox"), "mark_bbox": e.get("bbox"),
            "source": e.get("source", "manual"), "confidence": e.get("confidence"),
        })
    return {"version": VERSION, "original": "\n".join(original_lines), "final": "\n".join(final_lines),
            "operations": operations, "pending": pending, "rejected": rejected,
            "counts": {"tokens": len(tokens), "confirmed": len(confirmed), "pending": len(pending), "rejected": len(rejected)}}

def reconstruct_document(document: dict) -> dict:
    pages = document.get("pages") if isinstance(document, dict) else None
    if not isinstance(pages, list) or len(pages) > 30:
        raise ManuscriptError("项目必须包含最多30页的pages数组")
    parts = [reconstruct(page) for page in pages]
    operations = [dict(e, page=index+1) for index, item in enumerate(parts) for e in item["operations"]]
    return {"version": VERSION, "pages": parts,
            "original": "\n\n".join(p["original"] for p in parts),
            "final": "\n\n".join(p["final"] for p in parts),
            "operations": operations,
            "counts": {k: sum(item["counts"][k] for item in parts)
                       for k in ("tokens", "confirmed", "pending", "rejected")}}
