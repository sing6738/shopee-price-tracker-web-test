import json, os, re, sys, time, datetime, urllib.request, urllib.error
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')

def log(msg): print(msg, flush=True)

# ===== Cloud Config =====
CLOUD_URL = os.environ.get("CLOUD_URL", "https://shopee-tracker-7d91.onrender.com")
API_KEY   = os.environ.get("TRACKER_API_KEY", "ShopeeKey99")
# ========================

SHOPEE_URLS = [
    "https://shopee.co.th/Aolon-Tetra-R4-Smartwatch-AMOLED-AOD-%E0%B8%A5%E0%B9%87%E0%B8%AD%E0%B8%84-GPS-%E0%B9%80%E0%B8%82%E0%B9%87%E0%B8%A1%E0%B8%97%E0%B8%B4%E0%B8%A8%E0%B8%99%E0%B8%B2%E0%B8%AC%E0%B8%B4%E0%B8%81%E0%B8%B2%E0%B8%AA%E0%B8%A1%E0%B8%B2%E0%B8%A3%E0%B9%8C%E0%B8%97%E0%B8%9B%E0%B8%A5%E0%B8%B9%E0%B8%97%E0%B8%B9%E0%B8%98%E0%B9%82%E0%B8%97%E0%B8%A3%E0%B8%AA%E0%B8%A1%E0%B8%B2%E0%B8%A3%E0%B9%8C%E0%B8%97%E0%B8%97%E0%B8%A7%E0%B8%AD%E0%B8%97%E0%B9%8C%E0%B8%8A-1.43-466*466-%E0%B8%88%E0%B8%AD%E0%B9%81%E0%B8%AA%E0%B8%94%E0%B8%87%E0%B8%9C%E0%B8%A5-Heart-Rate-Blood-Oxygen-Sleep-Monitoring-100-%E0%B9%82%E0%B8%AB%E0%B8%A1%E0%B8%94%E0%B8%81%E0%B8%B5%E0%B8%AC%E0%B8%B2-i.872307385.29419806949",
    "https://shopee.co.th/%E3%80%90xtep%E3%80%912000KM-5.0-%E0%B8%A3%E0%B8%AD%E0%B8%87%E0%B9%80%E0%B8%97%E0%B9%89%E0%B8%B2%E0%B8%A7%E0%B8%B4%E0%B9%88%E0%B8%87-Durability-King-%E0%B9%82%E0%B8%9F%E0%B8%A1-ACE-%E0%B9%80%E0%B8%95%E0%B9%87%E0%B8%A1%E0%B8%84%E0%B8%A7%E0%B8%B2%E0%B8%A1%E0%B8%A2%E0%B8%B2%E0%B8%A7-TPU-%E0%B8%A3%E0%B8%B9%E0%B8%9B%E0%B8%9B%E0%B8%B5%E0%B8%81-%E0%B8%9E%E0%B8%B7%E0%B9%89%E0%B8%99%E0%B8%A3%E0%B8%AD%E0%B8%87%E0%B9%80%E0%B8%97%E0%B9%89%E0%B8%B2%E0%B8%A1%E0%B8%B1%E0%B9%89%E0%B8%99%E0%B8%99%E0%B8%AD%E0%B8%81%E0%B8%97%E0%B8%99%E0%B8%97%E0%B8%B2%E0%B8%99%E0%B8%A3%E0%B8%B0%E0%B8%94%E0%B8%B1%E0%B8%9A%E0%B8%AD%E0%B8%A7%E0%B8%81%E0%B8%B2%E0%B8%A8-D18-i.176052666.48102237970",
    "https://shopee.co.th/%E3%80%90XTEP%E3%80%912000KM-5.0-PRO-%E0%B8%A3%E0%B8%AD%E0%B8%87%E0%B9%80%E0%B8%97%E0%B9%89%E0%B8%B2%E0%B8%A7%E0%B8%B4%E0%B9%88%E0%B8%87%E0%B8%9D%E0%B8%B6%E0%B8%81%E0%B8%8B%E0%B9%89%E0%B8%AD%E0%B8%A1%E0%B8%A3%E0%B8%B0%E0%B8%94%E0%B8%B1%E0%B8%9ABSuper-Trainer-Running-Shoes-Full-length-ACE-Foam-midsole-i.176052666.46904662362"
]

BASE = os.path.dirname(os.path.abspath(__file__))
PROFILE_DIR = os.path.join(BASE, "shopee_profile")

def extract_ids(url):
    m = re.search(r'i\.(\d+)\.(\d+)', url)
    return (m.group(1), m.group(2)) if m else (None, None)

