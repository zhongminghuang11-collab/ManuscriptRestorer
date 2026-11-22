"""Image handling, real local OCR, conservative pen-mark candidate detection.

This does NOT promise semantic interpretation of arrows, marginalia, or all
handwritten corrections. All geometric guesses stay unconfirmed.
"""
from __future__ import annotations

from io import BytesIO
import math
import shutil
import uuid

from PIL import Image, ImageOps, ImageEnhance
from core import ManuscriptError
from ocr_adapter import run_paddleocr

MAX_PIXELS = 15_000_000
Image.MAX_IMAGE_PIXELS = MAX_PIXELS


def load_image(data: bytes) -> Image.Image:
    if len(data) > 16 * 1024 * 1024:
        raise ManuscriptError("图像不得超过16MB")
    try:
        with Image.open(BytesIO(data)) as im:
            if im.format not in ("PNG", "JPEG", "WEBP"):
                raise ManuscriptError("只支持PNG、JPEG、WebP")
            if im.width * im.height > MAX_PIXELS:
                raise ManuscriptError("图片像素总数过高，超过1500万")
            return ImageOps.exif_transpose(im).convert("RGB")
    except (OSError, ValueError) as exc:
        raise ManuscriptError("无法解码图像") from exc


def red_mask(im: Image.Image):
    import numpy as np
    data = np.asarray(im.convert("RGB"), dtype=np.int16)
    r, g, b = data[..., 0], data[..., 1], data[..., 2]
    # Red handwriting: protect dark ink from removal, allow pale ink via relative contrast.
    return (r >= 115) & (r > (g * 1.4)) & (r > (b * 1.40)) & ((r-g) > 38)


def clean_red(im: Image.Image) -> Image.Image:
    import numpy as np
    data = np.asarray(im.convert("RGB")).copy()
    m = red_mask(im)
    data[m] = [255,255,255]
    return Image.fromarray(data, "RGB")


def _roi_box(roi, size):
    if roi is None:
        return [0,0,size[0],size[1]]
    if not isinstance(roi, list) or len(roi) != 4 or any(type(n) not in (int, float) or not math.isfinite(n) for n in roi):
        raise ManuscriptError("OCR选区不是有效坐标")
    x1,y1,x2,y2 = [int(round(n)) for n in roi]
    x1, y1 = max(0,x1),max(0,y1)
    x2, y2 = min(size[0],x2),min(size[1],y2)
    if x2-x1 < 12 or y2-y1 < 12:
        raise ManuscriptError("OCR选区太小")
    return [x1,y1,x2,y2]


def _tesseract(im: Image.Image, language="chi_sim+eng", psm=6):
    if not shutil.which("tesseract"):
        raise RuntimeError("未找到Tesseract可执行程序；请安装Tesseract OCR及中文chi_sim语言包")
    try:
        import pytesseract
    except ImportError as exc:
        raise RuntimeError("请先 pip install -r requirements.txt 安装pytesseract") from exc
    try:
        d = pytesseract.image_to_data(im, lang=language, config=f"--psm {psm}", output_type=pytesseract.Output.DICT, timeout=120)
    except pytesseract.TesseractError as exc:
        raise RuntimeError(f"OCR识别失败，请核实已安装chi_sim中文语言包：{str(exc)[:350]}") from exc
    except RuntimeError as exc:
        raise RuntimeError(f"OCR超时：{exc}") from exc
    words = []
    for i, raw in enumerate(d["text"]):
        txt = raw.strip()
        if not txt:
            continue
        conf = float(d["conf"][i])
        if conf < -0.1:
            continue
        x,y,w,h = (int(d[k][i]) for k in ("left","top","width","height"))
        if w<1 or h<1:
            continue
        words.append({"text": txt, "bbox": [x,y,x+w,y+h],
                      "confidence": round(max(0.0, conf/100),3),
                      "block": (d["block_num"][i],d["par_num"][i],d["line_num"][i])})
    return words


def _group_words(words, offset=(0,0), prefix="ocr", source="tesseract"):
    """Keep OCR word fragments; order lines by bbox rather than unstable OCR indices."""
    if not words:
        return []
    lines = {}
    for i, item in enumerate(words):
        key = item.get("block", (0,0,i))
        lines.setdefault(key, []).append(item)
    ordered_lines = sorted(lines.values(), key=lambda row: (sum(w["bbox"][1] for w in row)/len(row), min(w["bbox"][0] for w in row)))
    result = []
    for line_index, line in enumerate(ordered_lines):
        for pos, item in enumerate(sorted(line, key=lambda w: w["bbox"][0])):
            box = item["bbox"]
            result.append({"id": f"{prefix}_{len(result)+1}", "text": item["text"],
                           "bbox": [box[0]+offset[0],box[1]+offset[1],box[2]+offset[0],box[3]+offset[1]],
                           "line": line_index, "order": pos,
                           "confidence": item.get("confidence"), "source": source})
    return result



