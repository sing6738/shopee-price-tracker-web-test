"""
dashboard_server.py — Render.com cloud version
รัน: python dashboard_server.py
เปิด https://your-app.onrender.com
"""
import os, json, sqlite3, datetime, threading, time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prices.db")
PORT    = int(os.environ.get("PORT", 8765))
# ใส่ URL ของ Render app ตัวเองหลัง deploy เช่น https://shopee-tracker.onrender.com
SELF_URL = os.environ.get("SELF_URL", "")
# API key กันคนอื่น push ข้อมูล (ตั้งใน Render Environment Variables)
API_KEY  = os.environ.get("TRACKER_API_KEY", "changeme123")

# ─── DB ──────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS price_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT, price_min REAL, price_max REAL,
        stock INTEGER, sold INTEGER, rating REAL,
        url TEXT, checked_at TEXT)""")
    conn.commit(); conn.close()

def get_all_data():
    if not os.path.exists(DB_PATH): return []
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    try:
        c.execute("SELECT * FROM price_history ORDER BY checked_at")
        rows = [dict(r) for r in c.fetchall()]
    except: rows = []
    conn.close()
    return rows

def insert_record(data):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""INSERT INTO price_history
        (title, price_min, price_max, stock, sold, rating, url, checked_at)
        VALUES (?,?,?,?,?,?,?,?)""",
        (data['title'], data['price_min'], data['price_max'],
         data['stock'], data['sold'], data['rating'],
         data['url'], data['checked_at']))
    conn.commit(); conn.close()

import re
def extract_item_id(url):
    m = re.search(r'i\.(\d+)\.(\d+)', url)
    return (m.group(1), m.group(2)) if m else (None, None)

def get_stats():
    rows = get_all_data()
    if not rows: return {"products": [], "total_checks": 0}
    products = {}
    for r in rows:
        _, item_id = extract_item_id(r['url'])
        key = item_id or r['url']
        if key not in products:
            products[key] = {"title": r['title'], "url": r['url'], "history": []}
        products[key]['history'].append(r)
    result = []
    for key, p in products.items():
        hist = p['history']
        latest = hist[-1]
        prices = [h['price_min'] for h in hist if h['price_min'] > 0]
        result.append({
            "title": p['title'], "url": p['url'],
            "latest_price": latest['price_min'],
            "price_max": latest['price_max'],
            "stock": latest['stock'], "sold": latest['sold'],
            "rating": round(latest['rating'], 1) if latest['rating'] else 0,
            "checked_at": latest['checked_at'],
            "min_ever": min(prices) if prices else 0,
            "max_ever": max(prices) if prices else 0,
            "checks": len(hist), "history": hist,
        })
    return {"products": result, "total_checks": len(rows)}

# ─── Keep-alive ping (กัน Render sleep) ──────────
def keep_alive():
    """Ping ตัวเองทุก 14 นาที กัน Render free tier sleep"""
    if not SELF_URL:
        print("ℹ️  SELF_URL ไม่ได้ตั้ง — keep-alive ปิดอยู่")
        return
    import urllib.request
    time.sleep(60)  # รอให้ server start ก่อน
    while True:
        try:
            urllib.request.urlopen(f"{SELF_URL}/ping", timeout=10)
            print(f"🏓 ping OK ({datetime.datetime.now().strftime('%H:%M')})")
        except Exception as e:
            print(f"⚠️ ping failed: {e}")
        time.sleep(14 * 60)  # 14 นาที

