#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""电影数据分析系统 Pro — Web GUI"""

import os, json, threading, webbrowser, math
from collections import Counter
import pandas as pd
import numpy as np
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

BASE       = os.path.dirname(os.path.abspath(__file__))
DATA_DIR   = os.path.join(BASE, "data")
MOVIES_CSV = os.path.join(DATA_DIR, "movies.csv")
RATINGS_CSV= os.path.join(DATA_DIR, "ratings.csv")

def load():
    m = pd.read_csv(MOVIES_CSV); r = pd.read_csv(RATINGS_CSV)
    m.dropna(inplace=True); r.dropna(inplace=True)
    r.drop_duplicates(subset=['userId','movieId'], inplace=True)
    r = r[r['rating'].between(0.5,5.0)].reset_index(drop=True)
    mg = pd.merge(r, m, on='movieId', how='left')
    return m, r, mg

try:
    MOVIES, RATINGS, MERGED = load()
    DATA_OK = True
except Exception as e:
    DATA_OK = False; DATA_ERR = str(e)

# ── API handlers ──────────────────────────────────────────────────────────────
def api_overview():
    if not DATA_OK: return {"error": DATA_ERR}
    r = RATINGS['rating']
    bins=[0,1,2,3,4,5]; labels=['0.5-1.0','1.5-2.0','2.5-3.0','3.5-4.0','4.5-5.0']
    seg = pd.cut(r, bins=bins, labels=labels).value_counts().sort_index()
    sc  = r.value_counts().sort_index()
    gm  = MERGED.groupby(['movieId','title'])['rating'].agg(avg='mean',votes='count').reset_index()
    best = gm[gm['votes']>=3].sort_values('avg',ascending=False).iloc[0]['title'] if len(gm)>0 else '-'
    return {
        "movies": int(MOVIES['movieId'].nunique()),
        "users":  int(RATINGS['userId'].nunique()),
        "records":int(len(RATINGS)),
        "avg":    round(float(r.mean()),3),
        "max":    float(r.max()), "min":float(r.min()),
        "std":    round(float(r.std()),3),
        "median": float(r.median()),
        "best_movie": str(best),
        "genres_count": int(MOVIES['genres'].str.split('|').explode().nunique()),
        "segments": [{"label":l,"count":int(c),"pct":round(c/len(r)*100,1)} for l,c in seg.items()],
        "freq": [{"score":float(s),"count":int(c)} for s,c in sc.items()],
    }

def api_rating():
    if not DATA_OK: return {"error": DATA_ERR}
    r = RATINGS['rating']
    sc = r.value_counts().sort_index()
    q1,q3 = float(r.quantile(.25)), float(r.quantile(.75))
    bins=[0,1,2,3,4,5]; labels=['0.5-1.0','1.5-2.0','2.5-3.0','3.5-4.0','4.5-5.0']
    seg = pd.cut(r, bins=bins, labels=labels).value_counts().sort_index()
    return {
        "avg":float(round(r.mean(),3)),"median":float(r.median()),
        "mode":float(r.mode().iloc[0]),"std":float(round(r.std(),3)),
        "max":float(r.max()),"min":float(r.min()),"total":int(len(r)),
        "q1":round(q1,2),"q3":round(q3,2),"iqr":round(q3-q1,2),
        "freq":[{"score":float(s),"count":int(c)} for s,c in sc.items()],
        "segments":[{"label":l,"count":int(c),"pct":round(c/len(r)*100,1)} for l,c in seg.items()],
    }

def api_top(n=15):
    if not DATA_OK: return {"error": DATA_ERR}
    gmap = dict(zip(MOVIES['movieId'], MOVIES['genres']))
    g = MERGED.groupby(['movieId','title'])['rating'].agg(avg='mean',votes='count',std='std').reset_index()
    top = g[g['votes']>=5].sort_values('avg',ascending=False).head(n).reset_index(drop=True)
    rows=[]
    for i,row in top.iterrows():
        g2 = gmap.get(row['movieId'],'')
        rows.append({"rank":i+1,"title":str(row['title']),"genre":g2.split('|')[0] if g2 else '',
                     "genres":g2,"avg":round(float(row['avg']),3),"votes":int(row['votes']),
                     "std":round(float(row['std']) if not pd.isna(row['std']) else 0,3)})
    # bottom 10
    bot = g[g['votes']>=5].sort_values('avg',ascending=True).head(10).reset_index(drop=True)
    brows=[]
    for i,row in bot.iterrows():
        g2=gmap.get(row['movieId'],'')
        brows.append({"rank":i+1,"title":str(row['title']),"avg":round(float(row['avg']),3),"votes":int(row['votes']),"genre":g2.split('|')[0] if g2 else ''})
    return {"top":rows,"bottom":brows}

def api_genre():
    if not DATA_OK: return {"error": DATA_ERR}
    exploded = MERGED.copy()
    exploded['genre'] = exploded['genres'].str.split('|')
    exploded = exploded.explode('genre')
    exploded['genre'] = exploded['genre'].str.strip()
    g = exploded.groupby('genre')['rating'].agg(avg='mean',count='count').reset_index()
    g = g[g['count']>=10].sort_values('count',ascending=False)
    gcount = MOVIES['genres'].str.split('|').explode().str.strip().value_counts()
    return {
        "genres": [{"genre":str(r['genre']),"avg":round(float(r['avg']),3),"count":int(r['count'])}
                   for _,r in g.iterrows()],
        "movie_counts": [{"genre":str(k),"count":int(v)} for k,v in gcount.head(12).items()],
    }

def api_user():
    if not DATA_OK: return {"error": DATA_ERR}
    ua = RATINGS.groupby('userId')['rating'].agg(count='count',avg='mean',std='std').reset_index()
    ua['std'] = ua['std'].fillna(0)
    ua = ua.sort_values('count',ascending=False)
    hist_vals,bins = np.histogram(ua['count'], bins=12)
    return {
        "total":int(len(ua)),"avg_cnt":round(float(ua['count'].mean()),1),
        "max_cnt":int(ua['count'].max()),"min_cnt":int(ua['count'].min()),
        "gte5":int((ua['count']>=5).sum()),"gte10":int((ua['count']>=10).sum()),
        "gte20":int((ua['count']>=20).sum()),
        "top":[{"uid":int(r['userId']),"count":int(r['count']),"avg":round(float(r['avg']),3),"std":round(float(r['std']),3)}
               for _,r in ua.head(15).iterrows()],
        "hist":{"counts":[int(x) for x in hist_vals],
                "edges":[round(float(x),1) for x in bins]},
    }

def api_trend():
    if not DATA_OK: return {"error": DATA_ERR}
    r = RATINGS.copy()
    r['date'] = pd.to_datetime(r['timestamp'], unit='s', errors='coerce')
    r = r.dropna(subset=['date'])
    r['year'] = r['date'].dt.year
    yt = r.groupby('year')['rating'].agg(avg='mean',count='count').reset_index()
    yt = yt[(yt['year']>=1995)&(yt['year']<=2020)].sort_values('year')
    ym = r.groupby(r['date'].dt.month)['rating'].agg(avg='mean',count='count').reset_index()
    ym.columns=['month','avg','count']
    return {
        "yearly":[{"year":int(r['year']),"avg":round(float(r['avg']),3),"count":int(r['count'])}
                  for _,r in yt.iterrows()],
        "monthly":[{"month":int(r['month']),"avg":round(float(r['avg']),3),"count":int(r['count'])}
                   for _,r in ym.iterrows()],
    }

def api_query(qtype, qid):
    if not DATA_OK: return {"error": DATA_ERR}
    try: qid=int(qid)
    except: return {"error":"ID 必须是整数"}
    if qtype=="movie":
        mi = MOVIES[MOVIES['movieId']==qid]
        if mi.empty: return {"error":f"未找到电影 ID {qid}，请输入 1-{int(MOVIES['movieId'].max())}"}
        mr = RATINGS[RATINGS['movieId']==qid]['rating']
        dist = mr.value_counts().sort_index()
        similar = MERGED.groupby(['movieId','title'])['rating'].agg(avg='mean',votes='count').reset_index()
        g = mi.iloc[0]['genres'].split('|')[0]
        sim = [r for _,r in similar[similar['title']!=mi.iloc[0]['title']].sort_values('avg',ascending=False).head(5).iterrows()]
        return {"type":"movie","title":str(mi.iloc[0]['title']),"genres":str(mi.iloc[0]['genres']),
                "votes":int(len(mr)),"avg":round(float(mr.mean()),3) if len(mr)>0 else 0,
                "max":float(mr.max()) if len(mr)>0 else 0,"min":float(mr.min()) if len(mr)>0 else 0,
                "std":round(float(mr.std()),3) if len(mr)>1 else 0,
                "dist":[{"score":float(s),"count":int(c)} for s,c in dist.items()],
                "similar":[{"title":str(r['title']),"avg":round(float(r['avg']),3)} for r in sim]}
    else:
        ud = MERGED[MERGED['userId']==qid]
        if ud.empty: return {"error":f"未找到用户 ID {qid}，请输入 1-{int(RATINGS['userId'].max())}"}
        fav_genre = ud['genres'].str.split('|').explode().value_counts().index[0] if len(ud)>0 else '-'
        def lbl(r): return "强烈推荐" if r>=4.5 else "推荐" if r>=3.5 else "一般" if r>=2.5 else "较差"
        return {"type":"user","uid":qid,"total":int(len(ud)),
                "avg":round(float(ud['rating'].mean()),3),
                "max":float(ud['rating'].max()),"min":float(ud['rating'].min()),
                "fav_genre":str(fav_genre),
                "movies":[{"title":str(r['title']),"rating":float(r['rating']),"label":lbl(r['rating'])}
                          for _,r in ud.sort_values('rating',ascending=False).iterrows()]}

