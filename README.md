# Shopee Price Tracker — Cloud Setup Guide

## Architecture

```
Windows เครื่องตัวเอง              Render.com (cloud)
┌──────────────────────┐           ┌─────────────────────┐
│  tracker_cloud.py    │ POST /push│  dashboard_server.py│
│  (ดึงราคาจาก Shopee  │ ────────► │  (เปิดตลอด 24/7)    │
│   ทุก 6 ชม.          │  + API key│  SQLite DB          │
└──────────────────────┘           └─────────────────────┘
                                          ↑
                                   เข้าได้จากมือถือ/ทุกที่
                                   https://yourapp.onrender.com
```

---

## Step 1: Deploy Dashboard บน Render

### 1.1 สร้าง GitHub Repository
1. ไปที่ https://github.com → New repository
2. ชื่อ: `shopee-tracker`
3. ใส่ไฟล์เหล่านี้:
   - `dashboard_server.py`
   - `requirements.txt`
   - (อย่าใส่ `shopee_cookies.json` หรือ `prices.db`)

### 1.2 สร้าง Web Service บน Render
1. ไปที่ https://dashboard.render.com → **New** → **Web Service**
2. Connect GitHub → เลือก repo `shopee-tracker`
3. ตั้งค่า:
   ```
   Name:         shopee-tracker
   Runtime:      Python 3
   Build Command: pip install -r requirements.txt
   Start Command: python dashboard_server.py
   Instance Type: Free
   ```

### 1.3 ตั้ง Environment Variables (สำคัญมาก!)
ใน Render → Web Service → **Environment** → Add:

| Key | Value |
|-----|-------|
| `TRACKER_API_KEY` | รหัสลับที่คุณตั้งเอง เช่น `MySecret@2025` |
| `SELF_URL` | URL ของ app เช่น `https://shopee-tracker.onrender.com` |

> ⚠️ SELF_URL ใส่หลัง deploy แล้วได้ URL จริง

### 1.4 Deploy!
กด **Create Web Service** → รอ 2–3 นาที
ได้ URL เช่น `https://shopee-tracker.onrender.com`

---

## Step 2: ตั้งค่า tracker_cloud.py บน Windows

### 2.1 แก้ไฟล์ run_tracker.bat
เปิดด้วย Notepad แก้ 2 บรรทัด:
```bat
set CLOUD_URL=https://shopee-tracker.onrender.com   ← URL ของคุณ
set TRACKER_API_KEY=MySecret@2025                    ← API key เดียวกับ Render
```

### 2.2 ทดสอบ
ดับเบิลคลิก `run_tracker.bat` → ดูว่า push ขึ้น cloud ได้ไหม
แล้วเปิด URL บน browser เช็คว่ามีข้อมูลปรากฏ

---

## Step 3: ตั้ง Task Scheduler รันอัตโนมัติทุก 6 ชั่วโมง

1. กด `Win + R` พิมพ์ `taskschd.msc`
2. **Create Basic Task** → ตั้งชื่อ: `Shopee Tracker`
3. Trigger: **Daily** → เวลา 08:00 → **Repeat task every 6 hours** for 1 day
4. Action: **Start a program**
   - Program: `C:\path\to\run_tracker.bat`
   - Start in: `C:\path\to\` (โฟลเดอร์ที่ใส่ไฟล์)
5. กด Finish → ✅

---

## การแก้ไขปัญหาที่พบบ่อย

**❌ push failed 403**
→ API Key ไม่ตรง เช็ค `TRACKER_API_KEY` ใน run_tracker.bat และ Render Environment

**❌ App ตอบช้า / timeout ครั้งแรก**
→ ปกติของ Render free tier (cold start ~30 วินาที) รอสักครู่แล้ว refresh

**❌ Dashboard แสดงว่าง**
→ รัน run_tracker.bat ก่อนอย่างน้อย 1 ครั้ง

**❌ tracker ดึงราคาไม่ได้**
→ รัน loginshopee.py บน Windows เพื่อ refresh cookies ก่อน