# ─── HTML ─────────────────────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Shopee Price Tracker</title>
<link href="https://fonts.googleapis.com/css2?family=Sarabun:wght@300;400;500;600;700&family=Rajdhani:wght@500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<style>
  :root {
    --bg:       #07060f;
    --bg2:      #0d0b1a;
    --surface:  #120f22;
    --surface2: #1a1630;
    --surface3: #221d3a;
    --border:   #2d2650;
    --border2:  #3d3468;
    --violet:   #8b5cf6;
    --violet2:  #a78bfa;
    --violet3:  #c4b5fd;
    --pink:     #d946ef;
    --cyan:     #22d3ee;
    --green:    #34d399;
    --red:      #f87171;
    --gold:     #fbbf24;
    --text:     #ede9fe;
    --text2:    #c4b5fd;
    --muted:    #6b5fa0;
    --muted2:   #4c4575;
    --radius:   14px;
    --radius-sm: 8px;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: 'Sarabun', sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    padding-bottom: 80px;
    overflow-x: hidden;
  }

  /* ── Background grid ── */
  body::before {
    content: '';
    position: fixed; inset: 0; z-index: 0; pointer-events: none;
    background-image:
      linear-gradient(rgba(139,92,246,.04) 1px, transparent 1px),
      linear-gradient(90deg, rgba(139,92,246,.04) 1px, transparent 1px);
    background-size: 40px 40px;
  }

  body::after {
    content: '';
    position: fixed; inset: 0; z-index: 0; pointer-events: none;
    background: radial-gradient(ellipse 80% 50% at 50% -10%, rgba(139,92,246,.18) 0%, transparent 70%);
  }

  /* ── Header ── */
  header {
    position: sticky; top: 0; z-index: 200;
    background: rgba(7,6,15,.85);
    backdrop-filter: blur(20px);
    border-bottom: 1px solid var(--border);
    padding: 0 32px;
    height: 64px;
    display: flex; align-items: center; justify-content: space-between;
  }

  header::after {
    content: '';
    position: absolute; bottom: 0; left: 0; right: 0; height: 1px;
    background: linear-gradient(90deg, transparent, var(--violet), var(--pink), var(--violet), transparent);
    opacity: .5;
  }

  .logo {
    display: flex; align-items: center; gap: 14px;
  }

  .logo-mark {
    width: 38px; height: 38px;
    background: linear-gradient(135deg, var(--violet), var(--pink));
    border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    font-size: 17px;
    box-shadow: 0 0 20px rgba(139,92,246,.5);
    flex-shrink: 0;
  }

  .logo-name {
    font-family: 'Rajdhani', sans-serif;
    font-size: 18px; font-weight: 700;
    letter-spacing: 2px;
    background: linear-gradient(90deg, var(--violet3), var(--pink));
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    text-transform: uppercase;
  }

  .logo-sub {
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px; color: var(--muted); letter-spacing: 1px;
    margin-top: 1px;
    display: flex; align-items: center; gap: 6px;
  }

  .pulse-dot {
    width: 6px; height: 6px; border-radius: 50%;
    background: var(--green);
    box-shadow: 0 0 8px var(--green);
    animation: breathe 2s ease-in-out infinite;
    flex-shrink: 0;
  }

  @keyframes breathe {
    0%,100% { opacity: 1; transform: scale(1); }
    50%      { opacity: .5; transform: scale(.7); }
  }

  .header-right { display: flex; align-items: center; gap: 10px; }

  .btn {
    font-family: 'Rajdhani', sans-serif;
    font-size: 13px; font-weight: 600; letter-spacing: 1.5px;
    text-transform: uppercase;
    padding: 8px 18px; border-radius: var(--radius-sm);
    cursor: pointer; transition: all .2s; border: none;
    display: flex; align-items: center; gap: 7px;
  }

  .btn-ghost {
    background: transparent;
    border: 1px solid var(--border2);
    color: var(--text2);
  }

  .btn-ghost:hover {
    background: var(--surface2);
    border-color: var(--violet);
    color: var(--violet3);
    box-shadow: 0 0 14px rgba(139,92,246,.2);
  }

  .btn-primary {
    background: linear-gradient(135deg, var(--violet), var(--pink));
    color: white;
    box-shadow: 0 4px 18px rgba(139,92,246,.35);
  }

  .btn-primary:hover {
    transform: translateY(-1px);
    box-shadow: 0 6px 24px rgba(139,92,246,.5);
  }

  /* ── Main ── */
  main {
    position: relative; z-index: 1;
    max-width: 1120px; margin: 0 auto;
    padding: 32px 28px;
  }

  /* ── Page title ── */
  .page-heading {
    margin-bottom: 28px;
    display: flex; align-items: flex-end; justify-content: space-between;
  }

  .page-title {
    font-family: 'Rajdhani', sans-serif;
    font-size: 28px; font-weight: 700; letter-spacing: 1px;
    background: linear-gradient(135deg, var(--text), var(--violet3));
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  }

  .page-subtitle {
    font-size: 13px; color: var(--muted); margin-top: 2px;
  }

  /* ── Stats bar ── */
  .stats-bar {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 14px;
    margin-bottom: 30px;
  }

  .stat-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 18px 20px;
    position: relative; overflow: hidden;
    transition: border-color .2s, transform .2s;
  }

  .stat-card:hover {
    border-color: var(--border2);
    transform: translateY(-2px);
  }

  .stat-card::before {
    content: '';
    position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, var(--violet), var(--pink));
  }

  .stat-card-glow {
    position: absolute; top: -30px; right: -30px;
    width: 90px; height: 90px; border-radius: 50%;
    background: radial-gradient(circle, rgba(139,92,246,.15), transparent 70%);
    pointer-events: none;
  }

  .stat-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px; color: var(--muted); letter-spacing: 1.2px;
    text-transform: uppercase; margin-bottom: 8px;
  }

  .stat-value {
    font-family: 'Rajdhani', sans-serif;
    font-size: 30px; font-weight: 700;
    color: var(--text);
    line-height: 1;
  }

  .stat-value.small { font-size: 16px; margin-top: 4px; }

  /* ── Product cards ── */
  .products-grid {
    display: flex; flex-direction: column; gap: 18px;
  }

  .product-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    overflow: hidden;
    transition: border-color .25s, box-shadow .25s, transform .2s;
    position: relative;
  }

  .product-card::before {
    content: '';
    position: absolute; left: 0; top: 0; bottom: 0; width: 3px;
    background: linear-gradient(180deg, var(--violet), var(--pink));
    opacity: 0; transition: opacity .25s;
  }

  .product-card:hover {
    border-color: var(--border2);
    box-shadow: 0 8px 40px rgba(139,92,246,.12);
    transform: translateY(-2px);
  }

  .product-card:hover::before { opacity: 1; }

  /* Card header */
  .card-head {
    padding: 20px 24px 16px;
    border-bottom: 1px solid var(--border);
    display: flex; justify-content: space-between; align-items: flex-start; gap: 16px;
  }

  .product-name {
    font-size: 14px; font-weight: 500; line-height: 1.5; flex: 1; color: var(--text);
  }

  .product-name a {
    color: inherit; text-decoration: none;
    transition: color .15s;
  }

  .product-name a:hover { color: var(--violet3); }

  .product-num {
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px; color: var(--muted); letter-spacing: 1px;
    margin-bottom: 6px; text-transform: uppercase;
  }

  /* Price badge */
  .price-pill {
    display: flex; flex-direction: column; align-items: flex-end; flex-shrink: 0;
  }

  .price-now {
    font-family: 'Rajdhani', sans-serif;
    font-size: 22px; font-weight: 700;
    background: linear-gradient(135deg, var(--violet2), var(--pink));
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    line-height: 1;
  }

  .price-now.zero {
    background: none; -webkit-text-fill-color: var(--muted);
    font-size: 16px;
  }

  .price-range-tag {
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px; color: var(--muted);
    margin-top: 3px;
  }

  /* Meta row */
  .card-meta {
    padding: 14px 24px;
    display: flex; gap: 0; flex-wrap: wrap;
    border-bottom: 1px solid var(--border);
  }

  .meta-cell {
    padding: 8px 20px 8px 0;
    min-width: 100px;
    display: flex; flex-direction: column; gap: 4px;
  }

  .meta-cell + .meta-cell {
    padding-left: 20px;
    border-left: 1px solid var(--border);
  }

  .meta-lbl {
    font-family: 'JetBrains Mono', monospace;
    font-size: 9px; color: var(--muted);
    text-transform: uppercase; letter-spacing: 1px;
  }

  .meta-val {
    font-family: 'Rajdhani', sans-serif;
    font-size: 16px; font-weight: 600; line-height: 1;
  }

  .meta-val.lo { color: var(--green); }
  .meta-val.hi { color: var(--red); }
  .meta-val.neutral { color: var(--text2); }
  .meta-val.gold { color: var(--gold); }

  /* Chart */
  .chart-wrap {
    padding: 16px 24px 20px;
    background: var(--bg2);
  }

  .chart-head {
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 12px;
  }

  .chart-lbl {
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px; color: var(--muted);
    text-transform: uppercase; letter-spacing: 1.2px;
    display: flex; align-items: center; gap: 8px;
  }

  .chart-lbl::before {
    content: '';
    display: inline-block; width: 8px; height: 2px;
    background: linear-gradient(90deg, var(--violet), var(--pink));
    border-radius: 2px;
  }

  canvas.price-chart { width: 100% !important; height: 100px !important; display: block; }

  .no-chart {
    padding: 20px 24px;
    text-align: center;
    font-size: 12px; color: var(--muted);
    font-family: 'JetBrains Mono', monospace;
    background: var(--bg2);
    border-top: 1px solid var(--border);
  }

  /* Empty state */
  .empty {
    text-align: center; padding: 100px 20px;
  }

  .empty-glyph {
    font-size: 56px; margin-bottom: 20px;
    filter: grayscale(.5);
  }

  .empty h2 {
    font-family: 'Rajdhani', sans-serif;
    font-size: 22px; font-weight: 700; letter-spacing: 1px;
    color: var(--text2); margin-bottom: 12px;
  }

  .empty p {
    color: var(--muted); font-size: 14px; line-height: 1.7;
  }

  .empty code {
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px; background: var(--surface);
    padding: 2px 8px; border-radius: 4px;
    border: 1px solid var(--border); color: var(--violet3);
  }

  /* Stars */
  .stars-val { color: var(--gold); }

  /* Scrollbar */
  ::-webkit-scrollbar { width: 6px; }
  ::-webkit-scrollbar-track { background: var(--bg2); }
  ::-webkit-scrollbar-thumb { background: var(--border2); border-radius: 3px; }
  ::-webkit-scrollbar-thumb:hover { background: var(--violet); }

  /* ── Responsive ── */
  @media (max-width: 600px) {
    header { padding: 0 16px; }
    main { padding: 20px 16px; }
    .card-head { flex-direction: column; }
    .price-pill { align-items: flex-start; }
    .meta-cell + .meta-cell { border-left: none; }
  }
