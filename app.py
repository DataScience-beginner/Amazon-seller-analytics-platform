from __future__ import annotations

import json
import math
import re
import shutil
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from openpyxl import load_workbook

BASE = Path(__file__).resolve().parent
DB = BASE / "selleros.db"
UPLOADS = BASE / "uploads"
UPLOADS.mkdir(exist_ok=True)
app = FastAPI(title="SellerOS Phase 1 MVP")

ALIASES = {
    "asin": ["ASIN"], "title": ["Title", "Product Title"], "brand": ["Brand"],
    "category": ["Categories: Root", "Category"], "subcategory": ["Categories: Sub", "Subcategory"],
    "buy_box": ["Buy Box: Current"], "buy_box_90": ["Buy Box: 90 days avg."],
    "rank_current": ["Sales Rank: Current"], "rank_90": ["Sales Rank: 90 days avg."],
    "rank_drops_90": ["Sales Rank: Drops last 90 days"], "rating": ["Reviews: Rating"],
    "reviews": ["Reviews: Rating Count", "Review Count"], "new_offers": ["New Offer Count: Current"],
    "total_offers": ["Total Offer Count"], "winner_count_90": ["Buy Box: Winner Count 90 days"],
    "buy_box_oos_90": ["Buy Box: 90 days OOS"], "is_fba": ["Buy Box: Is FBA"],
    "pick_pack_fee": ["FBA Pick&Pack Fee"], "referral_fee": ["Referral Fee based on current Buy Box price"],
    "referral_pct": ["Referral Fee %"], "monthly_sold": ["Monthly Sales Trends: Monthly Sold (Last Known)"],
    "image": ["Image"], "amazon_url": ["URL: Amazon"]
}

CSS = """
:root{--navy:#111827;--ink:#172033;--muted:#6b7280;--bg:#f4f6f8;--green:#0f9f6e;--border:#e5e7eb}*{box-sizing:border-box}body{margin:0;font-family:Inter,system-ui,sans-serif;background:var(--bg);color:var(--ink)}a{text-decoration:none;color:inherit}.layout{display:grid;grid-template-columns:245px 1fr;min-height:100vh}aside{background:var(--navy);color:#fff;padding:24px 18px;position:sticky;top:0;height:100vh}.brand{font-weight:800;font-size:22px;margin-bottom:35px}.brand small{display:block;color:#9ca3af;font-size:11px;font-weight:400}nav{display:grid;gap:8px}nav a{padding:12px;border-radius:10px;color:#d1d5db}nav a:hover{background:#1f2937;color:#fff}main{min-width:0}header{height:70px;background:#fff;border-bottom:1px solid var(--border);display:flex;align-items:center;padding:0 26px;position:sticky;top:0;z-index:3}header b{font-size:16px}.content{padding:26px;max-width:1500px;margin:auto}.head{display:flex;justify-content:space-between;align-items:center;margin-bottom:22px}.head h1{margin:0 0 6px;font-size:28px}.head p{margin:0;color:var(--muted)}.btn{background:var(--green);color:#fff;border:0;border-radius:10px;padding:12px 17px;font-weight:700;cursor:pointer}.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:15px;margin-bottom:18px}.card,.panel{background:#fff;border:1px solid var(--border);border-radius:16px}.card{padding:19px}.card small,.card span{display:block;color:var(--muted)}.card b{display:block;font-size:28px;margin:8px 0}.grid{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-bottom:18px}.panel{padding:20px;overflow:auto}.panel h2{font-size:17px;margin:0 0 16px}.mix{display:grid;grid-template-columns:1fr 1fr;gap:12px}.mix div{display:flex;justify-content:space-between;padding:9px;background:#f8fafc;border-radius:9px}.filters{display:flex;gap:10px;margin-bottom:16px}.filters input,.filters select,input{padding:11px;border:1px solid var(--border);border-radius:10px;font:inherit}.filters input{flex:1}table{width:100%;border-collapse:collapse}th,td{padding:13px 14px;border-bottom:1px solid var(--border);font-size:13px;text-align:left}th{background:#fafafa;color:var(--muted);font-size:11px;text-transform:uppercase}.pill{display:inline-block;padding:5px 10px;border-radius:999px;background:#eef2ff;color:#4338ca;font-size:12px;font-weight:700}.product{display:flex;gap:10px;align-items:center;min-width:300px}.product img{width:45px;height:45px;object-fit:contain;border:1px solid var(--border);border-radius:8px}.product small,td small{display:block;color:var(--muted);margin-top:4px}.score-row{display:grid;grid-template-columns:repeat(5,1fr);gap:10px}.score-row div,.profit div{padding:13px;background:#f8fafc;border-radius:10px}.score-row b,.score-row small,.profit b,.profit small{display:block}.score-row small,.profit small{color:var(--muted);font-size:11px}.profit{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.form{display:grid;grid-template-columns:1fr 1fr;gap:12px}.form label{font-size:12px;color:var(--muted)}.form input{width:100%;display:block;margin-top:5px}.upload{border:2px dashed #cbd5e1;border-radius:14px;padding:38px;text-align:center}.success{padding:12px;background:#e8f8f1;color:#087a54;border-radius:10px;margin-bottom:15px}@media(max-width:900px){.layout{grid-template-columns:1fr}aside{display:none}.content{padding:16px}.kpis{grid-template-columns:1fr 1fr}.grid{grid-template-columns:1fr}.head{align-items:flex-start;gap:12px}.score-row{grid-template-columns:1fr 1fr}.filters{flex-wrap:wrap}.filters input{flex-basis:100%}}@media(max-width:520px){.head{display:block}.head .btn{display:inline-block;margin-top:12px}.profit,.form{grid-template-columns:1fr 1fr}}
"""