def parse_item(item, url):
    raw_min = item.get('price_min') or item.get('price') or 0
    raw_max = item.get('price_max') or item.get('price') or 0
    div = 100000 if raw_min > 100000 else (100 if raw_min > 1000 else 1)
    return {
        "title": item.get('name', 'unknown'),
        "price_min": raw_min/div, "price_max": raw_max/div,
        "stock": item.get('stock', 0),
        "sold": item.get('historical_sold', 0),
        "rating": round((item.get('item_rating') or {}).get('rating_star', 0), 2),
        "url": url,
        "checked_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

def push_to_cloud(data):
    url = f"{CLOUD_URL}/push"
    body = json.dumps(data, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(
        url, data=body, method='POST',
        headers={'Content-Type': 'application/json', 'X-API-Key': API_KEY}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return True
    except: return False

def run_tracker(headless=True):
    log("=" * 55)
    log(f"  Shopee Price Tracker (Mode: {'Headless' if headless else 'Visual'})")
    log("=" * 55)
    
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=headless,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            ignore_default_args=["--enable-automation"],
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            viewport={"width": 1280, "height": 800}
        )
        page = browser.pages[0] if browser.pages else browser.new_page()
        
        try:
            from playwright_stealth import stealth_sync
            stealth_sync(page)
        except: pass

        # Session Check
        log("🔍 Checking Session Health...")
        try:
            page.goto("https://shopee.co.th/", wait_until="domcontentloaded", timeout=30000)
            time.sleep(3)
            if "buyer/login" in page.url or page.evaluate("() => document.querySelector('.navbar__username') === null"):
                log("❌ Session Expired. Please login via loginshopee.py")
                browser.close()
                return False
            log("✅ Session is Healthy.")
        except: pass

        # Block heavy media
        page.route("**/*.{png,jpg,jpeg,svg,webp,mp4}", lambda route: route.abort())

        success_count = 0
        for i, url in enumerate(SHOPEE_URLS):
            log(f"\n[{i+1}/{len(SHOPEE_URLS)}] Tracking: {url[:60]}...")
            shop_id, item_id = extract_ids(url)
            if not shop_id: continue

            captured = {}
            def on_response(resp):
                # Watch for any API that might contain item data
                if (f'itemid={item_id}' in resp.url or f'item_id={item_id}' in resp.url) and resp.status == 200:
                    try:
                        data = resp.json()
                        item = data.get('data') or data.get('item')
                        if isinstance(item,dict) and item.get('item'): item=item['item']
                        if item and item.get('name'):
                            captured['item'] = item
                    except: pass

            page.on("response", on_response)
            
            try:
                page.goto(url, wait_until="load", timeout=40000)
                page.mouse.wheel(0, 600)
                time.sleep(3)

                # Try to extract from SSR (Preloaded State) if XHR didn't trigger yet
                if not captured.get('item'):
                    try:
                        ssr_data = page.evaluate("() => window.__PRELOADED_STATE__")
                        if ssr_data:
                            # Search through preloaded state for the item
                            item_info = ssr_data.get('item', {}).get('itemInfo', {})
                            if item_info and item_info.get('itemid') == int(item_id):
                                captured['item'] = item_info
                    except: pass

                # Wait loop
                for _ in range(10):
                    if captured.get('item'): break
                    time.sleep(1)

                # Manual API Fetch attempt
                if not captured.get('item'):
                    api = f"https://shopee.co.th/api/v4/item/get?itemid={item_id}&shopid={shop_id}"
                    try:
                        data = page.evaluate(f'async()=>{{const r=await fetch("{api}", {{headers: {{"x-api-source": "pc"}}}});return r.ok?await r.json():null;}}')
                        if data:
                            item = data.get('data') or data.get('item')
                            if isinstance(item,dict) and item.get('item'): item=item['item']
                            if item and item.get('name'): captured['item'] = item
                    except: pass

                if captured.get('item'):
                    result = parse_item(captured['item'], url)
                    log(f"   ✅ Price: {result['price_min']:.0f} THB | {result['title'][:35]}...")
                    if push_to_cloud(result):
                        log("   🚀 Cloud Sync: OK")
                        success_count += 1
                else:
                    log("   ⚠️ Capture Failed.")
                    if headless: page.screenshot(path=f"fail_{i}.png")
            
            except Exception as e:
                log(f"   ❌ Error: {e}")
            
            page.remove_listener("response", on_response)
            time.sleep(4)

        browser.close()
        log(f"\n✨ Done! {success_count}/{len(SHOPEE_URLS)} items tracked.")
        return success_count > 0

if __name__ == "__main__":
    if not run_tracker(headless=True):
        log("\n🔄 Retrying with VISUAL MODE...")
        run_tracker(headless=False)