</style>
</head>
<body>

<!-- ── HEADER ── -->
<header>
  <div class="logo">
    <div class="logo-mark">🛒</div>
    <div>
      <div class="logo-name">Price Tracker</div>
      <div class="logo-sub">
        <span class="pulse-dot"></span>
        Shopee · Thailand
      </div>
    </div>
  </div>
  <div class="header-right">
    <button class="btn btn-ghost" onclick="location.reload()">
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/>
        <path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/>
        <path d="M8 16H3v5"/>
      </svg>
      รีเฟรช
    </button>
  </div>
</header>

<!-- ── MAIN ── -->
<main>
  <div id="app">
    <div style="text-align:center;padding:80px 0;font-family:'JetBrains Mono',monospace;color:var(--muted);font-size:13px;">
      กำลังโหลด...
    </div>
  </div>
</main>

<script>
const DATA = __DATA__;

function fmt(p) {
  if (!p && p !== 0) return '—';
  if (!p) return '—';
  return p.toLocaleString('th-TH', {maximumFractionDigits: 0}) + ' ฿';
}

function stars(r) {
  if (!r) return '—';
  const full = Math.min(5, Math.floor(r));
  const empty = 5 - full;
  return '<span class="stars-val">' + '★'.repeat(full) + '<span style="opacity:.3">★</span>'.repeat(empty) + ' ' + r.toFixed(1) + '</span>';
}