def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS imports(id INTEGER PRIMARY KEY,filename TEXT,imported_at TEXT,row_count INTEGER,column_count INTEGER,mapped_json TEXT,unmapped_json TEXT);
        CREATE TABLE IF NOT EXISTS products(asin TEXT PRIMARY KEY,title TEXT,brand TEXT,category TEXT,subcategory TEXT,image TEXT,amazon_url TEXT,metrics_json TEXT,scores_json TEXT,raw_json TEXT,sourcing_cost REAL DEFAULT 0,inventory_units INTEGER DEFAULT 0,lead_time_days INTEGER DEFAULT 30,updated_at TEXT);
        CREATE TABLE IF NOT EXISTS snapshots(id INTEGER PRIMARY KEY,import_id INTEGER,asin TEXT,snapshot_at TEXT,metrics_json TEXT);
        """)


def norm(v: Any) -> str:
    return re.sub(r"\s+", " ", str(v or "").strip()).lower()


def number(v: Any):
    if v in (None, "", "-"): return None
    if isinstance(v, (int, float)): return float(v)
    try: return float(str(v).replace("₹", "").replace(",", "").replace("%", "").strip())
    except ValueError: return None


def parse_excel(path: Path):
    ws = load_workbook(path, read_only=True, data_only=True).active
    it = ws.iter_rows(values_only=True)
    headers = [str(v).strip() if v is not None else "" for v in next(it)]
    lookup = {norm(h): h for h in headers if h}
    mapped = {}
    for key, aliases in ALIASES.items():
        for alias in aliases:
            if norm(alias) in lookup:
                mapped[key] = lookup[norm(alias)]; break
    rows = []
    for raw in it:
        record = {h: raw[i] if i < len(raw) else None for i, h in enumerate(headers) if h}
        p = {k: record.get(source) for k, source in mapped.items()}
        if not p.get("asin") and not p.get("title"): continue
        p["asin"] = str(p.get("asin") or f"ROW-{len(rows)+2}")
        p["title"] = str(p.get("title") or "Untitled product")
        p["image"] = str(p.get("image") or "").split(";")[0]
        for key in ["buy_box","buy_box_90","rank_current","rank_90","rank_drops_90","rating","reviews","new_offers","total_offers","winner_count_90","buy_box_oos_90","pick_pack_fee","referral_fee","referral_pct","monthly_sold"]:
            p[key] = number(p.get(key))
        p["raw_json"] = json.dumps(record, default=str, ensure_ascii=False)
        rows.append(p)
    return rows, headers, mapped, [h for h in headers if h and h not in mapped.values()]


def clamp(v): return round(max(0, min(100, v)), 1)


def score(p):
    rank, rank90, drops = p.get("rank_current"), p.get("rank_90"), p.get("rank_drops_90") or 0
    reviews, offers = p.get("reviews"), p.get("new_offers") if p.get("new_offers") is not None else p.get("total_offers")
    price, price90, winners, oos = p.get("buy_box"), p.get("buy_box_90"), p.get("winner_count_90") or 0, p.get("buy_box_oos_90") or 0
    demand = 35 + (max(-20, 35-math.log10(max(rank,1))*8) if rank else 0) + min(25,drops/3)
    if rank and rank90: demand += 12 if rank < rank90 else -10
    if p.get("monthly_sold"): demand += min(18,p["monthly_sold"]/4)
    demand = clamp(demand)
    competition = clamp(75 - ((offers or 0)*7) - min(20,winners*3) - (min(20,math.log10(reviews+1)*7) if reviews is not None else 0))
    stability = clamp((100-min(80,abs(price/price90-1)*250) if price and price90 else 70)-min(30,oos*1.5))
    risk = 25 + (8 if str(p.get("is_fba") or "").lower() != "yes" else 0) + (18 if offers and offers>8 else 0) + (15 if oos>10 else 0)
    if price and price90 and price < price90*.85: risk += 20
    risk = clamp(risk)
    overall = clamp(demand*.35+competition*.25+stability*.2+(100-risk)*.2)
    if risk>=70 or stability<35: strategy="Avoid"
    elif demand>=75 and competition>=55 and stability>=60: strategy="Growth"
    elif demand>=65 and stability>=70: strategy="Cash Cow"
    elif demand>=55 and competition>=55: strategy="Test Buy"
    elif (price or 0)>=2500 and competition>=45: strategy="Premium Margin"
    elif demand<40 or stability<50: strategy="Clearance Watch"
    else: strategy="Monitor"
    return {"demand_score":demand,"competition_score":competition,"stability_score":stability,"risk_score":risk,"overall_score":overall,"strategy":strategy}


def import_file(path: Path):
    rows, headers, mapped, unmapped = parse_excel(path)
    now = datetime.utcnow().isoformat()
    with db() as c:
        cur = c.execute("INSERT INTO imports(filename,imported_at,row_count,column_count,mapped_json,unmapped_json) VALUES(?,?,?,?,?,?)",(path.name,now,len(rows),len(headers),json.dumps(mapped),json.dumps(unmapped)))
        import_id = cur.lastrowid
        for p in rows:
            scores = score(p); metrics = {k:v for k,v in p.items() if k != "raw_json"}
            c.execute("""INSERT INTO products(asin,title,brand,category,subcategory,image,amazon_url,metrics_json,scores_json,raw_json,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(asin) DO UPDATE SET title=excluded.title,brand=excluded.brand,category=excluded.category,subcategory=excluded.subcategory,image=excluded.image,amazon_url=excluded.amazon_url,metrics_json=excluded.metrics_json,scores_json=excluded.scores_json,raw_json=excluded.raw_json,updated_at=excluded.updated_at""",
            (p["asin"],p["title"],p.get("brand"),p.get("category"),p.get("subcategory"),p.get("image"),p.get("amazon_url"),json.dumps(metrics),json.dumps(scores),p["raw_json"],now))
            c.execute("INSERT INTO snapshots(import_id,asin,snapshot_at,metrics_json) VALUES(?,?,?,?)",(import_id,p["asin"],now,json.dumps(metrics)))
    return len(rows), len(headers)


def products(search="", strategy=""):
    with db() as c:
        data=[]
        for row in c.execute("SELECT * FROM products"):
            p=dict(row); p.update(json.loads(p.pop("metrics_json"))); p.update(json.loads(p.pop("scores_json")))
            if search and search.lower() not in f"{p.get('asin')} {p.get('title')} {p.get('brand')}".lower(): continue
            if strategy and p.get("strategy") != strategy: continue
            data.append(p)
    return sorted(data,key=lambda x:x.get("overall_score",0),reverse=True)


def product(asin):
    with db() as c:
        row=c.execute("SELECT * FROM products WHERE asin=?",(asin,)).fetchone()
        if not row:return None
        p=dict(row);p.update(json.loads(p.pop("metrics_json")));p.update(json.loads(p.pop("scores_json")));return p


def profit(p, cost):
    selling=float(p.get("buy_box") or 0); referral=p.get("referral_fee")
    if referral is None: referral=selling*(p.get("referral_pct") or 15)/100
    total=cost+25+15+referral+float(p.get("pick_pack_fee") or 45)+selling*.05
    net=selling-total
    return {"selling":round(selling,2),"total":round(total,2),"net":round(net,2),"roi":round(net/cost*100,1) if cost else 0,"margin":round(net/selling*100,1) if selling else 0,"break_even":round(total,2)}


def layout(body,title="SellerOS"):
    return HTMLResponse(f"""<!doctype html><html><head><meta name='viewport' content='width=device-width,initial-scale=1'><title>{title}</title><style>{CSS}</style></head><body><div class='layout'><aside><div class='brand'>SellerOS<small>Amazon Intelligence Platform</small></div><nav><a href='/'>Dashboard</a><a href='/products'>Product Opportunities</a><a href='/planning'>Strategy & Planning</a><a href='/upload'>Upload Keepa Data</a></nav></aside><main><header><b>Amazon Seller Command Center</b></header><section class='content'>{body}</section></main></div></body></html>""")

@app.on_event("startup")
def startup(): init_db()

@app.get("/",response_class=HTMLResponse)
def dashboard():
    ps=products(); counts=Counter(p["strategy"] for p in ps); avg=round(sum(p["overall_score"] for p in ps)/len(ps),1) if ps else 0
    cards=f"<div class='kpis'><div class='card'><small>Products tracked</small><b>{len(ps)}</b><span>latest portfolio</span></div><div class='card'><small>Average opportunity</small><b>{avg}</b><span>out of 100</span></div><div class='card'><small>Growth candidates</small><b>{counts['Growth']}</b><span>prioritise sourcing</span></div><div class='card'><small>Exit / risk alerts</small><b>{counts['Avoid']+counts['Clearance Watch']}</b><span>protect cash</span></div></div>"
    mix="".join(f"<div><span>{name}</span><b>{counts[name]}</b></div>" for name in ['Growth','Cash Cow','Test Buy','Premium Margin','Monitor','Clearance Watch','Avoid'])
    actions="".join(f"<tr><td><a href='/products/{p['asin']}'><b>{p['title']}</b><small>{p.get('brand') or 'Unknown'} · {p['asin']}</small></a></td><td><span class='pill'>{p['strategy']}</span></td><td><b>{p['overall_score']}</b></td></tr>" for p in ps[:10])
    body=f"<div class='head'><div><h1>Portfolio overview</h1><p>Turn monthly Keepa exports into decisions that protect cash flow.</p></div><a class='btn' href='/upload'>Upload Keepa file</a></div>{cards}<div class='grid'><div class='panel'><h2>Strategy mix</h2><div class='mix'>{mix}</div></div><div class='panel'><h2>Recommended actions</h2><table>{actions or '<tr><td>Upload a Keepa workbook to begin.</td></tr>'}</table></div></div>"
    return layout(body,"Dashboard · SellerOS")

@app.get("/products",response_class=HTMLResponse)
def product_list(search:str="",strategy:str=""):
    ps=products(search,strategy); opts="".join(f"<option {'selected' if strategy==s else ''}>{s}</option>" for s in ['Growth','Cash Cow','Test Buy','Premium Margin','Monitor','Clearance Watch','Avoid'])
    rows="".join(f"<tr><td><div class='product'>{f'<img src={p[\"image\"]}>' if p.get('image') else ''}<div><a href='/products/{p['asin']}'><b>{p['title']}</b></a><small>{p.get('brand') or 'Unknown'} · {p['asin']}</small></div></div></td><td><span class='pill'>{p['strategy']}</span></td><td>{p['demand_score']}</td><td>{p['competition_score']}</td><td>{p['stability_score']}</td><td>{p['risk_score']}</td><td><b>{p['overall_score']}</b></td><td>₹{round(p.get('buy_box') or 0)}</td></tr>" for p in ps)
    body=f"<div class='head'><div><h1>Product opportunities</h1><p>Demand, competition, stability and risk in one view.</p></div></div><form class='filters'><input name='search' value='{search}' placeholder='Search ASIN, product or brand'><select name='strategy'><option value=''>All strategies</option>{opts}</select><button class='btn'>Apply</button></form><div class='panel'><table><thead><tr><th>Product</th><th>Strategy</th><th>Demand</th><th>Competition</th><th>Stability</th><th>Risk</th><th>Overall</th><th>Buy Box</th></tr></thead><tbody>{rows}</tbody></table></div>"
    return layout(body,"Products · SellerOS")

@app.get("/products/{asin}",response_class=HTMLResponse)
def detail(asin:str):
    p=product(asin)
    if not p:return RedirectResponse('/products',303)
    calc=profit(p,p.get('sourcing_cost') or 0)
    scores="".join(f"<div><b>{p[k]}</b><small>{label}</small></div>" for k,label in [('overall_score','Overall'),('demand_score','Demand'),('competition_score','Competition'),('stability_score','Stability'),('risk_score','Risk')])
    body=f"<a href='/products'>← Back</a><div class='head'><div><span class='pill'>{p['strategy']}</span><h1>{p['title']}</h1><p>{p.get('brand') or 'Unknown'} · {p.get('subcategory') or p.get('category') or 'Uncategorised'} · {p['asin']}</p></div></div><div class='score-row'>{scores}</div><br><div class='grid'><div class='panel'><h2>Business inputs</h2><form class='form' method='post' action='/products/{asin}/business'><label>Sourcing cost<input name='sourcing_cost' type='number' step='.01' value='{p.get('sourcing_cost') or 0}'></label><label>Inventory units<input name='inventory_units' type='number' value='{p.get('inventory_units') or 0}'></label><label>Lead time days<input name='lead_time_days' type='number' value='{p.get('lead_time_days') or 30}'></label><button class='btn'>Save</button></form></div><div class='panel'><h2>Profitability</h2><div class='profit'><div><small>Selling</small><b>₹{calc['selling']}</b></div><div><small>Net profit</small><b>₹{calc['net']}</b></div><div><small>ROI</small><b>{calc['roi']}%</b></div><div><small>Margin</small><b>{calc['margin']}%</b></div><div><small>Break-even</small><b>₹{calc['break_even']}</b></div><div><small>Total cost</small><b>₹{calc['total']}</b></div></div></div></div><div class='panel'><h2>Market evidence</h2><table><tr><th>Current rank</th><th>90-day rank</th><th>Rank drops</th><th>Reviews</th><th>Offers</th><th>90-day price</th></tr><tr><td>{p.get('rank_current') or '—'}</td><td>{p.get('rank_90') or '—'}</td><td>{p.get('rank_drops_90') or '—'}</td><td>{p.get('reviews') or '—'}</td><td>{p.get('new_offers') or p.get('total_offers') or '—'}</td><td>₹{p.get('buy_box_90') or '—'}</td></tr></table></div>"
    return layout(body,f"{asin} · SellerOS")

@app.post("/products/{asin}/business")
def save_inputs(asin:str,sourcing_cost:float=Form(0),inventory_units:int=Form(0),lead_time_days:int=Form(30)):
    with db() as c:c.execute("UPDATE products SET sourcing_cost=?,inventory_units=?,lead_time_days=? WHERE asin=?",(sourcing_cost,inventory_units,lead_time_days,asin))
    return RedirectResponse(f"/products/{asin}",303)

@app.get("/upload",response_class=HTMLResponse)
def upload_page(request:Request):
    with db() as c: history=list(c.execute("SELECT * FROM imports ORDER BY id DESC LIMIT 12"))
    rows="".join(f"<tr><td>{x['filename']}</td><td>{x['row_count']}</td><td>{x['column_count']}</td><td>{x['imported_at'][:16].replace('T',' ')}</td></tr>" for x in history)
    success="<div class='success'>Import completed and all scores were recalculated.</div>" if request.query_params.get('success') else ""
    body=f"<div class='head'><div><h1>Upload Keepa data</h1><p>Dynamic mapping keeps working when optional columns change.</p></div></div>{success}<div class='grid'><div class='panel'><form method='post' enctype='multipart/form-data'><div class='upload'><b>Choose monthly Keepa Excel file</b><br><br><input type='file' name='file' accept='.xlsx' required></div><br><button class='btn'>Analyse and import</button></form></div><div class='panel'><h2>Import behaviour</h2><p>Matches ASINs, stores monthly snapshots, maps known fields, preserves unknown columns and recalculates strategies.</p></div></div><div class='panel'><h2>Import history</h2><table><tr><th>File</th><th>Products</th><th>Columns</th><th>Imported</th></tr>{rows}</table></div>"
    return layout(body,"Upload · SellerOS")

@app.post("/upload")
def upload(file:UploadFile=File(...)):
    target=UPLOADS/Path(file.filename or 'keepa.xlsx').name
    with target.open('wb') as out:shutil.copyfileobj(file.file,out)
    import_file(target)
    return RedirectResponse('/upload?success=1',303)

@app.get("/planning",response_class=HTMLResponse)
def planning():
    ps=products()[:50]; total=0; rows=[]
    for p in ps:
        units=25 if p['strategy']=='Growth' else 10 if p['strategy']=='Test Buy' else 15
        cost=p.get('sourcing_cost') or (p.get('buy_box') or 0)*.55; investment=round(units*cost,2); total+=investment
        rows.append(f"<tr><td><a href='/products/{p['asin']}'><b>{p['title']}</b><small>{p['asin']}</small></a></td><td><span class='pill'>{p['strategy']}</span></td><td>{units}</td><td>₹{investment}</td><td>{p.get('monthly_sold') or max(1,round((p.get('rank_drops_90') or 3)/3))} units/mo</td></tr>")
    body=f"<div class='head'><div><h1>Strategy and buying plan</h1><p>First-cut sourcing quantities and working-capital requirement.</p></div></div><div class='kpis'><div class='card'><small>Products reviewed</small><b>{len(ps)}</b></div><div class='card'><small>Planned investment</small><b>₹{round(total)}</b></div></div><div class='panel'><table><tr><th>Product</th><th>Strategy</th><th>Planned units</th><th>Investment</th><th>Demand proxy</th></tr>{''.join(rows)}</table></div>"
    return layout(body,"Planning · SellerOS")