def _tesseract_dual(im, language="chi_sim+eng"):
    """Compare OCR of color image and image with red ink masked out.

    Keep the higher-scoring line where spatially aligned. Suppress *only*
    red-dominant annotation lines; do not silently erase uncertain black text.
    """
    import numpy as np
    raw_words=_tesseract(im,language=language)
    cleaned_words=_tesseract(clean_red(im),language=language)
    mask=red_mask(im)
    pixels=np.asarray(im.convert("RGB"))
    def groups(words):
        by={}
        for w in words:by.setdefault(w['block'],[]).append(w)
        out=[]
        for row in by.values():
            ys=[(w['bbox'][1]+w['bbox'][3])/2 for w in row]
            hs=[w['bbox'][3]-w['bbox'][1] for w in row]
            conf=sum(w['confidence'] for w in row)/max(1,len(row))
            red,ink=0,0
            for w in row:
                x1,y1,x2,y2=w['bbox'];sub=pixels[y1:y2,x1:x2];m=mask[y1:y2,x1:x2]
                red+=int(m.sum());ink+=int((sub.min(2)<210).sum())
            ratio=red/max(1,ink)
            out.append({'words':row,'cy':sum(ys)/len(ys),'height':sum(hs)/len(hs),
                        'conf':conf,'red_ratio':ratio})
        return sorted(out,key=lambda d:d['cy'])
    a=groups(raw_words);b=groups(cleaned_words)
    chosen=[]
    used=set()
    for raw in a:
        # Remove clearly red-only marginal handwriting (save as possible mark elsewhere).
        if raw['red_ratio']>.68:
            continue
        hits=[(abs(q['cy']-raw['cy']),i,q) for i,q in enumerate(b)
              if i not in used and abs(q['cy']-raw['cy'])<max(19,min(q['height'],raw['height'])*.6)]
        if hits:
            _,i,q=min(hits,key=lambda item:item[0]);used.add(i)
            winner=q if q['conf'] > raw['conf']+.035 else raw
        else:winner=raw
        chosen.append(winner)
    for i,q in enumerate(b):
        if i not in used and not any(abs(g['cy']-q['cy'])<max(19,q['height']*.6) for g in chosen):
            chosen.append(q)
    chosen.sort(key=lambda d:d['cy'])
    result=[]
    for i,g in enumerate(chosen):
        for pos,w in enumerate(sorted(g['words'],key=lambda item:item['bbox'][0])):
            result.append({'id':f'ocr_{len(result)+1}','text':w['text'],'bbox':w['bbox'],
                           'confidence':w['confidence'], 'source':'tesseract-dual',
                           'line':i,'order':pos})
    return result

def recognize(image_bytes: bytes, engine="auto", roi=None, language="chi_sim+eng", remove_red=True):
    im = load_image(image_bytes)
    box = _roi_box(roi, im.size)
    cropped = im.crop(tuple(box))
    if engine not in ("auto", "tesseract", "paddle"):
        raise ManuscriptError("OCR引擎无效")
    if engine == "paddle" or (engine == "auto" and _paddle_installed()):
        from pathlib import Path
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "page.png"
            (clean_red(cropped) if remove_red else cropped).save(path)
            try:
                tokens = run_paddleocr(path)
            except Exception:
                if engine == "paddle":
                    raise
                tokens = None
        if tokens is not None:
            for t in tokens:
                t["bbox"] = [n + (box[0] if i % 2 == 0 else box[1]) for i,n in enumerate(t["bbox"])]
                t["source"] = "paddleocr"
                t["id"] = "ocr_" + uuid.uuid4().hex[:10]
            return {"tokens": tokens, "engine": "paddle", "roi":box}
    if remove_red:
        tokens=_tesseract_dual(cropped,language=language)
        for t in tokens:
            t['bbox']=[v+(box[0] if i%2==0 else box[1]) for i,v in enumerate(t['bbox'])]
        return {"tokens":tokens,"engine":"tesseract-dual", "roi":box}
    words = _tesseract(cropped, language=language, psm=6)
    tokens = _group_words(words, offset=box[:2])
    return {"tokens": tokens, "engine": "tesseract", "roi":box}


def _paddle_installed():
    from importlib.util import find_spec
    return find_spec("paddleocr") is not None