function renderChart(id, history) {
  const canvas = document.getElementById(id);
  if (!canvas) return;
  const entries = history.filter(h => h.price_min > 0);
  const prices = entries.map(h => h.price_min);
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;

  if (prices.length < 2) {
    ctx.fillStyle = '#4c4575';
    ctx.font = '11px JetBrains Mono, monospace';
    ctx.textAlign = 'center';
    ctx.fillText('ยังไม่มีข้อมูลเพียงพอ', canvas.offsetWidth / 2, 50);
    return;
  }

  const W = canvas.offsetWidth, H = 100;
  canvas.width = W * dpr; canvas.height = H * dpr;
  canvas.style.width = W + 'px'; canvas.style.height = H + 'px';
  ctx.scale(dpr, dpr);

  const minP = Math.min(...prices) * .97, maxP = Math.max(...prices) * 1.03;
  const pad = { t: 12, b: 14, l: 6, r: 6 };
  const cw = W - pad.l - pad.r, ch = H - pad.t - pad.b;
  const xi = i => pad.l + (i / (prices.length - 1)) * cw;
  const yv = v => pad.t + ch - ((v - minP) / (maxP - minP || 1)) * ch;

  /* Grid lines */
  ctx.strokeStyle = 'rgba(45,38,80,.8)';
  ctx.lineWidth = 1;
  for (let i = 0; i <= 3; i++) {
    const gy = pad.t + (i / 3) * ch;
    ctx.beginPath(); ctx.moveTo(pad.l, gy); ctx.lineTo(W - pad.r, gy); ctx.stroke();
  }

  /* Fill gradient */
  const grad = ctx.createLinearGradient(0, pad.t, 0, H);
  grad.addColorStop(0, 'rgba(139,92,246,.35)');
  grad.addColorStop(.7, 'rgba(217,70,239,.12)');
  grad.addColorStop(1, 'rgba(139,92,246,0)');
  ctx.beginPath();
  ctx.moveTo(xi(0), yv(prices[0]));
  prices.forEach((p, i) => { if (i > 0) ctx.lineTo(xi(i), yv(p)); });
  ctx.lineTo(xi(prices.length - 1), H);
  ctx.lineTo(xi(0), H);
  ctx.closePath();
  ctx.fillStyle = grad; ctx.fill();

  /* Line */
  const lineGrad = ctx.createLinearGradient(0, 0, W, 0);
  lineGrad.addColorStop(0, '#8b5cf6');
  lineGrad.addColorStop(1, '#d946ef');
  ctx.beginPath();
  ctx.moveTo(xi(0), yv(prices[0]));
  prices.forEach((p, i) => { if (i > 0) ctx.lineTo(xi(i), yv(p)); });
  ctx.strokeStyle = lineGrad; ctx.lineWidth = 2.5; ctx.lineJoin = 'round'; ctx.stroke();

  /* Dots on data points */
  prices.forEach((p, i) => {
    const isLast = i === prices.length - 1;
    ctx.beginPath();
    ctx.arc(xi(i), yv(p), isLast ? 5 : 3, 0, Math.PI * 2);
    ctx.fillStyle = isLast ? '#d946ef' : 'rgba(139,92,246,.6)';
    if (isLast) { ctx.shadowColor = '#d946ef'; ctx.shadowBlur = 8; }
    ctx.fill();
    ctx.shadowBlur = 0;
  });

  /* Price labels: first & last */
  ctx.font = '10px JetBrains Mono, monospace';
  ctx.fillStyle = '#6b5fa0';
  ctx.textAlign = 'left';
  ctx.fillText(fmt(prices[0]), pad.l + 4, H - 3);
  ctx.textAlign = 'right';
  ctx.fillStyle = '#a78bfa';
  ctx.fillText(fmt(prices[prices.length - 1]), W - pad.r - 4, H - 3);
}