def api_compare(ids_str):
    if not DATA_OK: return {"error": DATA_ERR}
    try:
        ids = [int(x.strip()) for x in ids_str.split(',') if x.strip()]
    except: return {"error":"格式错误，请用逗号分隔电影ID，例如：1,2,3"}
    if len(ids)<2: return {"error":"请至少输入2个电影ID"}
    result=[]
    for mid in ids[:6]:
        mi = MOVIES[MOVIES['movieId']==mid]
        if mi.empty: continue
        mr = RATINGS[RATINGS['movieId']==mid]['rating']
        if len(mr)==0: continue
        dist = mr.value_counts().sort_index()
        result.append({"id":mid,"title":str(mi.iloc[0]['title']),"genres":str(mi.iloc[0]['genres']),
                       "avg":round(float(mr.mean()),3),"votes":int(len(mr)),
                       "std":round(float(mr.std()),3) if len(mr)>1 else 0,
                       "dist":[{"score":float(s),"count":int(c)} for s,c in dist.items()]})
    if not result: return {"error":"未找到有效的电影ID"}
    return {"movies":result}

# ── HTML ──────────────────────────────────────────────────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8"><title>电影数据分析系统 Pro</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#0f1117;--bg2:#1a1d27;--bg3:#242836;--bg4:#2e3347;
      --accent:#6c8fff;--accent2:#4ecdc4;--accent3:#ffd166;--accent4:#ff6b9d;
      --text:#e8eaf0;--text2:#9ba3b8;--text3:#5a6278;
      --border:#2e3347;--border2:#3d4560;
      --red:#ff6b6b;--green:#69db7c;--yellow:#ffd43b;--orange:#ffa94d;--blue:#74c0fc}
