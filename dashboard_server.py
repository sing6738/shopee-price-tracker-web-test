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
<link href="https://fonts.googleapis.com/css2?family=Sarabun:wght@300;400;600;700&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #0e0e12; --surface: #18181f; --surface2: #22222c;
    --border: #2e2e3e; --accent: #ff6230; --accent2: #ff9f1c;
    --text: #e8e8f0; --muted: #888899;
    --green: #22c55e; --red: #ef4444; --radius: 12px;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Sarabun', sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; padding-bottom: 60px; }
  header {
    background: linear-gradient(135deg,#1a1a24,#0e0e12);
    border-bottom: 1px solid var(--border);
    padding: 18px 28px;
    display: flex; align-items: center; justify-content: space-between;
    position: sticky; top: 0; z-index: 100; backdrop-filter: blur(8px);
  }
  .logo { display: flex; align-items: center; gap: 12px; }
  .logo-icon { width: 36px; height: 36px; background: var(--accent); border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 18px; }
  .logo-text { font-family: 'Space Mono', monospace; font-size: 14px; font-weight: 700; }
  .logo-sub { font-size: 11px; color: var(--muted); font-family: 'Space Mono', monospace; }
  .refresh-btn {
    background: var(--surface2); border: 1px solid var(--border); color: var(--text);
    padding: 7px 16px; border-radius: 8px; cursor: pointer;
    font-family: 'Sarabun', sans-serif; font-size: 13px;
    transition: all .2s; display: flex; gap: 6px; align-items: center;
  }
  .refresh-btn:hover { background: var(--accent); border-color: var(--accent); }
  main { padding: 24px 28px; max-width: 1100px; margin: 0 auto; }
  .summary-bar { display: grid; grid-template-columns: repeat(auto-fit,minmax(150px,1fr)); gap: 14px; margin-bottom: 28px; }
  .stat-card {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 16px 18px; position: relative; overflow: hidden;
  }
  .stat-card::before { content:''; position:absolute; top:0; left:0; right:0; height:2px; background:var(--accent); }
  .stat-label { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 5px; }
  .stat-value { font-family: 'Space Mono', monospace; font-size: 24px; font-weight: 700; }
  .products-grid { display: flex; flex-direction: column; gap: 20px; }
  .product-card {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--radius); overflow: hidden; transition: border-color .2s;
  }
  .product-card:hover { border-color: var(--accent); }
  .card-header {
    padding: 18px 22px 14px; border-bottom: 1px solid var(--border);
    display: flex; justify-content: space-between; align-items: flex-start; gap: 14px;
  }
  .product-title { font-size: 14px; font-weight: 600; line-height: 1.4; flex: 1; }
  .product-title a { color: var(--text); text-decoration: none; }
  .product-title a:hover { color: var(--accent); }
  .price-badge {
    background: var(--accent); color: white;
    padding: 5px 12px; border-radius: 20px;
    font-family: 'Space Mono', monospace; font-size: 14px; font-weight: 700; white-space: nowrap;
  }
  .price-badge.zero { background: var(--surface2); color: var(--muted); }
  .card-meta {
    padding: 12px 22px; display: flex; gap: 20px; flex-wrap: wrap;
    border-bottom: 1px solid var(--border);
  }
  .meta-item { display: flex; flex-direction: column; gap: 2px; }
  .meta-label { font-size: 10px; color: var(--muted); text-transform: uppercase; letter-spacing: .8px; }
  .meta-value { font-family: 'Space Mono', monospace; font-size: 13px; font-weight: 700; }
  .meta-value.good { color: var(--green); }
  .meta-value.bad { color: var(--red); }
  .chart-section { padding: 14px 22px 18px; }
  .chart-title { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px; }
  canvas.price-chart { width: 100% !important; height: 90px !important; }
  .no-history { color: var(--muted); font-size: 13px; padding: 20px; text-align: center; }
  .empty { text-align: center; padding: 80px 20px; }
  .empty-icon { font-size: 56px; margin-bottom: 18px; }
  .empty p { color: var(--muted); font-size: 14px; line-height: 1.6; }
  .last-update { font-size: 12px; color: var(--muted); }
  .stars { color: var(--accent2); }
  .status-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--green); display: inline-block; margin-right: 6px; animation: pulse 2s infinite; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.4} }
</style>
</head>
<body>
<header>
  <div class="logo">
    <div class="logo-icon">🛒</div>
    <div>
      <div class="logo-text">PRICE TRACKER</div>
      <div class="logo-sub"><span class="status-dot"></span>Shopee · Thailand</div>
    </div>
  </div>
  <button class="refresh-btn" onclick="location.reload()">🔄 รีเฟรช</button>
</header>
<main>
  <div id="app">กำลังโหลด...</div>