function render() {
  const app = document.getElementById('app');
  const { products, total_checks } = DATA;

  if (!products || !products.length) {
    app.innerHTML = `
      <div class="empty">
        <div class="empty-glyph">📦</div>
        <h2>ยังไม่มีข้อมูล</h2>
        <p>รัน <code>run_tracker.bat</code> บนเครื่องตัวเอง<br>แล้วรีเฟรชหน้านี้เพื่อดูข้อมูล</p>
      </div>`;
    return;
  }

  const lastUpdate = products.reduce((a, b) =>
    (a.checked_at || '') > (b.checked_at || '') ? a : b
  ).checked_at || '';

  const avgRating = products.filter(p => p.rating > 0)
    .reduce((s, p, _, a) => s + p.rating / a.length, 0);

  const statsHtml = `
    <div class="stats-bar">
      <div class="stat-card">
        <div class="stat-card-glow"></div>
        <div class="stat-label">สินค้าที่ติดตาม</div>
        <div class="stat-value">${products.length}</div>
      </div>
      <div class="stat-card">
        <div class="stat-card-glow"></div>
        <div class="stat-label">ตรวจสอบทั้งหมด</div>
        <div class="stat-value">${total_checks}</div>
      </div>
      <div class="stat-card">
        <div class="stat-card-glow"></div>
        <div class="stat-label">คะแนนเฉลี่ย</div>
        <div class="stat-value">${avgRating ? avgRating.toFixed(1) : '—'}</div>
      </div>
      <div class="stat-card">
        <div class="stat-card-glow"></div>
        <div class="stat-label">อัปเดตล่าสุด</div>
        <div class="stat-value small">${lastUpdate.slice(0, 16).replace('T', ' ') || '—'}</div>
      </div>
    </div>`;

  const cardsHtml = products.map((p, i) => {
    const hasPrices = p.history.filter(h => h.price_min > 0).length > 1;
    const priceChange = (() => {
      const prices = p.history.map(h => h.price_min).filter(v => v > 0);
      if (prices.length < 2) return null;
      const first = prices[0], last = prices[prices.length - 1];
      return ((last - first) / first * 100).toFixed(1);
    })();

    return `
      <div class="product-card">
        <div class="card-head">
          <div style="flex:1">
            <div class="product-num">PRODUCT ${String(i + 1).padStart(2, '0')}</div>
            <div class="product-name"><a href="${p.url}" target="_blank" rel="noopener">${p.title}</a></div>
          </div>
          <div class="price-pill">
            <div class="price-now ${!p.latest_price ? 'zero' : ''}">${fmt(p.latest_price)}</div>
            ${p.price_max && p.price_max !== p.latest_price
              ? `<div class="price-range-tag">max ${fmt(p.price_max)}</div>`
              : ''}
          </div>
        </div>

        <div class="card-meta">
          <div class="meta-cell">
            <div class="meta-lbl">ต่ำสุดเคยได้</div>
            <div class="meta-val lo">${fmt(p.min_ever)}</div>
          </div>
          <div class="meta-cell">
            <div class="meta-lbl">สูงสุดเคยได้</div>
            <div class="meta-val hi">${fmt(p.max_ever)}</div>
          </div>
          ${priceChange !== null ? `
          <div class="meta-cell">
            <div class="meta-lbl">เปลี่ยนแปลง</div>
            <div class="meta-val ${parseFloat(priceChange) <= 0 ? 'lo' : 'hi'}">${priceChange > 0 ? '+' : ''}${priceChange}%</div>
          </div>` : ''}
          <div class="meta-cell">
            <div class="meta-lbl">สต็อก</div>
            <div class="meta-val neutral">${p.stock ?? '—'}</div>
          </div>
          <div class="meta-cell">
            <div class="meta-lbl">ขายแล้ว</div>
            <div class="meta-val neutral">${p.sold?.toLocaleString('th-TH') ?? '—'}</div>
          </div>
          <div class="meta-cell">
            <div class="meta-lbl">คะแนน</div>
            <div class="meta-val gold">${p.rating ? p.rating.toFixed(1) + ' ★' : '—'}</div>
          </div>
          <div class="meta-cell">
            <div class="meta-lbl">ตรวจแล้ว</div>
            <div class="meta-val neutral">${p.checks} ครั้ง</div>
          </div>
        </div>

        ${hasPrices
          ? `<div class="chart-wrap">
               <div class="chart-head">
                 <div class="chart-lbl">กราฟราคาย้อนหลัง</div>
                 <div style="font-family:'JetBrains Mono',monospace;font-size:10px;color:var(--muted)">${p.history.length} รายการ</div>
               </div>
               <canvas class="price-chart" id="chart_${i}"></canvas>
             </div>`
          : `<div class="no-chart">— ยังไม่มีประวัติราคาเพียงพอ รัน tracker อีกครั้ง —</div>`
        }
      </div>`;
  }).join('');

  app.innerHTML = `
    <div class="page-heading">
      <div>
        <div class="page-title">ติดตามราคา</div>
        <div class="page-subtitle">อัปเดตอัตโนมัติทุก 6 ชั่วโมง</div>
      </div>
    </div>
    ${statsHtml}
    <div class="products-grid">${cardsHtml}</div>`;

  requestAnimationFrame(() => {
    products.forEach((_, i) => renderChart(`chart_${i}`, products[i].history));
  });
}