body{font-family:-apple-system,'Microsoft YaHei','Segoe UI',sans-serif;background:var(--bg);color:var(--text);font-size:13px;height:100vh;overflow:hidden}
.layout{display:flex;height:100vh}
/* Sidebar */
.sidebar{width:220px;background:var(--bg2);border-right:1px solid var(--border);display:flex;flex-direction:column;flex-shrink:0}
.brand{padding:20px 18px 16px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:10px}
.brand-icon{width:36px;height:36px;background:var(--accent);border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0}
.brand-name{font-size:14px;font-weight:700;color:var(--text)}
.brand-sub{font-size:10px;color:var(--text2);margin-top:1px}
.nav{flex:1;padding:10px 0;overflow-y:auto}
.nav-section{padding:8px 18px 4px;font-size:10px;font-weight:600;color:var(--text3);letter-spacing:.8px;text-transform:uppercase}
.nav-item{display:flex;align-items:center;gap:10px;padding:9px 18px;cursor:pointer;color:var(--text2);border-left:3px solid transparent;transition:all .15s;font-size:13px}
.nav-item:hover{background:var(--bg3);color:var(--text)}
.nav-item.active{background:var(--bg3);color:var(--accent);border-left-color:var(--accent);font-weight:600}
.nav-item .ico{width:20px;text-align:center;font-size:16px}
.nav-badge{margin-left:auto;background:var(--accent);color:#fff;font-size:10px;padding:1px 6px;border-radius:10px;font-weight:600}
.sidebar-foot{padding:12px 18px;border-top:1px solid var(--border)}
.status-row{display:flex;align-items:center;gap:6px;font-size:11px;color:var(--text2)}
.dot-green{width:6px;height:6px;border-radius:50%;background:var(--green)}
/* Main */
.main{flex:1;display:flex;flex-direction:column;overflow:hidden}
.topbar{height:52px;background:var(--bg2);border-bottom:1px solid var(--border);display:flex;align-items:center;padding:0 22px;gap:12px;flex-shrink:0}
.topbar-title{font-size:15px;font-weight:700;color:var(--text)}
.topbar-pill{background:var(--bg3);color:var(--accent);font-size:11px;padding:3px 10px;border-radius:20px;font-weight:600;border:1px solid var(--border2)}
.topbar-spacer{flex:1}
.topbar-info{font-size:11px;color:var(--text3)}
.content{flex:1;overflow-y:auto;padding:20px 22px}
.page{display:none}.page.active{display:block}
/* Cards */
.card{background:var(--bg2);border:1px solid var(--border);border-radius:12px;padding:16px 18px;margin-bottom:14px}
.card-title{font-size:12px;font-weight:600;color:var(--text2);text-transform:uppercase;letter-spacing:.6px;margin-bottom:14px;display:flex;align-items:center;gap:8px}
.card-title .ico{color:var(--accent);font-size:15px}
/* Metrics */
.metrics{display:grid;gap:10px;margin-bottom:14px}
.g2{grid-template-columns:repeat(2,1fr)}.g3{grid-template-columns:repeat(3,1fr)}.g4{grid-template-columns:repeat(4,1fr)}
.metric{background:var(--bg3);border-radius:10px;padding:14px 16px;border:1px solid var(--border)}
.metric-lbl{font-size:10px;color:var(--text3);font-weight:600;text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px}
.metric-val{font-size:22px;font-weight:700;color:var(--text)}
.metric-sub{font-size:11px;color:var(--text2);margin-top:3px}
.metric-accent{border-left:3px solid var(--accent)}
/* Bars */
.brow{display:flex;align-items:center;gap:10px;margin-bottom:8px}
.blbl{width:90px;color:var(--text2);font-size:12px;text-align:right;flex-shrink:0}
.btrack{flex:1;height:20px;background:var(--bg3);border-radius:4px;overflow:hidden;position:relative}
.bfill{height:100%;border-radius:4px;transition:width .9s cubic-bezier(.4,0,.2,1)}
.bval{width:80px;color:var(--text2);font-size:12px;text-align:right;flex-shrink:0}
/* Charts */
.chart-wrap{position:relative;height:160px;margin:4px 0}
canvas{display:block}
/* Tables */
.tbl{width:100%;border-collapse:collapse;table-layout:fixed}
.tbl th{font-size:10px;font-weight:600;color:var(--text3);padding:8px 10px;text-align:left;border-bottom:1px solid var(--border);text-transform:uppercase;letter-spacing:.4px}
.tbl td{font-size:12px;color:var(--text);padding:8px 10px;border-bottom:1px solid var(--border)}
.tbl tr:last-child td{border-bottom:none}
.tbl tr:hover td{background:var(--bg3)}
.rank-badge{width:22px;height:22px;border-radius:6px;display:inline-flex;align-items:center;justify-content:center;font-size:11px;font-weight:700}
.r1{background:#ffd70022;color:#ffd700}.r2{background:#c0c0c022;color:#c0c0c0}.r3{background:#cd7f3222;color:#cd7f32}.rn{background:var(--bg3);color:var(--text3)}
.tag{display:inline-block;font-size:10px;padding:2px 7px;border-radius:6px;background:var(--bg4);color:var(--text2);font-weight:500;border:1px solid var(--border2)}
.tag-blue{background:#6c8fff22;color:#6c8fff;border-color:#6c8fff44}
.stars{color:var(--accent3);font-size:12px;letter-spacing:-1px}
.stars-e{color:var(--text3);font-size:12px;letter-spacing:-1px}
/* Score pills */
.spill{display:inline-block;padding:2px 8px;border-radius:6px;font-size:11px;font-weight:600}
.sg{background:#69db7c22;color:#69db7c}.so{background:#ffd43b22;color:#ffd43b}.sb{background:#ff6b6b22;color:#ff6b6b}
/* Query form */
.qform{display:flex;gap:8px;margin-bottom:14px}
.qform select,.qform input{height:36px;padding:0 12px;background:var(--bg3);border:1px solid var(--border2);border-radius:8px;color:var(--text);font-size:13px;outline:none}
.qform select:focus,.qform input:focus{border-color:var(--accent)}
.btn{height:36px;padding:0 16px;border-radius:8px;border:1px solid var(--border2);background:var(--bg3);color:var(--text);cursor:pointer;font-size:13px;font-weight:500;transition:all .15s}
.btn:hover{background:var(--bg4);border-color:var(--accent)}
.btn-primary{background:var(--accent);color:#fff;border-color:var(--accent)}
.btn-primary:hover{background:#5573ee}
/* Result hint */
.rhint{padding:12px 14px;background:var(--bg3);border-radius:8px;border:1px solid var(--border);color:var(--text2);line-height:1.7;min-height:44px;font-size:13px}
.rhint .hl{color:var(--accent);font-weight:600}
.err-txt{color:var(--red)}
/* Histogram custom */
.hist-outer{display:flex;align-items:flex-end;gap:2px;height:90px;padding-bottom:0}
.hbar{flex:1;border-radius:3px 3px 0 0;min-width:4px;background:var(--accent);position:relative;cursor:pointer;transition:background .15s}
.hbar:hover{background:var(--accent2)}
.hbar .htip{position:absolute;bottom:calc(100% + 4px);left:50%;transform:translateX(-50%);background:var(--bg4);border:1px solid var(--border2);color:var(--text);padding:3px 8px;border-radius:6px;font-size:10px;white-space:nowrap;display:none;z-index:10}
.hbar:hover .htip{display:block}
.hxlbl{display:flex;gap:2px;font-size:9px;color:var(--text3);margin-top:3px}
.hxlbl span{flex:1;text-align:center}
/* Genre radar placeholder */
.genre-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:6px}
.genre-pill{display:flex;align-items:center;gap:8px;background:var(--bg3);border-radius:8px;padding:8px 10px;border:1px solid var(--border)}
.genre-name{flex:1;font-size:12px;color:var(--text)}
.genre-bar{width:80px;height:6px;background:var(--bg4);border-radius:3px;overflow:hidden}
.genre-fill{height:100%;border-radius:3px;background:var(--accent2)}
.genre-avg{font-size:12px;color:var(--accent2);font-weight:600;width:32px;text-align:right}
/* Compare */
.cmp-grid{display:grid;gap:10px}
.cmp-card{background:var(--bg3);border-radius:10px;padding:14px;border:1px solid var(--border)}
.cmp-title{font-size:13px;font-weight:600;color:var(--text);margin-bottom:8px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.cmp-score{font-size:28px;font-weight:700;color:var(--accent3)}
.cmp-sub{font-size:11px;color:var(--text2);margin-top:2px}
/* Scrollbar */
::-webkit-scrollbar{width:5px;height:5px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--border2);border-radius:4px}
/* Trend line */
.tline{width:100%;height:120px}
</style>
</head>
<body>
<div class="layout">
<div class="sidebar">
  <div class="brand">
    <div class="brand-icon">🎬</div>
    <div><div class="brand-name">电影分析系统</div><div class="brand-sub">Movie Analysis Pro</div></div>
  </div>
  <nav class="nav" id="nav">
    <div class="nav-section">主要功能</div>
    <div class="nav-item active" data-page="overview"><span class="ico">📊</span>数据概览</div>
    <div class="nav-item" data-page="rating"><span class="ico">⭐</span>评分统计</div>
    <div class="nav-item" data-page="top"><span class="ico">🏆</span>热门排行</div>
    <div class="nav-section">深度分析</div>
    <div class="nav-item" data-page="genre"><span class="ico">🎭</span>类型分析</div>
    <div class="nav-item" data-page="user"><span class="ico">👥</span>用户分析</div>
    <div class="nav-item" data-page="trend"><span class="ico">📈</span>趋势分析</div>
    <div class="nav-section">工具</div>
    <div class="nav-item" data-page="query"><span class="ico">🔍</span>详情查询</div>
    <div class="nav-item" data-page="compare"><span class="ico">⚖️</span>电影对比</div>
    <div class="nav-item" data-page="crud"><span class="ico">🗃️</span>数据管理</div>
  </nav>
  <div class="sidebar-foot"><div class="status-row"><div class="dot-green"></div>数据已就绪 · <span id="rec-count">-</span> 条记录</div></div>
</div>

<div class="main">
  <div class="topbar">
    <span class="topbar-title" id="pt">数据概览</span>
    <span class="topbar-pill" id="pb">OVERVIEW</span>
    <div class="topbar-spacer"></div>
    <span class="topbar-info" id="ptime"></span>
  </div>
  <div class="content">

    <div class="page active" id="page-overview"><div id="ov-inner"><div style="color:var(--text2);padding:40px;text-align:center">加载中…</div></div></div>
    <div class="page" id="page-rating"><div id="rt-inner"><div style="color:var(--text2);padding:40px;text-align:center">加载中…</div></div></div>
    <div class="page" id="page-top"><div id="tp-inner"><div style="color:var(--text2);padding:40px;text-align:center">加载中…</div></div></div>
    <div class="page" id="page-genre"><div id="gn-inner"><div style="color:var(--text2);padding:40px;text-align:center">加载中…</div></div></div>
    <div class="page" id="page-user"><div id="us-inner"><div style="color:var(--text2);padding:40px;text-align:center">加载中…</div></div></div>
    <div class="page" id="page-trend"><div id="tr-inner"><div style="color:var(--text2);padding:40px;text-align:center">加载中…</div></div></div>

    <div class="page" id="page-query">
      <div class="card">
        <div class="card-title"><span class="ico">🔍</span>详情查询</div>
        <div class="qform">
          <select id="qt" style="width:130px;flex-shrink:0"><option value="movie">按电影 ID</option><option value="user">按用户 ID</option></select>
          <input id="qi" type="text" placeholder="输入数字 ID，例如 1 或 5" style="flex:1">
          <button class="btn btn-primary" onclick="doQ()">查询</button>
        </div>
        <div class="rhint" id="qh">输入电影 ID 或用户 ID 后查询，系统将展示完整详情。</div>
      </div>
      <div id="qd"></div>
    </div>

    <div class="page" id="page-compare">
      <div class="card">
        <div class="card-title"><span class="ico">⚖️</span>电影多维对比</div>
        <div class="qform">
          <input id="ci" type="text" placeholder="输入多个电影 ID，用逗号分隔，例如：1,2,3,4" style="flex:1">
          <button class="btn btn-primary" onclick="doCmp()">对比</button>
        </div>
        <div class="rhint" id="ch">最多支持6部电影同时对比，展示评分、分布、类型等多维度数据。</div>
      </div>
      <div id="cd"></div>
    </div>


    <!-- 数据管理页 -->
    <div class="page" id="page-crud">
      <div class="card">
        <div class="card-title"><span class="ico">🎬</span>电影管理
          <button class="btn btn-primary" style="margin-left:auto;font-size:12px;height:30px;padding:0 12px" onclick="showMovieModal()">＋ 新增电影</button>
        </div>
        <div style="overflow-x:auto">
        <table class="tbl" id="movie-tbl">
          <thead><tr><th style="width:50px">ID</th><th>电影名称</th><th>类型</th><th style="width:110px">操作</th></tr></thead>
          <tbody id="movie-tbody"><tr><td colspan="4" style="text-align:center;color:var(--text3)">加载中…</td></tr></tbody>
        </table>
        </div>
      </div>
      <div class="card" style="margin-top:0">
        <div class="card-title"><span class="ico">⭐</span>评分管理
          <button class="btn btn-primary" style="margin-left:auto;font-size:12px;height:30px;padding:0 12px" onclick="showRatingModal()">＋ 新增评分</button>
        </div>
        <div style="display:flex;gap:8px;margin-bottom:10px">
          <input id="r-filter-uid" type="text" placeholder="筛选用户ID" style="width:120px;height:32px;padding:0 10px;background:var(--bg3);border:1px solid var(--border2);border-radius:7px;color:var(--text);font-size:12px;outline:none">
          <input id="r-filter-mid" type="text" placeholder="筛选电影ID" style="width:120px;height:32px;padding:0 10px;background:var(--bg3);border:1px solid var(--border2);border-radius:7px;color:var(--text);font-size:12px;outline:none">
          <button class="btn" style="height:32px;font-size:12px" onclick="loadRatings(1)">筛选</button>
          <button class="btn" style="height:32px;font-size:12px" onclick="document.getElementById('r-filter-uid').value='';document.getElementById('r-filter-mid').value='';loadRatings(1)">重置</button>
          <span style="margin-left:auto;font-size:11px;color:var(--text3);align-self:center" id="r-total-info"></span>
        </div>
        <div style="overflow-x:auto">
        <table class="tbl">
          <thead><tr><th style="width:70px">用户ID</th><th style="width:70px">电影ID</th><th>电影名称</th><th style="width:60px">评分</th><th style="width:110px">操作</th></tr></thead>
          <tbody id="rating-tbody"><tr><td colspan="5" style="text-align:center;color:var(--text3)">加载中…</td></tr></tbody>
        </table>
        </div>
        <div style="display:flex;align-items:center;gap:6px;margin-top:10px" id="r-pagination"></div>
      </div>
    </div>

  </div>
</div>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
<script>
const TITLES={overview:'数据概览',rating:'评分统计',top:'热门排行',genre:'类型分析',user:'用户分析',trend:'趋势分析',query:'详情查询',compare:'电影对比',crud:'数据管理'}
const BADGES={overview:'OVERVIEW',rating:'RATING STAT',top:'TOP RANK',genre:'GENRE',user:'USER STAT',trend:'TREND',query:'QUERY',compare:'COMPARE',crud:'CRUD'}
const C={accent:'#6c8fff',accent2:'#4ecdc4',accent3:'#ffd166',accent4:'#ff6b9d',red:'#ff6b6b',green:'#69db7c',text2:'#9ba3b8',bg3:'#242836',border:'#2e3347'}
const SEG_C=['#ff6b6b','#ffa94d','#ffd43b','#69db7c','#74c0fc']

document.getElementById('ptime').textContent = new Date().toLocaleDateString('zh-CN',{year:'numeric',month:'long',day:'numeric'})

const charts={}
function mkChart(id, cfg){
  if(charts[id]){charts[id].destroy();delete charts[id]}
  const ctx=document.getElementById(id)
  if(!ctx)return
  charts[id]=new Chart(ctx,cfg)
}

Chart.defaults.color=C.text2
Chart.defaults.borderColor=C.border
Chart.defaults.font.family="-apple-system,'Microsoft YaHei','Segoe UI',sans-serif"
Chart.defaults.font.size=11

async function api(ep){const r=await fetch('/api/'+ep);return r.json()}

const loaded={}
document.getElementById('nav').addEventListener('click',e=>{
  const item=e.target.closest('.nav-item')
  if(!item)return
  const p=item.dataset.page
  document.querySelectorAll('.nav-item').forEach(n=>n.classList.remove('active'))
  item.classList.add('active')
  document.querySelectorAll('.page').forEach(pg=>pg.classList.remove('active'))
  document.getElementById('page-'+p).classList.add('active')
  document.getElementById('pt').textContent=TITLES[p]
  document.getElementById('pb').textContent=BADGES[p]
  if(!loaded[p]){loaded[p]=true;if(p==='crud'){loadMovies();loadRatings(1)}else{pages[p]&&pages[p]()}}
})

function hbars(data,maxV,colors){
  return data.map((v,i)=>{
    const h=maxV>0?Math.round(v/maxV*85):2
    const c=Array.isArray(colors)?colors[i%colors.length]:colors
    return `<div class="hbar" style="height:${h}px;background:${c}"><div class="htip">${v}</div></div>`
  }).join('')
}

// ── Overview ──────────────────────────────────────────────────────
async function renderOverview(){
  const d=await api('overview')
  document.getElementById('rec-count').textContent=d.records.toLocaleString()
  const maxS=Math.max(...d.segments.map(s=>s.count))
  document.getElementById('ov-inner').innerHTML=`
    <div class="metrics g3">
      <div class="metric metric-accent"><div class="metric-lbl">电影总数</div><div class="metric-val">${d.movies}</div><div class="metric-sub">部影片</div></div>
      <div class="metric"><div class="metric-lbl">注册用户</div><div class="metric-val">${d.users}</div><div class="metric-sub">位用户</div></div>
      <div class="metric"><div class="metric-lbl">评分记录</div><div class="metric-val">${d.records.toLocaleString()}</div><div class="metric-sub">条数据</div></div>
      <div class="metric"><div class="metric-lbl">全局均分</div><div class="metric-val" style="color:var(--accent3)">${d.avg}</div><div class="metric-sub">满分 5.0</div></div>
      <div class="metric"><div class="metric-lbl">电影类型</div><div class="metric-val">${d.genres_count}</div><div class="metric-sub">种类型</div></div>
      <div class="metric"><div class="metric-lbl">评分标准差</div><div class="metric-val">${d.std}</div><div class="metric-sub">分布均匀</div></div>
    </div>
    <div class="card">
      <div class="card-title"><span class="ico">📊</span>评分段分布 · 全量数据</div>
      ${d.segments.map((s,i)=>`
        <div class="brow">
          <span class="blbl">${s.label}</span>
          <div class="btrack"><div class="bfill" style="width:${Math.round(s.count/maxS*100)}%;background:${SEG_C[i]}"></div>
            <span style="position:absolute;right:6px;top:3px;font-size:10px;color:var(--bg)">${s.pct}%</span></div>
          <span class="bval">${s.count.toLocaleString()}</span>
        </div>`).join('')}
    </div>
    <div class="card">
      <div class="card-title"><span class="ico">📈</span>评分频率概览</div>
      <div class="hist-outer">${hbars(d.freq.map(f=>f.count),Math.max(...d.freq.map(f=>f.count)),C.accent)}</div>
      <div class="hxlbl">${d.freq.map(f=>`<span>${f.score}</span>`).join('')}</div>
    </div>`
}

// ── Rating ────────────────────────────────────────────────────────
async function renderRating(){
  const d=await api('rating')
  document.getElementById('rt-inner').innerHTML=`
    <div class="metrics g4">
      <div class="metric"><div class="metric-lbl">平均分</div><div class="metric-val" style="color:var(--accent)">${d.avg}</div></div>
      <div class="metric"><div class="metric-lbl">中位数</div><div class="metric-val">${d.median}</div></div>
      <div class="metric"><div class="metric-lbl">众数</div><div class="metric-val">${d.mode}</div></div>
      <div class="metric"><div class="metric-lbl">标准差</div><div class="metric-val">${d.std}</div></div>
    </div>
    <div class="metrics g3">
      <div class="metric"><div class="metric-lbl">Q1 (25%)</div><div class="metric-val" style="font-size:18px">${d.q1}</div></div>
      <div class="metric"><div class="metric-lbl">Q3 (75%)</div><div class="metric-val" style="font-size:18px">${d.q3}</div></div>
      <div class="metric"><div class="metric-lbl">IQR 四分距</div><div class="metric-val" style="font-size:18px">${d.iqr}</div></div>
    </div>
    <div class="card">
      <div class="card-title"><span class="ico">📊</span>评分频率分布</div>
      <div class="chart-wrap"><canvas id="rt-chart"></canvas></div>
    </div>
    <div class="card">
      <div class="card-title"><span class="ico">🥧</span>各分数段占比</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;align-items:center">
        <div style="height:180px;position:relative"><canvas id="rt-pie"></canvas></div>
        <div>${d.segments.map((s,i)=>`
          <div class="brow" style="margin-bottom:6px">
            <span class="blbl" style="width:80px">${s.label}</span>
            <div class="btrack"><div class="bfill" style="width:${s.count/d.total*100}%;background:${SEG_C[i]}"></div></div>
            <span class="bval">${s.pct}%</span>
          </div>`).join('')}</div>
      </div>
    </div>`
  setTimeout(()=>{
    mkChart('rt-chart',{type:'bar',data:{labels:d.freq.map(f=>f.score),datasets:[{label:'评分次数',data:d.freq.map(f=>f.count),backgroundColor:d.freq.map((_,i)=>SEG_C[Math.floor(i/d.freq.length*5)]),borderRadius:4,borderSkipped:false}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{callbacks:{title:t=>`${t[0].label} 分`}}},scales:{x:{grid:{color:C.border}},y:{grid:{color:C.border}}}}})
    mkChart('rt-pie',{type:'doughnut',data:{labels:d.segments.map(s=>s.label),datasets:[{data:d.segments.map(s=>s.count),backgroundColor:SEG_C,borderWidth:2,borderColor:'#1a1d27'}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},cutout:'62%'}})
  },100)
}

// ── Top ───────────────────────────────────────────────────────────
async function renderTop(){
  const d=await api('top')
  const mc=['r1','r2','r3']
  document.getElementById('tp-inner').innerHTML=`
    <div class="card">
      <div class="card-title"><span class="ico">🥇</span>口碑最佳 Top 15 <span class="tag tag-blue" style="margin-left:6px">≥5人评分</span></div>
      <div style="overflow-x:auto">
      <table class="tbl">
        <thead><tr><th style="width:44px">排名</th><th>电影名称</th><th style="width:90px">类型</th><th style="width:64px">均分</th><th style="width:60px">评分数</th><th style="width:64px">稳定性</th><th style="width:80px">星级</th></tr></thead>
        <tbody>${d.top.map((m,i)=>{
          const s=Math.round(m.avg)
          const stab=m.std<0.8?'<span class="spill sg">稳定</span>':m.std<1.2?'<span class="spill so">一般</span>':'<span class="spill sb">波动</span>'
          return `<tr><td><span class="rank-badge ${mc[i]||'rn'}">${m.rank}</span></td>
            <td style="font-weight:600;max-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${m.title}</td>
            <td><span class="tag">${m.genre}</span></td>
            <td style="color:var(--accent3);font-weight:700">${m.avg}</td>
            <td style="color:var(--text2)">${m.votes}</td>
            <td>${stab}</td>
            <td><span class="stars">${'★'.repeat(s)}</span><span class="stars-e">${'☆'.repeat(5-s)}</span></td></tr>`}).join('')}
        </tbody>
      </table></div>
    </div>
    <div class="card">
      <div class="card-title"><span class="ico">📊</span>评分可视化对比（Top 10）</div>
      <div class="chart-wrap" style="height:200px"><canvas id="top-chart"></canvas></div>
    </div>
    <div class="card">
      <div class="card-title"><span class="ico">⬇️</span>口碑最差 Bottom 10</div>
      <div style="overflow-x:auto">
      <table class="tbl">
        <thead><tr><th style="width:44px">排名</th><th>电影名称</th><th style="width:90px">类型</th><th style="width:64px">均分</th><th style="width:60px">评分数</th></tr></thead>
        <tbody>${d.bottom.map(m=>`<tr>
          <td style="color:var(--text3)">${m.rank}</td>
          <td style="max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${m.title}</td>
          <td><span class="tag">${m.genre}</span></td>
          <td style="color:var(--red);font-weight:700">${m.avg}</td>
          <td style="color:var(--text2)">${m.votes}</td></tr>`).join('')}
        </tbody>
      </table></div>
    </div>`
  setTimeout(()=>{
    const t10=d.top.slice(0,10)
    mkChart('top-chart',{type:'bar',data:{labels:t10.map(m=>m.title.length>8?m.title.slice(0,8)+'…':m.title),datasets:[{label:'平均分',data:t10.map(m=>m.avg),backgroundColor:C.accent+'cc',borderRadius:6,borderSkipped:false}]},options:{indexAxis:'y',responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{min:0,max:5,grid:{color:C.border}},y:{grid:{display:false}}}}})
  },100)
}

// ── Genre ─────────────────────────────────────────────────────────
async function renderGenre(){
  const d=await api('genre')
  const maxAvg=Math.max(...d.genres.map(g=>g.avg))
  const maxCnt=Math.max(...d.genres.map(g=>g.count))
  document.getElementById('gn-inner').innerHTML=`
    <div class="card">
      <div class="card-title"><span class="ico">🎭</span>各类型平均评分</div>
      <div class="chart-wrap" style="height:200px"><canvas id="gn-chart"></canvas></div>
    </div>
    <div class="card">
      <div class="card-title"><span class="ico">🗂️</span>类型详情一览</div>
      <div class="genre-grid">${d.genres.slice(0,16).map(g=>`
        <div class="genre-pill">
          <span class="genre-name">${g.genre}</span>
          <div class="genre-bar"><div class="genre-fill" style="width:${Math.round(g.count/maxCnt*100)}%"></div></div>
          <span class="genre-avg">${g.avg}</span>
        </div>`).join('')}
      </div>
    </div>
    <div class="card">
      <div class="card-title"><span class="ico">🎬</span>各类型电影数量</div>
      <div class="hist-outer">${hbars(d.movie_counts.map(g=>g.count),Math.max(...d.movie_counts.map(g=>g.count)),C.accent2)}</div>
      <div class="hxlbl">${d.movie_counts.map(g=>`<span>${g.genre.slice(0,5)}</span>`).join('')}</div>
    </div>`
  setTimeout(()=>{
    const top12=d.genres.slice(0,12)
    mkChart('gn-chart',{type:'radar',data:{labels:top12.map(g=>g.genre),datasets:[{label:'平均评分',data:top12.map(g=>g.avg),backgroundColor:C.accent+'33',borderColor:C.accent,pointBackgroundColor:C.accent,pointRadius:3}]},options:{responsive:true,maintainAspectRatio:false,scales:{r:{min:2.5,max:4.5,grid:{color:C.border},pointLabels:{color:C.text2,font:{size:10}},ticks:{color:C.text2,backdropColor:'transparent'}}},plugins:{legend:{display:false}}}})
  },100)
}

// ── User ──────────────────────────────────────────────────────────
async function renderUser(){
  const d=await api('user')
  const maxC=d.top[0].count
  const maxH=Math.max(...d.hist.counts)
  document.getElementById('us-inner').innerHTML=`
    <div class="metrics g3">
      <div class="metric metric-accent"><div class="metric-lbl">总用户数</div><div class="metric-val">${d.total}</div><div class="metric-sub">位</div></div>
      <div class="metric"><div class="metric-lbl">人均评分次数</div><div class="metric-val">${d.avg_cnt}</div><div class="metric-sub">次</div></div>
      <div class="metric"><div class="metric-lbl">最多评分（单人）</div><div class="metric-val">${d.max_cnt}</div><div class="metric-sub">次</div></div>
      <div class="metric"><div class="metric-lbl">活跃用户(≥5次)</div><div class="metric-val">${d.gte5}</div><div class="metric-sub">人</div></div>
      <div class="metric"><div class="metric-lbl">核心用户(≥10次)</div><div class="metric-val">${d.gte10}</div><div class="metric-sub">人</div></div>
      <div class="metric"><div class="metric-lbl">超级用户(≥20次)</div><div class="metric-val">${d.gte20}</div><div class="metric-sub">人</div></div>
    </div>
    <div class="card">
      <div class="card-title"><span class="ico">📉</span>用户评分次数分布（长尾效应）</div>
      <div class="hist-outer">${hbars(d.hist.counts,maxH,C.accent)}</div>
      <div class="hxlbl">${d.hist.edges.slice(0,-1).map(e=>`<span>${Math.round(e)}</span>`).join('')}</div>
    </div>
    <div class="card">
      <div class="card-title"><span class="ico">🏅</span>最活跃用户 Top 15</div>
      <div style="overflow-x:auto">
      <table class="tbl">
        <thead><tr><th style="width:44px">排名</th><th style="width:80px">用户 ID</th><th style="width:70px">评分数</th><th style="width:70px">均分</th><th style="width:60px">稳定性</th><th>活跃度</th></tr></thead>
        <tbody>${d.top.map((u,i)=>{
          const mc=['r1','r2','r3']
          const w=Math.round(u.count/maxC*100)
          const stab=u.std<0.8?'<span class="spill sg">稳定</span>':u.std<1.2?'<span class="spill so">普通</span>':'<span class="spill sb">分散</span>'
          return `<tr>
            <td><span class="rank-badge ${mc[i]||'rn'}">${i+1}</span></td>
            <td style="font-weight:600">用户 ${u.uid}</td>
            <td style="color:var(--accent3);font-weight:700">${u.count}</td>
            <td>${u.avg}</td>
            <td>${stab}</td>
            <td><div class="btrack" style="height:14px"><div class="bfill" style="width:${w}%;background:var(--accent)"></div></div></td>
          </tr>`}).join('')}
        </tbody>
      </table></div>
    </div>`
}

// ── Trend ─────────────────────────────────────────────────────────
async function renderTrend(){
  const d=await api('trend')
  document.getElementById('tr-inner').innerHTML=`
    <div class="card">
      <div class="card-title"><span class="ico">📅</span>年度评分均值趋势</div>
      <div class="chart-wrap" style="height:180px"><canvas id="yr-chart"></canvas></div>
    </div>
    <div class="card">
      <div class="card-title"><span class="ico">📅</span>月度评分均值 & 活跃度</div>
      <div class="chart-wrap" style="height:160px"><canvas id="mo-chart"></canvas></div>
    </div>
    <div class="card">
      <div class="card-title"><span class="ico">📊</span>年度评分量趋势</div>
      <div class="chart-wrap" style="height:160px"><canvas id="yc-chart"></canvas></div>
    </div>`
  const MN=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
  setTimeout(()=>{
    if(d.yearly.length>0){
      mkChart('yr-chart',{type:'line',data:{labels:d.yearly.map(y=>y.year),datasets:[{label:'年均分',data:d.yearly.map(y=>y.avg),borderColor:C.accent,backgroundColor:C.accent+'22',fill:true,tension:.4,pointRadius:3,pointBackgroundColor:C.accent}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{grid:{color:C.border}},y:{min:2.5,max:4.5,grid:{color:C.border}}}}})
      mkChart('yc-chart',{type:'bar',data:{labels:d.yearly.map(y=>y.year),datasets:[{label:'评分数',data:d.yearly.map(y=>y.count),backgroundColor:C.accent2+'99',borderRadius:4}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{grid:{display:false}},y:{grid:{color:C.border}}}}})
    }
    if(d.monthly.length>0){
      mkChart('mo-chart',{type:'line',data:{labels:d.monthly.map(m=>MN[m.month-1]||m.month),datasets:[{label:'月均分',data:d.monthly.map(m=>m.avg),borderColor:C.accent3,backgroundColor:C.accent3+'22',fill:true,tension:.4,pointRadius:3,pointBackgroundColor:C.accent3},{label:'评分量',data:d.monthly.map(m=>m.count),borderColor:C.accent4,tension:.4,pointRadius:2,yAxisID:'y2'}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{labels:{color:C.text2,font:{size:11}}}},scales:{x:{grid:{color:C.border}},y:{min:2.8,max:4.2,grid:{color:C.border},position:'left'},y2:{grid:{display:false},position:'right'}}}})
    }
  },100)
}

// ── Query ─────────────────────────────────────────────────────────
document.getElementById('qi').addEventListener('keydown',e=>{if(e.key==='Enter')doQ()})
async function doQ(){
  const type=document.getElementById('qt').value
  const val=document.getElementById('qi').value.trim()
  const hint=document.getElementById('qh')
  const det=document.getElementById('qd')
  if(!val){hint.innerHTML='请输入 ID 编号。';det.innerHTML='';return}
  hint.innerHTML='查询中…'
  const d=await api(`query?type=${type}&id=${val}`)
  if(d.error){hint.innerHTML=`<span class="err-txt">❌ ${d.error}</span>`;det.innerHTML='';return}
  if(d.type==='movie'){
    const mx=d.dist.length?Math.max(...d.dist.map(x=>x.count)):1
    hint.innerHTML=`找到电影 <span class="hl">${d.title}</span>，类型 <span class="hl">${d.genres}</span>，共 <span class="hl">${d.votes}</span> 人评分，均分 <span class="hl">${d.avg}</span>，标准差 <span class="hl">${d.std}</span>。`
    det.innerHTML=`
      <div class="card">
        <div class="card-title"><span class="ico">🎬</span>${d.title}</div>
        <div class="metrics g4" style="margin-bottom:12px">
          <div class="metric"><div class="metric-lbl">均分</div><div class="metric-val" style="color:var(--accent3)">${d.avg}</div></div>
          <div class="metric"><div class="metric-lbl">评分人数</div><div class="metric-val">${d.votes}</div></div>
          <div class="metric"><div class="metric-lbl">最高/最低</div><div class="metric-val" style="font-size:16px">${d.max} / ${d.min}</div></div>
          <div class="metric"><div class="metric-lbl">标准差</div><div class="metric-val">${d.std}</div></div>
        </div>
        <div style="font-size:11px;color:var(--text3);margin-bottom:12px">类型标签：${d.genres.split('|').map(g=>`<span class="tag" style="margin-right:4px">${g}</span>`).join('')}</div>
        <div class="card-title"><span class="ico">📊</span>评分分布</div>
        ${d.dist.map(x=>`<div class="brow"><span class="blbl">${x.score.toFixed(1)} 分</span><div class="btrack"><div class="bfill" style="width:${Math.round(x.count/mx*100)}%;background:var(--accent)"></div></div><span class="bval">${x.count} 人</span></div>`).join('')}
        ${d.similar.length?`<div class="card-title" style="margin-top:14px"><span class="ico">🎯</span>相关推荐</div>
        <div style="display:flex;flex-wrap:wrap;gap:6px">${d.similar.map(s=>`<span class="tag" style="padding:4px 10px">${s.title} · ${s.avg}</span>`).join('')}</div>`:''}
      </div>`
    setTimeout(()=>{},100)
  } else {
    const lc=l=>l==='强烈推荐'?'sg':l==='推荐'?'sg':l==='一般'?'so':'sb'
    hint.innerHTML=`用户 <span class="hl">${d.uid}</span> 共评分 <span class="hl">${d.total}</span> 部电影，个人均分 <span class="hl">${d.avg}</span>，最喜欢类型 <span class="hl">${d.fav_genre}</span>。`
    det.innerHTML=`
      <div class="card">
        <div class="card-title"><span class="ico">👤</span>用户 ${d.uid} · 完整评分记录</div>
        <div class="metrics g4" style="margin-bottom:12px">
          <div class="metric"><div class="metric-lbl">评分总数</div><div class="metric-val">${d.total}</div></div>
          <div class="metric"><div class="metric-lbl">个人均分</div><div class="metric-val" style="color:var(--accent)">${d.avg}</div></div>
          <div class="metric"><div class="metric-lbl">最高/最低</div><div class="metric-val" style="font-size:16px">${d.max} / ${d.min}</div></div>
          <div class="metric"><div class="metric-lbl">最爱类型</div><div class="metric-val" style="font-size:16px">${d.fav_genre}</div></div>
        </div>
        <div style="overflow-x:auto">
        <table class="tbl">
          <thead><tr><th>电影名称</th><th style="width:60px">评分</th><th style="width:80px">评价</th></tr></thead>
          <tbody>${d.movies.map(m=>`<tr><td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-weight:500">${m.title}</td><td style="font-weight:700;color:var(--accent3)">${m.rating.toFixed(1)}</td><td><span class="spill ${lc(m.label)}">${m.label}</span></td></tr>`).join('')}</tbody>
        </table></div>
      </div>`
  }
}

// ── Compare ───────────────────────────────────────────────────────
document.getElementById('ci').addEventListener('keydown',e=>{if(e.key==='Enter')doCmp()})
async function doCmp(){
  const val=document.getElementById('ci').value.trim()
  const hint=document.getElementById('ch')
  const det=document.getElementById('cd')
  if(!val){hint.innerHTML='请输入电影ID，用逗号分隔。';det.innerHTML='';return}
  hint.innerHTML='对比中…'
  const d=await api('compare?ids='+encodeURIComponent(val))
  if(d.error){hint.innerHTML=`<span class="err-txt">❌ ${d.error}</span>`;det.innerHTML='';return}
  const best=d.movies.reduce((a,b)=>a.avg>b.avg?a:b)
  hint.innerHTML=`共对比 <span class="hl">${d.movies.length}</span> 部电影。综合评分最高：<span class="hl">${best.title}（${best.avg}分）</span>。`
  const cols=d.movies.length<=3?d.movies.length:3
  det.innerHTML=`
    <div class="card">
      <div class="card-title"><span class="ico">📊</span>综合评分对比</div>
      <div class="chart-wrap" style="height:180px"><canvas id="cmp-chart"></canvas></div>
    </div>
    <div class="card">
      <div class="card-title"><span class="ico">🗂️</span>详细数据</div>
      <div class="cmp-grid" style="grid-template-columns:repeat(${cols},1fr)">
        ${d.movies.map(m=>`
          <div class="cmp-card" style="${m.title===best.title?'border-color:var(--accent3)':''}">
            ${m.title===best.title?'<div style="font-size:10px;color:var(--accent3);margin-bottom:6px;font-weight:600">★ 综合最佳</div>':''}
            <div class="cmp-title">${m.title}</div>
            <div class="cmp-score">${m.avg}</div>
            <div class="cmp-sub">${m.votes} 人评分 · 标准差 ${m.std}</div>
            <div style="margin-top:10px;font-size:10px;color:var(--text3)">${m.genres.split('|').slice(0,3).map(g=>`<span class="tag" style="margin-right:3px;margin-bottom:3px">${g}</span>`).join('')}</div>
            <div style="margin-top:10px">${m.dist.map(x=>`<div class="brow" style="margin-bottom:4px"><span style="font-size:10px;color:var(--text2);width:30px;text-align:right;flex-shrink:0">${x.score.toFixed(1)}</span><div class="btrack" style="height:12px"><div class="bfill" style="width:${Math.round(x.count/Math.max(...m.dist.map(x=>x.count))*100)}%;background:var(--accent)"></div></div><span style="font-size:10px;color:var(--text2);width:28px;text-align:right;flex-shrink:0">${x.count}</span></div>`).join('')}</div>
          </div>`).join('')}
      </div>
    </div>`
  setTimeout(()=>{
    mkChart('cmp-chart',{type:'bar',data:{labels:d.movies.map(m=>m.title.length>8?m.title.slice(0,8)+'…':m.title),datasets:[{label:'平均分',data:d.movies.map(m=>m.avg),backgroundColor:d.movies.map(m=>m.title===best.title?C.accent3+'cc':C.accent+'99'),borderRadius:6,borderSkipped:false},{label:'标准差',data:d.movies.map(m=>m.std),backgroundColor:C.accent4+'66',borderRadius:6,borderSkipped:false}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{labels:{color:C.text2}}},scales:{x:{grid:{display:false}},y:{min:0,max:5,grid:{color:C.border}}}}})
  },100)
}

const pages={overview:renderOverview,rating:renderRating,top:renderTop,genre:renderGenre,user:renderUser,trend:renderTrend}
pages.overview()
</script>
</body>
</html>"""


# ── CRUD helpers ──────────────────────────────────────────────────────────────
def save_data():
    """将内存数据写回 CSV"""
    MOVIES.to_csv(MOVIES_CSV, index=False)
    RATINGS.to_csv(RATINGS_CSV, index=False)

def reload_data():
    global MOVIES, RATINGS, MERGED, DATA_OK
    try:
        MOVIES, RATINGS, MERGED = load()
        DATA_OK = True
    except Exception as e:
        DATA_OK = False

# ── 电影 CRUD ─────────────────────────────────────────────────────────────────
def api_movie_list():
    rows = []
    for _, r in MOVIES.iterrows():
        rows.append({"id": int(r['movieId']), "title": str(r['title']), "genres": str(r['genres'])})
    return {"movies": rows}

def api_movie_add(title, genres):
    global MOVIES, MERGED
    title = title.strip(); genres = genres.strip()
    if not title: return {"error": "电影名称不能为空"}
    if MOVIES['title'].str.lower().eq(title.lower()).any():
        return {"error": f"电影《{title}》已存在"}
    new_id = int(MOVIES['movieId'].max()) + 1
    new_row = pd.DataFrame([{"movieId": new_id, "title": title, "genres": genres or "Unknown"}])
    MOVIES = pd.concat([MOVIES, new_row], ignore_index=True)
    MERGED = pd.merge(RATINGS, MOVIES, on='movieId', how='left')
    save_data()
    return {"ok": True, "id": new_id, "msg": f"✅ 电影《{title}》（ID:{new_id}）已添加"}

def api_movie_edit(mid, title, genres):
    global MOVIES, MERGED
    mid = int(mid)
    if not MOVIES['movieId'].eq(mid).any(): return {"error": f"未找到电影 ID {mid}"}
    title = title.strip(); genres = genres.strip()
    if not title: return {"error": "电影名称不能为空"}
    MOVIES.loc[MOVIES['movieId'] == mid, 'title']  = title
    MOVIES.loc[MOVIES['movieId'] == mid, 'genres'] = genres or "Unknown"
    MERGED = pd.merge(RATINGS, MOVIES, on='movieId', how='left')
    save_data()
    return {"ok": True, "msg": f"✅ 电影 ID {mid} 已更新为《{title}》"}

def api_movie_delete(mid):
    global MOVIES, RATINGS, MERGED
    mid = int(mid)
    if not MOVIES['movieId'].eq(mid).any(): return {"error": f"未找到电影 ID {mid}"}
    title = MOVIES.loc[MOVIES['movieId'] == mid, 'title'].iloc[0]
    MOVIES   = MOVIES[MOVIES['movieId'] != mid].reset_index(drop=True)
    RATINGS  = RATINGS[RATINGS['movieId'] != mid].reset_index(drop=True)
    MERGED   = pd.merge(RATINGS, MOVIES, on='movieId', how='left')
    save_data()
    return {"ok": True, "msg": f"✅ 电影《{title}》及其所有评分已删除"}

# ── 评分 CRUD ─────────────────────────────────────────────────────────────────
def api_rating_list(page=1, page_size=30):
    page = max(1, int(page)); ps = int(page_size)
    total = len(RATINGS)
    start = (page - 1) * ps; end = start + ps
    chunk = RATINGS.iloc[start:end].copy()
    chunk = pd.merge(chunk, MOVIES[['movieId','title']], on='movieId', how='left')
    rows = [{"userId": int(r['userId']), "movieId": int(r['movieId']),
             "title": str(r.get('title', '')), "rating": float(r['rating'])}
            for _, r in chunk.iterrows()]
    return {"ratings": rows, "total": total, "page": page,
            "pages": math.ceil(total / ps)}

def api_rating_add(uid, mid, rating):
    global RATINGS, MERGED
    uid = int(uid); mid = int(mid); rating = float(rating)
    if not MOVIES['movieId'].eq(mid).any(): return {"error": f"电影 ID {mid} 不存在"}
    if not 0.5 <= rating <= 5.0: return {"error": "评分须在 0.5 ~ 5.0 之间"}
    exists = RATINGS[(RATINGS['userId']==uid) & (RATINGS['movieId']==mid)]
    if not exists.empty:
        return {"error": f"用户 {uid} 已对电影 {mid} 评过分，请使用编辑功能"}
    import time
    new_row = pd.DataFrame([{"userId": uid, "movieId": mid, "rating": rating,
                              "timestamp": int(time.time())}])
    RATINGS = pd.concat([RATINGS, new_row], ignore_index=True)
    MERGED  = pd.merge(RATINGS, MOVIES, on='movieId', how='left')
    save_data()
    return {"ok": True, "msg": f"✅ 用户 {uid} 对电影 {mid} 的评分 {rating} 已添加"}

def api_rating_edit(uid, mid, rating):
    global RATINGS, MERGED
    uid = int(uid); mid = int(mid); rating = float(rating)
    if not 0.5 <= rating <= 5.0: return {"error": "评分须在 0.5 ~ 5.0 之间"}
    mask = (RATINGS['userId']==uid) & (RATINGS['movieId']==mid)
    if not mask.any(): return {"error": f"未找到用户 {uid} 对电影 {mid} 的评分记录"}
    RATINGS.loc[mask, 'rating'] = rating
    MERGED = pd.merge(RATINGS, MOVIES, on='movieId', how='left')
    save_data()
    return {"ok": True, "msg": f"✅ 用户 {uid} 对电影 {mid} 的评分已更新为 {rating}"}

def api_rating_delete(uid, mid):
    global RATINGS, MERGED
    uid = int(uid); mid = int(mid)
    mask = (RATINGS['userId']==uid) & (RATINGS['movieId']==mid)
    if not mask.any(): return {"error": f"未找到用户 {uid} 对电影 {mid} 的评分记录"}
    RATINGS = RATINGS[~mask].reset_index(drop=True)
    MERGED  = pd.merge(RATINGS, MOVIES, on='movieId', how='left')
    save_data()
    return {"ok": True, "msg": f"✅ 用户 {uid} 对电影 {mid} 的评分已删除"}



def api_rating_list_filtered(page=1, uid='', mid=''):
    page = max(1, int(page)); ps = 30
    df = RATINGS.copy()
    if uid:
        try: df = df[df['userId']==int(uid)]
        except: pass
    if mid:
        try: df = df[df['movieId']==int(mid)]
        except: pass
    total = len(df)
    start = (page-1)*ps; end = start+ps
    chunk = df.iloc[start:end].copy()
    chunk = pd.merge(chunk, MOVIES[['movieId','title']], on='movieId', how='left')
    rows = [{"userId":int(r['userId']),"movieId":int(r['movieId']),
             "title":str(r.get('title','')),"rating":float(r['rating'])}
            for _,r in chunk.iterrows()]
    return {"ratings":rows,"total":total,"page":page,"pages":math.ceil(total/ps) if total>0 else 1}

# ── CRUD 页面 HTML ────────────────────────────────────────────────────────────
CRUD_HTML = r"""

    <!-- 电影弹窗 -->
    <div id="movie-modal" style="display:none;position:fixed;inset:0;background:#00000088;z-index:100;align-items:center;justify-content:center">
      <div style="background:var(--bg2);border:1px solid var(--border2);border-radius:14px;padding:22px 24px;width:380px;box-shadow:0 20px 60px #000a">
        <div style="font-size:14px;font-weight:700;color:var(--text);margin-bottom:16px" id="mm-title">新增电影</div>
        <input type="hidden" id="mm-id">
        <div style="margin-bottom:10px">
          <div style="font-size:11px;color:var(--text3);margin-bottom:4px">电影名称 *</div>
          <input id="mm-name" type="text" placeholder="请输入电影名称" style="width:100%;height:36px;padding:0 12px;background:var(--bg3);border:1px solid var(--border2);border-radius:8px;color:var(--text);font-size:13px;outline:none">
        </div>
        <div style="margin-bottom:16px">
          <div style="font-size:11px;color:var(--text3);margin-bottom:4px">类型（用 | 分隔）</div>
          <input id="mm-genres" type="text" placeholder="如：Action|Drama|Thriller" style="width:100%;height:36px;padding:0 12px;background:var(--bg3);border:1px solid var(--border2);border-radius:8px;color:var(--text);font-size:13px;outline:none">
        </div>
        <div style="font-size:11px;color:var(--red);min-height:16px;margin-bottom:10px" id="mm-err"></div>
        <div style="display:flex;gap:8px;justify-content:flex-end">
          <button class="btn" onclick="closeModal('movie-modal')" style="height:34px">取消</button>
          <button class="btn btn-primary" onclick="submitMovie()" style="height:34px" id="mm-btn">确认添加</button>
        </div>
      </div>
    </div>

    <!-- 评分弹窗 -->
    <div id="rating-modal" style="display:none;position:fixed;inset:0;background:#00000088;z-index:100;align-items:center;justify-content:center">
      <div style="background:var(--bg2);border:1px solid var(--border2);border-radius:14px;padding:22px 24px;width:340px;box-shadow:0 20px 60px #000a">
        <div style="font-size:14px;font-weight:700;color:var(--text);margin-bottom:16px" id="rm-title">新增评分</div>
        <input type="hidden" id="rm-mode">
        <div style="margin-bottom:10px">
          <div style="font-size:11px;color:var(--text3);margin-bottom:4px">用户 ID *</div>
          <input id="rm-uid" type="number" min="1" placeholder="用户ID" style="width:100%;height:36px;padding:0 12px;background:var(--bg3);border:1px solid var(--border2);border-radius:8px;color:var(--text);font-size:13px;outline:none">
        </div>
        <div style="margin-bottom:10px">
          <div style="font-size:11px;color:var(--text3);margin-bottom:4px">电影 ID *</div>
          <input id="rm-mid" type="number" min="1" placeholder="电影ID" style="width:100%;height:36px;padding:0 12px;background:var(--bg3);border:1px solid var(--border2);border-radius:8px;color:var(--text);font-size:13px;outline:none">
        </div>
        <div style="margin-bottom:16px">
          <div style="font-size:11px;color:var(--text3);margin-bottom:4px">评分（0.5 ~ 5.0）*</div>
          <input id="rm-rating" type="number" min="0.5" max="5.0" step="0.5" placeholder="如：4.0" style="width:100%;height:36px;padding:0 12px;background:var(--bg3);border:1px solid var(--border2);border-radius:8px;color:var(--text);font-size:13px;outline:none">
        </div>
        <div style="font-size:11px;color:var(--red);min-height:16px;margin-bottom:10px" id="rm-err"></div>
        <div style="display:flex;gap:8px;justify-content:flex-end">
          <button class="btn" onclick="closeModal('rating-modal')" style="height:34px">取消</button>
          <button class="btn btn-primary" onclick="submitRating()" style="height:34px" id="rm-btn">确认添加</button>
        </div>
      </div>
    </div>

    <!-- Toast 提示 -->
    <div id="toast" style="display:none;position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:var(--bg4);border:1px solid var(--border2);color:var(--text);padding:10px 20px;border-radius:10px;font-size:13px;z-index:200;box-shadow:0 8px 30px #000a;white-space:nowrap"></div>
"""

CRUD_JS = r"""
// ══════════════════════════════════════════════════════
//  增删改查模块
// ══════════════════════════════════════════════════════
function toast(msg, err=false){
  const el=document.getElementById('toast')
  el.textContent=msg
  el.style.color=err?'var(--red)':'var(--green)'
  el.style.display='block'
  clearTimeout(el._t); el._t=setTimeout(()=>el.style.display='none',3000)
}
function closeModal(id){document.getElementById(id).style.display='none'}

// ── 电影表格 ──────────────────────────────────────────
async function loadMovies(){
  const d=await fetch('/api/crud/movie/list').then(r=>r.json())
  const tb=document.getElementById('movie-tbody')
  tb.innerHTML=d.movies.map(m=>`
    <tr>
      <td style="color:var(--text3)">${m.id}</td>
      <td style="font-weight:600">${m.title}</td>
      <td>${m.genres.split('|').slice(0,3).map(g=>`<span class="tag" style="margin-right:3px">${g}</span>`).join('')}</td>
      <td>
        <button class="btn" style="height:26px;font-size:11px;padding:0 8px;margin-right:4px" onclick="editMovie(${m.id},'${m.title.replace(/'/g,"\\'")}','${m.genres.replace(/'/g,"\\'")}')">编辑</button>
        <button class="btn" style="height:26px;font-size:11px;padding:0 8px;background:var(--red);color:#fff;border-color:var(--red)" onclick="deleteMovie(${m.id},'${m.title.replace(/'/g,"\\'")}')">删除</button>
      </td>
    </tr>`).join('')
}

function showMovieModal(id='',name='',genres=''){
  document.getElementById('mm-id').value=id
  document.getElementById('mm-name').value=name
  document.getElementById('mm-genres').value=genres
  document.getElementById('mm-title').textContent=id?'编辑电影':'新增电影'
  document.getElementById('mm-btn').textContent=id?'确认修改':'确认添加'
  document.getElementById('mm-err').textContent=''
  document.getElementById('movie-modal').style.display='flex'
  setTimeout(()=>document.getElementById('mm-name').focus(),50)
}
function editMovie(id,name,genres){showMovieModal(id,name,genres)}

async function submitMovie(){
  const id=document.getElementById('mm-id').value
  const name=document.getElementById('mm-name').value.trim()
  const genres=document.getElementById('mm-genres').value.trim()
  const errEl=document.getElementById('mm-err')
  if(!name){errEl.textContent='电影名称不能为空';return}
  const ep=id?`/api/crud/movie/edit?id=${id}&title=${encodeURIComponent(name)}&genres=${encodeURIComponent(genres)}`
              :`/api/crud/movie/add?title=${encodeURIComponent(name)}&genres=${encodeURIComponent(genres)}`
  const d=await fetch(ep).then(r=>r.json())
  if(d.error){errEl.textContent=d.error;return}
  closeModal('movie-modal'); toast(d.msg); loadMovies()
}

async function deleteMovie(id,name){
  if(!confirm(`确认删除电影《${name}》及其所有评分记录？此操作不可撤销。`))return
  const d=await fetch(`/api/crud/movie/delete?id=${id}`).then(r=>r.json())
  if(d.error){toast(d.error,true);return}
  toast(d.msg); loadMovies(); loadRatings(1)
}

// ── 评分表格 ──────────────────────────────────────────
let curPage=1
async function loadRatings(page=1){
  curPage=page
  const uid=document.getElementById('r-filter-uid').value.trim()
  const mid=document.getElementById('r-filter-mid').value.trim()
  let url=`/api/crud/rating/list?page=${page}`
  if(uid)url+=`&uid=${uid}`; if(mid)url+=`&mid=${mid}`
  const d=await fetch(url).then(r=>r.json())
  document.getElementById('r-total-info').textContent=`共 ${d.total} 条，第 ${d.page}/${d.pages} 页`
  const tb=document.getElementById('rating-tbody')
  tb.innerHTML=d.ratings.length?d.ratings.map(r=>`
    <tr>
      <td>${r.userId}</td>
      <td>${r.movieId}</td>
      <td style="font-weight:500">${r.title||'-'}</td>
      <td style="color:var(--accent3);font-weight:700">${r.rating.toFixed(1)}</td>
      <td>
        <button class="btn" style="height:26px;font-size:11px;padding:0 8px;margin-right:4px" onclick="editRating(${r.userId},${r.movieId},${r.rating})">编辑</button>
        <button class="btn" style="height:26px;font-size:11px;padding:0 8px;background:var(--red);color:#fff;border-color:var(--red)" onclick="deleteRating(${r.userId},${r.movieId})">删除</button>
      </td>
    </tr>`).join(''):'<tr><td colspan="5" style="text-align:center;color:var(--text3);padding:20px">暂无数据</td></tr>'
  // 分页
  const pg=document.getElementById('r-pagination')
  pg.innerHTML=''
  if(d.pages<=1)return
  const addBtn=(txt,p,dis=false)=>{
    const b=document.createElement('button')
    b.className='btn'; b.style.cssText='height:28px;font-size:11px;padding:0 10px'
    b.textContent=txt; b.disabled=dis
    if(!dis)b.onclick=()=>loadRatings(p)
    if(p===curPage)b.style.background='var(--accent)',b.style.color='#fff'
    pg.appendChild(b)
  }
  addBtn('‹',curPage-1,curPage===1)
  const start=Math.max(1,curPage-2),end=Math.min(d.pages,curPage+2)
  for(let i=start;i<=end;i++)addBtn(i,i)
  addBtn('›',curPage+1,curPage===d.pages)
}

function showRatingModal(uid='',mid='',rating=''){
  document.getElementById('rm-uid').value=uid
  document.getElementById('rm-mid').value=mid
  document.getElementById('rm-rating').value=rating
  document.getElementById('rm-mode').value=uid&&mid?'edit':'add'
  document.getElementById('rm-title').textContent=uid&&mid?'编辑评分':'新增评分'
  document.getElementById('rm-btn').textContent=uid&&mid?'确认修改':'确认添加'
  document.getElementById('rm-uid').readOnly=!!(uid&&mid)
  document.getElementById('rm-mid').readOnly=!!(uid&&mid)
  document.getElementById('rm-err').textContent=''
  document.getElementById('rating-modal').style.display='flex'
  setTimeout(()=>document.getElementById('rm-rating').focus(),50)
}
function editRating(uid,mid,rating){showRatingModal(uid,mid,rating)}

async function submitRating(){
  const mode=document.getElementById('rm-mode').value
  const uid=document.getElementById('rm-uid').value
  const mid=document.getElementById('rm-mid').value
  const rating=document.getElementById('rm-rating').value
  const errEl=document.getElementById('rm-err')
  if(!uid||!mid||!rating){errEl.textContent='请填写所有必填项';return}
  const ep=mode==='edit'?`/api/crud/rating/edit?uid=${uid}&mid=${mid}&rating=${rating}`
                        :`/api/crud/rating/add?uid=${uid}&mid=${mid}&rating=${rating}`
  const d=await fetch(ep).then(r=>r.json())
  if(d.error){errEl.textContent=d.error;return}
  closeModal('rating-modal'); toast(d.msg); loadRatings(curPage)
}

async function deleteRating(uid,mid){
  if(!confirm(`确认删除用户 ${uid} 对电影 ${mid} 的评分记录？`))return
  const d=await fetch(`/api/crud/rating/delete?uid=${uid}&mid=${mid}`).then(r=>r.json())
  if(d.error){toast(d.error,true);return}
  toast(d.msg); loadRatings(curPage)
}
"""

class Handler(BaseHTTPRequestHandler):
    def log_message(self,fmt,*a): pass
    def do_GET(self):
        p=urlparse(self.path); qs=parse_qs(p.query)
        ep=p.path
        if ep in('/',''):   self._send(200,'text/html',(HTML.replace('</body>\n</html>','').replace('</body></html>','')+CRUD_HTML+'<script>'+CRUD_JS+'</script></body></html>').encode())
        elif ep=='/api/overview': self._json(api_overview())
        elif ep=='/api/rating':   self._json(api_rating())
        elif ep=='/api/top':      self._json(api_top())
        elif ep=='/api/genre':    self._json(api_genre())
        elif ep=='/api/user':     self._json(api_user())
        elif ep=='/api/trend':    self._json(api_trend())
        elif ep=='/api/query':    self._json(api_query(qs.get('type',['movie'])[0],qs.get('id',['0'])[0]))
        elif ep=='/api/compare':  self._json(api_compare(qs.get('ids',[''])[0]))
        elif ep=='/api/crud/movie/list':   self._json(api_movie_list())
        elif ep=='/api/crud/movie/add':    self._json(api_movie_add(qs.get('title',[''])[0],qs.get('genres',[''])[0]))
        elif ep=='/api/crud/movie/edit':   self._json(api_movie_edit(qs.get('id',['0'])[0],qs.get('title',[''])[0],qs.get('genres',[''])[0]))
        elif ep=='/api/crud/movie/delete': self._json(api_movie_delete(qs.get('id',['0'])[0]))
        elif ep=='/api/crud/rating/list':  self._json(api_rating_list_filtered(qs.get('page',['1'])[0],qs.get('uid',[''])[0],qs.get('mid',[''])[0]))
        elif ep=='/api/crud/rating/add':   self._json(api_rating_add(qs.get('uid',['0'])[0],qs.get('mid',['0'])[0],qs.get('rating',['0'])[0]))
        elif ep=='/api/crud/rating/edit':  self._json(api_rating_edit(qs.get('uid',['0'])[0],qs.get('mid',['0'])[0],qs.get('rating',['0'])[0]))
        elif ep=='/api/crud/rating/delete':self._json(api_rating_delete(qs.get('uid',['0'])[0],qs.get('mid',['0'])[0]))
        else: self._send(404,'text/plain',b'Not Found')
    def _json(self,d): self._send(200,'application/json',json.dumps(d,ensure_ascii=False).encode())
    def _send(self,code,ct,body):
        self.send_response(code)
        self.send_header('Content-Type',ct+'; charset=utf-8')
        self.send_header('Content-Length',len(body))
        self.end_headers(); self.wfile.write(body)

def main():
    PORT = 8765
    srv = HTTPServer(('127.0.0.1', PORT), Handler)
    url = f'http://127.0.0.1:{PORT}'
    print(f"\n    ╔══════════════════════════════════════════╗")
    print(f"    ║   🎬  电影数据分析系统 Pro  已启动           ║")
    print(f"    ╠══════════════════════════════════════════╣")
    print(f"    ║  地址：{url:<33}  ║")
    print(f"    ║  按 Ctrl+C 停止服务                        ║")
    print(f"    ╚══════════════════════════════════════════╝\n")
    threading.Timer(1.0,lambda:webbrowser.open(url)).start()
    try: srv.serve_forever()
    except KeyboardInterrupt: print("\n  服务已停止，再见！\n")

if __name__=='__main__': main()