</main>
<script>
const DATA = __DATA__;
function fmt(p) {
  if (!p) return '—';
  return p.toLocaleString('th-TH',{maximumFractionDigits:0}) + ' ฿';
}
function stars(r) {
  if (!r) return '—';
  return '★'.repeat(Math.floor(r)) + '☆'.repeat(5-Math.floor(r)) + ' ' + r.toFixed(1);
}
function renderChart(id, history) {
  const canvas = document.getElementById(id);
  if (!canvas) return;
  const prices = history.map(h => h.price_min).filter(p => p > 0);
  const ctx = canvas.getContext('2d');
  if (prices.length < 2) {
    ctx.fillStyle = '#888899'; ctx.font = '12px Sarabun';
    ctx.textAlign = 'center'; ctx.fillText('ยังไม่มีข้อมูลเพียงพอ', canvas.width/2, 45);
    return;
  }
  const W = canvas.offsetWidth||800, H = 90;
  canvas.width = W; canvas.height = H;
  const min = Math.min(...prices)*.98, max = Math.max(...prices)*1.02;
  const pad = {t:8,b:8,l:8,r:8};
  const w = W-pad.l-pad.r, h = H-pad.t-pad.b;
  const x = i => pad.l+(i/(prices.length-1))*w;
  const y = v => pad.t+h-((v-min)/(max-min))*h;
  const grad = ctx.createLinearGradient(0,pad.t,0,H);
  grad.addColorStop(0,'rgba(255,98,48,.3)'); grad.addColorStop(1,'rgba(255,98,48,0)');
  ctx.beginPath(); ctx.moveTo(x(0),y(prices[0]));
  prices.forEach((p,i) => { if(i>0) ctx.lineTo(x(i),y(p)); });
  ctx.lineTo(x(prices.length-1),H); ctx.lineTo(x(0),H);
  ctx.closePath(); ctx.fillStyle = grad; ctx.fill();
  ctx.beginPath(); ctx.moveTo(x(0),y(prices[0]));
  prices.forEach((p,i) => { if(i>0) ctx.lineTo(x(i),y(p)); });
  ctx.strokeStyle = '#ff6230'; ctx.lineWidth = 2; ctx.lineJoin = 'round'; ctx.stroke();
  const lx=x(prices.length-1), ly=y(prices[prices.length-1]);
  ctx.beginPath(); ctx.arc(lx,ly,4,0,Math.PI*2);
  ctx.fillStyle = '#ff6230'; ctx.fill();
}
function render() {
  const app = document.getElementById('app');
  const {products, total_checks} = DATA;
  if (!products || !products.length) {
    app.innerHTML = `<div class="empty"><div class="empty-icon">📦</div><h2>ยังไม่มีข้อมูล</h2><p>รัน tracker.py บนเครื่องตัวเอง<br>แล้วรีเฟรชหน้านี้</p></div>`;
    return;
  }
  const lastUpdate = products[0]?.checked_at || '';
  const summary = `<div class="summary-bar">
    <div class="stat-card"><div class="stat-label">สินค้าที่ติดตาม</div><div class="stat-value">${products.length}</div></div>
    <div class="stat-card"><div class="stat-label">ตรวจสอบทั้งหมด</div><div class="stat-value">${total_checks}</div></div>
    <div class="stat-card"><div class="stat-label">อัปเดตล่าสุด</div><div class="stat-value" style="font-size:13px;padding-top:5px">${lastUpdate.slice(0,16)}</div></div>
  </div>`;
  const cards = products.map((p,i) => {
    const hasPrices = p.history.filter(h=>h.price_min>0).length > 1;
    return `<div class="product-card">
      <div class="card-header">
        <div class="product-title"><a href="${p.url}" target="_blank">${p.title}</a></div>
        <div class="price-badge ${!p.latest_price?'zero':''}">${fmt(p.latest_price)}</div>
      </div>
      <div class="card-meta">
        <div class="meta-item"><div class="meta-label">ต่ำสุด (เคย)</div><div class="meta-value good">${fmt(p.min_ever)}</div></div>
        <div class="meta-item"><div class="meta-label">สูงสุด (เคย)</div><div class="meta-value bad">${fmt(p.max_ever)}</div></div>
        <div class="meta-item"><div class="meta-label">ราคาสูงสุด</div><div class="meta-value">${fmt(p.price_max)}</div></div>
        <div class="meta-item"><div class="meta-label">สต็อก</div><div class="meta-value">${p.stock??'—'}</div></div>
        <div class="meta-item"><div class="meta-label">ขายแล้ว</div><div class="meta-value">${p.sold?.toLocaleString()??'—'}</div></div>
        <div class="meta-item"><div class="meta-label">คะแนน</div><div class="meta-value stars">${stars(p.rating)}</div></div>
        <div class="meta-item"><div class="meta-label">ตรวจ</div><div class="meta-value">${p.checks} ครั้ง</div></div>
      </div>
      ${hasPrices
        ? `<div class="chart-section"><div class="chart-title">📈 กราฟราคาย้อนหลัง</div><canvas class="price-chart" id="chart_${i}"></canvas></div>`
        : `<div class="no-history">⚠️ ยังไม่มีประวัติราคา — รัน tracker อีกครั้ง</div>`}
    </div>`;
  }).join('');
  app.innerHTML = summary + `<div class="products-grid">${cards}</div>`;
  requestAnimationFrame(() => products.forEach((_,i) => renderChart(`chart_${i}`, products[i].history)));
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