render();
</script>
</body>
</html>"""

# ─── HTTP Handler ─────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def send_json(self, code, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == '/ping':
            self.send_json(200, {"ok": True, "time": datetime.datetime.now().isoformat()})
        elif path == '/data':
            self.send_json(200, get_stats())
        else:
            stats = get_stats()
            html = HTML.replace('__DATA__', json.dumps(stats, ensure_ascii=False))
            body = html.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type','text/html; charset=utf-8')
            self.send_header('Content-Length', len(body))
            self.end_headers()
            self.wfile.write(body)

    def do_POST(self):
        path = urlparse(self.path).path
        # POST /push — tracker ส่งข้อมูลมา
        if path == '/push':
            key = self.headers.get('X-API-Key','')
            if key != API_KEY:
                self.send_json(403, {"error": "unauthorized"})
                return
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body)
                # รับทั้ง single dict และ list
                records = data if isinstance(data, list) else [data]
                count = 0
                for r in records:
                    if r.get('title') and r.get('url'):
                        insert_record(r)
                        count += 1
                self.send_json(200, {"ok": True, "inserted": count})
                print(f"📥 push {count} records OK")
            except Exception as e:
                self.send_json(400, {"error": str(e)})
        else:
            self.send_json(404, {"error": "not found"})

if __name__ == "__main__":
    init_db()
    # Start keep-alive thread
    t = threading.Thread(target=keep_alive, daemon=True)
    t.start()
    print("=" * 50)
    print(f"  🌐 Dashboard → http://0.0.0.0:{PORT}")
    print(f"  🔑 API Key   → {API_KEY}")
    print(f"  🏓 Keep-alive → {'ON ('+SELF_URL+')' if SELF_URL else 'OFF (ตั้ง SELF_URL)'}")
    print("  กด Ctrl+C เพื่อหยุด")
    print("=" * 50)
    server = HTTPServer(('0.0.0.0', PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 หยุด server แล้ว")
