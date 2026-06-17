import sys, time, os, json, datetime
sys.stdout.reconfigure(encoding='utf-8')

print("=" * 50)
print("  SHOPEE LOGIN")
print("=" * 50)

try:
    import playwright_stealth
    print("✅ playwright-stealth พร้อมใช้")
except ImportError:
    print("📦 ติดตั้ง playwright-stealth...")
    os.system("pip install playwright-stealth --break-system-packages -q")

from playwright.sync_api import sync_playwright

BASE        = os.path.dirname(os.path.abspath(__file__))
PROFILE_DIR = os.path.join(BASE, "shopee_profile")
COOKIE_FILE = os.path.join(BASE, "shopee_cookies.json")
SESSION_INFO = os.path.join(BASE, "session_info.json")

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=PROFILE_DIR,
        headless=False,
        args=["--disable-blink-features=AutomationControlled"],
        ignore_default_args=["--enable-automation"],
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        viewport={"width": 1280, "height": 800},
    )
    page = ctx.pages[0] if ctx.pages else ctx.new_page()

    try:
        from playwright_stealth import stealth_sync
        stealth_sync(page)
        print("🛡️  Stealth mode เปิดแล้ว")
    except:
        pass

    try:
        page.goto("https://shopee.co.th/", wait_until="domcontentloaded", timeout=20000)
        # Check if already logged in by looking for username or logout button
        # Usually, if logged in, 'shopee-userlog-out' or similar exists
        time.sleep(3)
        is_logged_in = page.evaluate("() => document.querySelector('.navbar__username') !== null")
        
        if is_logged_in:
            print("✅ ตรวจพบ Session เดิมที่ยังใช้งานได้อยู่!")
            print("   ไม่ต้อง Login ใหม่ ระบบจะอัปเดต Cookies ให้โดยอัตโนมัติ")
        else:
            print()
            print(">>> ไม่พบ Session เดิม หรือ Session หมดอายุ")
            print(">>> เปิดหน้า Login Shopee แล้ว")
            print(">>> โปรด LOGIN ในหน้าต่างที่เด้งขึ้นมา")
            print(">>> เมื่อ Login สำเร็จแล้ว กลับมากด Enter ที่นี่")
            print()
            page.goto("https://shopee.co.th/buyer/login", wait_until="domcontentloaded", timeout=15000)
            input("กด Enter หลัง Login สำเร็จแล้ว...")
    except Exception as e:
        print(f"⚠️ เกิดข้อผิดพลาดขณะตรวจสอบ Session: {e}")
        page.goto("https://shopee.co.th/buyer/login", wait_until="domcontentloaded", timeout=15000)
        input("กด Enter หลัง Login สำเร็จแล้ว...")

    # บันทึก cookies
    cookies = ctx.cookies()
    with open(COOKIE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)

    # บันทึก session info + คำนวณวันหมดอายุ
    spc_sc = next((c for c in cookies if c.get('name') == 'SPC_SC'), None)
    expires_at = None
    days_valid = None
    if spc_sc and spc_sc.get('expires', 0) > 0:
        exp_dt = datetime.datetime.fromtimestamp(spc_sc['expires'])
        expires_at = exp_dt.isoformat()
        days_valid = (exp_dt - datetime.datetime.now()).days

    session_data = {
        "logged_in_at": datetime.datetime.now().isoformat(),
        "cookie_count": len(cookies),
        "spc_sc_expires": expires_at,
        "days_valid": days_valid,
    }
    with open(SESSION_INFO, 'w', encoding='utf-8') as f:
        json.dump(session_data, f, ensure_ascii=False, indent=2)

    ctx.close()

print(f"\n✅ บันทึก session แล้ว ({len(cookies)} cookies)")
if days_valid:
    print(f"   ⏰ Session ใช้ได้อีก ~{days_valid} วัน (ถึง {expires_at[:10]})")
print(f"   Profile: {PROFILE_DIR}")
print(f"   Cookies: {COOKIE_FILE}")
print(f"   Info:    {SESSION_INFO}")
print()
print("💡 ตั้ง Task Scheduler รัน cookie_checker.py ทุกวัน")
print("   เพื่อรับแจ้งเตือนก่อน session หมด")
print()
print("   ตอนนี้รัน: python tracker.py")

print()
print("=== เสร็จสิ้น ===")
input("กด Enter เพื่อปิด...")
