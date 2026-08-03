"""
RapidOCR → 줄(line) 단위 코드 그룹 - Cloudtype 최종
"""
import re
import uuid
from functools import lru_cache

CHORD_FULL = re.compile(
    r'^([A-G](?:#|b)?(?:maj|min|m|dim|aug|sus|add|M|°)?(?:\d{1,2})?(?:maj7|min7|m7|M7|dim7|sus2|sus4|add9|add11)?(?:/[A-G](?:#|b)?)?)$',
    re.IGNORECASE,
)
CHORD_IN_TEXT = re.compile(
    r'\b([A-G](?:#|b)?(?:maj|min|m|dim|aug|sus|add|M)?(?:\d{0,2})?(?:maj7|min7|m7|M7|dim7|sus2|sus4|add9)?(?:/[A-G](?:#|b)?)?)\b',
    re.IGNORECASE,
)

LINE_Y_THRESHOLD = 0.025  # 같은 줄 판단 y 차이

def _to_list(obj):
    if obj is None: return []
    if isinstance(obj, list): return obj
    try: return obj.tolist()
    except: return list(obj) if isinstance(obj, (tuple, set)) else []

def _box_to_norm(box, img_w, img_h):
    if not box or not img_w or not img_h: return None
    try:
        pts = _to_list(box)
        xs, ys = [], []
        if pts and isinstance(pts[0], (list, tuple)):
            for pt in pts: xs.append(float(pt[0])); ys.append(float(pt[1]))
        else:
            coords = [float(v) for v in pts]; xs, ys = coords[0::2], coords[1::2]
        if not xs: return None
        return {
            'x': round(min(xs)/img_w,5), 'y': round(min(ys)/img_h,5),
            'w': round(max(max(xs)-min(xs),1)/img_w,5),
            'h': round(max(max(ys)-min(ys),1)/img_h,5),
        }
    except: return None

def _looks_like_chord(token: str) -> bool:
    token = (token or '').strip()
    if not token or len(token)>12: return False
    return bool(CHORD_FULL.match(token))

@lru_cache(maxsize=1)
def get_ocr_engine():
    from rapidocr_onnxruntime import RapidOCR
    return RapidOCR(lang='korean_english', det_limit_side_len=1280)

def _flat_chord_hits(ocr_lines: list) -> list:
    hits=[]
    for line in ocr_lines:
        text=(line.get('text') or '').strip()
        norm=line.get('norm'); conf=line.get('confidence',0)
        y=(norm or {}).get('y',0.1); x=(norm or {}).get('x',0.05)
        if _looks_like_chord(text):
            hits.append({'chord':text,'x':x,'y':y,'confidence':conf}); continue
        for m in CHORD_IN_TEXT.finditer(text):
            token=m.group(1)
            if not _looks_like_chord(token): continue
            if norm:
                ratio=m.start()/max(len(text),1)
                cx=round(norm['x']+norm['w']*ratio,5); cy=norm['y']
            else: cx,cy=0.05,0.1
            hits.append({'chord':token,'x':cx,'y':cy,'confidence':conf})
    return hits

def group_hits_into_lines(hits: list) -> list:
    if not hits: return []
    sorted_hits=sorted(hits, key=lambda h:(h.get('y',0),h.get('x',0)))
    clusters=[]
    for h in sorted_hits:
        placed=False
        for cl in clusters:
            avg_y=sum(c['y'] for c in cl)/len(cl)
            if abs(h['y']-avg_y)<=LINE_Y_THRESHOLD: cl.append(h); placed=True; break
        if not placed: clusters.append([h])
    lines_out=[]
    for cl in clusters:
        cl.sort(key=lambda c:c.get('x',0))
        y=sum(c['y'] for c in cl)/len(cl)
        items=[{'id':uuid.uuid4().hex[:8],'chord':c['chord'],'t':round(max(0.02,min(0.98,c['x'])),5),'x_abs':round(c['x'],5)} for c in cl]
        lines_out.append({'id':'L'+uuid.uuid4().hex[:6],'y':round(min(0.98,max(0.02,y)),5),'xStart':0.01,'xEnd':0.99,'height':0.028,'items':items})
    lines_out.sort(key=lambda L:L['y'])
    return lines_out

def run_ocr(image_path: str) -> dict:
    from PIL import Image
    img_w=img_h=None
    try:
        with Image.open(image_path) as im: img_w,img_h=im.size
    except: pass

    ocr=get_ocr_engine()
    # RapidOCR API: (result, elapse)  where result = [[box,text,score],...]
    raw_result=ocr(str(image_path))
    result_list = raw_result[0] if isinstance(raw_result, tuple) else raw_result

    ocr_lines=[]; raw_texts=[]
    if result_list:
        # 구버전 object(txts/boxes) 대응도 포함
        if hasattr(result_list,'txts'):
            txts=_to_list(result_list.txts); boxes=_to_list(getattr(result_list,'boxes',[]))
            for i,txt in enumerate(txts):
                box=boxes[i] if i < len(boxes) else None
                txt=str(txt).strip()
                if not txt: continue
                norm=_box_to_norm(box,img_w,img_h)
                ocr_lines.append({'text':txt,'confidence':0.9,'box':box,'norm':norm}); raw_texts.append(txt)
        else:
            for item in result_list:
                if not item or len(item)<2: continue
                box, text = item[0], item[1]
                score = item[2] if len(item)>2 else 0.9
                text=str(text).strip()
                if not text: continue
                norm=_box_to_norm(box,img_w,img_h)
                ocr_lines.append({'text':text,'confidence':float(score) if isinstance(score,(int,float)) else 0.9,'box':box,'norm':norm})
                raw_texts.append(text)

    hits=_flat_chord_hits(ocr_lines)
    lines=group_hits_into_lines(hits)

    return {
        'raw_text':'\n'.join(raw_texts),
        'ocr_raw_text':'\n'.join(raw_texts),
        'txts': raw_texts,
        'lines':[{'text':l.get('text'),'confidence':l.get('confidence'),'norm':l.get('norm')} for l in ocr_lines],
        'chord_lines':lines,
        'chords':lines,
        'chord_candidates':[it['chord'] for L in lines for it in L['items']],
        'image_size':{'width':img_w,'height':img_h},
    }