def detect_red_strikes(image_bytes: bytes, tokens: list[dict]):
    """A conservative horizontal-red-stroke heuristic; span suggestions are NOT authoritative.

    Handles single or multi-token lines. Rejects short underlines and
    unfilled red annotation text. Estimates character spans geometrically.
    """
    import numpy as np
    im = load_image(image_bytes)
    mask = red_mask(im)
    hh, ww = mask.shape
    proposals, seen = [], set()
    for token in tokens:
        tid, bbox, text = token.get("id"), token.get("bbox"), token.get("text", "")
        if not bbox or not text or len(bbox) != 4 or tid in seen:
            continue
        x1,y1,x2,y2 = [int(round(v)) for v in bbox]
        x1,y1,x2,y2 = max(0,x1),max(0,y1),min(ww,x2),min(hh,y2)
        w,h = x2-x1,y2-y1
        if w<9 or h<9:
            continue
        # permit stroke 1-4 px outside the recognized box; text-only red margin not included.
        left,right = max(0,x1-3),min(ww,x2+3)
        top,bottom = max(0,y1+int(h*.20)),min(hh,y1+int(h*.83))
        best=None
        for y in range(top,bottom):
            # spatial continuity with tolerance for partially hidden character strokes
            line = mask[y,left:right]
            pts = np.flatnonzero(line)
            if pts.size < 7:
                continue
            # largest horizontal red run with gaps up to 8 pixels
            splits = np.where(np.diff(pts) > 8)[0]
            starts = np.r_[0,splits+1]
            ends = np.r_[splits,pts.size-1]
            for a,b in zip(starts,ends):
                xs = pts[a:b+1]
                span_width = int(xs[-1]-xs[0]+1)
                if span_width < max(16,int(w*.20)):
                    continue
                density=len(xs)/span_width
                if density<.46:
                    continue
                score = span_width*density
                if best is None or score>best[0]:
                    best = (score,y,left+int(xs[0]),left+int(xs[-1])+1,density)
        if best is None:
            continue
        _,y,mark_left,mark_right,density=best
        # underline guard: strike must pass through vertical center region
        if y > y1+h*.78:
            continue
        n = len(text)
        # Char mapping is approximate, inaccurate for mixed-width fonts. Do not auto-confirm.
        start=max(0,min(n-1,round(n*(mark_left-x1)/w)))
        end=max(start+1,min(n,round(n*(mark_right-x1)/w)))
        # expand one character for narrow, uncertain strokes if completely missed otherwise.
        if start>=end:
            continue
        proposals.append({"id": "suggest_"+uuid.uuid4().hex[:12],
                          "op":"delete", "target_id":tid,"span":[start,end],
                          "text":"", "status":"proposed", "source":"red-strike-geometry",
                          "confidence":round(min(.65,max(.15,density*.6)),2),
                          "bbox":[mark_left,max(0,y-3),mark_right,min(hh,y+4)],
                          "reason":"红笔横线疑似划除；字符位置由几何比例估计，请核对范围"})
        seen.add(tid)
    return proposals


def red_annotation_candidates(image_bytes: bytes, max_count=30):
    """Return red pen bounding boxes as evidence; no unsupported semantics.

    Uses cv2 if present. This is optional: its absence never prevents OCR.
    """
    try:
        import cv2
        import numpy as np
    except ImportError:
        return []
    im=load_image(image_bytes)
    mask=(red_mask(im).astype('uint8')*255)
    h,w=mask.shape
    # Connect red characters into groups of nearby writing without merging across full page.
    kernel=cv2.getStructuringElement(cv2.MORPH_RECT,(max(5,w//110),max(2,h//380)))
    joined=cv2.dilate(mask,kernel,iterations=1)
    contours,_=cv2.findContours(joined,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    out=[]
    for c in contours:
        x,y,bw,bh = cv2.boundingRect(c)
        if bw<8 or bh<7 or bw*bh > w*h*.2: continue
        region=mask[y:y+bh,x:x+bw]
        if int((region>0).sum())<20:continue
        out.append({"bbox":[x,y,x+bw,y+bh],"type":"red_ink","area":int((region>0).sum())})
    out.sort(key=lambda a:a['area'],reverse=True)
    return out[:max_count]


def render_pdf(data: bytes, pages_limit=20, dpi=145):
    """Rasterize a bounded PDF in memory using the permissively licensed PDFium binding.

    PDF contents remain on the local machine. Limits are applied before and after
    opening; pages and bitmaps are closed even if rendering fails.
    """
    if not data.startswith(b"%PDF"):
        raise ManuscriptError("不是有效的PDF文件")
    if len(data) > 20 * 1024 * 1024:
        raise ManuscriptError("PDF文件不能超过20MB")
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:
        raise RuntimeError("PDF导入需要pypdfium2：pip install -r requirements.txt") from exc
    try:
        doc = pdfium.PdfDocument(data)
    except Exception as exc:
        raise ManuscriptError("PDF无法打开、需要密码或格式损坏") from exc
    try:
        if len(doc) > pages_limit:
            raise ManuscriptError(f"PDF超过{pages_limit}页上限，请拆分后导入")
        result = []
        for i in range(len(doc)):
            page = doc[i]
            try:
                width, height = page.get_size()
                scale = dpi / 72
                # Avoid rendering large pages at full resolution even once.
                if width <= 0 or height <= 0:
                    raise ManuscriptError("PDF页面尺寸无效")
                pixels = width * height * scale * scale
                if pixels > MAX_PIXELS:
                    scale *= math.sqrt(MAX_PIXELS / pixels) * .98
                bitmap = page.render(scale=scale)
                try:
                    image = bitmap.to_pil().convert("RGB")
                    with BytesIO() as output:
                        image.save(output, format="PNG")
                        result.append({"name": f"PDF第{i+1}页", "data": output.getvalue()})
                finally:
                    bitmap.close()
            finally:
                page.close()
        return result
    finally:
        doc.close()
