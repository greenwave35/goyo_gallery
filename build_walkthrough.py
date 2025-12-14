#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
assets_new.zip + 그림목록.pdf 를 기반으로
1) index.html (오프라인) 2) 전시_워크쓰루.pdf 를 생성하는 스크립트입니다.

사용:
  python build_walkthrough.py --zip assets_new.zip --pdf 그림목록.pdf --out walkthrough_package

의존:
  pip install pdfplumber pillow reportlab
"""
import argparse, os, re, json, shutil, zipfile, unicodedata
from pathlib import Path
import pdfplumber
from PIL import Image

from reportlab import rl_config
rl_config.useA85 = 0
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image as RLImage, Table, TableStyle
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

def norm(s:str)->str:
    if s is None:
        return ""
    s=str(s).strip()
    s=unicodedata.normalize("NFKC", s)
    s=s.replace("_"," ")
    s=re.sub(r"\s+"," ",s)
    s=re.sub(r"[^0-9A-Za-z가-힣\s]","",s)
    return s.lower().strip()

SECTION_DEF = [
    {
        "id":"s1",
        "title":"에너지의 빛",
        "intro":"파도는 솟구치고, 고요는 멈춰 있으면서도 살아 움직입니다. 이 섹션의 빛은 풍경의 ‘조명’이 아니라, 화면 안에서 공명하며 균형을 찾아가는 ‘기운’입니다. 보이지 않는 세계가 더 오색창연하게 빛난다는 믿음이, 추상과 리듬을 통해 먼저 전시의 문을 엽니다.",
        "orders":[1,2,3,4,5]
    },
    {
        "id":"s2",
        "title":"풍경이 되는 마음",
        "intro":"목련이 환하게 빛나던 봄밤의 가로등, 5월의 푸르름, 늦여름 산책로의 공기. 이 섹션에서 빛은 ‘기억의 온도’가 됩니다. 걸으며 마주친 풍경은 곧 마음의 풍경이 되고, 그 풍경은 다시 누군가를 “환해지게” 하는 기도가 됩니다.",
        "orders":[6,7,8,9,10]
    },
    {
        "id":"s3",
        "title":"사람의 빛",
        "intro":"등 뒤에서 느껴지는 숨통(낚시), 말없던 사춘기의 커피 한 잔, 번쩍 안아 올린 아이의 웃음, 선물로 건네는 사과, 열렬히 행복하길 바라는 춤의 마음. 이 섹션의 빛은 관계에서 생깁니다. 사랑과 그리움, 응원과 흐뭇함이 겹쳐지며 ‘삶을 계속하게 하는 빛’으로 남습니다.",
        "orders":list(range(11,25))
    }
]

def extract_table(pdf_path:Path):
    rows=[]
    with pdfplumber.open(str(pdf_path)) as pdf:
        for p in pdf.pages:
            tbls = p.extract_tables() or []
            for tbl in tbls:
                if not tbl or len(tbl)<2:
                    continue
                header=tbl[0]
                for r in tbl[1:]:
                    if not any(r):
                        continue
                    rec=dict(zip(header, r))
                    rows.append(rec)
    return rows

def html_escape(s:str)->str:
    return (s.replace("&","&amp;")
             .replace("<","&lt;")
             .replace(">","&gt;")
             .replace('"',"&quot;")
             .replace("'","&#39;"))

def html_br(s:str)->str:
    return "<br>".join(html_escape(s).splitlines())

def build_html(out_dir:Path, sections, art_list):
    images_dir=out_dir/"images"
    art_by_order={a["order"]:a for a in art_list}
    orders=[a["order"] for a in art_list]
    prev_next={}
    for i,o in enumerate(orders):
        prev_next[o]=(orders[i-1] if i>0 else None, orders[i+1] if i<len(orders)-1 else None)

    def artwork_card(a):
        o=a["order"]
        prev_o,next_o=prev_next[o]
        meta=[]
        if a.get("method"): meta.append(a["method"])
        if a.get("size"): meta.append(a["size"])
        if a.get("date"): meta.append(a["date"])
        meta_str=" · ".join([html_escape(x) for x in meta]) if meta else ""
        desc=a.get("desc","").strip()
        desc_html=f"<div class='desc'>{html_br(desc)}</div>" if desc else ""
        nav="<div class='work-nav'>"
        nav += f"<a class='btn' href='#work-{prev_o:02d}'>← 이전</a>" if prev_o else "<span class='btn disabled'>← 이전</span>"
        nav += "<a class='btn' href='#top'>목록</a>"
        nav += f"<a class='btn' href='#work-{next_o:02d}'>다음 →</a>" if next_o else "<span class='btn disabled'>다음 →</span>"
        nav += "</div>"
        return f"""
        <article class="work" id="work-{o:02d}">
          <div class="work-head">
            <h3><span class="num">{o:02d}</span> {html_escape(a['title'])}</h3>
            {f"<div class='meta'>{meta_str}</div>" if meta_str else ""}
          </div>
          <div class="img-wrap">
            <img src="images/{html_escape(a['filename'])}" alt="{html_escape(a['title'])}" loading="lazy" onclick="openModal({o});">
          </div>
          {desc_html}
          {nav}
        </article>
        """

    js_map={a["order"]: {"title":a["title"], "file":a["filename"]} for a in art_list}
    js_json=json.dumps(js_map, ensure_ascii=False)

    toc=[]
    blocks=[]
    for s in sections:
        toc.append(f"<a class='toc-item' href='#{s['id']}'>{html_escape(s['title'])}</a>")
        thumbs=""
        for o in s["orders"]:
            a=art_by_order[o]
            thumbs += f"""<a class="thumb" href="#work-{o:02d}">
                <img src="images/{html_escape(a['filename'])}" alt="{html_escape(a['title'])}">
                <div class="thumb-cap">{o:02d}. {html_escape(a['title'])}</div>
            </a>"""
        works="".join(artwork_card(art_by_order[o]) for o in s["orders"])
        blocks.append(f"""
        <section class="section" id="{s['id']}">
          <h2>{html_escape(s['title'])}</h2>
          <p class="section-intro">{html_br(s['intro'])}</p>
          <div class="thumbs">{thumbs}</div>
          <div class="works">{works}</div>
          <div class="backtop"><a href="#top">↑ 위로</a></div>
        </section>
        """)

    html=f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>전시 워크쓰루</title>
<style>
  :root {{ --bg:#0b0c10; --card:#15171c; --text:#f2f4f8; --muted:#aab1bd; --line:#2a2f38; --accent:#7dd3fc; }}
  body {{ margin:0; font-family: system-ui,-apple-system,"Malgun Gothic","Apple SD Gothic Neo",sans-serif;
         background: linear-gradient(180deg,#0b0c10,#0b0c10 40%,#0f1117); color:var(--text); }}
  a {{ color:var(--accent); text-decoration:none; }} a:hover {{ text-decoration:underline; }}
  header {{ position:sticky; top:0; z-index:10; backdrop-filter: blur(10px);
           background: rgba(11,12,16,.72); border-bottom:1px solid var(--line); }}
  .wrap {{ max-width:980px; margin:0 auto; padding:18px 14px; }}
  h1 {{ font-size:20px; margin:0; }} .sub {{ color:var(--muted); font-size:13px; margin-top:4px; }}
  .toc {{ display:flex; gap:10px; flex-wrap:wrap; margin-top:10px; }}
  .toc-item {{ padding:8px 10px; border:1px solid var(--line); border-radius:999px; background: rgba(255,255,255,.03); }}
  main {{ padding:10px 0 60px; }}
  .section {{ margin-top:26px; }} .section h2 {{ margin:0 0 10px; font-size:18px; }}
  .section-intro {{ margin:0 0 14px; color:var(--muted); line-height:1.65; padding:12px; border:1px solid var(--line);
                   border-radius:12px; background: rgba(255,255,255,.03); }}
  .thumbs {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(150px,1fr)); gap:10px; margin-bottom:14px; }}
  .thumb {{ border:1px solid var(--line); border-radius:12px; overflow:hidden; background: rgba(255,255,255,.02); }}
  .thumb img {{ width:100%; height:110px; object-fit:cover; display:block; }}
  .thumb-cap {{ padding:8px 10px; font-size:12px; color:var(--muted); }}
  .work {{ border:1px solid var(--line); border-radius:16px; background: rgba(255,255,255,.03); padding:14px; margin:12px 0; }}
  .work-head h3 {{ margin:0; font-size:16px; }}
  .num {{ display:inline-block; min-width:3ch; color:var(--accent); font-variant-numeric: tabular-nums; }}
  .meta {{ margin-top:6px; color:var(--muted); font-size:13px; }}
  .img-wrap {{ margin-top:12px; }}
  .img-wrap img {{ width:100%; height:auto; display:block; border-radius:12px; border:1px solid rgba(255,255,255,.08); cursor: zoom-in; }}
  .desc {{ margin-top:10px; line-height:1.7; }}
  .work-nav {{ display:flex; justify-content:space-between; gap:10px; flex-wrap:wrap; margin-top:12px; }}
  .btn {{ padding:8px 12px; border-radius:10px; border:1px solid var(--line); background: rgba(255,255,255,.02); color:var(--text); }}
  .btn:hover {{ text-decoration:none; border-color: rgba(125,211,252,.55); }}
  .btn.disabled {{ opacity:.35; pointer-events:none; }}
  .backtop {{ margin-top:14px; text-align:right; }}
  .modal {{ position:fixed; inset:0; display:none; z-index:100; background: rgba(0,0,0,.86); }}
  .modal.open {{ display:block; }}
  .modal-inner {{ position:absolute; inset:12px; display:flex; flex-direction:column; }}
  .modal-bar {{ display:flex; align-items:center; justify-content:space-between; gap:10px; font-size:14px; padding:10px 12px;
              border:1px solid rgba(255,255,255,.14); border-radius:14px; background: rgba(10,10,12,.5); }}
  .modal-bar .m-btn {{ padding:6px 10px; border-radius:10px; border:1px solid rgba(255,255,255,.18); background: rgba(255,255,255,.06);
                     color:var(--text); cursor:pointer; }}
  .modal-img {{ margin-top:10px; flex:1; display:flex; align-items:center; justify-content:center; }}
  .modal-img img {{ max-width:100%; max-height:100%; border-radius:14px; border:1px solid rgba(255,255,255,.15); cursor: zoom-out; }}
</style>
</head>
<body>
<header id="top">
  <div class="wrap">
    <h1>전시 동선 워크쓰루</h1>
    <div class="sub">섹션 3개 · 작품 24점 · 이미지 클릭하면 크게 보기</div>
    <nav class="toc">{''.join(toc)}</nav>
  </div>
</header>

<main class="wrap">
  {''.join(blocks)}
</main>

<div class="modal" id="modal" onclick="closeModal()">
  <div class="modal-inner" onclick="event.stopPropagation();">
    <div class="modal-bar">
      <div id="modalTitle">작품</div>
      <div style="display:flex; gap:8px; align-items:center;">
        <button class="m-btn" onclick="step(-1); event.stopPropagation();">←</button>
        <button class="m-btn" onclick="step(1); event.stopPropagation();">→</button>
        <button class="m-btn" onclick="closeModal(); event.stopPropagation();">닫기</button>
      </div>
    </div>
    <div class="modal-img">
      <img id="modalImg" src="" alt="">
    </div>
  </div>
</div>

<script>
const works = {js_json};
let current = null;
function openModal(order) {{
  current = order;
  const w = works[order];
  document.getElementById('modalTitle').textContent = String(order).padStart(2,'0') + ". " + w.title;
  const img = document.getElementById('modalImg');
  img.src = "images/" + w.file;
  img.alt = w.title;
  document.getElementById('modal').classList.add('open');
}}
function closeModal() {{
  document.getElementById('modal').classList.remove('open');
}}
function step(dir) {{
  if (current === null) return;
  const keys = Object.keys(works).map(k=>parseInt(k,10)).sort((a,b)=>a-b);
  const idx = keys.indexOf(current);
  const nextIdx = Math.max(0, Math.min(keys.length-1, idx + dir));
  current = keys[nextIdx];
  openModal(current);
}}
document.addEventListener('keydown', (e)=>{{
  const m = document.getElementById('modal');
  if (!m.classList.contains('open')) return;
  if (e.key === "Escape") closeModal();
  if (e.key === "ArrowLeft") step(-1);
  if (e.key === "ArrowRight") step(1);
}});
</script>
</body>
</html>
"""
    (out_dir/"index.html").write_text(html, encoding="utf-8")

