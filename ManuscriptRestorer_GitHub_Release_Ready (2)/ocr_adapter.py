"""PaddleOCR 3.x 可选接口：OCR 只是候选文本，不能把模型输出当成已确认事实。"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any


def _xyxy(poly: Any):
    if hasattr(poly, "tolist"):
        poly = poly.tolist()
    if not poly:
        return None
    if len(poly) == 4 and all(isinstance(n, (int, float)) for n in poly):
        x1, y1, x2, y2 = poly
        return [round(float(x1), 1), round(float(y1), 1), round(float(x2), 1), round(float(y2), 1)]
    try:
        return [
            round(float(min(p[0] for p in poly)), 1),
            round(float(min(p[1] for p in poly)), 1),
            round(float(max(p[0] for p in poly)), 1),
            round(float(max(p[1] for p in poly)), 1),
        ]
    except (ValueError, IndexError, TypeError):
        return None


def parse_ocr_payload(payload: dict) -> list[dict]:
    """将 PaddleOCR 3.x 的 rec_texts/rec_boxes/rec_polys 转换为片段。

    文本行通过中心点高度+中位行高分组，保留原文与模型置信度。
    """
    if "res" in payload and isinstance(payload["res"], dict):
        payload = payload["res"]
    texts = payload.get("rec_texts", [])
    boxes = payload.get("rec_boxes")
    if boxes is None:
        boxes = payload.get("rec_polys", [])
    scores = payload.get("rec_scores", [])
    if hasattr(boxes, "tolist"):
        boxes = boxes.tolist()
    if hasattr(scores, "tolist"):
        scores = scores.tolist()
    if not isinstance(texts, list):
        texts = list(texts)
    output = []
    for i, s in enumerate(texts):
        if not s or not isinstance(s, str):
            continue
        b = _xyxy(boxes[i]) if boxes is not None and i < len(boxes) else None
        if b is None:
            continue
        confidence = float(scores[i]) if i < len(scores) else None
        if confidence is not None and (math.isnan(confidence) or math.isinf(confidence)):
            confidence = None
        output.append({"id": f"ocr_{i+1}", "text": s, "bbox": b,
                       "confidence": confidence, "source": "paddleocr"})
    if not output:
        return []
    heights = sorted(t["bbox"][3] - t["bbox"][1] for t in output)
    typical_h = heights[len(heights) // 2]
    # OCR输出的是字词或整行；使用纵向中点接近进行分行，不凭文字内容猜测。
    by_y = sorted(output, key=lambda t: ((t["bbox"][1]+t["bbox"][3])/2, t["bbox"][0]))
    groups = []
    for item in by_y:
        cy = (item["bbox"][1]+item["bbox"][3])/2
        if groups and abs(cy - groups[-1]["cy"]) <= max(8.0, typical_h * 0.45):
            group = groups[-1]
            group["items"].append(item)
            n = len(group["items"])
            group["cy"] += (cy - group["cy"]) / n
        else:
            groups.append({"cy": cy, "items": [item]})
    result = []
    for ln, group in enumerate(groups):
        for pos, item in enumerate(sorted(group["items"], key=lambda t: t["bbox"][0])):
            result.append({**item, "line": ln, "order": pos})
    return result


def run_paddleocr(image_path: str | Path) -> list[dict]:
    try:
        from paddleocr import PaddleOCR
    except ImportError as exc:
        raise RuntimeError(
            "尚未安装 PaddleOCR。请先 pip install paddlepaddle paddleocr，"
            "再重新启动。也可直接使用手动标注与示例模式。"
        ) from exc
    # 模型可能在首次运行时下载，离线使用前需提前缓存模型。
    ocr = PaddleOCR(
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
    )
    collected = []
    for result in ocr.predict(str(image_path)):
        data = result.json if hasattr(result, "json") else result
        collected.extend(parse_ocr_payload(data))
    # 多页未来可增加 page 字段；当前限制单幅图片。
    for i, token in enumerate(collected):
        token["id"] = f"ocr_{i+1}"
    return collected