def build_pdf(out_dir:Path, sections, art_list):
    # font
    try:
        pdfmetrics.registerFont(UnicodeCIDFont("HYGothic-Medium"))
        base_font="HYGothic-Medium"
    except Exception:
        base_font="Helvetica"

    styles=getSampleStyleSheet()
    def add_style(name, **kwargs):
        if name in styles: return
        styles.add(ParagraphStyle(name=name, **kwargs))
    add_style("KTitle", fontName=base_font, fontSize=20, leading=26, spaceAfter=12)
    add_style("KHeader", fontName=base_font, fontSize=16, leading=22, spaceAfter=8)
    add_style("KBody", fontName=base_font, fontSize=11, leading=16)
    add_style("KMeta", fontName=base_font, fontSize=10, leading=14, textColor=colors.gray)
    add_style("KSmall", fontName=base_font, fontSize=9, leading=13, textColor=colors.gray)

    pdf_out=out_dir/"전시_워크쓰루.pdf"
    doc=SimpleDocTemplate(str(pdf_out), pagesize=A4, leftMargin=18*mm, rightMargin=18*mm, topMargin=18*mm, bottomMargin=18*mm)

    images_dir=out_dir/"images"
    conv_dir=out_dir/"_converted"
    if conv_dir.exists():
        shutil.rmtree(conv_dir)
    conv_dir.mkdir(exist_ok=True)

    def ensure_jpg(filename):
        src=images_dir/filename
        dst=conv_dir/(Path(filename).stem + ".jpg")
        im=Image.open(src)
        if im.mode in ("RGBA","LA"):
            bg=Image.new("RGB", im.size, (255,255,255))
            bg.paste(im, mask=im.split()[-1])
            im=bg
        else:
            im=im.convert("RGB")
        max_dim=max(im.size)
        if max_dim>1600:
            scale=1600/max_dim
            im=im.resize((int(im.size[0]*scale), int(im.size[1]*scale)))
        im.save(dst, "JPEG", quality=85, optimize=True, progressive=True)
        return dst

    art_by_order={a["order"]:a for a in art_list}

    story=[]
    story.append(Paragraph("전시 동선 워크쓰루", styles["KTitle"]))
    story.append(Paragraph("assets_new 기반 · 작품 24점 · 섹션 3개", styles["KMeta"]))
    story.append(Spacer(1, 12))
    toc=[["섹션","작품 번호(순서)"]]
    for s in sections:
        toc.append([s["title"], ", ".join([f"{o:02d}" for o in s["orders"]])])
    tbl=Table(toc, colWidths=[55*mm, doc.width-55*mm])
    tbl.setStyle(TableStyle([
        ("FONT",(0,0),(-1,-1), base_font, 10),
        ("BACKGROUND",(0,0),(-1,0), colors.whitesmoke),
        ("GRID",(0,0),(-1,-1), 0.3, colors.lightgrey),
        ("VALIGN",(0,0),(-1,-1), "TOP"),
        ("PADDING",(0,0),(-1,-1), 6),
    ]))
    story.append(tbl)
    story.append(PageBreak())

    for s in sections:
        story.append(Paragraph(f"Section {s['id'][-1]}. {s['title']}", styles["KHeader"]))
        story.append(Paragraph(s["intro"].replace("\n","<br/>"), styles["KBody"]))
        story.append(Spacer(1, 10))
        story.append(Paragraph("대표 작품 순서: " + " → ".join([art_by_order[o]["title"] for o in s["orders"]]), styles["KSmall"]))
        story.append(PageBreak())

        for o in s["orders"]:
            a=art_by_order[o]
            story.append(Paragraph(f"{o:02d}. {a['title']}", styles["KHeader"]))
            meta=[]
            if a.get("method"): meta.append(a["method"])
            if a.get("size"): meta.append(a["size"])
            if a.get("date"): meta.append(a["date"])
            if meta:
                story.append(Paragraph(" · ".join(meta), styles["KMeta"]))
            story.append(Spacer(1, 8))
            jpg=ensure_jpg(a["filename"])
            im=Image.open(jpg)
            w,h=im.size
            max_w=doc.width
            max_h=135*mm
            scale=min(max_w/w, max_h/h)
            img=RLImage(str(jpg), width=w*scale, height=h*scale)
            img.hAlign="CENTER"
            story.append(img)
            story.append(Spacer(1, 10))
            desc=(a.get("desc") or "").strip()
            if desc:
                story.append(Paragraph(desc.replace("\n","<br/>"), styles["KBody"]))
            story.append(PageBreak())

    doc.build(story)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--zip", required=True)
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--out", default="walkthrough_package")
    args=ap.parse_args()

    zip_path=Path(args.zip)
    pdf_path=Path(args.pdf)
    out_dir=Path(args.out)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    images_dir=out_dir/"images"
    images_dir.mkdir()

    # unzip
    tmp=out_dir/"_tmp"
    tmp.mkdir()
    with zipfile.ZipFile(str(zip_path),"r") as z:
        z.extractall(str(tmp))

    # collect images
    imgs=[]
    for p in tmp.rglob("*"):
        if p.is_file() and re.search(r"\.(webp|png|jpg|jpeg)$", p.name, re.I):
            imgs.append(p)

    # copy to images/
    for p in imgs:
        shutil.copy2(str(p), str(images_dir/p.name))

    # parse list
    rows=extract_table(pdf_path)
    title_map={norm(r.get("제목","")): r for r in rows if r.get("제목")}
    # build art list from filenames (01_제목.webp)
    art_list=[]
    for fn in sorted([p.name for p in images_dir.iterdir()]):
        m=re.match(r"(\d+)[-_ ]+(.*)\.(webp|png|jpg|jpeg)$", fn, re.I)
        if not m:
            continue
        order=int(m.group(1))
        raw_title=m.group(2)
        r=title_map.get(norm(raw_title))
        if not r:
            # fallback: use raw_title
            r={"제목":raw_title, "방법":"", "사이즈":"", "날짜":"", "설명":""}
        art_list.append({
            "order": order,
            "filename": fn,
            "title": r.get("제목","").strip() or raw_title,
            "method": (r.get("방법") or "").strip(),
            "size": (r.get("사이즈") or "").strip(),
            "date": (r.get("날짜") or "").strip(),
            "desc": (r.get("설명") or "").strip(),
        })
    art_list.sort(key=lambda x:x["order"])

    meta={"sections":SECTION_DEF, "artworks":art_list}
    (out_dir/"metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    build_html(out_dir, SECTION_DEF, art_list)
    build_pdf(out_dir, SECTION_DEF, art_list)

    (out_dir/"README.txt").write_text("index.html을 여시면 오프라인 워크쓰루가 열립니다.\n", encoding="utf-8")
    shutil.rmtree(tmp)

    print("DONE:", out_dir.resolve())

if __name__=="__main__":
    main()
